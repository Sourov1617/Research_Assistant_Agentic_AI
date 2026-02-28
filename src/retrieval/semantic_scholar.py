"""
Semantic Scholar Retriever
Uses the public Semantic Scholar Graph API (free, optional key for higher limits).
Docs: https://api.semanticscholar.org/graph/v1
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from config import settings

logger = logging.getLogger(__name__)

_FIELDS = (
    "title,authors,year,abstract,citationCount,url,externalIds,"
    "publicationDate,venue,openAccessPdf,fieldsOfStudy"
)


def search_semantic_scholar(
    query: str,
    max_results: Optional[int] = None,
    offset: int = 0,
) -> list[dict]:
    """
    Search Semantic Scholar and return normalized paper dicts.
    Results are sorted by relevance; year-based re-ranking happens in the ranker.
    offset — number of results to skip (for fetch-more pagination).
    """
    limit = min(max_results or settings.MAX_PAPERS_PER_SOURCE, 100)
    results = []

    headers = {"Accept": "application/json"}
    if settings.SEMANTIC_SCHOLAR_API_KEY and "your_" not in settings.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

    params = {
        "query": query,
        "limit": limit,
        "offset": offset,
        "fields": _FIELDS,
    }

    try:
        url = f"{settings.SEMANTIC_SCHOLAR_BASE_URL}/paper/search"
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for paper in data.get("data", []):
            authors = [a.get("name", "") for a in paper.get("authors", [])]
            external_ids = paper.get("externalIds") or {}
            doi = external_ids.get("DOI", "")
            arxiv_id = external_ids.get("ArXiv", "")
            pdf_url = ""
            if oap := paper.get("openAccessPdf"):
                pdf_url = oap.get("url", "")

            results.append({
                "title": paper.get("title", ""),
                "authors": authors,
                "year": paper.get("year"),
                "published_date": paper.get("publicationDate", ""),
                "abstract": paper.get("abstract", ""),
                "url": paper.get("url", f"https://www.semanticscholar.org/paper/{paper.get('paperId','')}"),
                "pdf_url": pdf_url,
                "doi": doi,
                "source": "Semantic Scholar",
                "venue": paper.get("venue", ""),
                "fields_of_study": paper.get("fieldsOfStudy") or [],
                "citation_count": paper.get("citationCount", 0),
                "relevance_score": 0.0,
                "raw": {
                    "paper_id": paper.get("paperId"),
                    "arxiv_id": arxiv_id,
                },
            })

    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            logger.warning("Semantic Scholar rate limit hit — waiting 5s")
            time.sleep(5)
        else:
            logger.error("Semantic Scholar HTTP error: %s", exc)
    except Exception as exc:
        logger.error("Semantic Scholar search failed: %s", exc)

    logger.info("Semantic Scholar returned %d results for: %s", len(results), query)
    return results


def get_paper_details(paper_id: str) -> dict:
    """Fetch detailed metadata for a single Semantic Scholar paper by ID."""
    headers = {"Accept": "application/json"}
    if settings.SEMANTIC_SCHOLAR_API_KEY and "your_" not in settings.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

    try:
        url = f"{settings.SEMANTIC_SCHOLAR_BASE_URL}/paper/{paper_id}"
        resp = requests.get(url, params={"fields": _FIELDS}, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Failed to fetch Semantic Scholar paper %s: %s", paper_id, exc)
        return {}
