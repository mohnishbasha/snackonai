# SnackOnAIClips — System Design & Architecture Notes

## Overview

SnackOnAIClips is a modular Python pipeline that converts any blog URL into a ≤60-second
vertical video optimized for LinkedIn. This document captures the key design decisions,
trade-offs, and reasoning behind the architecture.

---

## Module Breakdown

### `config.py` — Centralized Configuration
- **Pattern**: Singleton AppConfig built from environment variables and dataclass defaults.
- **Why**: Avoids passing config dicts through every function call. A single `get_config()`
  call anywhere in the codebase returns the same typed object.
- **Trade-off**: Singletons are harder to test in isolation — we expose a `reset_config()`
  function that tests can call to clear state between runs.

### `extractor.py` — Content Extraction
- **Strategy Pattern**: Three extractors are tried in priority order:
  1. `trafilatura` — best-in-class noise removal, structured metadata
  2. `readability-lxml` — Mozilla's Readability ported to Python
  3. `newspaper3k` — broad compatibility, downloads independently
- **Why cascade?** No single extractor works on all sites. Paywalled, JavaScript-heavy,
  or ad-saturated pages behave differently. The cascade maximizes coverage without
  requiring site-specific scrapers.
- **Retry logic**: HTTP fetches use exponential backoff via `@retry` decorator. Transient
  network errors (rate limits, flaky DNS) are handled automatically.
- **Security**: We use a descriptive User-Agent so servers can identify our bot and
  apply appropriate access policies.

### `summarizer.py` — LLM Summarization
- **Structured output**: The LLM is instructed to return JSON only. We strip markdown
  fences and validate the schema before trusting the response.
- **Why JSON output mode?** OpenAI's `response_format={"type": "json_object"}` virtually
  eliminates schema violations. For Ollama, we use `"format": "json"` equivalently.
- **Prompt design**: The system prompt establishes the persona (content strategist),
  the user prompt provides the article and explicit constraints (word counts, no jargon).
  Temperature 0.4 balances creativity with consistency.
- **Fallback summarizer**: When all LLM calls fail (no API key, network outage, Ollama
  not running), a pure rule-based summarizer splits the article into sentences and
  selects the top 3–5. Output quality is lower but the pipeline never crashes.
- **Input truncation**: Articles are capped at 6,000 characters before being sent to
  the LLM. This prevents excessive cost/latency while preserving the most valuable
  early paragraphs (inverted pyramid pattern common in blog writing).

### `tts.py` — Text-to-Speech
- **Provider abstraction**: A single `generate_voiceover()` function dispatches to
  gTTS or ElevenLabs based on config. Adding a new provider (e.g., OpenAI TTS,
  Coqui) requires only a new `_generate_*` function + an enum value.
- **gTTS vs ElevenLabs**: gTTS is free, offline-capable (saves MP3 locally), and
  requires no API key — ideal for development and CI. ElevenLabs produces
  broadcast-quality voice cloning but costs money and requires an API key.
- **Audio duration**: We use `mutagen` for MP3 duration detection (fast, accurate)
  with a moviepy fallback. This drives slide timing when voiceover is present.

### `video_generator.py` — Video Rendering
- **MoviePy over ffmpeg-python**: MoviePy provides a Pythonic clip composition API
  that maps cleanly to our slide-based mental model. ffmpeg-python would require
  manual filter graph construction, which is powerful but verbose for this use case.
- **ImageMagick dependency**: MoviePy's `TextClip` requires ImageMagick for font
  rendering. This is a known friction point — we document the install step and use
  the DejaVu font family which ships with most ImageMagick installations.
- **Gradient backgrounds**: Generated in pure NumPy (no external image assets
  required). This makes the package fully self-contained and eliminates licensing
  concerns around stock imagery.
- **Style presets**: Three palettes (minimal, modern, cinematic) share the same
  rendering pipeline — only color values and font sizes differ. New styles can be
  added by extending the `STYLES` dict without touching any rendering code.
- **Slide timing budget**: Total duration is strictly capped at `max_duration` (default 60s).
  Time is distributed proportionally: title 15%, outro 10%, summary 22%, bullets split
  the remainder. `clamp()` ensures no slide is shorter than 3s or longer than 12s.
- **Crossfade transitions**: `fadein`/`fadeout` from `moviepy.video.fx.all` create
  smooth 0.5s transitions without requiring GPU acceleration.
- **Codec choices**: `libx264` + AAC is the universal LinkedIn-compatible codec pair.
  `preset=medium` balances encode speed vs. file size. `bitrate=4000k` targets
  ~30MB for a 60-second 1080p video — within LinkedIn's 5GB upload limit.

### `cli.py` — CLI Interface
- **argparse over click**: argparse is stdlib, eliminating a dependency. For a tool
  of this scope, argparse is sufficient and easier to unit-test.
- **Rich for UX**: `rich.Progress` provides spinner + bar + elapsed time. `rich.Panel`
  renders the summary in a visually structured way before video generation begins.
  The user sees meaningful output at every pipeline stage, not just at the end.
- **Exit codes**: `0` = success, `1` = input/extraction error, `2` = dependency
  missing, `3` = video render error. This makes the CLI scriptable in pipelines.

---

## LLM Provider Trade-offs

| Dimension        | OpenAI (GPT-4o-mini)       | Ollama (Llama 3.2)         |
|------------------|----------------------------|-----------------------------|
| Quality          | High                       | Good (varies by model)      |
| Cost             | ~$0.0001/call              | Free (local GPU/CPU)        |
| Latency          | 1–3s (API)                 | 2–30s (hardware-dependent)  |
| Privacy          | Data sent to OpenAI        | Fully local                 |
| Reliability      | 99.9% SLA                  | Depends on local service    |
| JSON consistency | Very high (response_format) | Good (format=json)          |
| Setup friction   | API key only               | Docker + model download     |

**Recommendation**: OpenAI for production, Ollama for development / air-gapped environments.

---

## Video Rendering Trade-offs

| Approach         | Pros                          | Cons                              |
|------------------|-------------------------------|-----------------------------------|
| MoviePy          | Pythonic, slide-model friendly | Requires ImageMagick, slower      |
| ffmpeg-python    | Fast, precise control         | Verbose filter graphs             |
| Remotion (JS)    | Browser-grade rendering       | Requires Node.js runtime          |
| Canva API        | Professional templates        | Paid, vendor lock-in              |

MoviePy was chosen for developer ergonomics and self-contained deployment.

---

## Scaling Considerations

1. **Horizontal scaling**: Each pipeline run is stateless. Deploy as a Lambda/Cloud Run
   function with a queue trigger (SQS/Pub-Sub) for batch processing.
2. **Rendering bottleneck**: Video encoding is CPU-bound. Use `threads=4` in
   `write_videofile()`. At scale, offload to dedicated render workers or AWS Elemental.
3. **LLM caching**: Cache `(url_hash, model) → summary_json` in Redis. Blog posts
   don't change frequently; a 24-hour TTL prevents redundant API calls.
4. **Storage**: Output videos should be uploaded to S3/GCS rather than stored locally.
   Add a post-render upload step with pre-signed URL generation for delivery.
5. **Observability**: Replace `logging.basicConfig` with structured logging (structlog)
   and ship to Datadog/CloudWatch. Add span tracing per pipeline stage.
6. **Rate limits**: trafilatura and newspaper3k have no built-in rate limiting.
   Add per-domain request throttling before running at scale against public sites.
