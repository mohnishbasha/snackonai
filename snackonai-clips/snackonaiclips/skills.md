# SnackOnAIClips — Skills & Technologies Demonstrated

## Technologies Used

### Languages & Runtimes
- **Python 3.10+** — type hints, `dataclasses`, `X | Y` union types, `platform` stdlib
- **NumPy** — gradient frame generation for video backgrounds (cross-platform, no native deps)

### AI / LLM
- **OpenAI API (GPT-4o-mini)** — structured JSON output via `response_format`, prompt engineering
- **Ollama** — local LLM inference with REST API, model-agnostic design
- **Prompt engineering** — persona-based system prompts, strict output format constraints, temperature tuning

### Content Extraction
- **trafilatura** — state-of-the-art HTML boilerplate removal, metadata extraction
- **readability-lxml** — Mozilla Readability algorithm ported to Python
- **newspaper3k** — multi-strategy article extraction with NLP
- **Local file I/O** — `file://` URL and filesystem path support for offline use

### Video Production
- **MoviePy 1.0.3** — Python-native video composition, clip concatenation, audio mixing
- **ImageMagick** — font rendering (IMv6 on Ubuntu, IMv7 on macOS — handled automatically)
- **imageio-ffmpeg** — bundled ffmpeg binary, no system-level install required
- **Pillow** — image processing and frame manipulation

### Text-to-Speech
- **gTTS** — Google Text-to-Speech, free MP3 generation (works on macOS + Ubuntu)
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
each encapsulated in its own function. The caller never knows which succeeded. The same
pattern extends to local file reading — a fourth implicit strategy that short-circuits the
HTTP path entirely.

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
URL/file → Extractor → Summarizer → TTS → VideoGenerator → Output
```
Each stage is independently testable and replaceable. The CLI orchestrates them but
has no knowledge of their internals.

### Graceful Degradation
- LLM unavailable → rule-based fallback summarizer
- TTS fails → video is generated without audio
- Single extractor fails → cascade to next strategy
- Thumbnail generation fails → log warning and continue
- Font not found → ImageMagick picks its own default

### Fail-Fast with Actionable Errors
The Ubuntu ImageMagick policy restriction is detected at startup (before any processing),
raising a `RuntimeError` that includes the exact `sed` command to fix it. This avoids
wasting 30+ seconds on extraction and summarization before hitting a cryptic OSError
deep in MoviePy's stack.

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

### Cross-Platform Systems Engineering
- Runtime platform detection via `platform.system()` to apply OS-specific fixes
- ImageMagick binary selection: `magick` (IMv7/macOS) vs `convert` (IMv6/Ubuntu)
- Security policy detection and early failure with actionable fix instructions
- Font path resolution across Homebrew, apt, and macOS system font directories
- Bundled ffmpeg via `imageio-ffmpeg` to eliminate system dependency differences

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

### Cross-Platform Production Readiness
The codebase runs identically on macOS (developer laptops) and Ubuntu (production servers
and CI/CD). Platform-specific quirks — ImageMagick binary names, security policies, font
paths — are handled automatically at runtime with no manual configuration required beyond
the documented one-time system dependency install.

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
generators, and sales enablement video production at scale. The Ubuntu compatibility
makes it deployable in standard cloud infrastructure (EC2, GCE, Cloud Run) without
custom AMIs or container base images.
