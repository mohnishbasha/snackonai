"""
LTX-2 Video Generator — MacBook Pro 2024 (Apple Silicon M4/M4 Pro, MPS backend)
Single-file CLI: python generate.py --prompt "..." [options]
"""

import os

# Reduce MPS memory fragmentation before torch is imported
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import typer
from PIL import Image
from rich import print as rprint
from rich.panel import Panel
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

console = Console()
app = typer.Typer(add_completion=False)

# ---------------------------------------------------------------------------
# Format presets (capped at 720p for 24 GB MPS)
# ---------------------------------------------------------------------------
FORMAT_PRESETS = {
    "linkedin":  {"width": 1280, "height": 720,  "ratio": "16:9"},
    "tiktok":    {"width": 720,  "height": 1280, "ratio": "9:16"},
    "instagram": {"width": 720,  "height": 720,  "ratio": "1:1"},
}

CACHE_DIR = Path("./cache")
OUTPUT_DIR_DEFAULT = Path("./outputs")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _resolve_dims(fmt: str, mode: str) -> tuple[int, int]:
    preset = FORMAT_PRESETS[fmt]
    w, h = preset["width"], preset["height"]
    if mode == "preview":
        w, h = w // 2, h // 2
    # LTXPipeline requires dimensions divisible by 32
    w = (w // 32) * 32
    h = (h // 32) * 32
    return w, h


def _cache_key(prompt: str, width: int, height: int, num_frames: int, steps: int) -> str:
    raw = f"{prompt}|{width}|{height}|{num_frames}|{steps}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _load_from_cache(key: str) -> Optional[torch.Tensor]:
    path = CACHE_DIR / key / "frames.pt"
    if path.exists():
        console.log(f"[green]Cache hit[/green] → {path}")
        return torch.load(path, map_location="cpu", weights_only=True)
    return None


def _save_to_cache(key: str, frames: torch.Tensor) -> None:
    path = CACHE_DIR / key
    path.mkdir(parents=True, exist_ok=True)
    torch.save(frames, path / "frames.pt")
    console.log(f"[dim]Cached frames → {path / 'frames.pt'}[/dim]")


def _frames_tensor_to_pil(frames: torch.Tensor) -> list[Image.Image]:
    """
    Convert a frames tensor of shape (T, C, H, W) or (T, H, W, C) or (B, T, C, H, W)
    to a list of PIL images.
    """
    t = frames.float().cpu()

    # Squeeze batch dim if present
    if t.ndim == 5:
        t = t[0]  # (T, C, H, W)

    # Convert (T, C, H, W) → (T, H, W, C)
    if t.ndim == 4 and t.shape[1] in (1, 3, 4):
        t = t.permute(0, 2, 3, 1)

    # Normalize to [0, 255]
    if t.max() <= 1.0:
        t = (t * 255).clamp(0, 255)
    else:
        t = t.clamp(0, 255)

    imgs = []
    for frame in t:
        arr = frame.numpy().astype(np.uint8)
        if arr.shape[-1] == 1:
            arr = arr.squeeze(-1)
            imgs.append(Image.fromarray(arr, mode="L").convert("RGB"))
        else:
            imgs.append(Image.fromarray(arr[..., :3], mode="RGB"))
    return imgs


def _save_mp4(pil_frames: list[Image.Image], path: Path, fps: int) -> None:
    import imageio.v3 as iio

    arrays = [np.array(f) for f in pil_frames]
    iio.imwrite(str(path), arrays, fps=fps, codec="libx264", plugin="FFMPEG",
                output_params=["-crf", "23", "-preset", "fast", "-pix_fmt", "yuv420p"])


def _save_thumbnail(pil_frames: list[Image.Image], path: Path) -> None:
    pil_frames[0].save(str(path), "JPEG", quality=90)


def _save_gif(pil_frames: list[Image.Image], path: Path, fps: int, duration_secs: float) -> None:
    import imageio.v3 as iio

    gif_fps = 15
    max_frames = int(min(duration_secs, 3.0) * fps)
    subset = pil_frames[:max_frames]

    # Scale to 480px wide
    sample = subset[0]
    w, h = sample.size
    new_w = 480
    new_h = int(h * new_w / w)
    resized = [f.resize((new_w, new_h), Image.LANCZOS) for f in subset]

    # Step to approximate gif_fps
    step = max(1, fps // gif_fps)
    sampled = resized[::step]

    arrays = [np.array(f) for f in sampled]
    iio.imwrite(str(path), arrays, fps=gif_fps, plugin="pillow", loop=0)


def _generate_tts_audio(prompt: str, output_path: Path) -> None:
    """Generate TTS audio from prompt using Coqui TTS."""
    from TTS.api import TTS as CoquiTTS

    console.log("[cyan]Generating TTS audio…[/cyan]")
    tts = CoquiTTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False)
    tts.tts_to_file(text=prompt, file_path=str(output_path))
    console.log(f"[green]TTS audio saved → {output_path}[/green]")


def _mux_audio(video_path: Path, audio_path: Path, output_path: Path) -> None:
    """Mux audio into video using ffmpeg via subprocess."""
    import subprocess

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        console.log(f"[yellow]ffmpeg mux warning:[/yellow] {result.stderr[-400:]}")
    else:
        console.log(f"[green]Audio muxed → {output_path}[/green]")


# ---------------------------------------------------------------------------
# Pipeline loader
# ---------------------------------------------------------------------------

def _load_pipeline(device: torch.device):
    from diffusers import LTXPipeline

    console.log("[cyan]Loading LTX-Video pipeline from HuggingFace…[/cyan]")
    console.log("[dim](First run downloads ~8 GB — be patient)[/dim]")

    pipe = LTXPipeline.from_pretrained(
        "Lightricks/LTX-Video",
        torch_dtype=torch.float32,  # MPS requires float32
    )

    # MPS memory optimizations — check before calling, LTXPipeline doesn't support all of these
    pipe.enable_model_cpu_offload()
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing(slice_size="auto")
    if hasattr(pipe, "enable_vae_slicing"):
        pipe.enable_vae_slicing()

    return pipe


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

@app.command()
def main(
    prompt: str = typer.Option(..., "--prompt", "-p", help="Text prompt for video generation"),
    duration: float = typer.Option(5.0, "--duration", "-d", help="Video duration in seconds"),
    fps: int = typer.Option(24, "--fps", help="Frames per second"),
    fmt: str = typer.Option("linkedin", "--format", "-f",
                             help="Output format: linkedin | tiktok | instagram"),
    mode: str = typer.Option("preview", "--mode", "-m",
                              help="Quality mode: preview | production"),
    output_dir: Path = typer.Option(OUTPUT_DIR_DEFAULT, "--output-dir", "-o",
                                    help="Directory to write output files"),
    use_tts: bool = typer.Option(False, "--tts", help="Generate TTS audio from prompt"),
    audio: Optional[Path] = typer.Option(None, "--audio", help="Path to audio file to mux in"),
) -> None:
    """
    LTX-2 Video Generator — Apple Silicon MPS backend.
    Generates a video from a text prompt with optional audio.
    """

    # --- Validate inputs ---
    fmt = fmt.lower()
    mode = mode.lower()

    if fmt not in FORMAT_PRESETS:
        rprint(f"[red]Unknown format '{fmt}'. Choose: linkedin, tiktok, instagram[/red]")
        raise typer.Exit(1)
    if mode not in ("preview", "production"):
        rprint(f"[red]Unknown mode '{mode}'. Choose: preview or production[/red]")
        raise typer.Exit(1)
    if audio and not audio.exists():
        rprint(f"[red]Audio file not found: {audio}[/red]")
        raise typer.Exit(1)

    device = _get_device()
    width, height = _resolve_dims(fmt, mode)
    num_frames = int(duration * fps)
    num_inference_steps = 10 if mode == "preview" else 25
    preset = FORMAT_PRESETS[fmt]

    # --- Startup panel ---
    rprint(Panel.fit(
        f"[bold]LTX-2 Video Generator[/bold]\n\n"
        f"  Device     : [cyan]{device}[/cyan]\n"
        f"  Format     : [cyan]{fmt}[/cyan]  ({preset['ratio']})\n"
        f"  Resolution : [cyan]{width}x{height}[/cyan]\n"
        f"  Mode       : [cyan]{mode}[/cyan]  ({num_inference_steps} steps)\n"
        f"  Duration   : [cyan]{duration}s[/cyan]  @ {fps} fps → {num_frames} frames\n"
        f"  Prompt     : [dim]{prompt[:80]}{'…' if len(prompt) > 80 else ''}[/dim]",
        title="[bold green]LTX-2 on Apple Silicon[/bold green]",
        border_style="green",
    ))

    # --- Output dir setup ---
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    job_id = str(uuid.uuid4())
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    base_name = f"{ts}_{fmt}_{mode}_{job_id[:8]}"

    # --- Cache check ---
    cache_key = _cache_key(prompt, width, height, num_frames, num_inference_steps)
    frames_tensor = _load_from_cache(cache_key)

    if frames_tensor is None:
        # --- Load pipeline ---
        try:
            pipe = _load_pipeline(device)
        except ImportError as exc:
            rprint(f"[red]Failed to import pipeline: {exc}[/red]")
            rprint("[yellow]Run: pip install diffusers>=0.30.0[/yellow]")
            raise typer.Exit(1)

        # --- Run inference ---
        console.log("[cyan]Running inference…[/cyan]")
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Generating video frames…", total=None)

                result = pipe(
                    prompt=prompt,
                    width=width,
                    height=height,
                    num_frames=num_frames,
                    num_inference_steps=num_inference_steps,
                )
                progress.update(task, description="Done.")

        except RuntimeError as exc:
            err = str(exc).lower()
            if "out of memory" in err or "mps" in err:
                rprint(Panel(
                    "[bold red]MPS Out of Memory[/bold red]\n\n"
                    "Suggestions:\n"
                    "  • Use [bold]--mode preview[/bold] to halve the resolution\n"
                    "  • Use a shorter [bold]--duration[/bold] (e.g. 3.0)\n"
                    "  • Reduce [bold]--fps[/bold] (e.g. 12)\n"
                    "  • Quit other GPU-intensive applications\n\n"
                    f"[dim]Original error: {exc}[/dim]",
                    title="Memory Error",
                    border_style="red",
                ))
                raise typer.Exit(1)
            raise

        # result.frames is a list of lists of PIL images: [[frame0, frame1, …]]
        # Depending on diffusers version it may be result.frames[0] or result.frames
        raw_frames = result.frames
        if isinstance(raw_frames[0], list):
            pil_frames = raw_frames[0]
        elif isinstance(raw_frames[0], Image.Image):
            pil_frames = list(raw_frames)
        else:
            # Tensor path
            frames_tensor = raw_frames
            pil_frames = None

        if pil_frames is None and frames_tensor is not None:
            pil_frames = _frames_tensor_to_pil(frames_tensor)

        # Build tensor for caching: (T, H, W, C) uint8
        arr = np.stack([np.array(f) for f in pil_frames], axis=0)  # (T, H, W, C)
        frames_tensor = torch.from_numpy(arr)
        _save_to_cache(cache_key, frames_tensor)

    else:
        # Reconstruct PIL frames from cached tensor
        pil_frames = _frames_tensor_to_pil(frames_tensor)

    console.log(f"[green]Got {len(pil_frames)} frames ({pil_frames[0].size})[/green]")

    # --- Save outputs ---
    video_path = output_dir / f"{base_name}.mp4"
    thumb_path = output_dir / f"{base_name}_thumb.jpg"
    gif_path = output_dir / f"{base_name}_preview.gif"

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        t1 = p.add_task("Encoding MP4…", total=None)
        _save_mp4(pil_frames, video_path, fps)
        p.update(t1, description="[green]MP4 saved[/green]")

        t2 = p.add_task("Saving thumbnail…", total=None)
        _save_thumbnail(pil_frames, thumb_path)
        p.update(t2, description="[green]Thumbnail saved[/green]")

        t3 = p.add_task("Creating preview GIF…", total=None)
        _save_gif(pil_frames, gif_path, fps, duration)
        p.update(t3, description="[green]GIF saved[/green]")

    output_files = {
        "video": str(video_path.resolve()),
        "thumbnail": str(thumb_path.resolve()),
        "gif": str(gif_path.resolve()),
    }

    # --- Audio handling ---
    final_audio_path: Optional[Path] = None

    if use_tts:
        tts_audio_path = output_dir / f"{base_name}_tts.wav"
        try:
            _generate_tts_audio(prompt, tts_audio_path)
            final_audio_path = tts_audio_path
            output_files["tts_audio"] = str(tts_audio_path.resolve())
        except Exception as exc:
            console.log(f"[yellow]TTS generation failed (skipping): {exc}[/yellow]")

    if audio:
        final_audio_path = audio

    if final_audio_path:
        muxed_path = output_dir / f"{base_name}_with_audio.mp4"
        try:
            _mux_audio(video_path, final_audio_path, muxed_path)
            output_files["video_with_audio"] = str(muxed_path.resolve())
        except Exception as exc:
            console.log(f"[yellow]Audio mux failed (skipping): {exc}[/yellow]")

    # --- Metadata ---
    metadata = {
        "job_id": job_id,
        "prompt": prompt,
        "format": fmt,
        "resolution": f"{width}x{height}",
        "fps": fps,
        "duration": duration,
        "mode": mode,
        "num_frames": num_frames,
        "num_inference_steps": num_inference_steps,
        "cache_key": cache_key,
        "device": str(device),
        "output_files": output_files,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    meta_path = output_dir / f"{base_name}_meta.json"
    meta_path.write_text(json.dumps(metadata, indent=2))
    output_files["metadata"] = str(meta_path.resolve())

    # --- Success panel ---
    file_lines = "\n".join(f"  {k:18s}: {v}" for k, v in output_files.items())
    rprint(Panel(
        f"[bold green]Generation complete![/bold green]\n\n"
        f"[bold]Job ID:[/bold] {job_id}\n\n"
        f"[bold]Output files:[/bold]\n{file_lines}",
        title="Done",
        border_style="green",
    ))


if __name__ == "__main__":
    app()
