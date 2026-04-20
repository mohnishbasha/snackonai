#!/usr/bin/env python3
"""
AI Image Generator using Ollama (x/z-image-turbo, vision models)
and HuggingFace Diffusers (FLUX.1 Schnell) with Pillow watermarking.

Usage:
  mr-pixel-smith -p "Your prompt here" [-m flux1:schnell] [-w 1024] [-H 1024] [-o output.png]
  mr-pixel-smith -p "Your prompt" --review [--review-model moondream]
  mr-pixel-smith          # interactive mode
"""

import argparse
import base64
import json
import re
import subprocess
import sys
import shutil
import threading
import time
import itertools
import urllib.request
import urllib.error
from datetime import datetime
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: Pillow is not installed. Run: pip install pillow", file=sys.stderr)
    sys.exit(1)


# ── Constants / Defaults ──────────────────────────────────────────────────────
DEFAULT_WIDTH       = 1200
DEFAULT_HEIGHT      = 628
WATERMARK_TEXT      = "www.snackonai.com"
OUTPUT_FILE         = "output.png"
MAX_PROMPT_LEN      = 2000
MIN_DIM             = 64
MAX_DIM             = 4096
DEFAULT_REVIEW_MODEL = "moondream"

SUPPORTED_MODELS = {
    "1": ("flux1:schnell",       "FLUX.1 Schnell       (HuggingFace Diffusers, Apple MPS/CUDA/CPU — default)"),
    "2": ("x/z-image-turbo",    "x/z-image-turbo      (Ollama, supports custom width/height)"),
    "3": ("llama3.2-vision:11b", "Llama 3.2 Vision 11B (Ollama)"),
    "4": ("llava:13b",           "LLaVA 13B            (Ollama)"),
    "5": ("moondream",           "Moondream            (Ollama)"),
}
DEFAULT_MODEL = "flux1:schnell"

VISION_MODELS          = {"llama3.2-vision:11b", "llava:13b", "moondream"}
DIFFUSERS_MODELS       = {"flux1:schnell"}
DIMENSION_AWARE_MODELS = {"x/z-image-turbo"}

OLLAMA_API = "http://localhost:11434"


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_ollama() -> None:
    if not shutil.which("ollama"):
        print("Error: 'ollama' binary not found. Install it from https://ollama.com", file=sys.stderr)
        sys.exit(1)
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            print("Error: Ollama is installed but doesn't appear to be running.", file=sys.stderr)
            print("       Start it with: ollama serve", file=sys.stderr)
            if result.stderr.strip():
                print(f"       Details: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Error: Ollama is not responding (timeout). Is 'ollama serve' running?", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error checking Ollama status: {e}", file=sys.stderr)
        sys.exit(1)


def select_model_interactive() -> str:
    print("\nSelect model:")
    for key, (model_id, label) in SUPPORTED_MODELS.items():
        print(f"  [{key}] {label}")
    while True:
        raw = input("Choice [default: 1]: ").strip()
        if raw == "":
            return DEFAULT_MODEL
        if raw in SUPPORTED_MODELS:
            return SUPPORTED_MODELS[raw][0]
        print(f"  Invalid choice — enter 1–{len(SUPPORTED_MODELS)}.")


def validate_prompt(prompt: str) -> str:
    prompt = prompt.strip()
    if not prompt:
        print("Error: Prompt cannot be empty.", file=sys.stderr)
        sys.exit(1)
    if len(prompt) > MAX_PROMPT_LEN:
        print(f"Error: Prompt is too long ({len(prompt)} chars, max {MAX_PROMPT_LEN}).", file=sys.stderr)
        sys.exit(1)
    return prompt


def validate_dimension(value: int, name: str) -> int:
    if not (MIN_DIM <= value <= MAX_DIM):
        print(f"Error: {name} must be between {MIN_DIM} and {MAX_DIM} (got {value}).", file=sys.stderr)
        sys.exit(1)
    return value


def snap_to_multiple(value: int, multiple: int = 16) -> int:
    return ((value + multiple - 1) // multiple) * multiple


def get_int_input(prompt_text: str, default: int) -> int:
    while True:
        raw = input(f"{prompt_text} [default: {default}]: ").strip()
        if raw == "":
            return default
        try:
            value = int(raw)
            if not (MIN_DIM <= value <= MAX_DIM):
                print(f"  Please enter a value between {MIN_DIM} and {MAX_DIM}.")
                continue
            return value
        except ValueError:
            print("  Invalid input — please enter a whole number.")


# ── Watermark ─────────────────────────────────────────────────────────────────

def add_watermark(image_bytes: bytes, text: str) -> bytes:
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    except Exception as e:
        raise ValueError(f"Could not open image data: {e}") from e

    w, h    = img.size
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw    = ImageDraw.Draw(overlay)

    font_size      = max(20, int(min(w, h) * 0.025))
    bold_font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    font = ImageFont.load_default()
    for path in bold_font_paths:
        try:
            font = ImageFont.truetype(path, font_size)
            break
        except (IOError, OSError):
            continue

    LIGHT_BLUE_DIM    = (173, 216, 230, 60)
    LIGHT_BLUE_BRIGHT = (173, 216, 230, 220)

    bbox   = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    step_x = int(tw * 2.5)
    step_y = int(th * 4)
    for y in range(-h, h * 2, step_y):
        for x in range(-w, w * 2, step_x):
            draw.text((x, y), text, font=font, fill=LIGHT_BLUE_DIM)

    margin = 12
    cx = w - tw - margin
    cy = h - th - margin
    draw.rectangle([cx - 6, cy - 4, cx + tw + 6, cy + th + 4], fill=(0, 0, 0, 100))
    draw.text((cx, cy), text, font=font, fill=LIGHT_BLUE_BRIGHT)

    watermarked = Image.alpha_composite(img, overlay).convert("RGB")
    buf = BytesIO()
    watermarked.save(buf, format="PNG")
    return buf.getvalue()


# ── Diffusers path (FLUX.1 Schnell) ──────────────────────────────────────────

def _generate_via_diffusers(prompt: str, width: int, height: int) -> bytes:
    import os

    try:
        from diffusers import FluxPipeline
        import torch
    except ImportError:
        print(
            "Error: 'diffusers' or 'torch' not installed.\n"
            "  Run: pip install diffusers transformers accelerate torch",
            file=sys.stderr,
        )
        sys.exit(1)

    # Authenticate with HuggingFace if a token is available
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        try:
            from huggingface_hub import login
            login(token=hf_token, add_to_git_credential=False)
        except Exception:
            pass  # will fail below with a clear message if token is invalid

    width  = snap_to_multiple(width)
    height = snap_to_multiple(height)

    if torch.backends.mps.is_available():
        device = "mps"
        dtype  = torch.float16
    elif torch.cuda.is_available():
        device = "cuda"
        dtype  = torch.float16
    else:
        device = "cpu"
        dtype  = torch.float32

    print(f"  Device: {device}  |  dtype: {dtype}  |  size: {width}×{height}")
    print("  Loading FLUX.1-schnell pipeline (first run downloads ~24 GB)…")

    try:
        pipe = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-schnell",
            torch_dtype=dtype,
        )
    except Exception as e:
        err = str(e)
        if "GatedRepoError" in type(e).__name__ or "gated" in err.lower() or "401" in err:
            print(
                "\nError: FLUX.1-schnell is a gated model — authentication required.\n"
                "\n  Fix (one-time setup):\n"
                "  1. Accept the license at:\n"
                "     https://huggingface.co/black-forest-labs/FLUX.1-schnell\n"
                "  2. Log in locally:\n"
                "     huggingface-cli login\n"
                "     (paste your token from https://huggingface.co/settings/tokens)\n"
                "\n  Or set the HF_TOKEN environment variable:\n"
                "     export HF_TOKEN=hf_your_token_here",
                file=sys.stderr,
            )
        else:
            print(f"Error loading FLUX pipeline: {e}", file=sys.stderr)
        sys.exit(1)

    # On MPS (Apple Silicon), enable_model_cpu_offload moves model components
    # on/off the GPU one at a time, avoiding OOM when unified memory is tight.
    if device == "mps":
        pipe.enable_model_cpu_offload()
    else:
        pipe.to(device)

    result_container: dict = {}
    error_container:  dict = {}

    def _run():
        try:
            result_container["image"] = pipe(
                prompt,
                width=width,
                height=height,
                num_inference_steps=4,
                guidance_scale=0.0,
            ).images[0]
        except Exception as e:
            error_container["msg"] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
    while thread.is_alive():
        sys.stdout.write(f"\r  {next(spinner)} Generating image (FLUX.1 Schnell)…")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r  ✓ Done.                                      \n")
    sys.stdout.flush()
    thread.join()

    if error_container:
        print(f"Error during FLUX generation: {error_container['msg']}", file=sys.stderr)
        sys.exit(1)

    buf = BytesIO()
    result_container["image"].save(buf, format="PNG")
    return buf.getvalue()


# ── Ollama paths (CLI + HTTP API) ─────────────────────────────────────────────

def _generate_via_cli(prompt: str, width: int, height: int, model: str):
    result_container: dict = {}
    error_container:  dict = {}

    cmd = ["ollama", "run", model, prompt]
    if model in DIMENSION_AWARE_MODELS:
        cmd += ["--width", str(width), "--height", str(height)]

    def _run():
        try:
            result_container["result"] = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )
        except subprocess.TimeoutExpired:
            error_container["type"] = "timeout"
        except OSError as e:
            error_container["type"] = "os"
            error_container["msg"]  = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
    while thread.is_alive():
        sys.stdout.write(f"\r  {next(spinner)} Generating image (CLI)…")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r  ✓ Done.                          \n")
    sys.stdout.flush()
    thread.join()

    if error_container:
        return None

    result = result_container.get("result")
    if not result or result.returncode != 0:
        return None

    combined = result.stdout + "\n" + result.stderr
    for line in combined.splitlines():
        if line.startswith("Image saved to:"):
            saved_path = line.split(":", 1)[1].strip()
            try:
                image_bytes = Path(saved_path).read_bytes()
                Path(saved_path).unlink(missing_ok=True)
                return image_bytes
            except OSError:
                return None

    return None


def _generate_via_api(prompt: str, width: int, height: int, model: str):
    result_container: dict = {}
    error_container:  dict = {}

    options = {"width": width, "height": height} if model in DIMENSION_AWARE_MODELS else {}

    def _run():
        try:
            payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": options,
            }).encode()
            req = urllib.request.Request(
                f"{OLLAMA_API}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                result_container["body"] = resp.read().decode()
        except urllib.error.URLError as e:
            error_container["msg"] = str(e)
        except TimeoutError:
            error_container["timeout"] = True

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
    while thread.is_alive():
        sys.stdout.write(f"\r  {next(spinner)} Generating image (API)…")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r  ✓ Done.                          \n")
    sys.stdout.flush()
    thread.join()

    if error_container:
        return None

    try:
        data = json.loads(result_container.get("body", ""))
    except (json.JSONDecodeError, KeyError):
        return None

    for key in ("image", "response", "images"):
        val = data.get(key)
        if not val:
            continue
        if isinstance(val, list):
            val = val[0]
        try:
            return base64.b64decode(val)
        except Exception:
            pass

    return None


# ── Vision review ─────────────────────────────────────────────────────────────

def review_image(image_bytes: bytes, prompt: str, review_model: str) -> None:
    """Send the generated image to a vision model and print its critique."""
    print(f"\nReviewing image with {review_model}…")

    b64_image = base64.b64encode(image_bytes).decode()
    review_prompt = (
        f'This image was generated from the following prompt: "{prompt}". '
        "Please describe what you see, assess how well it matches the prompt, "
        "and suggest one concrete improvement."
    )

    result_container: dict = {}
    error_container:  dict = {}

    def _run():
        try:
            payload = json.dumps({
                "model": review_model,
                "prompt": review_prompt,
                "images": [b64_image],
                "stream": False,
            }).encode()
            req = urllib.request.Request(
                f"{OLLAMA_API}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result_container["body"] = resp.read().decode()
        except urllib.error.URLError as e:
            error_container["msg"] = str(e)
        except TimeoutError:
            error_container["timeout"] = True

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
    while thread.is_alive():
        sys.stdout.write(f"\r  {next(spinner)} Analyzing…")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r                    \r")
    sys.stdout.flush()
    thread.join()

    if error_container:
        print(f"  Warning: Review failed — {error_container.get('msg', 'timeout')}",
              file=sys.stderr)
        return

    try:
        data     = json.loads(result_container.get("body", ""))
        critique = data.get("response", "").strip()
    except (json.JSONDecodeError, KeyError):
        print("  Warning: Could not parse review response.", file=sys.stderr)
        return

    if critique:
        print("─" * 95)
        print(f"  Vision review ({review_model}):")
        print()
        for line in critique.splitlines():
            print(f"  {line}")
        print("─" * 95)
    else:
        print("  Warning: Vision model returned an empty response.", file=sys.stderr)


# ── Router ────────────────────────────────────────────────────────────────────

def generate_image(prompt: str, width: int, height: int, model: str) -> bytes:
    print(f"\nGenerating image with {model} ({width}×{height}) — this may take a moment…")

    if model in DIFFUSERS_MODELS:
        return _generate_via_diffusers(prompt, width, height)

    image_bytes = _generate_via_cli(prompt, width, height, model)
    if image_bytes:
        return image_bytes

    print("  CLI produced no output, trying HTTP API…")
    image_bytes = _generate_via_api(prompt, width, height, model)
    if image_bytes:
        return image_bytes

    print("Error: Both CLI and HTTP API failed to produce an image.", file=sys.stderr)
    print(f"  Ensure the model is pulled: ollama pull {model}", file=sys.stderr)
    sys.exit(1)


# ── Filename ──────────────────────────────────────────────────────────────────

def make_output_filename(prompt: str, width: int, height: int, model: str) -> str:
    slug       = re.sub(r"[^a-z0-9]+", "-", prompt.lower().strip())[:40].strip("-")
    model_slug = re.sub(r"[^a-z0-9]+", "-", model.lower())
    ts         = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{slug}-{model_slug}-{width}x{height}-{ts}.png"


# ── Argument Parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    model_choices = [m for m, _ in SUPPORTED_MODELS.values()]
    parser = argparse.ArgumentParser(
        description="AI Image Generator — FLUX.1 Schnell (Diffusers) + Ollama models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  mr-pixel-smith -p "A futuristic city at sunset"\n'
            '  mr-pixel-smith -p "Portrait" -m flux1:schnell --review\n'
            '  mr-pixel-smith -p "Portrait" -m flux1:schnell --review --review-model llava:13b\n'
            '  mr-pixel-smith -p "Abstract art" -m x/z-image-turbo -w 800 -H 600\n'
            "  mr-pixel-smith          # interactive mode"
        ),
    )
    parser.add_argument("-p", "--prompt", metavar="PROMPT",
                        help=f"Image prompt (max {MAX_PROMPT_LEN} characters)")
    parser.add_argument("-m", "--model", metavar="MODEL",
                        choices=model_choices, default=None,
                        help=f"Generation model (default: {DEFAULT_MODEL})")
    parser.add_argument("-w", "--width",  type=int, default=DEFAULT_WIDTH,  metavar="PX",
                        help=f"Width in pixels (default: {DEFAULT_WIDTH})")
    parser.add_argument("-H", "--height", type=int, default=DEFAULT_HEIGHT, metavar="PX",
                        help=f"Height in pixels (default: {DEFAULT_HEIGHT})")
    parser.add_argument("-o", "--output", default=OUTPUT_FILE, metavar="FILE",
                        help="Output PNG filename (default: auto-generated)")
    parser.add_argument("--review", action="store_true",
                        help="After generating, send image to a vision model for critique")
    parser.add_argument("--review-model", default=DEFAULT_REVIEW_MODEL, metavar="MODEL",
                        choices=list(VISION_MODELS),
                        help=f"Vision model used for --review (default: {DEFAULT_REVIEW_MODEL})")
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    print("═" * 95)
    print("  Mr. Pixel Smith: AI Image Generator  │  FLUX.1 Schnell · Ollama · Pillow")
    print("═" * 95)

    print()
    if args.prompt:
        prompt = validate_prompt(args.prompt)
    else:
        raw    = input("Enter your image prompt: ")
        prompt = validate_prompt(raw)

    # Model selection: CLI flag → interactive → default
    if args.model:
        model = args.model
    elif args.prompt:
        model = DEFAULT_MODEL
    else:
        model = select_model_interactive()

    # Ollama is needed for non-diffusers generation AND for --review
    needs_ollama = (model not in DIFFUSERS_MODELS) or args.review
    if needs_ollama:
        print("\nChecking Ollama…")
        check_ollama()
        print("  ✓ Ollama is running")

    width  = validate_dimension(args.width,  "Width")
    height = validate_dimension(args.height, "Height")

    if not args.prompt and model in DIMENSION_AWARE_MODELS:
        width  = get_int_input("Width  (px)", width)
        height = get_int_input("Height (px)", height)

    if args.output and args.output.strip() and args.output.strip() != OUTPUT_FILE:
        output_path = args.output.strip()
        if not output_path.lower().endswith(".png"):
            output_path += ".png"
    else:
        output_path = make_output_filename(prompt, width, height, model)

    print(f"\nModel: {model}")
    if args.review:
        print(f"Review: {args.review_model}")

    # Generate
    image_bytes = generate_image(prompt, width, height, model)
    print("  ✓ Image received")

    # Watermark
    print(f"Applying watermark: '{WATERMARK_TEXT}'…")
    try:
        watermarked_bytes = add_watermark(image_bytes, WATERMARK_TEXT)
        print("  ✓ Watermark applied")
    except Exception as e:
        print(f"Warning: Watermarking failed ({e}). Saving original image.", file=sys.stderr)
        watermarked_bytes = image_bytes

    # Save
    try:
        Path(output_path).write_bytes(watermarked_bytes)
        print(f"\n✓ Image saved → {output_path}")
    except OSError as e:
        print(f"Error saving file '{output_path}': {e}", file=sys.stderr)
        sys.exit(1)

    # Vision review (uses the pre-watermark bytes for a cleaner signal)
    if args.review:
        review_image(image_bytes, prompt, args.review_model)


if __name__ == "__main__":
    main()
