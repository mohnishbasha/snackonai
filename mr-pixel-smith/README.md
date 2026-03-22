# Mr. Pixel Smith

An AI image generator powered by [Ollama](https://ollama.com) with automatic watermarking via Pillow.

<img width="1200" height="624" alt="mr-pixel-smith-floating-clouds-stars-4k" src="https://github.com/user-attachments/assets/068bbd41-0b60-41cc-a42e-4a0e5903135c" />


## Requirements

- **macOS with Apple Silicon** — `x/z-image-turbo` uses Apple's MLX framework and only runs on macOS. Linux and Docker are not supported.
- [Ollama](https://ollama.com) installed and running (`ollama serve`)
- The `x/z-image-turbo` model pulled locally
- Python 3.8+

## Setup

```bash
# Install as a package (recommended)
pip install -e .

# Pull the image model
ollama pull x/z-image-turbo
```

Alternatively, install dependencies directly:

```bash
pip install -r requirements.txt
```

## Usage

### CLI (after `pip install -e .`)

```bash
# Interactive mode
mr-pixel-smith

# Non-interactive with flags
mr-pixel-smith -p "A futuristic city at sunset"
mr-pixel-smith -p "A serene fantasy landscape with floating islands at sunrise"
mr-pixel-smith -p "Abstract art" -w 800 -H 600 -o abstract.png
```

**Flags:**

| Flag | Description | Default |
|------|-------------|---------|
| `-p`, `--prompt` | Image prompt (max 2000 chars) | _(interactive)_ |
| `-w`, `--width` | Width in pixels (64–4096) | `1200` |
| `-H`, `--height` | Height in pixels (64–4096) | `628` |
| `-o`, `--output` | Output PNG filename | `output.png` |

### Run directly (no install)

```bash
python mr_pixel_smith/cli.py -p "Your prompt here"
```

### Shell Script (no Python required)

```bash
bash mr_pixel_smith.sh -p "A futuristic city at sunset"
bash mr_pixel_smith.sh -p "Abstract art" -w 800 -h 600 -o abstract.png
```

**Flags:**

| Flag | Description | Default |
|------|-------------|---------|
| `-p` | Image prompt (required, max 2000 chars) | — |
| `-w` | Width in pixels (64–4096) | `1200` |
| `-h` | Height in pixels (64–4096) | `628` |
| `-o` | Output PNG filename | `output.png` |

Note: the shell script does **not** apply the watermark — use the Python CLI for watermarked output.

## Output

Generated images are saved as PNG files with a tiled `snackonai.com` watermark overlaid diagonally and a corner stamp.

## Defaults

| Setting | Value |
|---------|-------|
| Model | `x/z-image-turbo` |
| Width | 1200 px |
| Height | 628 px |
| Watermark | `snackonai.com` |
| Output | `output.png` |

## Project Structure

```
mr-pixel-smith/
├── mr_pixel_smith/
│   ├── __init__.py   # package API
│   └── cli.py        # CLI entry point
├── mr_pixel_smith.py # standalone script (legacy)
├── mr_pixel_smith.sh # shell wrapper (no Python required)
├── pyproject.toml
├── requirements.txt
└── README.md
```
