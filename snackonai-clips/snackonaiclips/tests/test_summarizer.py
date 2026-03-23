"""
Unit tests for the summarizer module.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from snackonaiclips.extractor import ArticleContent
from snackonaiclips.summarizer import (
    Summary,
    SummarizationError,
    _build_user_prompt,
    _extract_json,
    _fallback_summarize,
    _validate_summary_dict,
    summarize,
)
from snackonaiclips.config import LLMConfig, LLMProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ARTICLE = ArticleContent(
    url="https://example.com/ai-article",
    title="The Future of AI in Healthcare",
    text=(
        "Artificial intelligence is revolutionizing healthcare delivery. "
        "Machine learning models can now diagnose diseases with accuracy matching "
        "or exceeding experienced physicians. Early detection of cancer, diabetic "
        "retinopathy, and heart disease has improved dramatically. "
        "However, regulatory frameworks struggle to keep pace with innovation. "
        "Data privacy and algorithmic bias remain significant concerns. "
        "Healthcare systems must balance innovation with patient safety."
    ),
)

VALID_SUMMARY_DICT = {
    "headline": "AI Is Reshaping Modern Healthcare Delivery",
    "summary": (
        "Artificial intelligence is transforming how diseases are diagnosed and treated. "
        "ML models now match physician accuracy in several domains. "
        "Regulatory and ethical challenges remain key hurdles."
    ),
    "bullets": [
        "AI matches physician accuracy in disease diagnosis",
        "Early cancer detection rates have improved dramatically",
        "Regulatory frameworks lag behind AI innovation",
    ],
}


# ---------------------------------------------------------------------------
# Summary dataclass
# ---------------------------------------------------------------------------

class TestSummaryDataclass:
    def test_to_dict(self):
        s = Summary.from_dict(VALID_SUMMARY_DICT)
        d = s.to_dict()
        assert d["headline"] == VALID_SUMMARY_DICT["headline"]
        assert isinstance(d["bullets"], list)

    def test_from_dict_round_trip(self):
        s = Summary.from_dict(VALID_SUMMARY_DICT)
        assert s.headline == VALID_SUMMARY_DICT["headline"]
        assert len(s.bullets) == 3


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

class TestExtractJSON:
    def test_plain_json(self):
        raw = json.dumps(VALID_SUMMARY_DICT)
        result = _extract_json(raw)
        assert result["headline"] == VALID_SUMMARY_DICT["headline"]

    def test_json_with_code_fence(self):
        raw = f"```json\n{json.dumps(VALID_SUMMARY_DICT)}\n```"
        result = _extract_json(raw)
        assert "headline" in result

    def test_json_with_plain_fence(self):
        raw = f"```\n{json.dumps(VALID_SUMMARY_DICT)}\n```"
        result = _extract_json(raw)
        assert "headline" in result

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _extract_json("not json at all")


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestValidateSummaryDict:
    def test_valid_dict_passes(self):
        _validate_summary_dict(VALID_SUMMARY_DICT)  # Should not raise

    def test_missing_headline_raises(self):
        bad = {k: v for k, v in VALID_SUMMARY_DICT.items() if k != "headline"}
        with pytest.raises(ValueError, match="Missing key"):
            _validate_summary_dict(bad)

    def test_wrong_type_bullets_raises(self):
        bad = {**VALID_SUMMARY_DICT, "bullets": "not a list"}
        with pytest.raises(ValueError):
            _validate_summary_dict(bad)

    def test_too_few_bullets_raises(self):
        bad = {**VALID_SUMMARY_DICT, "bullets": ["only one"]}
        with pytest.raises(ValueError, match="3–5"):
            _validate_summary_dict(bad)

    def test_too_many_bullets_raises(self):
        bad = {**VALID_SUMMARY_DICT, "bullets": [f"bullet {i}" for i in range(6)]}
        with pytest.raises(ValueError, match="3–5"):
            _validate_summary_dict(bad)


# ---------------------------------------------------------------------------
# Fallback summarizer
# ---------------------------------------------------------------------------

class TestFallbackSummarize:
    def test_returns_summary_object(self):
        result = _fallback_summarize(SAMPLE_ARTICLE)
        assert isinstance(result, Summary)
        assert len(result.headline) > 0
        assert len(result.summary) > 0
        assert 3 <= len(result.bullets) <= 5

    def test_handles_short_text(self):
        short = ArticleContent(
            url="https://example.com",
            title="Short",
            text="Very short text.",
        )
        result = _fallback_summarize(short)
        assert isinstance(result, Summary)
        assert len(result.bullets) >= 3

    def test_uses_title_for_headline(self):
        result = _fallback_summarize(SAMPLE_ARTICLE)
        # Headline should be derived from title or first sentence
        assert len(result.headline) > 0


# ---------------------------------------------------------------------------
# summarize() — OpenAI path (mocked)
# ---------------------------------------------------------------------------

class TestSummarizeOpenAI:
    def _make_cfg(self):
        return LLMConfig(
            provider=LLMProvider.OPENAI,
            openai_api_key="test-key",
            openai_model="gpt-4o-mini",
        )

    @patch("snackonaiclips.summarizer._summarize_openai")
    def test_returns_summary_on_success(self, mock_openai):
        mock_openai.return_value = VALID_SUMMARY_DICT
        result = summarize(SAMPLE_ARTICLE, cfg=self._make_cfg())
        assert isinstance(result, Summary)
        assert result.headline == VALID_SUMMARY_DICT["headline"]

    @patch("snackonaiclips.summarizer._summarize_openai")
    def test_falls_back_on_llm_exception(self, mock_openai):
        mock_openai.side_effect = Exception("API timeout")
        result = summarize(SAMPLE_ARTICLE, cfg=self._make_cfg())
        # Should fall back to rule-based, not raise
        assert isinstance(result, Summary)


# ---------------------------------------------------------------------------
# summarize() — Ollama path (mocked)
# ---------------------------------------------------------------------------

class TestSummarizeOllama:
    def _make_cfg(self):
        return LLMConfig(
            provider=LLMProvider.OLLAMA,
            ollama_base_url="http://localhost:11434",
            ollama_model="llama3.2",
        )

    @patch("snackonaiclips.summarizer._summarize_ollama")
    def test_returns_summary_on_success(self, mock_ollama):
        mock_ollama.return_value = VALID_SUMMARY_DICT
        result = summarize(SAMPLE_ARTICLE, cfg=self._make_cfg())
        assert isinstance(result, Summary)

    @patch("snackonaiclips.summarizer._summarize_ollama")
    def test_falls_back_on_connection_error(self, mock_ollama):
        mock_ollama.side_effect = Exception("Connection refused")
        result = summarize(SAMPLE_ARTICLE, cfg=self._make_cfg())
        assert isinstance(result, Summary)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

class TestBuildUserPrompt:
    def test_includes_title(self):
        prompt = _build_user_prompt("body text here", "My Article Title")
        assert "My Article Title" in prompt

    def test_includes_json_schema(self):
        prompt = _build_user_prompt("body text", "title")
        assert "headline" in prompt
        assert "bullets" in prompt

    def test_truncates_long_body(self):
        long_body = "word " * 10_000
        prompt = _build_user_prompt(long_body, "Title")
        # Prompt should not be insanely long
        assert len(prompt) < 20_000
