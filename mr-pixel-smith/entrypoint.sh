#!/usr/bin/env bash
# Entrypoint for the mr-pixel-smith Docker container.
# Starts the Ollama daemon, waits for it to be ready, pulls the model if
# needed, then hands control to mr-pixel-smith (passes all CLI args through).
#
# NOTE: x/z-image-turbo requires Apple MLX and only works on macOS Apple Silicon.
# Image generation will fail inside Linux-based Docker containers.

set -euo pipefail

MODEL="x/z-image-turbo"

# ── Start Ollama daemon in the background ────────────────────────────────────
echo "Starting Ollama daemon…"
ollama serve &
OLLAMA_PID=$!

# ── Wait until the daemon is accepting connections ───────────────────────────
echo "Waiting for Ollama to be ready…"
for i in $(seq 1 30); do
    if ollama list >/dev/null 2>&1; then
        echo "  ✓ Ollama is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "Error: Ollama did not start within 30 seconds." >&2
        kill "$OLLAMA_PID" 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# ── Pull the model if it is not already cached ───────────────────────────────
if ! ollama list 2>/dev/null | grep -q "$MODEL"; then
    echo "Pulling model '$MODEL' (first-run only)…"
    ollama pull "$MODEL"
    echo "  ✓ Model ready"
fi

# ── Run the app, forwarding all arguments ────────────────────────────────────
exec mr-pixel-smith "$@"
