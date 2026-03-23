"""
Video generation module — produces 1080x1920 vertical videos optimized for LinkedIn.

Architecture:
  Each "slide" is a MoviePy ImageClip or CompositeVideoClip.
  Slides are concatenated with crossfade transitions.
  Optional voiceover audio is overlaid.
  Optional background music is mixed at low volume.

Style presets:
  minimal   — dark gradient, clean white text
  modern    — vibrant gradient, bold headline, accent colours
  cinematic — dark overlay on a blurred-color background, film-grain texture
"""

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from .config import VideoConfig, VideoStyle, get_config
from .summarizer import Summary
from .utils import clamp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Style palettes
# ---------------------------------------------------------------------------

@dataclass
class StylePalette:
    bg_top: tuple[int, int, int]
    bg_bottom: tuple[int, int, int]
    headline_color: str
    body_color: str
    accent_color: str
    watermark_color: str
    font_size_headline: int
    font_size_body: int
    font_size_bullet: int


STYLES: dict[VideoStyle, StylePalette] = {
    VideoStyle.MINIMAL: StylePalette(
        bg_top=(15, 15, 20),
        bg_bottom=(30, 30, 40),
        headline_color="white",
        body_color="#CCCCCC",
        accent_color="#4FC3F7",
        watermark_color="#555555",
        font_size_headline=72,
        font_size_body=48,
        font_size_bullet=44,
    ),
    VideoStyle.MODERN: StylePalette(
        bg_top=(13, 13, 26),
        bg_bottom=(26, 0, 51),
        headline_color="#FFFFFF",
        body_color="#E0E0FF",
        accent_color="#B388FF",
        watermark_color="#7E57C2",
        font_size_headline=76,
        font_size_body=50,
        font_size_bullet=46,
    ),
    VideoStyle.CINEMATIC: StylePalette(
        bg_top=(5, 5, 8),
        bg_bottom=(18, 12, 8),
        headline_color="#F5F5DC",
        body_color="#D4C5A9",
        accent_color="#FFB300",
        watermark_color="#5D4037",
        font_size_headline=70,
        font_size_body=46,
        font_size_bullet=42,
    ),
}


# ---------------------------------------------------------------------------
# Gradient background
# ---------------------------------------------------------------------------

def _make_gradient(
    width: int,
    height: int,
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
) -> np.ndarray:
    """Create a vertical linear gradient as an RGB numpy array."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        t = y / height
        for c in range(3):
            frame[y, :, c] = int(top_color[c] * (1 - t) + bottom_color[c] * t)
    return frame


# ---------------------------------------------------------------------------
# Text wrapping helpers
# ---------------------------------------------------------------------------

def _wrap_text(text: str, max_chars_per_line: int = 30) -> str:
    """Naive word-wrap for MoviePy TextClip."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars_per_line:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ImageMagick + font detection  (cross-platform: macOS & Ubuntu)
# ---------------------------------------------------------------------------

import platform as _platform
import shutil as _shutil


def _check_linux_imagemagick_policy() -> None:
    """
    Detect Ubuntu's restrictive ImageMagick policy.xml and raise a clear error.

    Ubuntu ships ImageMagick with a security policy that blocks writing PNG files
    from temporary paths — exactly what MoviePy's TextClip does internally.
    The symptom is an OSError that looks identical to a missing font.
    We detect the restriction early and surface the exact fix command.
    """
    import glob

    for policy_path in glob.glob("/etc/ImageMagick-*/policy.xml"):
        try:
            content = Path(policy_path).read_text()
        except OSError:
            continue

        blocked = (
            'rights="none" pattern="PNG"' in content
            or 'rights="none" pattern="@*"' in content
        )
        if not blocked:
            continue

        # Build the sed command that fixes the specific restriction found
        if 'rights="none" pattern="PNG"' in content:
            sed_expr = r's/rights="none" pattern="PNG"/rights="read|write" pattern="PNG"/'
        else:
            sed_expr = r's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/'

        raise RuntimeError(
            f"ImageMagick's security policy blocks PNG writing (required by MoviePy TextClip).\n\n"
            f"Fix it with:\n"
            f"  sudo sed -i '{sed_expr}' {policy_path}\n\n"
            f"Then re-run the command."
        )


def _configure_imagemagick() -> None:
    """
    Configure MoviePy's ImageMagick binary for the current platform.

    macOS (Homebrew IMv7):
        `convert` is deprecated — set binary to `magick`.

    Ubuntu (IMv6, default apt package):
        `convert` still works — no binary change needed.
        But check for the restrictive policy.xml that blocks TextClip.

    Ubuntu (IMv7, manually installed):
        Same as macOS — set binary to `magick`, check policy.

    Windows:
        ImageMagick installer registers `magick` — set binary if found.
    """
    from moviepy.config import change_settings

    system = _platform.system()  # "Darwin" | "Linux" | "Windows"

    if system in ("Darwin", "Windows"):
        # IMv7 uses `magick`; prefer it to avoid the deprecation warning from `convert`
        if _shutil.which("magick"):
            change_settings({"IMAGEMAGICK_BINARY": "magick"})
            logger.debug("ImageMagick binary → 'magick' (%s IMv7)", system)

    elif system == "Linux":
        if _shutil.which("magick") and not _shutil.which("convert"):
            # IMv7 only — use `magick`
            change_settings({"IMAGEMAGICK_BINARY": "magick"})
            logger.debug("ImageMagick binary → 'magick' (Linux IMv7)")
        elif _shutil.which("magick"):
            # Both present — prefer `magick` to silence the deprecation warning
            change_settings({"IMAGEMAGICK_BINARY": "magick"})
            logger.debug("ImageMagick binary → 'magick' (Linux, both present)")
        # else: IMv6 only → keep MoviePy's default 'convert'

        # Always check the policy on Linux — fails fast with a clear fix command
        _check_linux_imagemagick_policy()


# ---------------------------------------------------------------------------
# Font detection — platform-aware, cached
# ---------------------------------------------------------------------------

# Bold font candidates — checked in priority order
_BOLD_FONT_CANDIDATES = [
    # macOS: Homebrew DejaVu (arm64 and x86)
    "/opt/homebrew/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/local/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    # macOS: system fonts
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    # Ubuntu/Debian: fonts-dejavu-core (most common)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    # Ubuntu/Debian: fonts-liberation (often pre-installed)
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
    # Ubuntu/Debian: fonts-freefont-ttf
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    # Ubuntu/Debian: Ubuntu font family
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    # Generic Linux fallback
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]

_REGULAR_FONT_CANDIDATES = [
    # macOS: Homebrew DejaVu
    "/opt/homebrew/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/local/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    # macOS: system fonts
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    # Ubuntu/Debian: fonts-dejavu-core
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    # Ubuntu/Debian: fonts-liberation
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    # Ubuntu/Debian: fonts-freefont-ttf
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    # Ubuntu/Debian: Ubuntu font family
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    # Generic Linux fallback
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]


def _find_font(candidates: list[str]) -> str | None:
    """Return the first candidate path that exists on disk, or None."""
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _get_fonts() -> tuple[str | None, str | None]:
    """
    Return (bold_font, regular_font) as absolute .ttf paths.
    Returns None for either if no matching file is found (ImageMagick picks its own default).
    Result is cached after the first call.
    """
    if not hasattr(_get_fonts, "_cache"):
        bold = _find_font(_BOLD_FONT_CANDIDATES)
        regular = _find_font(_REGULAR_FONT_CANDIDATES)

        if bold:
            logger.debug("Bold font resolved: %s", bold)
        else:
            system = _platform.system()
            hint = {
                "Darwin": "brew install font-dejavu  # requires: brew tap homebrew/cask-fonts",
                "Linux": "sudo apt install fonts-dejavu-core",
                "Windows": "Install DejaVu fonts from https://dejavu-fonts.github.io",
            }.get(system, "Install DejaVu or Liberation fonts for your OS")
            logger.warning(
                "No bold font found — text will use ImageMagick's default. "
                "For best results: %s",
                hint,
            )

        _get_fonts._cache = (bold, regular)  # type: ignore[attr-defined]
    return _get_fonts._cache  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Slide builders
# ---------------------------------------------------------------------------

def _try_import_moviepy():
    """Import moviepy components and apply runtime fixes for IMv7."""
    try:
        from moviepy.editor import (
            ImageClip,
            TextClip,
            CompositeVideoClip,
            AudioFileClip,
            concatenate_videoclips,
            ColorClip,
        )
        _configure_imagemagick()
        return ImageClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips, ColorClip
    except ImportError as exc:
        raise ImportError(
            "moviepy is required for video generation.\n"
            "Install it with: pip install moviepy\n"
            "You also need ImageMagick for text rendering:\n"
            "  macOS:  brew install imagemagick\n"
            "  Ubuntu: apt install imagemagick"
        ) from exc


def _build_title_slide(
    summary: Summary,
    palette: StylePalette,
    cfg: VideoConfig,
    watermark: str,
    duration: float,
) -> "CompositeVideoClip":
    """Build the opening title slide."""
    (ImageClip, TextClip, CompositeVideoClip,
     AudioFileClip, concatenate_videoclips, ColorClip) = _try_import_moviepy()

    W, H = cfg.width, cfg.height
    bg_arr = _make_gradient(W, H, palette.bg_top, palette.bg_bottom)
    bg = ImageClip(bg_arr).set_duration(duration)

    layers: list = [bg]

    # Accent bar
    accent_bar = ColorClip(size=(W // 3, 8), color=_hex_to_rgb(palette.accent_color))
    accent_bar = accent_bar.set_position(("center", H // 4 - 20)).set_duration(duration)
    layers.append(accent_bar)

    # Headline
    wrapped = _wrap_text(summary.headline, max_chars_per_line=22)
    headline_clip = (
        TextClip(
            wrapped,
            fontsize=palette.font_size_headline,
            color=palette.headline_color,
            font=_get_fonts()[0],
            method="caption",
            size=(W - 120, None),
            align="center",
        )
        .set_position(("center", H // 4))
        .set_duration(duration)
    )
    layers.append(headline_clip)

    # Sub-label
    label = (
        TextClip(
            "AI Video Summary",
            fontsize=36,
            color=palette.accent_color,
            font=_get_fonts()[1],
            method="label",
        )
        .set_position(("center", H // 4 + headline_clip.h + 40))
        .set_duration(duration)
    )
    layers.append(label)

    # Watermark
    if watermark:
        wm = (
            TextClip(
                watermark,
                fontsize=32,
                color=palette.watermark_color,
                font=_get_fonts()[1],
                method="label",
            )
            .set_position((40, H - 80))
            .set_duration(duration)
        )
        layers.append(wm)

    return CompositeVideoClip(layers, size=(W, H))


def _build_summary_slide(
    summary: Summary,
    palette: StylePalette,
    cfg: VideoConfig,
    watermark: str,
    duration: float,
) -> "CompositeVideoClip":
    """Build the summary narration slide."""
    (ImageClip, TextClip, CompositeVideoClip,
     AudioFileClip, concatenate_videoclips, ColorClip) = _try_import_moviepy()

    W, H = cfg.width, cfg.height
    bg_arr = _make_gradient(W, H, palette.bg_bottom, palette.bg_top)
    bg = ImageClip(bg_arr).set_duration(duration)

    layers: list = [bg]

    section_label = (
        TextClip(
            "SUMMARY",
            fontsize=36,
            color=palette.accent_color,
            font=_get_fonts()[0],
            method="label",
        )
        .set_position((60, H // 6))
        .set_duration(duration)
    )
    layers.append(section_label)

    wrapped = _wrap_text(summary.summary, max_chars_per_line=28)
    body = (
        TextClip(
            wrapped,
            fontsize=palette.font_size_body,
            color=palette.body_color,
            font=_get_fonts()[1],
            method="caption",
            size=(W - 120, None),
            align="West",
        )
        .set_position((60, H // 6 + 80))
        .set_duration(duration)
    )
    layers.append(body)

    if watermark:
        wm = (
            TextClip(watermark, fontsize=32, color=palette.watermark_color,
                     font=_get_fonts()[1], method="label")
            .set_position((40, H - 80))
            .set_duration(duration)
        )
        layers.append(wm)

    return CompositeVideoClip(layers, size=(W, H))


def _build_bullet_slide(
    index: int,
    bullet: str,
    total: int,
    palette: StylePalette,
    cfg: VideoConfig,
    watermark: str,
    duration: float,
) -> "CompositeVideoClip":
    """Build a single bullet-point slide."""
    (ImageClip, TextClip, CompositeVideoClip,
     AudioFileClip, concatenate_videoclips, ColorClip) = _try_import_moviepy()

    W, H = cfg.width, cfg.height

    # Alternate gradient direction for visual variety
    if index % 2 == 0:
        top, bot = palette.bg_top, palette.bg_bottom
    else:
        top, bot = palette.bg_bottom, palette.bg_top

    bg_arr = _make_gradient(W, H, top, bot)
    bg = ImageClip(bg_arr).set_duration(duration)
    layers: list = [bg]

    # Step counter pill
    counter_text = f"{index + 1} / {total}"
    counter = (
        TextClip(counter_text, fontsize=34, color=palette.accent_color,
                 font=_get_fonts()[0], method="label")
        .set_position((60, H // 5))
        .set_duration(duration)
    )
    layers.append(counter)

    # Accent underline
    accent_bar = ColorClip(size=(80, 6), color=_hex_to_rgb(palette.accent_color))
    accent_bar = accent_bar.set_position((60, H // 5 + 50)).set_duration(duration)
    layers.append(accent_bar)

    # Bullet text
    wrapped = _wrap_text(bullet, max_chars_per_line=26)
    bullet_clip = (
        TextClip(
            wrapped,
            fontsize=palette.font_size_bullet,
            color=palette.headline_color,
            font=_get_fonts()[0],
            method="caption",
            size=(W - 120, None),
            align="West",
        )
        .set_position((60, H // 5 + 80))
        .set_duration(duration)
    )
    layers.append(bullet_clip)

    if watermark:
        wm = (
            TextClip(watermark, fontsize=32, color=palette.watermark_color,
                     font=_get_fonts()[1], method="label")
            .set_position((40, H - 80))
            .set_duration(duration)
        )
        layers.append(wm)

    return CompositeVideoClip(layers, size=(W, H))


def _build_outro_slide(
    palette: StylePalette,
    cfg: VideoConfig,
    watermark: str,
    duration: float,
) -> "CompositeVideoClip":
    """Build a closing CTA slide."""
    (ImageClip, TextClip, CompositeVideoClip,
     AudioFileClip, concatenate_videoclips, ColorClip) = _try_import_moviepy()

    W, H = cfg.width, cfg.height
    bg_arr = _make_gradient(W, H, palette.bg_top, palette.bg_bottom)
    bg = ImageClip(bg_arr).set_duration(duration)
    layers: list = [bg]

    cta = (
        TextClip(
            "Follow for more\nAI-powered insights",
            fontsize=60,
            color=palette.headline_color,
            font=_get_fonts()[0],
            method="caption",
            size=(W - 120, None),
            align="center",
        )
        .set_position("center")
        .set_duration(duration)
    )
    layers.append(cta)

    brand = (
        TextClip(
            watermark or "SnackOnAI",
            fontsize=42,
            color=palette.accent_color,
            font=_get_fonts()[0],
            method="label",
        )
        .set_position(("center", H * 2 // 3))
        .set_duration(duration)
    )
    layers.append(brand)

    return CompositeVideoClip(layers, size=(W, H))


# ---------------------------------------------------------------------------
# Hex → RGB helper
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (r, g, b)


# ---------------------------------------------------------------------------
# Transition
# ---------------------------------------------------------------------------

def _crossfade(clip_a, clip_b, fade_duration: float = 0.5):
    """Apply crossfade transition between two clips."""
    from moviepy.video.fx.all import fadein, fadeout
    a_faded = fadeout(clip_a, fade_duration)
    b_faded = fadein(clip_b, fade_duration)
    return a_faded, b_faded


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_video(
    summary: Summary,
    output_path: str,
    audio_path: str | None = None,
    style: VideoStyle = VideoStyle.MODERN,
    watermark: str = "SnackOnAI",
    cfg: VideoConfig | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> str:
    """
    Generate a vertical video from a Summary object.

    Args:
        summary:           Structured summary with headline, summary, bullets.
        output_path:       Destination .mp4 path.
        audio_path:        Optional path to voiceover MP3.
        style:             Visual style preset.
        watermark:         Watermark text (empty string to disable).
        cfg:               VideoConfig override.
        progress_callback: Called with (current_slide, total_slides).

    Returns:
        The resolved output_path.
    """
    if cfg is None:
        cfg = get_config().video

    (ImageClip, TextClip, CompositeVideoClip,
     AudioFileClip, concatenate_videoclips, ColorClip) = _try_import_moviepy()

    palette = STYLES[style]
    n_bullets = len(summary.bullets)

    # --- Timing budget ---
    # Distribute time: title + summary + bullets + outro ≤ max_duration
    max_dur = float(cfg.max_duration)
    title_dur = clamp(max_dur * 0.15, 3.0, 8.0)
    outro_dur = clamp(max_dur * 0.10, 2.0, 5.0)
    remaining = max_dur - title_dur - outro_dur
    summary_dur = clamp(remaining * 0.30, 4.0, 12.0)
    bullet_budget = remaining - summary_dur
    bullet_dur = clamp(bullet_budget / max(n_bullets, 1), 3.0, 12.0)

    logger.info(
        "Timing: title=%.1fs summary=%.1fs bullet=%.1fs×%d outro=%.1fs",
        title_dur, summary_dur, bullet_dur, n_bullets, outro_dur,
    )

    total_slides = 3 + n_bullets  # title + summary + bullets + outro

    def _progress(step: int) -> None:
        if progress_callback:
            progress_callback(step, total_slides)

    logger.info("Building title slide…")
    title_slide = _build_title_slide(summary, palette, cfg, watermark, title_dur)
    _progress(1)

    logger.info("Building summary slide…")
    summary_slide = _build_summary_slide(summary, palette, cfg, watermark, summary_dur)
    _progress(2)

    bullet_slides = []
    for i, bullet in enumerate(summary.bullets):
        logger.info("Building bullet slide %d/%d…", i + 1, n_bullets)
        slide = _build_bullet_slide(i, bullet, n_bullets, palette, cfg, watermark, bullet_dur)
        bullet_slides.append(slide)
        _progress(3 + i)

    logger.info("Building outro slide…")
    outro_slide = _build_outro_slide(palette, cfg, watermark, outro_dur)
    _progress(total_slides)

    all_slides = [title_slide, summary_slide] + bullet_slides + [outro_slide]
    video = concatenate_videoclips(all_slides, method="compose")

    # --- Audio ---
    if audio_path and os.path.exists(audio_path):
        logger.info("Attaching voiceover: %s", audio_path)
        voice = AudioFileClip(audio_path)
        # Trim voice to video length if needed
        if voice.duration > video.duration:
            voice = voice.subclip(0, video.duration)
        video = video.set_audio(voice)

        # Optional background music
        if cfg.background_music_path and os.path.exists(cfg.background_music_path):
            from moviepy.audio.fx.all import audio_loop, volumex
            from moviepy.editor import CompositeAudioClip

            music = AudioFileClip(cfg.background_music_path)
            if music.duration < video.duration:
                music = audio_loop(music, duration=video.duration)
            else:
                music = music.subclip(0, video.duration)
            music = volumex(music, cfg.music_volume)
            mixed = CompositeAudioClip([video.audio, music])
            video = video.set_audio(mixed)

    # --- Render ---
    logger.info("Rendering video to: %s", output_path)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    video.write_videofile(
        output_path,
        fps=cfg.fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        bitrate="4000k",
        audio_bitrate="128k",
        temp_audiofile=os.path.join(tempfile.gettempdir(), "snackonai_temp_audio.m4a"),
        remove_temp=True,
        logger=None,  # suppress moviepy progress bar (we have our own)
        threads=4,
    )

    actual_size = os.path.getsize(output_path) / 1024 / 1024
    logger.info("Video saved: %s (%.1f MB)", output_path, actual_size)
    return output_path


def generate_thumbnail(
    summary: Summary,
    output_path: str,
    style: VideoStyle = VideoStyle.MODERN,
    watermark: str = "SnackOnAI",
    cfg: VideoConfig | None = None,
) -> str:
    """
    Generate a 1080x1920 PNG thumbnail for the video.

    Returns:
        The resolved output_path.
    """
    if cfg is None:
        cfg = get_config().video

    (ImageClip, TextClip, CompositeVideoClip,
     AudioFileClip, concatenate_videoclips, ColorClip) = _try_import_moviepy()

    palette = STYLES[style]
    W, H = cfg.width, cfg.height

    bg_arr = _make_gradient(W, H, palette.bg_top, palette.bg_bottom)
    bg = ImageClip(bg_arr)

    layers: list = [bg]

    headline_clip = (
        TextClip(
            _wrap_text(summary.headline, 22),
            fontsize=palette.font_size_headline,
            color=palette.headline_color,
            font=_get_fonts()[0],
            method="caption",
            size=(W - 120, None),
            align="center",
        )
        .set_position("center")
    )
    layers.append(headline_clip)

    if watermark:
        wm = (
            TextClip(watermark, fontsize=36, color=palette.accent_color,
                     font=_get_fonts()[0], method="label")
            .set_position((40, H - 80))
        )
        layers.append(wm)

    thumbnail = CompositeVideoClip(layers, size=(W, H))
    thumbnail.save_frame(output_path, t=0)
    logger.info("Thumbnail saved: %s", output_path)
    return output_path
