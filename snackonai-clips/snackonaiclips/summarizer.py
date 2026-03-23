"""
LLM-based summarization with OpenAI and Ollama backends.

Produces structured JSON with:
  - headline  : 5–10 word title
  - summary   : 2–3 sentence paragraph
  - bullets   : 3–5 key takeaway strings
"""

import json
import logging
import re
import textwrap
from dataclasses import dataclass
from typing import Any

from .config import LLMConfig, LLMProvider, get_config
from .extractor import ArticleContent
from .utils import retry, truncate_text

logger = logging.getLogger(__name__)

# Max chars of article text fed to LLM (avoid huge prompts / high cost)
_MAX_INPUT_CHARS = 6000

SUMMARY_SCHEMA = {
    "headline": str,
    "summary": str,
    "bullets": list,
}


@dataclass
class Summary:
    headline: str
    summary: str
    bullets: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "summary": self.summary,
            "bullets": self.bullets,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Summary":
        return cls(
            headline=str(data["headline"]),
            summary=str(data["summary"]),
            bullets=[str(b) for b in data["bullets"]],
        )


class SummarizationError(Exception):
    """Raised when all summarization strategies fail."""


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an expert content strategist specializing in LinkedIn short-form videos.
    Your job is to distill blog articles into punchy, engaging video scripts.
    Always respond with valid JSON only — no markdown fences, no extra commentary.
    """
).strip()


def _build_user_prompt(text: str, title: str) -> str:
    body = truncate_text(text, _MAX_INPUT_CHARS)
    article_block = f"Title: {title}\n\n{body}" if title else body
    return textwrap.dedent(
        f"""
        Summarize the following article for a 60-second LinkedIn vertical video.

        Return ONLY this JSON structure (no code fences):
        {{
          "headline": "<5-10 word punchy headline>",
          "summary": "<2-3 sentence spoken narration>",
          "bullets": ["<key point 1>", "<key point 2>", "<key point 3>"]
        }}

        Rules:
        - headline must be ≤ 10 words, no period at end
        - summary must be conversational and < 60 words
        - bullets must be 3–5 items, each < 15 words
        - avoid jargon; write for a general LinkedIn audience

        Article:
        ---
        {article_block}
        ---
        """
    ).strip()


# ---------------------------------------------------------------------------
# JSON extraction / validation
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict[str, Any]:
    """Extract JSON from raw LLM output, handling markdown code fences."""
    # Strip ```json ... ``` or ``` ... ``` wrappers
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw.strip())
    return json.loads(raw)


def _validate_summary_dict(data: dict[str, Any]) -> None:
    """Raise ValueError if data doesn't match the expected schema."""
    for key, expected_type in SUMMARY_SCHEMA.items():
        if key not in data:
            raise ValueError(f"Missing key in LLM response: {key!r}")
        if not isinstance(data[key], expected_type):
            raise ValueError(
                f"Key {key!r} expected {expected_type.__name__}, "
                f"got {type(data[key]).__name__}"
            )
    if not (3 <= len(data["bullets"]) <= 5):
        raise ValueError(
            f"bullets must have 3–5 items, got {len(data['bullets'])}"
        )


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _summarize_openai(prompt: str, cfg: LLMConfig) -> dict[str, Any]:
    """Call OpenAI chat completions API."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SummarizationError(
            "openai package not installed. Run: pip install openai"
        ) from exc

    if not cfg.openai_api_key:
        raise SummarizationError(
            "OPENAI_API_KEY environment variable is not set."
        )

    client = OpenAI(api_key=cfg.openai_api_key, timeout=cfg.timeout)

    @retry(max_attempts=cfg.max_retries, exceptions=(Exception,))
    def _call() -> str:
        response = client.chat.completions.create(
            model=cfg.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""

    raw = _call()
    logger.debug("OpenAI raw response: %s", raw[:200])
    return _extract_json(raw)


def _summarize_ollama(prompt: str, cfg: LLMConfig) -> dict[str, Any]:
    """Call local Ollama API."""
    try:
        import requests as req
    except ImportError as exc:
        raise SummarizationError("requests package not installed") from exc

    payload = {
        "model": cfg.ollama_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",
    }

    @retry(max_attempts=cfg.max_retries, exceptions=(Exception,))
    def _call() -> str:
        resp = req.post(
            f"{cfg.ollama_base_url}/api/chat",
            json=payload,
            timeout=cfg.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]

    raw = _call()
    logger.debug("Ollama raw response: %s", raw[:200])
    return _extract_json(raw)


# ---------------------------------------------------------------------------
# Fallback: rule-based summarization (no LLM required)
# ---------------------------------------------------------------------------

def _fallback_summarize(content: ArticleContent) -> Summary:
    """
    Produce a basic summary using simple heuristics when all LLM calls fail.
    Splits text into sentences and picks the first few as summary + bullets.
    """
    logger.warning("Using fallback rule-based summarizer — LLM unavailable")
    sentences = re.split(r"(?<=[.!?])\s+", content.text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    headline = truncate_text(content.title or sentences[0] if sentences else "Key Insights", 80)
    # Remove trailing punctuation from headline
    headline = re.sub(r"[.!?]+$", "", headline).strip()

    summary_sentences = sentences[:3] if len(sentences) >= 3 else sentences
    summary = " ".join(summary_sentences)
    summary = truncate_text(summary, 300)

    raw_bullets = sentences[3:8] if len(sentences) > 3 else sentences[:5]
    bullets = [truncate_text(b, 100) for b in raw_bullets[:5]]
    if len(bullets) < 3:
        bullets += ["Read the full article for more insights"] * (3 - len(bullets))

    return Summary(headline=headline, summary=summary, bullets=bullets)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def summarize(content: ArticleContent, cfg: LLMConfig | None = None) -> Summary:
    """
    Summarize article content using the configured LLM provider.

    Falls back to rule-based summarization if LLM is unavailable or fails.
    """
    if cfg is None:
        cfg = get_config().llm

    prompt = _build_user_prompt(content.text, content.title)

    try:
        if cfg.provider == LLMProvider.OPENAI:
            logger.info("Summarizing with OpenAI (%s)…", cfg.openai_model)
            data = _summarize_openai(prompt, cfg)
        elif cfg.provider == LLMProvider.OLLAMA:
            logger.info("Summarizing with Ollama (%s)…", cfg.ollama_model)
            data = _summarize_ollama(prompt, cfg)
        else:
            raise SummarizationError(f"Unknown LLM provider: {cfg.provider}")

        _validate_summary_dict(data)
        summary = Summary.from_dict(data)
        logger.info("Summary generated: %r", summary.headline)
        return summary

    except SummarizationError:
        raise
    except Exception as exc:
        logger.warning("LLM summarization failed (%s), using fallback", exc)
        return _fallback_summarize(content)
