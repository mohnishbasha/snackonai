# SnackOnAIClips

> Turn any blog post into a LinkedIn-ready short video in seconds.

**SnackOnAIClips** is a production-grade Python CLI and package that:
1. Fetches and cleans article content from any URL **or local file**
2. Summarizes it into a headline, 2–3 sentence narration, and 3–5 bullet points using an LLM
3. Generates a **1080×1920 vertical MP4** (≤60 seconds) with text slides, optional voiceover, and your watermark

Runs on **macOS** and **Ubuntu** (22.04 / 24.04).

---

## Features

- Multi-strategy content extraction (trafilatura → readability → newspaper3k)
- **Local file support** — pass a `.html` or `.txt` path instead of a URL (works fully offline)
- LLM summarization via **OpenAI** or **Ollama** (fully local, no API key needed)
- Automatic fallback summarizer if LLM is unavailable
- Optional TTS voiceover via **gTTS** (free) or **ElevenLabs** (premium)
- Three visual style presets: `minimal`, `modern`, `cinematic`
- Optional thumbnail PNG generation
- Optional background music mixing
- Rich terminal progress output
- Retry logic with exponential backoff for network calls
- Fully typed, modular, and tested codebase

---

## Platform Compatibility

| Component | macOS (Homebrew) | Ubuntu 22.04 / 24.04 |
|-----------|-----------------|----------------------|
| Python | 3.11+ via `brew` or `pyenv` | 3.10 (22.04) / 3.12 (24.04) |
| ImageMagick | IMv7 — `brew install imagemagick` | IMv6 — `apt install imagemagick` |
| IM binary | auto-set to `magick` | kept as `convert` (IMv6 default) |
| IM policy | no restriction | policy.xml fix required (see below) |
| Fonts | Homebrew DejaVu or system Arial | `apt install fonts-dejavu-core` |
| ffmpeg | bundled via `imageio-ffmpeg` | bundled via `imageio-ffmpeg` |
| Ollama | native app | Docker or native binary |

---

## Installation

### macOS

```bash
# 1. System dependencies
brew install imagemagick
brew install --cask font-dejavu   # or: brew tap homebrew/cask-fonts first

# 2. Clone and set up Python environment
git clone https://github.com/snackonai/snackonai-clips.git
cd snackonai-clips
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Ubuntu 22.04 / 24.04

```bash
# 1. System dependencies
sudo apt update
sudo apt install -y imagemagick fonts-dejavu-core

# 2. Fix ImageMagick's restrictive security policy (required for MoviePy TextClip)
#    Ubuntu ships with a policy that blocks PNG writes from temp paths.
sudo sed -i 's/rights="none" pattern="PNG"/rights="read|write" pattern="PNG"/' \
  /etc/ImageMagick-6/policy.xml

# 3. Clone and set up Python environment
git clone https://github.com/snackonai/snackonai-clips.git
cd snackonai-clips
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Ubuntu 20.04**: Python 3.8 is the default but the codebase requires 3.10+.
> Install a newer version first:
> ```bash
> sudo add-apt-repository ppa:deadsnakes/ppa
> sudo apt install python3.11 python3.11-venv
> python3.11 -m venv .venv
> ```

### Set environment variables

```bash
# Required for OpenAI (default LLM provider)
export OPENAI_API_KEY="sk-..."

# Optional: use Ollama instead (fully offline)
export SNACKONAI_LLM_PROVIDER="ollama"
export OLLAMA_MODEL="llama3.2"

# Optional: ElevenLabs TTS
export ELEVENLABS_API_KEY="..."
export SNACKONAI_TTS_PROVIDER="elevenlabs"
```

---

## Usage

### Basic (remote URL)

```bash
python snackonaiclips.py --url https://example.com/blog/post
```

### Local file (fully offline)

```bash
# HTML file
python snackonaiclips.py --url ./my-article.html --llm ollama --no-tts

# Plain text file
python snackonaiclips.py --url ./my-article.txt --llm ollama --no-tts

# Absolute path or file:// URL
python snackonaiclips.py --url "file:///home/user/articles/post.html" --llm ollama --no-tts
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

### Silent video (no TTS)

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

## Offline / Air-gapped Usage

SnackOnAIClips can run with **zero internet connectivity**:

```bash
# 1. Start Ollama locally
ollama pull llama3.2
ollama serve

# 2. Run against a local file
python snackonaiclips.py \
  --url ./article.html \
  --llm ollama \
  --no-tts \
  --output output.mp4
```

| Component | Offline alternative |
|-----------|---------------------|
| Remote URL fetch | Pass a local `.html` or `.txt` file path |
| OpenAI LLM | `--llm ollama` with a locally-pulled model |
| gTTS voiceover | `--no-tts` |
| Video rendering | Always local (MoviePy + NumPy) |

---

## CLI Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | *(required)* | URL **or** local file path (`.html`, `.txt`, `file://...`) |
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

## Dependencies

### Python packages (`pip install -r requirements.txt`)

| Package | Version | Purpose |
|---------|---------|---------|
| `moviepy` | `==1.0.3` | Video composition (pinned — 2.x has breaking API changes) |
| `numpy` | `>=1.24,<2.0` | Frame generation (moviepy 1.x incompatible with numpy 2.x) |
| `imageio-ffmpeg` | `>=0.4.9` | Bundled ffmpeg binary — no separate ffmpeg install needed |
| `trafilatura` | `>=1.9` | Primary HTML extractor |
| `readability-lxml` | `>=0.8.1` | Fallback HTML extractor |
| `openai` | `>=1.35` | OpenAI API client |
| `gTTS` | `>=2.5` | Free text-to-speech |
| `rich` | `>=13.7` | Terminal progress & formatting |

### System dependencies

| Tool | macOS | Ubuntu | Required for |
|------|-------|--------|-------------|
| **ImageMagick** | `brew install imagemagick` | `sudo apt install imagemagick` | Text rendering in video slides |
| **Fonts (DejaVu)** | `brew install --cask font-dejavu` | `sudo apt install fonts-dejavu-core` | Slide typography |
| **IM policy fix** | *(not needed)* | `sudo sed -i ...` (see install section) | Allow MoviePy PNG temp writes on Ubuntu |

---

## Troubleshooting

### `OSError: convert: unable to read font` (macOS)

ImageMagick v7 deprecated `convert`. The code auto-detects this and switches to `magick`, but fonts must be installed:

```bash
brew install --cask font-dejavu
# or install any TTF font and set SNACKONAI_FONT_DIR
```

### `OSError: ... PNG32:/tmp/tmp*.png` (Ubuntu)

ImageMagick's policy.xml is blocking writes to `/tmp`. Run the policy fix:

```bash
sudo sed -i 's/rights="none" pattern="PNG"/rights="read|write" pattern="PNG"/' \
  /etc/ImageMagick-6/policy.xml
```

The tool will also detect this automatically and print the exact fix command if it encounters the restriction at startup.

### `WARNING: The convert command is deprecated in IMv7`

This is suppressed automatically — the code sets the binary to `magick` when IMv7 is detected. If you still see it, ensure ImageMagick is installed: `brew install imagemagick`.

---

## Project Structure

```
snackonai-clips/
├── snackonaiclips.py          # Entry-point script
├── snackonaiclips/
│   ├── __init__.py
│   ├── cli.py                 # CLI argument parsing & pipeline orchestration
│   ├── config.py              # Typed configuration (env vars + defaults)
│   ├── extractor.py           # URL / local file → clean article text
│   ├── summarizer.py          # Article text → structured JSON summary
│   ├── tts.py                 # Summary → voiceover MP3
│   ├── video_generator.py     # Summary + audio → MP4 (cross-platform)
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
┌──────────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────────┐
│  URL or file     │───▶│  Extractor   │───▶│ Summarizer  │───▶│  Video Generator │
│                  │    │              │    │             │    │                  │
│ https://...      │    │ trafilatura  │    │ OpenAI      │    │ MoviePy slides   │
│ ./article.html   │    │ readability  │    │ Ollama      │    │ Gradient BG      │
│ ./article.txt    │    │ newspaper3k  │    │ Fallback    │    │ TTS voiceover    │
│ file:///...      │    │ local read   │    │             │    │ cross-platform   │
└──────────────────┘    └──────────────┘    └─────────────┘    └──────────────────┘
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
