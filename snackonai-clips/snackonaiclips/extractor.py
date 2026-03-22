"""
Content extraction from URLs.

Priority order:
  1. trafilatura  — best noise reduction
  2. readability-lxml — fallback
  3. newspaper3k  — last resort

Each strategy is tried in order until clean text is obtained.
"""

import logging
import re
from dataclasses import dataclass

import requests

from .config import ExtractorConfig, get_config
from .utils import is_valid_url, retry

logger = logging.getLogger(__name__)


@dataclass
class ArticleContent:
    url: str
    title: str
    text: str
    author: str = ""
    publish_date: str = ""


class ExtractionError(Exception):
    """Raised when content cannot be extracted from a URL."""


class URLValidationError(ExtractionError):
    """Raised when the URL is invalid or unreachable."""


def _fetch_html(url: str, cfg: ExtractorConfig) -> str:
    """Fetch raw HTML with retry logic."""
    headers = {"User-Agent": cfg.user_agent}

    @retry(max_attempts=cfg.max_retries, backoff=cfg.retry_backoff, exceptions=(requests.RequestException,))
    def _get() -> str:
        resp = requests.get(url, headers=headers, timeout=cfg.request_timeout)
        resp.raise_for_status()
        return resp.text

    return _get()


def _clean_text(text: str) -> str:
    """Remove excessive whitespace and non-printable chars from text."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _extract_with_trafilatura(html: str, url: str) -> ArticleContent | None:
    """Attempt extraction using trafilatura."""
    try:
        import trafilatura

        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            output_format="txt",
        )
        meta = trafilatura.extract_metadata(html)
        if result and len(result.strip()) > 100:
            return ArticleContent(
                url=url,
                title=meta.title if meta and meta.title else "",
                text=_clean_text(result),
                author=meta.author if meta and meta.author else "",
                publish_date=str(meta.date) if meta and meta.date else "",
            )
    except ImportError:
        logger.debug("trafilatura not installed, skipping")
    except Exception as exc:
        logger.debug("trafilatura failed: %s", exc)
    return None


def _extract_with_readability(html: str, url: str) -> ArticleContent | None:
    """Attempt extraction using readability-lxml."""
    try:
        from readability import Document

        doc = Document(html)
        summary_html = doc.summary()

        # Strip HTML tags naively for text
        text = re.sub(r"<[^>]+>", " ", summary_html)
        text = _clean_text(text)

        if text and len(text) > 100:
            return ArticleContent(
                url=url,
                title=_clean_text(doc.title()),
                text=text,
            )
    except ImportError:
        logger.debug("readability-lxml not installed, skipping")
    except Exception as exc:
        logger.debug("readability-lxml failed: %s", exc)
    return None


def _extract_with_newspaper(url: str) -> ArticleContent | None:
    """Attempt extraction using newspaper3k."""
    try:
        from newspaper import Article

        article = Article(url)
        article.download()
        article.parse()
        text = _clean_text(article.text)
        if text and len(text) > 100:
            return ArticleContent(
                url=url,
                title=article.title or "",
                text=text,
                author=", ".join(article.authors),
                publish_date=str(article.publish_date) if article.publish_date else "",
            )
    except ImportError:
        logger.debug("newspaper3k not installed, skipping")
    except Exception as exc:
        logger.debug("newspaper3k failed: %s", exc)
    return None


def extract_content(url: str, cfg: ExtractorConfig | None = None) -> ArticleContent:
    """
    Extract clean article content from the given URL.

    Tries trafilatura → readability-lxml → newspaper3k in order.
    Raises ExtractionError if all strategies fail.
    """
    if cfg is None:
        cfg = get_config().extractor

    if not is_valid_url(url):
        raise URLValidationError(f"Invalid or unsupported URL: {url!r}")

    logger.info("Fetching content from: %s", url)

    try:
        html = _fetch_html(url, cfg)
    except requests.HTTPError as exc:
        raise URLValidationError(f"HTTP error fetching URL: {exc}") from exc
    except requests.RequestException as exc:
        raise URLValidationError(f"Network error fetching URL: {exc}") from exc

    # Strategy 1: trafilatura
    content = _extract_with_trafilatura(html, url)
    if content:
        logger.info("Extracted %d chars via trafilatura", len(content.text))
        return content

    # Strategy 2: readability-lxml
    content = _extract_with_readability(html, url)
    if content:
        logger.info("Extracted %d chars via readability-lxml", len(content.text))
        return content

    # Strategy 3: newspaper3k (fetches again internally)
    content = _extract_with_newspaper(url)
    if content:
        logger.info("Extracted %d chars via newspaper3k", len(content.text))
        return content

    raise ExtractionError(
        f"Could not extract meaningful content from {url!r}. "
        "The page may be behind a paywall, require JavaScript, or contain only ads."
    )
