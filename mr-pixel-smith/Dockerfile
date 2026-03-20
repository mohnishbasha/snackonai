FROM python:3.11-slim

# NOTE: x/z-image-turbo uses Apple's MLX framework and only runs on macOS Apple Silicon.
# This container will build and start correctly, but image generation will fail on Linux.
# To generate images, run the app natively on macOS instead (see README).

# ── Layer 1: system packages ──────────────────────────────────────────────────
# curl + zstd are required by the Ollama installer; fonts-dejavu for watermark
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        zstd \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# ── Layer 2: Ollama CLI ───────────────────────────────────────────────────────
RUN curl -fsSL https://ollama.com/install.sh | sh

# ── Layer 3: Python build toolchain ──────────────────────────────────────────
RUN pip install --upgrade pip

# ── Layer 4: Python dependencies (cached until requirements change) ───────────
WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt ./
RUN pip install -r requirements.txt

# ── Layer 5: application source (most frequently changed) ────────────────────
COPY mr_pixel_smith/ ./mr_pixel_smith/
COPY mr_pixel_smith.py ./

# Create the mr-pixel-smith entry point so the CLI command works
RUN printf '#!/usr/bin/env python3\nfrom mr_pixel_smith.cli import main\nmain()\n' \
        > /usr/local/bin/mr-pixel-smith && \
    chmod +x /usr/local/bin/mr-pixel-smith

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Mount a host directory here to retrieve generated PNGs
VOLUME ["/app/output"]

ENTRYPOINT ["/entrypoint.sh"]
