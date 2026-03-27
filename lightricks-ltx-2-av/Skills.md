# Skills — LTX-Video Generator

Capabilities this tool has out of the box.

---

## Video generation

| Skill | How to invoke |
|---|---|
| Generate a video from a text prompt | `--prompt "..."` |
| LinkedIn 16:9 (default) | `--format linkedin` |
| TikTok 9:16 vertical | `--format tiktok` |
| Instagram 1:1 square | `--format instagram` |
| Fast preview (half resolution, 10 steps) | `--mode preview` |
| Full production quality (25 steps) | `--mode production` |
| Custom duration | `--duration 8` (seconds) |
| Custom frame rate | `--fps 30` |
| Custom output directory | `--output-dir ./renders` |

---

## Audio

| Skill | How to invoke |
|---|---|
| Auto-generate narration from prompt (TTS) | `--tts` |
| Attach an existing audio file | `--audio ./voiceover.mp3` |
| Mux audio into video | Automatic when `--tts` or `--audio` is used |

TTS uses Coqui Tacotron2-DDC (English). The resulting audio is saved as `_tts.wav` and the final muxed file as `_with_audio.mp4`.

---

## Outputs (per run)

| Output | Description |
|---|---|
| `.mp4` | H.264 video, yuv420p |
| `_thumb.jpg` | First frame as JPEG |
| `_preview.gif` | 480px GIF, first 3 s at 15 fps |
| `_meta.json` | Full job metadata (prompt, resolution, paths, timestamp) |
| `_tts.wav` | TTS audio (only with `--tts`) |
| `_with_audio.mp4` | Video + audio muxed (only when audio is used) |

---

## Caching

Inference results are cached by SHA256 of `prompt + resolution + frame count + steps`. Re-running with identical parameters skips the model entirely and loads frames from `./cache/`. This makes iteration fast after the first run.

---

## Supported platforms

| Platform | Status |
|---|---|
| MacBook Pro M4 / M4 Pro (24 GB) | Fully supported |
| Other Apple Silicon (M1/M2/M3) | Should work; untested |
| Cloud GPU (A10G, A100, L4) | Works with CUDA; switch dtype to float16 for speed |
| CPU-only | Possible but extremely slow |

---

## Not supported (yet)

- Image-to-video (img2vid)
- Multi-language TTS
- Automatic cloud upload (S3, GCS)
- Batch prompt files
- API server / web UI
