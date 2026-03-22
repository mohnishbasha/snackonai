# SnackOnAIClips — Skills & Technologies Demonstrated

## Technologies Used

### Languages & Runtimes
- **Python 3.11+** — type hints, `dataclasses`, `match` expressions, `X | Y` union types
- **NumPy** — gradient frame generation for video backgrounds

### AI / LLM
- **OpenAI API (GPT-4o-mini)** — structured JSON output via `response_format`, prompt engineering
- **Ollama** — local LLM inference with REST API, model-agnostic design
- **Prompt engineering** — persona-based system prompts, strict output format constraints, temperature tuning

### Content Extraction
- **trafilatura** — state-of-the-art HTML boilerplate removal, metadata extraction
- **readability-lxml** — Mozilla Readability algorithm ported to Python
- **newspaper3k** — multi-strategy article extraction with NLP

### Video Production
- **MoviePy** — Python-native video composition, clip concatenation, audio mixing
- **ImageMagick / Pillow** — font rendering, image processing
- **ffmpeg** (via MoviePy) — H.264 encoding, AAC audio, MP4 muxing

### Text-to-Speech
- **gTTS** — Google Text-to-Speech, free offline MP3 generation
- **ElevenLabs** — AI voice cloning, premium audio quality
- **mutagen** — MP3 audio duration detection for timing sync

### CLI / DevX
- **argparse** — stdlib CLI argument parsing, extensible flag design
- **rich** — terminal progress bars, styled panels, spinner animations

### Testing
- **pytest** — fixtures, parametrize, marks
- **unittest.mock** — patch, MagicMock for LLM/HTTP isolation
- **pytest-cov** — coverage reporting

### Build / Packaging
- **pyproject.toml** — PEP 517/518 build system, optional dependency groups
- **setuptools** — entry-point script registration

---

## System Design Concepts Demonstrated

### Strategy Pattern
The extractor uses a cascade of three strategies (trafilatura → readability → newspaper3k),
each encapsulated in its own function. The caller never knows which succeeded.

### Factory / Provider Pattern
LLM and TTS providers are selected at runtime via config enum. Each provider has an
identical function signature, making them interchangeable without changing calling code.

### Decorator-based Retry
The `@retry` decorator wraps any function with exponential backoff logic. Applied to
HTTP fetches and LLM API calls without polluting business logic with retry loops.

### Singleton Configuration
`AppConfig` is instantiated once and shared globally via `get_config()`. All components
read from the same config object, which can be overridden by CLI flags before first use.

### Pipeline Architecture
```
URL → Extractor → Summarizer → TTS → VideoGenerator → Output
```
Each stage is independently testable and replaceable. The CLI orchestrates them but
has no knowledge of their internals.

### Graceful Degradation
- If the LLM is unavailable → rule-based fallback summarizer
- If TTS fails → video is generated without audio
- If a single extractor fails → cascade to next strategy
- If thumbnail generation fails → log warning and continue

---

## AI & Infrastructure Skills

### Prompt Engineering
- Persona-based system prompts that establish voice and domain expertise
- Output format constraints embedded in user prompts (JSON schema, word limits)
- Temperature tuning for creative-but-consistent output
- Token budget management via input truncation

### LLM Integration
- OpenAI Python SDK with structured JSON response mode
- Ollama REST API integration with streaming disabled
- Retry logic for transient API failures
- Schema validation before trusting LLM output

### Video Synthesis Pipeline
- Programmatic slide composition from structured data
- Timing budget calculation to fit within duration constraints
- Audio-video synchronization via duration metadata
- Multi-track audio mixing (voiceover + background music)

### Production Code Practices
- Type hints throughout all public interfaces
- Structured logging with caller-specific loggers (`logging.getLogger(__name__)`)
- Separation of concerns: each file owns exactly one domain
- Environment-variable-driven configuration (12-factor app compatible)
- Comprehensive error hierarchy with specific exception types

---

## Why This Project Is Valuable

### Content Creators & Marketers
Converting long-form blog content into short videos is time-consuming and requires
video editing skills most people lack. SnackOnAIClips automates the entire pipeline
in seconds — extraction, summarization, narration, and rendering.

### LinkedIn-Optimized Format
Short vertical videos (1080×1920) are LinkedIn's highest-engagement content format.
This tool produces exactly that format, with typography optimized for mobile viewing
where 80%+ of LinkedIn traffic originates.

### AI Engineering Showcase
The project demonstrates the full stack of modern AI engineering:
- **Prompt engineering** to get structured, reliable LLM output
- **Multi-provider design** (OpenAI + Ollama) for flexibility and cost control
- **Graceful degradation** when AI services are unavailable
- **Pipeline orchestration** connecting disparate AI systems (LLM + TTS + video)

### Extensibility
The modular design makes it easy to add:
- New video styles (just extend `STYLES` dict)
- New LLM providers (add enum value + `_summarize_*` function)
- New TTS providers (add enum value + `_generate_*` function)
- New content extractors (add `_extract_with_*` function to cascade)
- Thumbnail variants, subtitle overlays, background music packs

### Business Applicability
This architecture translates directly to production content automation systems:
newsletter-to-video pipelines, podcast-to-shorts tools, documentation-to-demo
generators, and sales enablement video production at scale.
