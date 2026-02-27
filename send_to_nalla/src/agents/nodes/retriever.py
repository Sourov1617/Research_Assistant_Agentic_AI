"""
Research Retriever Node
Executes the search plan across all configured sources concurrently
and aggregates raw paper results.
"""
from __future__ import annotations

import logging
import threading
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


def retrieve_papers_node(state: "ResearchState") -> "ResearchState":
    """
    LangGraph node: run all enabled sources from the search plan in parallel
    and merge results into state['papers'].
    """
    plan = state.get("search_plan", {})
    sources_cfg = plan.get("sources", {})
    limit = settings.MAX_PAPERS_PER_SOURCE

    all_papers: list[dict] = []
    lock = threading.Lock()
    threads = []
    errors: list[str] = []

    def _run(name: str, fn, queries: list[str], extra_kwargs: dict):
        results = []
        for q in queries[:2]:  # max 2 queries per source to control rate limits
            try:
                batch = fn(q, max_results=limit, **extra_kwargs)
                results.extend(batch)
            except Exception as exc:
                logger.error("Source '%s' failed for query '%s': %s", name, q, exc)
                errors.append(f"{name}: {exc}")
        with lock:
            all_papers.extend(results)
        logger.info("Source '%s' contributed %d papers", name, len(results))

    source_map = {
        "arxiv": (search_arxiv, {}),
        "semantic_scholar": (search_semantic_scholar, {}),
        "crossref": (search_crossref, {}),
        "core": (search_core, {}),
        "web": (search_web, {}),
    }

    for src_name, src_cfg in sources_cfg.items():
        if not src_cfg.get("enabled", False):
            continue
        queries = src_cfg.get("queries", [state.get("query", "")])
        if src_name not in source_map:
            continue
        fn, extra = source_map[src_name]
        t = threading.Thread(target=_run, args=(src_name, fn, queries, extra))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=45)  # 45-second per-source timeout

    # Deduplicate by (title lowercase)
    seen_titles: set[str] = set()
    unique_papers = []
    for p in all_papers:
        key = (p.get("title") or "").lower().strip()[:80]
        if key and key not in seen_titles:
            seen_titles.add(key)
            unique_papers.append(p)

    logger.info(
        "Retrieval complete: %d unique papers from %d sources",
        len(unique_papers),
        len(threads),
    )

    status = (
        f"🔍 Retrieved **{len(unique_papers)}** unique papers "
        f"from {len(threads)} sources"
    )
    if errors:
        status += f" ({len(errors)} source error(s))"

    return {
        **state,
        "papers": unique_papers,
        "status_message": status,
    }
