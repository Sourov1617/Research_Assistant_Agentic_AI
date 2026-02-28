"""
Research Retriever Node
Executes the search plan across all configured sources concurrently.
ONE query per source — precise and rate-limit-friendly.

Key design choices:
- All source threads run in parallel and share a single wall-clock deadline,
  so the total retrieval time is bounded by thread_timeout (not n × timeout).
- A stop_event (threading.Event) passed from the UI is checked during joins,
  allowing immediate cancellation when the user clicks Stop.
- Web-based journal sources tag results with their proper publisher name so the
  ranker can apply accurate credibility scores.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.state import ResearchState

from config import settings
from src.retrieval.arxiv_retriever import search_arxiv
from src.retrieval.semantic_scholar import search_semantic_scholar
from src.retrieval.crossref_retriever import search_crossref
from src.retrieval.core_retriever import search_core
from src.retrieval.web_retriever import search_web

logger = logging.getLogger(__name__)

# Source name → retrieval function mapping
_SOURCE_FN_MAP = {
    # Structured academic APIs
    "arxiv":            search_arxiv,
    "semantic_scholar": search_semantic_scholar,
    "crossref":         search_crossref,
    "core":             search_core,
    # Journal / publisher web sources (all via search_web with site: operators)
    "ieee_web":          search_web,
    "sciencedirect_web": search_web,
    "mdpi_web":          search_web,
    "nature_web":        search_web,
    "acm_web":           search_web,
    "springer_web":      search_web,
    "pubmed_web":        search_web,
    "openreview_web":    search_web,
    # Generic web fallback (legacy key)
    "web":               search_web,
}

# Semantic Scholar rate-limit buffer (skip in fast mode)
_RATE_LIMIT_DELAY = {
    "semantic_scholar": 1.0,
}

# Sources that are silently skipped when their API key is a placeholder / missing.
_WEB_SOURCES = frozenset({
    "ieee_web", "sciencedirect_web", "mdpi_web", "nature_web",
    "acm_web", "springer_web", "pubmed_web", "openreview_web", "web",
})


def _is_source_configured(src_name: str) -> bool:
    """
    Return False when a source needs an API key that hasn't been configured.
    These sources are silently skipped so the pipeline never stalls waiting on
    an unauthenticated call that will fail or hang.
    """
    if src_name == "core":
        k = settings.CORE_API_KEY
        return bool(k) and "your_" not in k and k.strip() != ""
    # Web sources work with either Tavily (key required) or the DuckDuckGo
    # fallback (no key needed).  Both paths have hard timeouts, so they are
    # always "configured" from a pipeline-safety perspective.
    # All other sources (arxiv, semantic_scholar, crossref) work without a key.
    return True


# Source label override for web results — used by ranker SOURCE_CREDIBILITY
_WEB_SOURCE_LABELS = {
    "ieee_web":          "IEEE Xplore",
    "sciencedirect_web": "ScienceDirect",
    "mdpi_web":          "MDPI",
    "nature_web":        "Nature",
    "acm_web":           "ACM Digital Library",
    "springer_web":      "Springer",
    "pubmed_web":        "PubMed",
    "openreview_web":    "OpenReview",
}


def retrieve_papers_node(state: "ResearchState") -> "ResearchState":
    """
    LangGraph node: run all enabled sources in parallel, bounded by a single
    wall-clock deadline so total retrieval time ≤ thread_timeout regardless of
    how many sources are active.  Respects an optional stop_event for instant
    user-initiated cancellation.
    """
    plan = state.get("search_plan", {})
    sources_cfg = plan.get("sources", {})
    year_after = plan.get("year_after", 0)
    year_max = plan.get("year_max") or state.get("year_max")
    limit = settings.MAX_PAPERS_PER_SOURCE
    fast_mode = bool(state.get("fast_mode", False))
    stop_event = state.get("_stop_event")  # threading.Event or None

    # Single wall-clock budget for ALL parallel threads.
    # Increased to 45s (normal) to accommodate the _DDGS_SEMAPHORE in
    # web_retriever which may queue a thread briefly before it can proceed.
    thread_timeout = 15 if fast_mode else 45

    all_papers: list[dict] = []
    lock = threading.Lock()
    threads: list[threading.Thread] = []
    errors: list[str] = []
    source_counts: dict[str, int] = {}

    def _run(src_name: str, fn, query: str, fallback_query: str = ""):
        # Small delay for rate-limited sources (skip in fast mode)
        delay = 0.0 if fast_mode else _RATE_LIMIT_DELAY.get(src_name, 0)
        if delay:
            # Check stop_event during the delay so we abort immediately
            if stop_event and stop_event.wait(timeout=delay):
                return
            else:
                time.sleep(delay)

        # Check stop before starting the (potentially slow) network call
        if stop_event and stop_event.is_set():
            return

        results = []
        try:
            results = fn(query, max_results=limit)
        except Exception as exc:
            logger.warning("Source '%s' primary query failed: %s", src_name, exc)
            with lock:
                errors.append(f"{src_name}: {exc}")

        # Sequential topic-query fallback: run only when primary returned nothing.
        # This avoids doubling the number of concurrent DDGS calls (which causes
        # rate-limiting) while still fetching on-topic results when the
        # method-specific primary query is too narrow.
        if not results and fallback_query and fallback_query.strip() != query.strip():
            if stop_event and stop_event.is_set():
                return
            try:
                results = fn(fallback_query, max_results=limit)
                if results:
                    logger.info("Source '%s': fallback query returned %d results",
                                src_name, len(results))
            except Exception as exc:
                logger.warning("Source '%s' fallback query failed: %s", src_name, exc)

        if not results:
            return

        with lock:
            label = _WEB_SOURCE_LABELS.get(src_name)
            if label:
                for r in results:
                    r["source"] = label
            all_papers.extend(results)
            source_counts[src_name] = len(results)
        logger.info("Source '%s': %d results", src_name, len(results))

    # Start all threads concurrently
    for src_name, src_cfg in sources_cfg.items():
        if not isinstance(src_cfg, dict) or not src_cfg.get("enabled", False):
            continue
        fn = _SOURCE_FN_MAP.get(src_name)
        if fn is None:
            continue
        # Skip sources whose API key is not configured — avoids dead hangs
        if not _is_source_configured(src_name):
            logger.info("Skipping source '%s': API key not configured.", src_name)
            continue
        query = src_cfg.get("query") or ""
        if not query:
            legacy = src_cfg.get("queries", [])
            query = legacy[0] if legacy else state.get("query", "")
        if not query:
            continue

        topic_query = src_cfg.get("topic_query") or ""
        t = threading.Thread(
            target=_run,
            args=(src_name, fn, query, topic_query),
            daemon=True,
        )
        threads.append(t)
        t.start()

        # topic_query is run as a SEQUENTIAL fallback inside the same thread,
        # not as an extra parallel thread.  Firing 16 simultaneous DDGS calls
        # (8 sources × 2 queries) saturates the DuckDuckGo backend and causes
        # "No results found" on every call.  Instead we fire one thread per
        # source, and that thread tries the topic_query only when the main
        # query returns nothing.  This is handled inside the _run_with_fallback
        # wrapper below.

    # ── Single wall-clock deadline join ───────────────────────────────────────
    # All threads share ONE deadline instead of each getting a fresh timeout.
    # This ensures total retrieval time ≤ thread_timeout regardless of thread count.
    deadline = time.monotonic() + thread_timeout
    for t in threads:
        # Also abort early if stop has been requested
        if stop_event and stop_event.is_set():
            logger.info("Stop requested — aborting retrieval joins early")
            break
        remaining = max(0.0, deadline - time.monotonic())
        if remaining == 0.0:
            break
        t.join(timeout=remaining)

    # ── Deduplication ─────────────────────────────────────────────────────────
    seen: set[str] = set()
    unique: list[dict] = []
    for p in all_papers:
        key = (p.get("title") or "").lower().strip()[:100]
        if key and key not in seen:
            seen.add(key)
            unique.append(p)

    # ── Year filtering ────────────────────────────────────────────────────────
    if year_after:
        unique = [p for p in unique
                  if not p.get("year") or int(p.get("year") or 0) >= year_after]
    if year_max:
        unique = [p for p in unique
                  if not p.get("year") or int(p.get("year") or 0) <= year_max]

    active_src = len([k for k, v in source_counts.items() if v > 0])
    logger.info("Retrieval complete: %d unique papers from %d/%d active sources",
                len(unique), active_src, len(threads))

    status = (f"\U0001f50d Retrieved **{len(unique)}** unique papers "
              f"from {active_src} source(s)")
    if errors:
        status += f" ({len(errors)} error(s))"

    return {
        **state,
        "papers": unique,
        "status_message": status,
    }
