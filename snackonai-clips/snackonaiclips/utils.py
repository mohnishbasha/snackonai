"""
Shared utilities: logging setup, retry decorator, and helpers.
"""

import logging
import time
import functools
from typing import Callable, TypeVar, Any
from urllib.parse import urlparse

F = TypeVar("F", bound=Callable[..., Any])


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure structured logging for the application."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "charset_normalizer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger("snackonaiclips")


def retry(
    max_attempts: int = 3,
    backoff: float = 1.5,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries a function on specified exceptions with exponential backoff."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger("snackonaiclips.retry")
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        wait = backoff ** (attempt - 1)
                        logger.warning(
                            "Attempt %d/%d failed (%s). Retrying in %.1fs…",
                            attempt,
                            max_attempts,
                            exc,
                            wait,
                        )
                        time.sleep(wait)
                    else:
                        logger.error(
                            "All %d attempts failed. Last error: %s", max_attempts, exc
                        )
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


def is_valid_url(url: str) -> bool:
    """Return True if url has a valid scheme and netloc."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def truncate_text(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, appending ellipsis if needed."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def seconds_to_timestamp(seconds: float) -> str:
    """Convert float seconds to HH:MM:SS.mmm string."""
    ms = int((seconds % 1) * 1000)
    total_sec = int(seconds)
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(value, max_val))
