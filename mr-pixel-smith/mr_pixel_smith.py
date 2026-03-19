#!/usr/bin/env python3
"""
AI Image Generator using Ollama with Pillow watermarking.
Requires: ollama, pillow
  pip install pillow

Usage:
  python mr-pixel-smith.py -p "Your prompt here" [-w 1200] [-h 628] [-o output.png]
  python mr-pixel-smith.py          # interactive mode
"""

import argparse
import subprocess
import sys
import shutil
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


def generate_image(prompt: str, width: int, height: int) -> bytes:
    """Call Ollama CLI and return raw PNG bytes."""
    print(f"\nGenerating image ({width}×{height}) — this may take a moment…")
    try:
        result = subprocess.run(
            ["ollama", "run", MODEL, prompt, "--width", str(width), "--height", str(height)],
            capture_output=True, text=True, timeout=300
        )
    except subprocess.TimeoutExpired:
        print("Error: Image generation timed out after 5 minutes.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error running Ollama: {e}", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print("Error: Ollama returned a non-zero exit code.", file=sys.stderr)
        stderr_msg = result.stderr.strip()
        if stderr_msg:
            print(f"  stderr: {stderr_msg}", file=sys.stderr)
        sys.exit(1)

    if not result.stdout.strip():
        print("Error: Ollama returned empty output. Check that the model is pulled:", file=sys.stderr)
        print(f"  ollama pull {MODEL}", file=sys.stderr)
        sys.exit(1)

    # Ollama saves the image to disk and prints: "Image saved to: <path>"
    for line in result.stdout.splitlines():
        if line.startswith("Image saved to:"):
            saved_path = line.split(":", 1)[1].strip()
            try:
                image_bytes = Path(saved_path).read_bytes()
                Path(saved_path).unlink(missing_ok=True)
                return image_bytes
            except OSError as e:
                print(f"Error reading generated image '{saved_path}': {e}", file=sys.stderr)
                sys.exit(1)

    print("Error: Could not find 'Image saved to:' in Ollama output.", file=sys.stderr)
    print(f"  Raw output (first 300 chars): {result.stdout[:300]}", file=sys.stderr)
    sys.exit(1)


# ── Argument Parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Image Generator powered by Ollama + Pillow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python mr-pixel-smith.py -p "A futuristic city at sunset"\n'
            '  python mr-pixel-smith.py -p "Abstract art" -w 800 -h 600 -o abstract.png\n'
            "  python mr-pixel-smith.py          # interactive mode"
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

    print("═" * 55)
    print("  AI Image Generator  │  Powered by Ollama + Pillow")
    print("═" * 55)

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

    # In interactive mode, allow overriding width/height interactively
    if not args.prompt:
        width  = get_int_input("Width  (px)", width)
        height = get_int_input("Height (px)", height)

    output_path = args.output.strip()
    if not output_path:
        output_path = OUTPUT_FILE
    if not output_path.lower().endswith(".png"):
        output_path += ".png"

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
