"""
Unit tests for the extractor module.
"""

import pytest
from unittest.mock import MagicMock, patch

from snackonaiclips.extractor import (
    ArticleContent,
    ExtractionError,
    URLValidationError,
    _clean_text,
    _extract_with_trafilatura,
    _extract_with_readability,
    extract_content,
)
from snackonaiclips.config import ExtractorConfig


# ---------------------------------------------------------------------------
# Sample HTML for tests
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>How AI is Changing Software Development</title></head>
<body>
  <nav>Home | About | Contact</nav>
  <article>
    <h1>How AI is Changing Software Development</h1>
    <p>
      Artificial intelligence is rapidly transforming the way software is built.
      From automated code completion to intelligent debugging, AI tools are becoming
      indispensable for modern developers. This shift is not just about productivity —
      it fundamentally changes what it means to write software.
    </p>
    <p>
      Large language models like GPT-4 can generate entire functions from natural
      language descriptions. GitHub Copilot, built on OpenAI Codex, has been adopted
      by millions of developers worldwide. Studies show productivity improvements of
      up to 55% for common programming tasks.
    </p>
    <p>
      The implications for software architecture are profound. Teams can now prototype
      faster, iterate more frequently, and offload boilerplate to AI assistants.
      However, critical thinking about design, security, and correctness remains
      irreplacably human.
    </p>
  </article>
  <footer>© 2024 TechBlog</footer>
</body>
</html>
"""

EMPTY_HTML = "<html><body><p>Click here to subscribe.</p></body></html>"
MINIMAL_HTML = "<html><body></body></html>"


# ---------------------------------------------------------------------------
# _clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_collapses_multiple_newlines(self):
        raw = "Line one\n\n\n\nLine two"
        result = _clean_text(raw)
        assert "\n\n\n" not in result

    def test_strips_leading_trailing_whitespace(self):
        assert _clean_text("  hello  ") == "hello"

    def test_collapses_multiple_spaces(self):
        raw = "word1    word2"
        result = _clean_text(raw)
        assert "    " not in result


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

class TestURLValidation:
    def test_invalid_url_raises(self):
        with pytest.raises(URLValidationError, match="Invalid or unsupported URL"):
            extract_content("not-a-url")

    def test_missing_scheme_raises(self):
        with pytest.raises(URLValidationError):
            extract_content("example.com/article")

    def test_ftp_raises(self):
        with pytest.raises(URLValidationError):
            extract_content("ftp://example.com/article")


# ---------------------------------------------------------------------------
# Trafilatura extraction
# ---------------------------------------------------------------------------

class TestTrafilaturaExtractor:
    def test_extracts_from_valid_html(self):
        result = _extract_with_trafilatura(SAMPLE_HTML, "https://example.com/article")
        # trafilatura may or may not be installed in test env
        if result is not None:
            assert len(result.text) > 50
            assert result.url == "https://example.com/article"

    def test_returns_none_for_empty_html(self):
        result = _extract_with_trafilatura(EMPTY_HTML, "https://example.com")
        # Should return None since content is too short / noisy
        assert result is None or len(result.text) < 200


# ---------------------------------------------------------------------------
# Readability extraction
# ---------------------------------------------------------------------------

class TestReadabilityExtractor:
    def test_extracts_from_valid_html(self):
        result = _extract_with_readability(SAMPLE_HTML, "https://example.com/article")
        if result is not None:
            assert len(result.text) > 50


# ---------------------------------------------------------------------------
# extract_content integration (mocked HTTP)
# ---------------------------------------------------------------------------

class TestExtractContent:
    @patch("snackonaiclips.extractor._fetch_html", return_value=SAMPLE_HTML)
    def test_returns_article_content(self, mock_fetch):
        content = extract_content("https://example.com/article")
        assert isinstance(content, ArticleContent)
        assert len(content.text) > 50
        assert content.url == "https://example.com/article"

    @patch("snackonaiclips.extractor._fetch_html")
    def test_http_error_raises_url_validation_error(self, mock_fetch):
        import requests
        mock_fetch.side_effect = requests.HTTPError("404 Not Found")
        with pytest.raises(URLValidationError):
            extract_content("https://example.com/missing")

    @patch("snackonaiclips.extractor._fetch_html", return_value=MINIMAL_HTML)
    @patch("snackonaiclips.extractor._extract_with_trafilatura", return_value=None)
    @patch("snackonaiclips.extractor._extract_with_readability", return_value=None)
    @patch("snackonaiclips.extractor._extract_with_newspaper", return_value=None)
    def test_all_strategies_fail_raises_extraction_error(
        self, mock_news, mock_read, mock_trafi, mock_fetch
    ):
        with pytest.raises(ExtractionError, match="Could not extract"):
            extract_content("https://example.com/empty")

    @patch("snackonaiclips.extractor._fetch_html", return_value=SAMPLE_HTML)
    def test_uses_config_extractor(self, mock_fetch):
        cfg = ExtractorConfig(request_timeout=5, max_retries=1, retry_backoff=1.0)
        result = extract_content("https://example.com/article", cfg=cfg)
        assert result is not None
