# SnackOnAIClips — System Design & Architecture Notes

## Overview

SnackOnAIClips is a modular Python pipeline that converts any blog URL (or local file) into
a ≤60-second vertical video optimized for LinkedIn. This document captures the key design
decisions, trade-offs, and reasoning behind the architecture.

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
- **Local file support**: Before attempting any HTTP fetch, `is_local_input()` checks if
  the input is a `file://` URL or an existing filesystem path. `.txt` files are returned
  as-is; `.html` files go through the same extraction cascade. This enables fully offline
  use without changing the caller's interface.
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
- **gTTS vs ElevenLabs**: gTTS is free, requires no API key, and works on both
  macOS and Ubuntu without any extra system dependencies. ElevenLabs produces
  broadcast-quality voice cloning but costs money and requires an API key.
- **Audio duration**: We use `mutagen` for MP3 duration detection (fast, accurate)
  with a moviepy fallback. This drives slide timing when voiceover is present.

### `video_generator.py` — Video Rendering (Cross-Platform)
- **MoviePy over ffmpeg-python**: MoviePy provides a Pythonic clip composition API
  that maps cleanly to our slide-based mental model. ffmpeg-python would require
  manual filter graph construction, which is powerful but verbose for this use case.
- **Cross-platform ImageMagick handling**: MoviePy 1.x hard-codes the `convert` binary,
  which is deprecated in ImageMagick v7 (Homebrew macOS). We call
  `_configure_imagemagick()` at import time to detect the platform and set the correct
  binary (`magick` on macOS/IMv7, `convert` on Ubuntu/IMv6).
- **Ubuntu policy.xml detection**: Ubuntu ships ImageMagick with a security policy that
  blocks writing PNG files from temp directories — exactly what `TextClip` does. We scan
  `/etc/ImageMagick-*/policy.xml` at startup, detect the restriction, and raise a
  `RuntimeError` with the exact `sed` command to fix it. This fails fast and clearly
  rather than producing a cryptic OSError mid-render.
- **Font detection**: Font names (e.g., `"DejaVu-Sans-Bold"`) are not portable —
  ImageMagick uses different font registries on each OS. Instead, we scan a prioritized
  list of absolute `.ttf` file paths covering Homebrew (macOS), `fonts-dejavu-core`
  (Ubuntu), `fonts-liberation` (Ubuntu), the Ubuntu font family, and macOS system fonts.
  The first path that exists on disk is used; `None` lets ImageMagick pick its own default.
- **Gradient backgrounds**: Generated in pure NumPy (no external image assets required).
  This makes the package fully self-contained and eliminates licensing concerns around
  stock imagery. Works identically on all platforms.
- **Style presets**: Three palettes (minimal, modern, cinematic) share the same rendering
  pipeline — only color values and font sizes differ. New styles can be added by extending
  the `STYLES` dict without touching any rendering code.
- **Slide timing budget**: Total duration is strictly capped at `max_duration` (default 60s).
  Time is distributed proportionally: title 15%, outro 10%, summary 22%, bullets split
  the remainder. `clamp()` ensures no slide is shorter than 3s or longer than 12s.
- **Codec choices**: `libx264` + AAC is the universal LinkedIn-compatible codec pair.
  `preset=medium` balances encode speed vs. file size. `bitrate=4000k` targets
  ~30MB for a 60-second 1080p video — within LinkedIn's 5GB upload limit.
  `imageio-ffmpeg` bundles the ffmpeg binary, so no system-level ffmpeg install is needed
  on either platform.

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

| Dimension        | OpenAI (GPT-4o-mini)        | Ollama (Llama 3.2)          |
|------------------|-----------------------------|-----------------------------|
| Quality          | High                        | Good (varies by model)      |
| Cost             | ~$0.0001/call               | Free (local GPU/CPU)        |
| Latency          | 1–3s (API)                  | 2–30s (hardware-dependent)  |
| Privacy          | Data sent to OpenAI         | Fully local                 |
| Reliability      | 99.9% SLA                   | Depends on local service    |
| JSON consistency | Very high (response_format) | Good (format=json)          |
| Setup friction   | API key only                | Docker + model download     |
| Cross-platform   | Works everywhere            | macOS native app or Docker  |

**Recommendation**: OpenAI for production, Ollama for development / air-gapped environments.

---

## Video Rendering Trade-offs

| Approach         | Pros                           | Cons                               |
|------------------|--------------------------------|------------------------------------|
| MoviePy          | Pythonic, slide-model friendly | Requires ImageMagick, slower       |
| ffmpeg-python    | Fast, precise control          | Verbose filter graphs              |
| Remotion (JS)    | Browser-grade rendering        | Requires Node.js runtime           |
| Canva API        | Professional templates         | Paid, vendor lock-in               |

MoviePy was chosen for developer ergonomics and self-contained deployment.

---

## Cross-Platform Design Decisions

### Why not abstract ImageMagick into a separate module?
The platform logic (`_configure_imagemagick`, `_check_linux_imagemagick_policy`,
`_get_fonts`) lives in `video_generator.py` rather than a separate `platform.py` because
it is tightly coupled to MoviePy internals (`change_settings`, `TextClip`). Extracting it
would add indirection without adding reusability — nothing else in the codebase needs these
functions.

### Why detect the Ubuntu policy.xml at startup vs. at render time?
Detecting it at render time (inside `_build_title_slide`) produces a cryptic OSError
deep in the MoviePy stack. Detecting it in `_configure_imagemagick()` — which runs when
MoviePy is first imported — surfaces the error early with a clear fix command before any
time is spent on extraction or summarization.

### Why use absolute font file paths instead of font names?
ImageMagick font names are OS-specific registry entries. `"DejaVu-Sans-Bold"` works on
some Linux distros but not on macOS Homebrew; `"Arial-Bold"` works on macOS but not on
a headless Ubuntu server. Absolute `.ttf` paths are unambiguous and consistent across
all ImageMagick versions and OS configurations.

### Why is `imageio-ffmpeg` preferred over a system ffmpeg?
`imageio-ffmpeg` ships a statically-linked ffmpeg binary as a Python package. This means:
- No `brew install ffmpeg` or `apt install ffmpeg` needed
- The exact same ffmpeg version runs on macOS and Ubuntu CI
- No PATH conflicts with system-installed ffmpeg versions

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
7. **Container deployment**: The Ubuntu setup (ImageMagick + policy fix + fonts +
   imageio-ffmpeg) maps cleanly to a Dockerfile. Pin the base image to
   `ubuntu:22.04` or `ubuntu:24.04` for reproducibility.
