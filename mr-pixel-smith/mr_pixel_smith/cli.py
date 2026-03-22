#!/usr/bin/env python3
"""
AI Image Generator using Ollama with Pillow watermarking.
Requires: ollama, pillow
  pip install pillow

Usage:
  mr-pixel-smith -p "Your prompt here" [-w 1200] [-H 628] [-o output.png]
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
DEFAULT_WIDTH  = 1200
DEFAULT_HEIGHT = 628
MODEL          = "x/z-image-turbo"
WATERMARK_TEXT = "www.snackonai.com"
OUTPUT_FILE    = "output.png"
MAX_PROMPT_LEN = 2000
MIN_DIM        = 64
MAX_DIM        = 4096


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_ollama() -> None:
    """Verify Ollama is installed and its daemon is reachable."""
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


def validate_prompt(prompt: str) -> str:
    """Validate and return the prompt, or exit with an error."""
    prompt = prompt.strip()
    if not prompt:
        print("Error: Prompt cannot be empty.", file=sys.stderr)
        sys.exit(1)
    if len(prompt) > MAX_PROMPT_LEN:
        print(f"Error: Prompt is too long ({len(prompt)} chars, max {MAX_PROMPT_LEN}).", file=sys.stderr)
        sys.exit(1)
    return prompt


def validate_dimension(value: int, name: str) -> int:
    """Validate image dimension is within the allowed range."""
    if not (MIN_DIM <= value <= MAX_DIM):
        print(f"Error: {name} must be between {MIN_DIM} and {MAX_DIM} (got {value}).", file=sys.stderr)
        sys.exit(1)
    return value


def get_int_input(prompt_text: str, default: int) -> int:
    """Prompt user for an integer, falling back to default on empty input."""
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


def add_watermark(image_bytes: bytes, text: str) -> bytes:
    """
    Overlay a semi-transparent diagonal watermark onto the image.
    Returns the modified image as PNG bytes.
    """
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    except Exception as e:
        raise ValueError(f"Could not open image data: {e}") from e

    w, h = img.size

    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw    = ImageDraw.Draw(overlay)

    font_size = max(20, int(min(w, h) * 0.025))
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

    # Light blue: (173, 216, 230)
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


OLLAMA_API = "http://localhost:11434"


def _generate_via_cli(prompt, width, height):
    """Try CLI approach: ollama run → look for 'Image saved to:' in output."""
    result_container: dict = {}
    error_container: dict = {}

    def _run():
        try:
            result_container["result"] = subprocess.run(
                ["ollama", "run", MODEL, prompt, "--width", str(width), "--height", str(height)],
                capture_output=True, text=True, timeout=300
            )
        except subprocess.TimeoutExpired:
            error_container["type"] = "timeout"
        except OSError as e:
            error_container["type"] = "os"
            error_container["msg"] = str(e)

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


def _generate_via_api(prompt, width, height):
    """Fallback: Ollama HTTP API → base64 response."""
    result_container: dict = {}
    error_container: dict = {}

    def _run():
        try:
            payload = json.dumps({
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"width": width, "height": height},
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

    # Try known keys where ollama may return image data
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


def make_output_filename(prompt: str, width: int, height: int) -> str:
    """Generate a descriptive filename from prompt and dimensions."""
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower().strip())[:40].strip("-")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{slug}-{width}x{height}-{ts}.png"


def generate_image(prompt, width, height):
    """Try CLI first, fall back to HTTP API."""
    print(f"\nGenerating image ({width}×{height}) — this may take a moment…")

    image_bytes = _generate_via_cli(prompt, width, height)
    if image_bytes:
        return image_bytes

    print("  CLI produced no output, trying HTTP API…")
    image_bytes = _generate_via_api(prompt, width, height)
    if image_bytes:
        return image_bytes

    print("Error: Both CLI and HTTP API failed to produce an image.", file=sys.stderr)
    print(f"  Ensure the model is pulled: ollama pull {MODEL}", file=sys.stderr)
    sys.exit(1)


# ── Argument Parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Image Generator powered by Ollama + Pillow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  mr-pixel-smith -p "A futuristic city at sunset"\n'
            '  mr-pixel-smith -p "Abstract art" -w 800 -H 600 -o abstract.png\n'
            "  mr-pixel-smith          # interactive mode"
        ),
    )
    parser.add_argument("-p", "--prompt", metavar="PROMPT",
                        help=f"Image prompt (max {MAX_PROMPT_LEN} characters)")
    parser.add_argument("-w", "--width", type=int, default=DEFAULT_WIDTH, metavar="PX",
                        help=f"Image width in pixels (default: {DEFAULT_WIDTH}, range: {MIN_DIM}–{MAX_DIM})")
    parser.add_argument("-H", "--height", type=int, default=DEFAULT_HEIGHT, metavar="PX",
                        help=f"Image height in pixels (default: {DEFAULT_HEIGHT}, range: {MIN_DIM}–{MAX_DIM})")
    parser.add_argument("-o", "--output", default=OUTPUT_FILE, metavar="FILE",
                        help=f"Output PNG filename (default: {OUTPUT_FILE})")
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    print("═" * 95)
    print("  Mr. Pixel Smith: AI Image Generator  │  Powered by Ollama + Pillow")
    print("═" * 95)

    # 1. Preflight
    print("\nChecking Ollama…")
    check_ollama()
    print("  ✓ Ollama is running")

    # 2. Collect & validate inputs
    print()

    if args.prompt:
        prompt = validate_prompt(args.prompt)
    else:
        raw = input("Enter your image prompt: ")
        prompt = validate_prompt(raw)

    width  = validate_dimension(args.width, "Width")
    height = validate_dimension(args.height, "Height")

    if not args.prompt:
        width  = get_int_input("Width  (px)", width)
        height = get_int_input("Height (px)", height)

    if args.output and args.output.strip() and args.output.strip() != OUTPUT_FILE:
        output_path = args.output.strip()
        if not output_path.lower().endswith(".png"):
            output_path += ".png"
    else:
        output_path = make_output_filename(prompt, width, height)

    # 3. Generate
    image_bytes = generate_image(prompt, width, height)
    print("  ✓ Image received from Ollama")

    # 4. Watermark
    print(f"Applying watermark: '{WATERMARK_TEXT}'…")
    try:
        watermarked_bytes = add_watermark(image_bytes, WATERMARK_TEXT)
        print("  ✓ Watermark applied")
    except Exception as e:
        print(f"Warning: Watermarking failed ({e}). Saving original image.", file=sys.stderr)
        watermarked_bytes = image_bytes

    # 5. Save
    try:
        Path(output_path).write_bytes(watermarked_bytes)
        print(f"\n✓ Image saved → {output_path}")
    except OSError as e:
        print(f"Error saving file '{output_path}': {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
