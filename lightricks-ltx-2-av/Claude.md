# CLAUDE.md — LTX-Video Generator

This file gives Claude Code context for working in this project.

---

## What this project does

Single-file Python CLI (`generate.py`) that generates short social-media videos from text prompts using the Lightricks LTX-Video diffusion model. Designed to run locally on Apple Silicon (MPS backend) with no cloud dependency.

---

## Project layout

```
lightricks-ltx-2-av/
├── generate.py        # Entire CLI — one file, no modules
├── requirements.txt   # Python deps (pip)
├── setup.sh           # One-shot venv + dep installer
├── outputs/           # Runtime: generated mp4, gif, thumb, meta (gitignored)
└── cache/             # Runtime: SHA256-keyed frame tensors (gitignored)
```

Everything lives in `generate.py`. Do not split it into modules unless explicitly asked.

---

## Tech stack

| Layer | Library |
|---|---|
| Video generation | `diffusers` LTXPipeline (Lightricks/LTX-Video) |
| ML backend | PyTorch MPS (Apple Silicon) |
| TTS audio | Coqui TTS (`tts_models/en/ljspeech/tacotron2-DDC`) |
| Video encoding | `imageio[ffmpeg]` + ffmpeg subprocess |
| CLI | `typer` |
| Terminal UI | `rich` |

---

## Key constraints

- **MPS only** — the pipeline uses `torch.float32` (MPS does not support float16 for this model). Do not change the dtype.
- **Dimensions must be divisible by 32** — enforced in `_resolve_dims()`. Any resolution change must maintain this.
- **Single-file rule** — `generate.py` is intentionally self-contained. Keep helpers in the same file.
- **ffmpeg must be on PATH** — audio muxing and video encoding both depend on it.
- **TTS is optional** — `TTS` (Coqui) is a heavy dependency and may fail to install on some systems. All TTS paths are wrapped in try/except and should remain optional.

---

## Running the project

```bash
# Bootstrap (once)
bash setup.sh
source .venv/bin/activate

# Basic run
python generate.py --prompt "..."

# With TTS audio
python generate.py --prompt "..." --tts

# With external audio
python generate.py --prompt "..." --audio ./file.mp3

# Production quality
python generate.py --prompt "..." --format linkedin --mode production --duration 6
```

---

## Common pitfalls

- `MPS out of memory` → use `--mode preview` or reduce `--duration`
- `TTS install fails` → try `pip install TTS --no-build-isolation`
- Cache is keyed on `prompt + width + height + num_frames + steps` — changing any of these busts the cache
- `result.frames` shape varies across diffusers versions; the `_frames_tensor_to_pil` helper normalizes all known shapes
