"""
Web Retriever — search the open web for industrial posts, technical blogs,
GitHub repos, and recent industry implementations.

Priority order:
  1. Tavily AI Search  (research-optimized, needs API key)
  2. DuckDuckGo Search (free fallback, no key required)
"""
from __future__ import annotations

import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


# ── Public entry point ────────────────────────────────────────────────────────

def search_web(
    query: str,
    max_results: Optional[int] = None,
    include_domains: Optional[list[str]] = None,
) -> list[dict]:
    """
    Search the web and return normalized result dicts.

    Parameters
    ----------
    query : str
        Search query.
    max_results : int, optional
        Number of results to fetch.
    include_domains : list[str], optional
        Restrict results to these domains (Tavily only).
    """
    limit = max_results or settings.MAX_PAPERS_PER_SOURCE

    # Try Tavily first
    if settings.TAVILY_API_KEY and "your_" not in settings.TAVILY_API_KEY:
        results = _search_tavily(query, limit, include_domains)
        if results:
            return results

    # Fallback to DuckDuckGo
    if settings.USE_DUCKDUCKGO_FALLBACK:
        return _search_duckduckgo(query, limit)

    return []


# ── Tavily ────────────────────────────────────────────────────────────────────

def _search_tavily(
    query: str,
    max_results: int,
    include_domains: Optional[list[str]] = None,
) -> list[dict]:
    """Use Tavily AI search API."""
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        kwargs: dict = {
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False,
        }
        if include_domains:
            kwargs["include_domains"] = include_domains

        response = client.search(**kwargs)
        results = []
        for item in response.get("results", []):
            results.append(_normalize_web_result(item, source="Tavily"))

        logger.info("Tavily returned %d results for: %s", len(results), query)
        return results

    except ImportError:
        logger.warning("tavily-python not installed; falling back to DuckDuckGo")
        return []
    except Exception as exc:
        logger.error("Tavily search failed: %s", exc)
        return []


# ── DuckDuckGo ────────────────────────────────────────────────────────────────

def _search_duckduckgo(query: str, max_results: int) -> list[dict]:
    """Use DuckDuckGo Search as a free fallback."""
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for item in ddgs.text(
                query,
                max_results=max_results,
                safesearch="moderate",
            ):
                results.append(_normalize_web_result(item, source="DuckDuckGo"))

        logger.info("DuckDuckGo returned %d results for: %s", len(results), query)
        return results

    except ImportError:
        logger.warning("duckduckgo-search not installed; no web results")
        return []
    except Exception as exc:
        logger.error("DuckDuckGo search failed: %s", exc)
        return []


# ── Normalizer ────────────────────────────────────────────────────────────────

def _normalize_web_result(item: dict, source: str) -> dict:
    """Convert a raw Tavily / DDG result dict to the common paper schema."""
    title = item.get("title", "")
    url = item.get("url", item.get("href", ""))
    snippet = item.get("content", item.get("body", ""))
    score = item.get("score", 0.0)

    return {
        "title": title,
        "authors": [],
        "year": None,
        "published_date": item.get("published_date", ""),
        "abstract": snippet,
        "url": url,
        "pdf_url": "",
        "doi": "",
        "source": source,
        "venue": _extract_domain(url),
        "citation_count": None,
        "relevance_score": float(score) if score else 0.0,
        "raw": item,
    }


def _extract_domain(url: str) -> str:
    """Extract bare domain from a URL."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""
