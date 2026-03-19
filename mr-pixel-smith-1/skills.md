# Skills — Mr. Pixel Smith

Reusable techniques and patterns used in this project.

## Image Generation via Ollama CLI

Call a local Ollama model from Python using `subprocess.run` and parse JSON output:

```python
result = subprocess.run(
    ["ollama", "run", MODEL, prompt, "--width", str(width), "--height", str(height)],
    capture_output=True, text=True, timeout=300
)
data = json.loads(result.stdout)
image_bytes = base64.b64decode(data["response"])
```

**Key points:**
- Always set a `timeout` to avoid hanging indefinitely.
- Check `returncode` and non-empty `stdout` before parsing.
- The `response` field contains base64-encoded PNG bytes.

## Pillow Watermarking

Overlay a tiled semi-transparent watermark on any image:

```python
img = Image.open(BytesIO(image_bytes)).convert("RGBA")
overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
draw = ImageDraw.Draw(overlay)
# draw.text(...) in a grid loop
result = Image.alpha_composite(img, overlay).convert("RGB")
```

**Key points:**
- Convert to `RGBA` before compositing; convert back to `RGB` before saving as PNG.
- Use `draw.textbbox()` (Pillow 8+) to measure text dimensions.
- Fall back to `ImageFont.load_default()` when system TTF fonts are unavailable.

## Robust Integer Input

Prompt the user for an integer with validation and a default:

```python
def get_int_input(prompt_text, default, min_val=64, max_val=4096):
    while True:
        raw = input(f"{prompt_text} [default: {default}]: ").strip()
        if raw == "":
            return default
        try:
            value = int(raw)
            if min_val <= value <= max_val:
                return value
            print(f"  Please enter a value between {min_val} and {max_val}.")
        except ValueError:
            print("  Invalid input — please enter a whole number.")
```

## Preflight Binary Check

Verify an external CLI tool is installed and responsive before using it:

```python
if not shutil.which("ollama"):
    sys.exit(1)
subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
```
