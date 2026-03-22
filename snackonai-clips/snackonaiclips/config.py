"""
Configuration management for SnackOnAIClips.

Loads settings from environment variables and provides typed defaults.
"""

import os
from dataclasses import dataclass, field
from enum import Enum


class LLMProvider(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"


class TTSProvider(str, Enum):
    GTTS = "gtts"
    ELEVENLABS = "elevenlabs"
    DISABLED = "disabled"


class VideoStyle(str, Enum):
    MINIMAL = "minimal"
    MODERN = "modern"
    CINEMATIC = "cinematic"


@dataclass
class LLMConfig:
    provider: LLMProvider = field(
        default_factory=lambda: LLMProvider(
            os.getenv("SNACKONAI_LLM_PROVIDER", LLMProvider.OPENAI)
        )
    )
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2")
    )
    max_retries: int = 3
    timeout: int = 30


@dataclass
class TTSConfig:
    provider: TTSProvider = field(
        default_factory=lambda: TTSProvider(
            os.getenv("SNACKONAI_TTS_PROVIDER", TTSProvider.GTTS)
        )
    )
    elevenlabs_api_key: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", "")
    )
    elevenlabs_voice_id: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_VOICE_ID", "Rachel")
    )
    gtts_lang: str = "en"
    gtts_slow: bool = False


@dataclass
class VideoConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    max_duration: int = 60  # seconds
    font_dir: str = field(
        default_factory=lambda: os.getenv("SNACKONAI_FONT_DIR", "")
    )
    background_music_path: str = field(
        default_factory=lambda: os.getenv("SNACKONAI_MUSIC_PATH", "")
    )
    music_volume: float = 0.08


@dataclass
class ExtractorConfig:
    request_timeout: int = 15
    max_retries: int = 3
    retry_backoff: float = 1.5
    user_agent: str = (
        "Mozilla/5.0 (compatible; SnackOnAIClips/1.0; +https://snackonai.com)"
    )


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    extractor: ExtractorConfig = field(default_factory=ExtractorConfig)
    log_level: str = field(
        default_factory=lambda: os.getenv("SNACKONAI_LOG_LEVEL", "INFO")
    )
    watermark: str = "SnackOnAI"


# Singleton instance
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Return the global config singleton."""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reset_config() -> None:
    """Reset config singleton (useful in tests)."""
    global _config
    _config = None
