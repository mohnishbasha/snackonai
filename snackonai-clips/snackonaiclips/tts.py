"""
Text-to-speech (TTS) module.

Supported providers:
  - gTTS    : free, no API key required, English only by default
  - ElevenLabs : premium quality, requires API key
  - disabled   : skip audio generation entirely
"""

import logging
import os
import tempfile
from pathlib import Path

from .config import TTSConfig, TTSProvider, get_config
from .summarizer import Summary

logger = logging.getLogger(__name__)


class TTSError(Exception):
    """Raised when TTS generation fails."""


def _build_narration_script(summary: Summary) -> str:
    """Assemble a narration script from Summary for TTS."""
    bullets_text = ". ".join(summary.bullets)
    return (
        f"{summary.headline}. "
        f"{summary.summary} "
        f"Here are the key takeaways: {bullets_text}."
    )


def _generate_gtts(text: str, cfg: TTSConfig, output_path: str) -> str:
    """Generate audio using gTTS."""
    try:
        from gtts import gTTS
    except ImportError as exc:
        raise TTSError(
            "gTTS not installed. Run: pip install gtts"
        ) from exc

    tts = gTTS(text=text, lang=cfg.gtts_lang, slow=cfg.gtts_slow)
    tts.save(output_path)
    logger.info("gTTS audio saved to: %s", output_path)
    return output_path


def _generate_elevenlabs(text: str, cfg: TTSConfig, output_path: str) -> str:
    """Generate audio using ElevenLabs API."""
    try:
        from elevenlabs import ElevenLabs, Voice, VoiceSettings
    except ImportError as exc:
        raise TTSError(
            "elevenlabs not installed. Run: pip install elevenlabs"
        ) from exc

    if not cfg.elevenlabs_api_key:
        raise TTSError("ELEVENLABS_API_KEY environment variable is not set.")

    client = ElevenLabs(api_key=cfg.elevenlabs_api_key)
    audio = client.generate(
        text=text,
        voice=Voice(
            voice_id=cfg.elevenlabs_voice_id,
            settings=VoiceSettings(stability=0.5, similarity_boost=0.75),
        ),
        model="eleven_monolingual_v1",
    )

    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)

    logger.info("ElevenLabs audio saved to: %s", output_path)
    return output_path


def generate_voiceover(
    summary: Summary,
    output_path: str | None = None,
    cfg: TTSConfig | None = None,
) -> str | None:
    """
    Generate a voiceover MP3 for the given summary.

    Returns the path to the generated audio file, or None if TTS is disabled.
    Raises TTSError on failure.
    """
    if cfg is None:
        cfg = get_config().tts

    if cfg.provider == TTSProvider.DISABLED:
        logger.info("TTS disabled — skipping voiceover generation")
        return None

    script = _build_narration_script(summary)
    logger.debug("TTS script (%d chars): %s", len(script), script[:120])

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        output_path = tmp.name
        tmp.close()

    if cfg.provider == TTSProvider.GTTS:
        return _generate_gtts(script, cfg, output_path)
    elif cfg.provider == TTSProvider.ELEVENLABS:
        return _generate_elevenlabs(script, cfg, output_path)
    else:
        raise TTSError(f"Unknown TTS provider: {cfg.provider}")


def get_audio_duration(audio_path: str) -> float:
    """Return audio duration in seconds using mutagen or moviepy."""
    try:
        from mutagen.mp3 import MP3
        audio = MP3(audio_path)
        return float(audio.info.length)
    except ImportError:
        pass

    try:
        from moviepy.audio.io.AudioFileClip import AudioFileClip
        with AudioFileClip(audio_path) as clip:
            return clip.duration
    except Exception:
        pass

    # Default fallback estimate: 130 wpm average reading speed
    logger.warning("Cannot determine audio duration — estimating from file size")
    size = os.path.getsize(audio_path)
    # ~16KB/s for 128kbps MP3
    return size / 16_000
