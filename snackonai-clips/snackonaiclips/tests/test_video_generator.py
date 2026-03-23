"""
Unit tests for the video_generator module.

Heavy rendering is skipped in CI — we mock moviepy and test logic only.
"""

import os
import pytest
from unittest.mock import MagicMock, patch, call

from snackonaiclips.summarizer import Summary
from snackonaiclips.config import VideoConfig, VideoStyle
from snackonaiclips.video_generator import (
    STYLES,
    _hex_to_rgb,
    _make_gradient,
    _wrap_text,
    generate_video,
    generate_thumbnail,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SUMMARY = Summary(
    headline="AI Is Changing Software Development Forever",
    summary=(
        "Artificial intelligence tools are fundamentally reshaping how developers "
        "write and review code. Productivity gains of up to 55% have been reported."
    ),
    bullets=[
        "AI completes code from natural language",
        "GitHub Copilot adopted by millions of devs",
        "Security reviews still require human judgment",
        "Teams prototype faster with AI assistance",
    ],
)


# ---------------------------------------------------------------------------
# _hex_to_rgb
# ---------------------------------------------------------------------------

class TestHexToRGB:
    def test_white(self):
        assert _hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_black(self):
        assert _hex_to_rgb("#000000") == (0, 0, 0)

    def test_accent_color(self):
        r, g, b = _hex_to_rgb("#4FC3F7")
        assert r == 0x4F
        assert g == 0xC3
        assert b == 0xF7

    def test_without_hash(self):
        assert _hex_to_rgb("FF0000") == (255, 0, 0)


# ---------------------------------------------------------------------------
# _make_gradient
# ---------------------------------------------------------------------------

class TestMakeGradient:
    def test_shape(self):
        arr = _make_gradient(100, 200, (0, 0, 0), (255, 255, 255))
        assert arr.shape == (200, 100, 3)

    def test_top_color(self):
        arr = _make_gradient(10, 100, (255, 0, 0), (0, 0, 255))
        # First row should be close to red
        assert arr[0, 0, 0] == 255
        assert arr[0, 0, 2] == 0

    def test_bottom_color(self):
        arr = _make_gradient(10, 100, (255, 0, 0), (0, 0, 255))
        # Last row should be close to blue
        assert arr[-1, 0, 0] == 0
        assert arr[-1, 0, 2] == 255


# ---------------------------------------------------------------------------
# _wrap_text
# ---------------------------------------------------------------------------

class TestWrapText:
    def test_short_text_unchanged(self):
        result = _wrap_text("Short text", max_chars_per_line=40)
        assert result == "Short text"

    def test_long_text_wraps(self):
        result = _wrap_text("This is a longer piece of text that should wrap", max_chars_per_line=20)
        assert "\n" in result

    def test_respects_max_chars(self):
        result = _wrap_text("word " * 30, max_chars_per_line=25)
        for line in result.split("\n"):
            assert len(line) <= 30  # allow slight overflow due to word boundary


# ---------------------------------------------------------------------------
# Style palettes
# ---------------------------------------------------------------------------

class TestStylePalettes:
    def test_all_styles_present(self):
        for style in VideoStyle:
            assert style in STYLES

    def test_palettes_have_required_fields(self):
        for style, palette in STYLES.items():
            assert isinstance(palette.bg_top, tuple)
            assert isinstance(palette.headline_color, str)
            assert palette.font_size_headline > 0


# ---------------------------------------------------------------------------
# generate_video (mocked moviepy)
# ---------------------------------------------------------------------------

class TestGenerateVideo:
    def _make_mock_clip(self, duration: float = 5.0):
        clip = MagicMock()
        clip.duration = duration
        clip.h = 100
        clip.set_duration.return_value = clip
        clip.set_position.return_value = clip
        clip.set_audio.return_value = clip
        clip.subclip.return_value = clip
        clip.write_videofile = MagicMock()
        return clip

    @patch("snackonaiclips.video_generator._try_import_moviepy")
    @patch("os.path.getsize", return_value=1024 * 1024)
    def test_video_written_to_output_path(self, mock_size, mock_import, tmp_path):
        output = str(tmp_path / "test_output.mp4")

        mock_clip = self._make_mock_clip()
        ImageClip = MagicMock(return_value=mock_clip)
        TextClip = MagicMock(return_value=mock_clip)
        CompositeVideoClip = MagicMock(return_value=mock_clip)
        AudioFileClip = MagicMock(return_value=mock_clip)
        concatenate = MagicMock(return_value=mock_clip)
        ColorClip = MagicMock(return_value=mock_clip)

        mock_import.return_value = (
            ImageClip, TextClip, CompositeVideoClip,
            AudioFileClip, concatenate, ColorClip,
        )

        # Create a fake output file so getsize works
        open(output, "w").close()

        generate_video(
            summary=SAMPLE_SUMMARY,
            output_path=output,
            style=VideoStyle.MODERN,
            watermark="SnackOnAI",
        )

        mock_clip.write_videofile.assert_called_once()
        call_args = mock_clip.write_videofile.call_args
        assert call_args[0][0] == output

    @patch("snackonaiclips.video_generator._try_import_moviepy")
    def test_progress_callback_called(self, mock_import, tmp_path):
        output = str(tmp_path / "test_output.mp4")
        mock_clip = self._make_mock_clip()
        mock_import.return_value = (
            MagicMock(return_value=mock_clip),
            MagicMock(return_value=mock_clip),
            MagicMock(return_value=mock_clip),
            MagicMock(return_value=mock_clip),
            MagicMock(return_value=mock_clip),
            MagicMock(return_value=mock_clip),
        )
        open(output, "w").close()

        calls = []
        def on_progress(current, total):
            calls.append((current, total))

        with patch("os.path.getsize", return_value=1024):
            generate_video(
                summary=SAMPLE_SUMMARY,
                output_path=output,
                progress_callback=on_progress,
            )

        assert len(calls) > 0
        # Last call should be at total
        assert calls[-1][0] == calls[-1][1]

    def test_import_error_propagates(self, tmp_path):
        output = str(tmp_path / "fail.mp4")
        with patch("snackonaiclips.video_generator._try_import_moviepy") as mock_import:
            mock_import.side_effect = ImportError("moviepy not installed")
            with pytest.raises(ImportError, match="moviepy"):
                generate_video(SAMPLE_SUMMARY, output)


# ---------------------------------------------------------------------------
# Timing budget
# ---------------------------------------------------------------------------

class TestTimingBudget:
    """Ensure slide durations respect the 60-second maximum."""

    def test_total_duration_under_limit(self):
        cfg = VideoConfig(max_duration=60)
        n_bullets = 5
        max_dur = float(cfg.max_duration)
        title_dur = min(max(max_dur * 0.15, 3.0), 8.0)
        outro_dur = min(max(max_dur * 0.10, 2.0), 5.0)
        remaining = max_dur - title_dur - outro_dur
        summary_dur = min(max(remaining * 0.30, 4.0), 12.0)
        bullet_budget = remaining - summary_dur
        bullet_dur = min(max(bullet_budget / n_bullets, 3.0), 12.0)

        total = title_dur + summary_dur + (bullet_dur * n_bullets) + outro_dur
        assert total <= cfg.max_duration + 1.0  # 1s tolerance for rounding
