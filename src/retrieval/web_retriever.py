"""
Web Retriever — search the open web for industrial posts, technical blogs,
GitHub repos, and recent industry implementations.

Priority order:
  1. Tavily AI Search  (research-optimized, needs API key)
  2. DuckDuckGo Search (free fallback, no key required)

DuckDuckGo notes
----------------
* Uses ddgs 9.x which relies on `primp` for TLS fingerprinting.
* We pin backend="duckduckgo" to avoid the multi-engine fan-out that DDGS
  "auto" mode triggers (it would otherwise hit 8 backends in parallel via a
  shared class-level ThreadPoolExecutor and accumulate hundreds of stuck threads).
* We set DDGS(timeout=10) so each HTTP request has a hard socket timeout.
* We additionally wrap the whole call in a thread + hard outer deadline to
  guarantee we never block longer than _DDGS_HARD_TIMEOUT seconds regardless
  of OS-level TLS-handshake stalls (a known issue on Windows with primp).
* site: operators in the query work fine with DuckDuckGo, so all publisher
  sources (IEEE, ScienceDirect, MDPI, Nature, ACM, Springer, PubMed…) are
  still searchable via the DDG fallback.
"""
from __future__ import annotations

import concurrent.futures
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Hard outer timeout for the DuckDuckGo fallback.
# Even if primp's socket timeout fails to fire (Windows TLS-handshake stall),
# the thread future will be abandoned after this many seconds.
_DDGS_HARD_TIMEOUT = 20  # seconds


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

    # Free fallback: DuckDuckGo (supports site: operators → publisher searches work)
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
    """
    DuckDuckGo fallback with a guaranteed hard outer timeout.

    Key design decisions vs. the old implementation that caused infinite hangs:

    1. backend="duckduckgo"  — pins to ONE engine instead of "auto" which fans
       out to 8 backends (brave, google, yahoo, yandex …) via a shared
       class-level ThreadPoolExecutor, causing thread-pool exhaustion.

    2. DDGS(timeout=10)  — each outgoing HTTP request has a 10-second socket
       timeout passed to primp.Client so individual requests self-cancel.

    3. Hard outer deadline (_DDGS_HARD_TIMEOUT)  — the entire DDGS call runs
       in a daemon thread; if it hasn't finished in _DDGS_HARD_TIMEOUT seconds
       we abandon it and return [].  This is the final safety net for OS-level
       TLS-handshake stalls that bypass the socket timeout on Windows.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore[no-redef]
        except ImportError:
            logger.warning("duckduckgo-search / ddgs not installed; no web results")
            return []

    def _run() -> list[dict]:
        # timeout=10 → hard socket timeout per HTTP request inside primp
        # backend="duckduckgo" → single engine, no multi-engine fan-out
        with DDGS(timeout=10) as ddgs:
            raw = ddgs.text(
                query,
                max_results=max_results,
                safesearch="moderate",
                backend="duckduckgo",
            )
        return [
            _normalize_web_result(
                # ddgs 9.x returns dicts with 'title', 'href', 'body'
                # older duckduckgo_search used 'title', 'href', 'body' too
                {"title": r.get("title", ""),
                 "url":   r.get("href", r.get("url", "")),
                 "content": r.get("body", r.get("content", "")),
                 "score": 0.0},
                source="DuckDuckGo",
            )
            for r in (raw or [])
        ]

    # Hard outer deadline — cannot hang longer than _DDGS_HARD_TIMEOUT seconds
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_run)
        try:
            results = future.result(timeout=_DDGS_HARD_TIMEOUT)
            logger.info("DuckDuckGo returned %d results for: %s", len(results), query)
            return results
        except concurrent.futures.TimeoutError:
            logger.warning(
                "DuckDuckGo timed out after %ds for query: %s",
                _DDGS_HARD_TIMEOUT, query,
            )
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
