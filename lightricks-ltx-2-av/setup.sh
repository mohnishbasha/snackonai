#!/usr/bin/env bash
# setup.sh — Environment bootstrap for LTX-2 Video Generator
# Tested on macOS 14+ with Apple Silicon (M4 / M4 Pro)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

# ---------------------------------------------------------------------------
# 1. Check Python version >= 3.10
# ---------------------------------------------------------------------------
check_python() {
    local python_bin
    python_bin="$(command -v python3 2>/dev/null || true)"

    if [[ -z "$python_bin" ]]; then
        echo "ERROR: python3 not found. Install it via Homebrew: brew install python@3.11"
        exit 1
    fi

    local version
    version="$("$python_bin" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    local major minor
    major="$(echo "$version" | cut -d. -f1)"
    minor="$(echo "$version" | cut -d. -f2)"

    if [[ "$major" -lt 3 ]] || { [[ "$major" -eq 3 ]] && [[ "$minor" -lt 10 ]]; }; then
        echo "ERROR: Python 3.10+ required, found $version"
        echo "Install a newer Python: brew install python@3.11"
        exit 1
    fi

    echo "✓ Python $version found at $python_bin"
    echo "$python_bin"
}

# ---------------------------------------------------------------------------
# 2. Check ffmpeg
# ---------------------------------------------------------------------------
check_ffmpeg() {
    if ! command -v ffmpeg &>/dev/null; then
        echo ""
        echo "WARNING: ffmpeg not found. Video encoding will fail."
        echo "Install it with: brew install ffmpeg"
        echo ""
    else
        echo "✓ ffmpeg found: $(command -v ffmpeg)"
    fi
}

# ---------------------------------------------------------------------------
# 3. Create virtualenv
# ---------------------------------------------------------------------------
create_venv() {
    local python_bin="$1"

    if [[ -d "$VENV_DIR" ]]; then
        echo "✓ Virtualenv already exists at $VENV_DIR"
    else
        echo "Creating virtualenv at $VENV_DIR …"
        "$python_bin" -m venv "$VENV_DIR"
        echo "✓ Virtualenv created"
    fi
}

# ---------------------------------------------------------------------------
# 4. Install requirements
# ---------------------------------------------------------------------------
install_deps() {
    local pip="$VENV_DIR/bin/pip"

    echo ""
    echo "Upgrading pip…"
    "$pip" install --upgrade pip --quiet

    echo "Installing requirements from $REQUIREMENTS …"
    echo "(This may take several minutes on first run)"
    "$pip" install -r "$REQUIREMENTS"

    echo ""
    echo "✓ Dependencies installed"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo "================================================"
    echo "  LTX-2 Video Generator — Environment Setup"
    echo "================================================"
    echo ""

    local python_bin
    python_bin="$(check_python | tail -n1)"

    check_ffmpeg
    create_venv "$python_bin"
    install_deps

    echo ""
    echo "================================================"
    echo "  Setup complete!"
    echo "================================================"
    echo ""
    echo "To activate the environment:"
    echo ""
    echo "    source $VENV_DIR/bin/activate"
    echo ""
    echo "To generate a video:"
    echo ""
    echo "    python generate.py --prompt \"A serene mountain lake at sunrise\""
    echo ""
    echo "For TikTok preview mode:"
    echo ""
    echo "    python generate.py --prompt \"...\" --format tiktok --mode preview"
    echo ""
    echo "For production LinkedIn with audio:"
    echo ""
    echo "    python generate.py --prompt \"...\" --format linkedin --mode production --duration 6"
    echo ""
    echo "See README.md for full usage and troubleshooting."
    echo ""
}

main "$@"
