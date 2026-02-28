"""
arXiv Retriever — search arXiv preprint server.
Uses the official arXiv API (free, no key required).
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import arxiv

from config import settings

logger = logging.getLogger(__name__)

# arXiv category shortcuts often used in research
ARXIV_CATEGORIES = {
    "cs.AI", "cs.CV", "cs.LG", "cs.CL", "cs.RO",
    "eess.IV", "stat.ML", "q-bio.QM",
}


def search_arxiv(
    query: str,
    max_results: Optional[int] = None,
    offset: int = 0,
    sort_by: arxiv.SortCriterion = arxiv.SortCriterion.SubmittedDate,
) -> list[dict]:
    """
    Search arXiv and return a list of normalized paper dicts.

    Parameters
    ----------
    query : str
        Free-text or keyword search query.
    max_results : int, optional
        Number of results (defaults to ARXIV_MAX_RESULTS in .env).
    offset : int
        Number of results to skip (for fetch-more pagination).
    sort_by : arxiv.SortCriterion
        Sort order — default is newest first.
    """
    limit = max_results or settings.ARXIV_MAX_RESULTS
    # To skip `offset` results we request `limit + offset` total and slice.
    fetch_total = limit + offset
    results = []

    try:
        client = arxiv.Client(num_retries=3, delay_seconds=1)
        search = arxiv.Search(
            query=query,
            max_results=fetch_total,
            sort_by=sort_by,
            sort_order=arxiv.SortOrder.Descending,
        )
        papers = list(client.results(search))[offset:]

        for paper in papers:
            authors = [str(a) for a in paper.authors]
            results.append({
                "title": paper.title,
                "authors": authors,
                "year": paper.published.year if paper.published else None,
                "published_date": str(paper.published.date()) if paper.published else None,
                "abstract": paper.summary,
                "url": paper.entry_id,
                "pdf_url": paper.pdf_url,
                "doi": paper.doi or "",
                "source": "arXiv",
                "categories": paper.categories,
                "citation_count": None,  # arXiv doesn't expose citation counts
                "relevance_score": 0.0,   # filled by ranker
                "raw": {
                    "arxiv_id": paper.entry_id.split("/")[-1],
                    "journal_ref": paper.journal_ref,
                    "comment": paper.comment,
                },
            })

    except Exception as exc:
        logger.error("arXiv search failed for query '%s': %s", query, exc)

    logger.info("arXiv returned %d results for: %s", len(results), query)
    return results
