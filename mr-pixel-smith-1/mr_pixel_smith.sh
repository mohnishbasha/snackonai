#!/bin/bash
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_WIDTH=1200
DEFAULT_HEIGHT=628
MODEL="x/z-image-turbo"

# ── Usage ─────────────────────────────────────────────────────────────────────
usage() {
    echo "Usage: $0 -p <prompt> [-w <width>] [-h <height>] [-o <output.png>]"
    echo ""
    echo "  -p  Image prompt (required, max 2000 chars)"
    echo "  -w  Width in pixels  (default: $DEFAULT_WIDTH, range: 64–4096)"
    echo "  -h  Height in pixels (default: $DEFAULT_HEIGHT, range: 64–4096)"
    echo "  -o  Output filename  (default: output.png)"
    echo ""
    echo "Example:"
    echo "  $0 -p \"A futuristic city at sunset\" -w 1200 -h 628 -o city.png"
    exit 1
}

# ── Argument Parsing ───────────────────────────────────────────────────────────
PROMPT=""
WIDTH=$DEFAULT_WIDTH
HEIGHT=$DEFAULT_HEIGHT
OUTPUT="output.png"

while getopts ":p:w:h:o:" opt; do
    case $opt in
        p) PROMPT="$OPTARG" ;;
        w) WIDTH="$OPTARG" ;;
        h) HEIGHT="$OPTARG" ;;
        o) OUTPUT="$OPTARG" ;;
        :) echo "Error: Option -$OPTARG requires an argument." >&2; usage ;;
        \?) echo "Error: Unknown option -$OPTARG." >&2; usage ;;
    esac
done

# ── Validation ────────────────────────────────────────────────────────────────
if [[ -z "$PROMPT" ]]; then
    echo "Error: -p <prompt> is required." >&2
    usage
fi

if [[ ${#PROMPT} -gt 2000 ]]; then
    echo "Error: Prompt exceeds 2000 characters (got ${#PROMPT})." >&2
    exit 1
fi

if ! [[ "$WIDTH" =~ ^[0-9]+$ ]] || (( WIDTH < 64 || WIDTH > 4096 )); then
    echo "Error: Width must be an integer between 64 and 4096 (got '$WIDTH')." >&2
    exit 1
fi

if ! [[ "$HEIGHT" =~ ^[0-9]+$ ]] || (( HEIGHT < 64 || HEIGHT > 4096 )); then
    echo "Error: Height must be an integer between 64 and 4096 (got '$HEIGHT')." >&2
    exit 1
fi

if [[ "$OUTPUT" != *.png ]]; then
    OUTPUT="${OUTPUT}.png"
fi

# ── Preflight: Ollama ──────────────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    echo "Error: 'ollama' not found. Install it from https://ollama.com" >&2
    exit 1
fi

if ! ollama list &>/dev/null; then
    echo "Error: Ollama is not responding. Start it with: ollama serve" >&2
    exit 1
fi

# ── Generate ──────────────────────────────────────────────────────────────────
echo "Generating image (${WIDTH}×${HEIGHT})…"
echo "Prompt: $PROMPT"
echo ""

if ! ollama run "$MODEL" "$PROMPT" --width "$WIDTH" --height "$HEIGHT" > "$OUTPUT"; then
    echo "Error: Image generation failed." >&2
    rm -f "$OUTPUT"
    exit 1
fi

if [[ ! -s "$OUTPUT" ]]; then
    echo "Error: Output file is empty or was not created." >&2
    rm -f "$OUTPUT"
    exit 1
fi

echo "Image saved → $OUTPUT"
