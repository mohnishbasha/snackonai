# SnackOnAIClips

> Turn any blog post into a LinkedIn-ready short video in seconds.

**SnackOnAIClips** is a production-grade Python CLI and package that:
1. Fetches and cleans article content from any URL
2. Summarizes it into a headline, 2–3 sentence narration, and 3–5 bullet points using an LLM
3. Generates a **1080×1920 vertical MP4** (≤60 seconds) with text slides, optional voiceover, and your watermark

---

## Features

- Multi-strategy content extraction (trafilatura → readability → newspaper3k)
- LLM summarization via **OpenAI** or **Ollama** (local, free)
- Automatic fallback summarizer if LLM is unavailable
- Optional TTS voiceover via **gTTS** (free) or **ElevenLabs** (premium)
- Three visual style presets: `minimal`, `modern`, `cinematic`
- Optional thumbnail PNG generation
- Optional background music mixing
- Rich terminal progress output
- Retry logic with exponential backoff for network calls
- Fully typed, modular, and tested codebase

---

## Installation

### 1. Clone and set up a virtual environment

```bash
git clone https://github.com/snackonai/mr-video-smith.git
cd mr-video-smith
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install ImageMagick (required for text rendering)

```bash
# macOS
brew install imagemagick

# Ubuntu/Debian
sudo apt install imagemagick

# Windows (via Chocolatey)
choco install imagemagick
```

### 3. Set environment variables

```bash
# Required for OpenAI (default LLM provider)
export OPENAI_API_KEY="sk-..."

# Optional: use Ollama instead
export SNACKONAI_LLM_PROVIDER="ollama"
export OLLAMA_MODEL="llama3.2"

# Optional: ElevenLabs TTS
export ELEVENLABS_API_KEY="..."
export SNACKONAI_TTS_PROVIDER="elevenlabs"
```

---

## Usage

### Basic

```bash
python snackonaiclips.py --url https://example.com/blog/post
```

### With style and watermark

```bash
python snackonaiclips.py \
  --url https://techcrunch.com/some-article \
  --output my_video.mp4 \
  --style cinematic \
  --watermark "MyBrand"
```

### Summary only (no video)

```bash
python snackonaiclips.py \
  --url https://example.com/article \
  --summary-only \
  --json-output summary.json
```

### Disable TTS (silent video)

```bash
python snackonaiclips.py \
  --url https://example.com/article \
  --no-tts \
  --style minimal
```

### Use Ollama instead of OpenAI

```bash
python snackonaiclips.py \
  --url https://example.com/article \
  --llm ollama \
  --ollama-model llama3.2
```

### Generate thumbnail alongside video

```bash
python snackonaiclips.py \
  --url https://example.com/article \
  --thumbnail
```

---

## CLI Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | *(required)* | Blog or article URL to process |
| `--output` | `output.mp4` | Output video file path |
| `--style` | `modern` | Visual style: `minimal`, `modern`, `cinematic` |
| `--watermark` | `SnackOnAI` | Watermark text (pass `""` to disable) |
| `--llm` | env/`openai` | LLM provider: `openai` or `ollama` |
| `--openai-model` | `gpt-4o-mini` | OpenAI model name |
| `--ollama-model` | `llama3.2` | Ollama model name |
| `--no-tts` | `false` | Disable voiceover generation |
| `--tts-provider` | `gtts` | TTS provider: `gtts` or `elevenlabs` |
| `--thumbnail` | `false` | Also save a PNG thumbnail |
| `--json-output` | *(none)* | Save summary JSON to file |
| `--summary-only` | `false` | Print summary JSON and exit |
| `--log-level` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | OpenAI model (default: `gpt-4o-mini`) |
| `OLLAMA_BASE_URL` | Ollama server URL (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | Ollama model name (default: `llama3.2`) |
| `SNACKONAI_LLM_PROVIDER` | `openai` or `ollama` |
| `SNACKONAI_TTS_PROVIDER` | `gtts`, `elevenlabs`, or `disabled` |
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | ElevenLabs voice ID (default: `Rachel`) |
| `SNACKONAI_LOG_LEVEL` | Logging level (default: `INFO`) |
| `SNACKONAI_MUSIC_PATH` | Path to background music file |

---

## Project Structure

```
mr-video-smith/
├── snackonaiclips.py          # Entry-point script
├── snackonaiclips/
│   ├── __init__.py
│   ├── cli.py                 # CLI argument parsing & pipeline orchestration
│   ├── config.py              # Typed configuration (env vars + defaults)
│   ├── extractor.py           # URL → clean article text
│   ├── summarizer.py          # Article text → structured JSON summary
│   ├── tts.py                 # Summary → voiceover MP3
│   ├── video_generator.py     # Summary + audio → MP4
│   ├── utils.py               # Logging, retry decorator, helpers
│   ├── claude.md              # System design decisions
│   ├── skills.md              # Technologies & skills reference
│   └── tests/
│       ├── test_extractor.py
│       ├── test_summarizer.py
│       ├── test_video_generator.py
│       └── test_integration.py
├── requirements.txt
├── pyproject.toml
├── sample_output.json
└── README.md
```

---

## Running Tests

```bash
# All tests with coverage
pytest

# Specific module
pytest snackonaiclips/tests/test_summarizer.py -v

# Skip slow integration tests
pytest -k "not integration" -v
```

---

## Sample Output

Running against a real AI/tech blog post produces:

```json
{
  "headline": "AI Is Reshaping Modern Software Development Forever",
  "summary": "Artificial intelligence tools are fundamentally changing how developers write and review code. Models like GPT-4 can generate full functions from plain English, and GitHub Copilot is now used by over a million developers. The productivity gains are real, but critical thinking and system design remain irreplacably human.",
  "bullets": [
    "AI code completion cuts boilerplate by up to 55%",
    "GitHub Copilot adopted by millions of developers worldwide",
    "Natural language → working code is now production-ready",
    "Security review and architecture still demand human judgment",
    "Teams prototype and iterate faster than ever before"
  ]
}
```

---

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────────┐
│    URL      │───▶│  Extractor   │───▶│ Summarizer  │───▶│  Video Generator │
│             │    │              │    │             │    │                  │
│ blog post   │    │ trafilatura  │    │ OpenAI      │    │ MoviePy slides   │
│             │    │ readability  │    │ Ollama      │    │ Gradient BG      │
│             │    │ newspaper3k  │    │ Fallback    │    │ TTS voiceover    │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────────┘
                                                                    │
                                                                    ▼
                                                          ┌──────────────────┐
                                                          │   output.mp4     │
                                                          │  1080×1920       │
                                                          │  ≤ 60 seconds    │
                                                          └──────────────────┘
```

---

## License

MIT — see [LICENSE](LICENSE)

---

Built with Python, MoviePy, OpenAI, and caffeine. Made by [SnackOnAI](https://snackonai.com).
