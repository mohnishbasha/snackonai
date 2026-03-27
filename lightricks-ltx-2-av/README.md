# LTX-Video Generator (Apple Silicon + Cloud)

A minimal, single-file Python CLI that generates social-media-ready videos from text prompts using the [Lightricks LTX-Video](https://huggingface.co/Lightricks/LTX-Video) DiT model. Runs entirely on Apple Silicon via PyTorch MPS — no CUDA, no server, no cloud required.

---

## Quickstart

```bash
# Step 1 — Install system dependencies (once)
brew install python@3.11 ffmpeg

# Step 2 — Bootstrap the Python environment (once)
bash setup.sh

# Step 3 — Activate
source .venv/bin/activate

# Step 4 — Generate your first video
python generate.py --prompt "A serene mountain lake at sunrise, golden hour lighting, cinematic"
```

The first run downloads the LTX-Video model weights (~8 GB) from HuggingFace. This happens once and is cached at `~/.cache/huggingface/`. Subsequent runs start immediately.

---

## Requirements

| Requirement | Notes |
|---|---|
| MacBook Pro 2024 (M4 / M4 Pro) | Apple Silicon, MPS backend |
| macOS 14+ (Sonoma / Sequoia) | |
| Python 3.10+ | `brew install python@3.11` |
| ffmpeg | `brew install ffmpeg` |
| 24 GB unified memory | |
| ~10 GB free disk | For model weights (downloaded once) |

---

## How to Run

### Basic — LinkedIn 720p preview (default)

```bash
python generate.py --prompt "A serene mountain lake at sunrise, golden hour lighting, cinematic"
```

### TikTok vertical preview

```bash
python generate.py \
  --prompt "A chef flipping pancakes in a cozy kitchen, slow motion" \
  --format tiktok \
  --mode preview
```

### With external audio file

```bash
python generate.py \
  --prompt "A startup founder pitching on stage, dramatic lighting" \
  --audio ./my_voiceover.mp3 \
  --format linkedin \
  --duration 8
```

### TTS-generated audio from the prompt

```bash
python generate.py \
  --prompt "Welcome to our product launch event" \
  --tts \
  --format instagram
```

> Requires the `TTS` package: `pip install TTS`

### Production quality LinkedIn (full 1280x720, 25 steps)

```bash
python generate.py \
  --prompt "Aerial drone footage of a modern city at dusk" \
  --format linkedin \
  --mode production \
  --duration 6 \
  --output-dir ./renders
```

---

## All CLI options

```
Options:
  --prompt TEXT          Text prompt for video generation  [required]
  --duration FLOAT       Video duration in seconds  [default: 5.0]
  --fps INT              Frames per second  [default: 24]
  --format TEXT          linkedin | tiktok | instagram  [default: linkedin]
  --mode TEXT            preview | production  [default: preview]
  --output-dir PATH      Output directory  [default: ./outputs]
  --tts                  Generate TTS audio from prompt (requires TTS package)
  --audio PATH           Path to an existing audio file to mux in
  --help                 Show this message and exit.
```

---

## Format presets

| Format | Resolution (production) | Resolution (preview) | Aspect ratio |
|---|---|---|---|
| `linkedin` | 1280 x 720 | 640 x 360 | 16:9 |
| `tiktok` | 720 x 1280 | 360 x 640 | 9:16 |
| `instagram` | 720 x 720 | 360 x 360 | 1:1 |

---

## Output files

Each run writes the following to `./outputs/` (or your `--output-dir`):

| File | Description |
|---|---|
| `<timestamp>_<format>_<mode>_<id>.mp4` | Main video (H.264, yuv420p) |
| `<timestamp>_..._thumb.jpg` | First frame as JPEG thumbnail |
| `<timestamp>_..._preview.gif` | 480px-wide animated GIF (first 3 s, 15 fps) |
| `<timestamp>_..._meta.json` | Job metadata (prompt, resolution, paths, timestamp) |
| `<timestamp>_..._tts.wav` | TTS audio (only with `--tts`) |
| `<timestamp>_..._with_audio.mp4` | Video with muxed audio (only when audio is provided) |

### Caching

Inference results are cached in `./cache/<sha256>/frames.pt`. On re-runs with the same prompt, resolution, frame count, and step count, the model is skipped entirely and frames are loaded from disk.

---

## Performance

Expected generation times on M4 Pro (24 GB unified memory):

| Mode | Format | Duration | Approx. time |
|---|---|---|---|
| preview | linkedin | 5 s | ~3–5 min |
| preview | tiktok | 5 s | ~4–6 min |
| production | linkedin | 5 s | ~8–15 min |
| production | linkedin | 8 s | ~12–22 min |

Times vary with thermal throttling. First run is slower due to model compilation.

---

## Cost of running

### Local (Apple Silicon)

Running locally has zero per-generation API or compute cost. You pay only for electricity and the upfront hardware.

| Item | Cost |
|---|---|
| MacBook Pro M4 Pro (24 GB) | ~$2,000–$2,500 one-time |
| Power draw during inference | ~30–60 W (MPS) |
| Electricity per 5-second video | ~$0.001–$0.003 at $0.12/kWh |
| Model weights download | ~8 GB, one-time |

**Effective cost per video: essentially $0** after hardware purchase. Ideal for iterating locally, prototyping, or high-volume batch use without recurring spend.

---

### Cloud (GPU instances)

Running on cloud GPUs is useful when you don't have Apple Silicon, need faster generation, or want to scale beyond a single machine. LTX-Video requires a GPU with at least 16 GB VRAM (A10G or better recommended).

#### Hourly instance rates (approximate, as of 2025)

| Provider | Instance | GPU | VRAM | Hourly rate |
|---|---|---|---|---|
| AWS | `g5.xlarge` | A10G | 24 GB | ~$1.01/hr |
| AWS | `g5.2xlarge` | A10G | 24 GB | ~$1.21/hr |
| GCP | `g2-standard-4` | L4 | 24 GB | ~$0.70/hr |
| Azure | `NC4as T4 v3` | T4 | 16 GB | ~$0.53/hr |
| RunPod (spot) | A10G | A10G | 24 GB | ~$0.35–$0.54/hr |
| RunPod (spot) | A100 (40 GB) | A100 | 40 GB | ~$0.79–$1.09/hr |
| Lambda Labs | `gpu_1x_a10` | A10G | 24 GB | ~$0.60/hr |

#### Cost per video (cloud, estimated)

| Mode | Duration | GPU | Generation time | Cost |
|---|---|---|---|---|
| preview | 5 s | A10G | ~1–2 min | ~$0.01–$0.04 |
| production | 5 s | A10G | ~3–5 min | ~$0.05–$0.10 |
| production | 8 s | A100 | ~2–4 min | ~$0.03–$0.07 |

> Cloud generation is significantly faster than MPS (A10G is roughly 3–5× faster than M4 Pro for this model). Costs above include instance time only — storage and egress are additional but negligible for typical use.

#### Tips for reducing cloud cost

- Use **spot / preemptible instances** (RunPod, GCP Spot, AWS Spot) — 50–70% cheaper, acceptable for batch jobs
- Use **preview mode** for iteration; switch to production only for final renders
- **Cache inference results** — the built-in `./cache/` layer avoids re-running the model for identical prompts
- Spin the instance down immediately after a batch run; idle GPU time is wasted spend

---

## Troubleshooting

### Out of memory (MPS OOM)

The model will print a helpful message and exit gracefully. To recover:

- Switch to `--mode preview` (halves both dimensions)
- Reduce `--duration` (e.g. `--duration 3`)
- Reduce `--fps` (e.g. `--fps 12`)
- Quit other GPU-intensive apps (browsers with GPU acceleration, games, etc.)

### ffmpeg not found

```bash
brew install ffmpeg
```

### Python version error

```bash
brew install python@3.11
# Then re-run setup.sh using the new python3
```

### TTS install error

```bash
pip install TTS
```

Some systems may need `pip install TTS --no-build-isolation` if the build fails.

### HuggingFace download is slow / fails

```bash
export HF_ENDPOINT=https://hf-mirror.com   # optional mirror
huggingface-cli login                        # only needed for gated models
```

---

## Project structure

```
lightricks-ltx-2-av/
├── generate.py        # Single-file CLI entrypoint
├── requirements.txt   # Python dependencies
├── setup.sh           # Environment bootstrap script
├── README.md          # This file
├── .gitignore
├── .venv/             # Created by setup.sh (gitignored)
├── outputs/           # Generated videos, thumbnails, GIFs, metadata (gitignored)
└── cache/             # SHA256-keyed frame cache (gitignored)
```
