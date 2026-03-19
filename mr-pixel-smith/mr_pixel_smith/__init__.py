"""mr-pixel-smith — AI image generator powered by Ollama + Pillow."""

__version__ = "0.1.0"

from .cli import (
    add_watermark,
    check_ollama,
    generate_image,
    validate_prompt,
    validate_dimension,
)

__all__ = [
    "__version__",
    "add_watermark",
    "check_ollama",
    "generate_image",
    "validate_prompt",
    "validate_dimension",
]
