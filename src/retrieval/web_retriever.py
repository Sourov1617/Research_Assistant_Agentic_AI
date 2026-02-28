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
* site: operators are STRIPPED from queries before passing to DDGS —
  the ddgs 9.x duckduckgo HTML backend scrapes specific XPath selectors that
  break when site: changes the DuckDuckGo response page structure, causing
  "No results found" on every single call.  We strip site: from the query,
  do a general search, then post-filter results by domain URL (best-effort).
  If domain filtering removes all results, the unfiltered results are returned
  so the user always gets something.
* A module-level semaphore caps concurrent DDGS calls at 4 to prevent
  rate-limiting when many web sources are enabled simultaneously.
"""
from __future__ import annotations

import concurrent.futures
import logging
import re
import threading
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Hard outer timeout for the DuckDuckGo fallback.
_DDGS_HARD_TIMEOUT = 20  # seconds

# Max concurrent DDGS calls across ALL threads — prevents rate-limiting when
# many web sources fire simultaneously.
_DDGS_SEMAPHORE = threading.Semaphore(4)


# ── Public entry point ────────────────────────────────────────────────────────

def search_web(
    query: str,
    max_results: Optional[int] = None,
    include_domains: Optional[list[str]] = None,
    offset: int = 0,  # accepted but not used — DuckDuckGo has no offset API
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


# ── DuckDuckGo helpers ────────────────────────────────────────────────────────

def _strip_site_operator(query: str) -> tuple[str, list[str]]:
    """
    Remove ``site:example.com`` fragments from *query*.

    Returns
    -------
    clean_query : str
        The query with all ``site:`` fragments removed and whitespace normalised.
    domains : list[str]
        The domain strings extracted from the ``site:`` operators (e.g.
        ``["ieeexplore.ieee.org"]``).  Used for best-effort post-filtering of
        results after the DDGS call.
    """
    # Match site:<domain> — domain is a run of non-whitespace chars
    site_pattern = re.compile(r'\bsite:\S+', re.IGNORECASE)
    domains = [m.group(0)[5:].lower() for m in site_pattern.finditer(query)]
    clean = site_pattern.sub('', query)
    clean = re.sub(r'\s{2,}', ' ', clean).strip()
    return clean, domains


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
        # Strip site: operator — DDGS duckduckgo backend HTML parser breaks on it
        clean_query, domains = _strip_site_operator(query)
        if not clean_query:
            clean_query = query  # safety: if stripping ate everything, use original

        # Fetch more than needed when we'll domain-filter afterwards
        fetch_limit = max_results * 3 if domains else max_results

        def _ddgs_fetch(q: str, limit: int) -> list:
            """Single DDGS call, returns raw list or [] on any failure."""
            with _DDGS_SEMAPHORE:  # cap concurrent connections
                with DDGS(timeout=10) as ddgs:
                    return ddgs.text(
                        q,
                        max_results=limit,
                        safesearch="moderate",
                        backend="duckduckgo",
                    ) or []

        # --- Attempt 1: full (site:-stripped) query ---
        raw: list = []
        try:
            raw = _ddgs_fetch(clean_query, fetch_limit)
        except Exception as exc:
            no_results = "no results" in str(exc).lower()
            if not no_results:
                logger.warning("DuckDuckGo attempt 1 failed (%s): %s", type(exc).__name__, exc)
            # --- Attempt 2: simplified (first 6 words) ---
            words = clean_query.split()
            simplified = " ".join(words[:6])
            if len(words) > 6:
                try:
                    raw = _ddgs_fetch(simplified, max_results)
                except Exception as exc2:
                    if "no results" not in str(exc2).lower():
                        logger.warning("DuckDuckGo attempt 2 failed: %s", exc2)

        if not raw:
            return []

        # Normalise raw results (field names differ between ddgs versions)
        results = [
            _normalize_web_result(
                {"title":   r.get("title", ""),
                 "url":     r.get("href", r.get("url", "")),
                 "content": r.get("body", r.get("content", "")),
                 "score":   0.0},
                source="DuckDuckGo",
            )
            for r in raw
        ]

        # Best-effort domain filter: keep only results from the target domain(s)
        if domains:
            filtered = [
                r for r in results
                if any(d in (r.get("url") or "").lower() for d in domains)
            ]
            # If the filter removed everything, return unfiltered results
            # (better than nothing — the ranker will score them lower anyway)
            if filtered:
                return filtered[:max_results]

        return results[:max_results]

    # Hard outer deadline — cannot hang longer than _DDGS_HARD_TIMEOUT seconds
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_run)
        try:
            results = future.result(timeout=_DDGS_HARD_TIMEOUT)
            logger.info("DuckDuckGo returned %d results for: %s", len(results), query[:80])
            return results
        except concurrent.futures.TimeoutError:
            logger.warning(
                "DuckDuckGo timed out after %ds for query: %s",
                _DDGS_HARD_TIMEOUT, query[:80],
            )
            return []
        except Exception as exc:
            logger.warning("DuckDuckGo search failed: %s", exc)
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
