#!/usr/bin/env python3
"""
SnackOnAIClips — Entry point script.

Can be run directly:
    python snackonaiclips.py --url <blog_url> [options]

Or installed as a CLI tool via pip and run as:
    snackonaiclips --url <blog_url> [options]
"""

from snackonaiclips.cli import main

if __name__ == "__main__":
    main()
