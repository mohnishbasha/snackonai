"""
Integration tests for the end-to-end pipeline:
  URL → extraction → summarization → (video skipped for speed)

These tests mock HTTP and LLM calls but exercise the real pipeline glue.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from snackonaiclips.extractor import ArticleContent, ExtractionError, URLValidationError
from snackonaiclips.summarizer import Summary
from snackonaiclips.config import LLMConfig, LLMProvider, TTSProvider, get_config, reset_config


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<html>
<head><title>The Rise of Generative AI in Enterprise</title></head>
<body>
<article>
  <h1>The Rise of Generative AI in Enterprise</h1>
  <p>Generative AI has moved from research labs to boardrooms in under three years.
  Companies across finance, healthcare, and retail are deploying LLM-based systems
  to automate workflows, enhance customer support, and accelerate product development.</p>
  <p>The market for enterprise AI solutions is projected to exceed $500 billion by 2028.
  Early adopters report 30–40% reduction in operational costs for specific use cases.</p>
  <p>Key challenges include data governance, model hallucinations, and workforce adaptation.
  Successful deployments share common traits: executive sponsorship, phased rollout,
  and continuous human oversight of AI outputs.</p>
  <p>Organizations should start with low-risk, high-value use cases before expanding.
  Vendor lock-in risks must be evaluated alongside build-vs-buy decisions.
  Change management is often the hardest part of AI adoption.</p>
</article>
</body>
</html>
"""

VALID_SUMMARY_RESPONSE = {
    "headline": "Generative AI Transforms Enterprise Operations Fast",
    "summary": (
        "Generative AI has rapidly moved into enterprise applications across major industries. "
        "Companies are seeing 30-40% cost reductions in targeted use cases. "
        "Success requires phased rollouts and strong human oversight."
    ),
    "bullets": [
        "Enterprise AI market to exceed $500B by 2028",
        "Early adopters report 30–40% cost reductions",
        "Data governance remains a top challenge",
        "Start with low-risk, high-value use cases",
    ],
}


# ---------------------------------------------------------------------------
# Happy path: URL → Summary
# ---------------------------------------------------------------------------

class TestHappyPath:
    @patch("snackonaiclips.extractor._fetch_html", return_value=SAMPLE_HTML)
    @patch("snackonaiclips.summarizer._summarize_openai", return_value=VALID_SUMMARY_RESPONSE)
    def test_url_to_summary_pipeline(self, mock_llm, mock_fetch):
        from snackonaiclips.extractor import extract_content
        from snackonaiclips.summarizer import summarize

        cfg = LLMConfig(provider=LLMProvider.OPENAI, openai_api_key="test-key")

        content = extract_content("https://example.com/ai-enterprise")
        assert isinstance(content, ArticleContent)
        assert len(content.text) > 50

        summary = summarize(content, cfg=cfg)
        assert isinstance(summary, Summary)
        assert summary.headline == VALID_SUMMARY_RESPONSE["headline"]
        assert len(summary.bullets) >= 3

    @patch("snackonaiclips.extractor._fetch_html", return_value=SAMPLE_HTML)
    @patch("snackonaiclips.summarizer._summarize_openai", return_value=VALID_SUMMARY_RESPONSE)
    def test_summary_serializes_to_json(self, mock_llm, mock_fetch):
        from snackonaiclips.extractor import extract_content
        from snackonaiclips.summarizer import summarize

        cfg = LLMConfig(provider=LLMProvider.OPENAI, openai_api_key="test-key")
        content = extract_content("https://example.com/article")
        summary = summarize(content, cfg=cfg)

        data = summary.to_dict()
        serialized = json.dumps(data)
        parsed = json.loads(serialized)
        assert parsed["headline"] == summary.headline
        assert isinstance(parsed["bullets"], list)


# ---------------------------------------------------------------------------
# Edge case: invalid URL
# ---------------------------------------------------------------------------

class TestInvalidURL:
    def test_invalid_url_fails_at_extraction(self):
        from snackonaiclips.extractor import extract_content
        with pytest.raises(URLValidationError):
            extract_content("htp://bad-url")

    def test_empty_string_url_fails(self):
        from snackonaiclips.extractor import extract_content
        with pytest.raises(URLValidationError):
            extract_content("")

    def test_localhost_url_is_valid_but_may_fail_network(self):
        from snackonaiclips.extractor import extract_content
        import requests
        with patch("snackonaiclips.extractor._fetch_html") as mock_fetch:
            mock_fetch.side_effect = requests.ConnectionError("Connection refused")
            with pytest.raises(URLValidationError):
                extract_content("http://localhost:9999/nonexistent")


# ---------------------------------------------------------------------------
# Edge case: empty content
# ---------------------------------------------------------------------------

class TestEmptyContent:
    EMPTY_PAGE = "<html><body><p>Sign up for our newsletter.</p></body></html>"

    @patch("snackonaiclips.extractor._fetch_html", return_value=EMPTY_PAGE)
    @patch("snackonaiclips.extractor._extract_with_trafilatura", return_value=None)
    @patch("snackonaiclips.extractor._extract_with_readability", return_value=None)
    @patch("snackonaiclips.extractor._extract_with_newspaper", return_value=None)
    def test_empty_content_raises_extraction_error(self, *mocks):
        from snackonaiclips.extractor import extract_content
        with pytest.raises(ExtractionError, match="Could not extract"):
            extract_content("https://example.com/empty")


# ---------------------------------------------------------------------------
# Edge case: LLM failure → fallback
# ---------------------------------------------------------------------------

class TestLLMFailureFallback:
    @patch("snackonaiclips.extractor._fetch_html", return_value=SAMPLE_HTML)
    @patch("snackonaiclips.summarizer._summarize_openai")
    def test_llm_failure_returns_fallback_summary(self, mock_llm, mock_fetch):
        from snackonaiclips.extractor import extract_content
        from snackonaiclips.summarizer import summarize

        mock_llm.side_effect = Exception("OpenAI API is down")
        cfg = LLMConfig(provider=LLMProvider.OPENAI, openai_api_key="test-key")

        content = extract_content("https://example.com/article")
        summary = summarize(content, cfg=cfg)

        # Should still return a valid Summary via fallback
        assert isinstance(summary, Summary)
        assert len(summary.headline) > 0
        assert len(summary.bullets) >= 3

    @patch("snackonaiclips.extractor._fetch_html", return_value=SAMPLE_HTML)
    @patch("snackonaiclips.summarizer._summarize_ollama")
    def test_ollama_failure_returns_fallback(self, mock_ollama, mock_fetch):
        from snackonaiclips.extractor import extract_content
        from snackonaiclips.summarizer import summarize

        mock_ollama.side_effect = Exception("Ollama not running")
        cfg = LLMConfig(provider=LLMProvider.OLLAMA)

        content = extract_content("https://example.com/article")
        summary = summarize(content, cfg=cfg)

        assert isinstance(summary, Summary)
        assert len(summary.bullets) >= 3


# ---------------------------------------------------------------------------
# Edge case: malformed LLM JSON → fallback
# ---------------------------------------------------------------------------

class TestMalformedLLMResponse:
    @patch("snackonaiclips.extractor._fetch_html", return_value=SAMPLE_HTML)
    @patch("snackonaiclips.summarizer._summarize_openai")
    def test_malformed_json_uses_fallback(self, mock_llm, mock_fetch):
        from snackonaiclips.extractor import extract_content
        from snackonaiclips.summarizer import summarize
        import json

        mock_llm.side_effect = json.JSONDecodeError("bad json", "", 0)
        cfg = LLMConfig(provider=LLMProvider.OPENAI, openai_api_key="test-key")

        content = extract_content("https://example.com/article")
        summary = summarize(content, cfg=cfg)

        assert isinstance(summary, Summary)


# ---------------------------------------------------------------------------
# JSON output schema validation
# ---------------------------------------------------------------------------

class TestSummaryJSONSchema:
    def test_output_matches_expected_schema(self):
        summary = Summary(
            headline="Test Headline Here",
            summary="This is a test summary. It has two sentences.",
            bullets=["Point one", "Point two", "Point three"],
        )
        data = summary.to_dict()

        assert "headline" in data
        assert "summary" in data
        assert "bullets" in data
        assert isinstance(data["headline"], str)
        assert isinstance(data["summary"], str)
        assert isinstance(data["bullets"], list)
        assert all(isinstance(b, str) for b in data["bullets"])
