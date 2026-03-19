# CLAUDE.md — Mr. Pixel Smith

## Project Overview

`mr-pixel-smith.py` is an interactive AI image generator that calls Ollama's `x/z-image-turbo` model via the CLI, then watermarks the output using Pillow.

## Architecture

- **`mr-pixel-smith.py`** — main entry point; interactive prompts → Ollama subprocess → Pillow watermark → PNG save
- **`mr-pixel-smith.sh`** — one-shot shell wrapper for a fixed prompt
- **`requirements.txt`** — `requests`, `pillow>=10.0.0`

## Key Constants (mr-pixel-smith.py)

| Constant | Value | Purpose |
|----------|-------|---------|
| `MODEL` | `x/z-image-turbo` | Ollama model name |
| `DEFAULT_WIDTH` | 1200 | Default image width (px) |
| `DEFAULT_HEIGHT` | 628 | Default image height (px) |
| `WATERMARK_TEXT` | `snackonai.com` | Text stamped on every image |
| `OUTPUT_FILE` | `output.png` | Default output filename |

## Flow

1. `check_ollama()` — verifies the `ollama` binary exists and the daemon responds
2. Collect prompt, width, height, output path from stdin
3. `generate_image()` — runs `ollama run MODEL PROMPT --width W --height H`, parses JSON, base64-decodes the PNG
4. `add_watermark()` — composites a semi-transparent tiled watermark + corner badge
5. Writes final PNG to disk

## Development Notes

- Ollama returns a JSON object with a `response` field containing base64-encoded PNG data.
- Font falls back to Pillow's built-in default if DejaVu Sans Bold is unavailable.
- Image generation timeout is 5 minutes (`timeout=300`).
