"""
CORE API Retriever — search CORE open-access repository.
Register for a free API key at https://core.ac.uk/services/api
Key is optional for low-volume use.
Docs: https://api.core.ac.uk/docs/v3
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from config import settings

logger = logging.getLogger(__name__)


def search_core(
    query: str,
    max_results: Optional[int] = None,
    offset: int = 0,
) -> list[dict]:
    """
    Search CORE for open-access papers and return normalized paper dicts.
    offset — number of results to skip (for fetch-more pagination).
    """
    limit = min(max_results or settings.MAX_PAPERS_PER_SOURCE, 100)

    if not settings.CORE_API_KEY or "your_" in settings.CORE_API_KEY:
        logger.warning(
            "CORE_API_KEY not configured — skipping CORE retrieval. "
            "Get a free key at https://core.ac.uk/services/api"
        )
        return []

    headers = {
        "Authorization": f"Bearer {settings.CORE_API_KEY}",
        "Accept": "application/json",
    }
    payload = {
        "q": query,
        "limit": limit,
        "offset": offset,
        "sort": "recency",
    }

    results = []
    try:
        url = f"{settings.CORE_BASE_URL}/search/works"
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("results", []):
            authors = [
                a.get("name", "") for a in (item.get("authors") or [])
            ]
            year = None
            if pub_date := item.get("publishedDate") or item.get("yearPublished"):
                try:
                    year = int(str(pub_date)[:4])
                except (ValueError, TypeError):
                    year = None

            doi = item.get("doi", "") or ""
            url_item = (
                item.get("downloadUrl")
                or item.get("sourceFulltextUrls", [None])[0]
                or (f"https://doi.org/{doi}" if doi else "")
                or f"https://core.ac.uk/works/{item.get('id','')}"
            )

            results.append({
                "title": item.get("title", "Untitled"),
                "authors": authors,
                "year": year,
                "published_date": str(item.get("publishedDate", "")),
                "abstract": item.get("abstract", ""),
                "url": url_item,
                "pdf_url": item.get("downloadUrl", ""),
                "doi": doi,
                "source": "CORE",
                "venue": item.get("journals", [{}])[0].get("title", "") if item.get("journals") else "",
                "citation_count": None,
                "relevance_score": 0.0,
                "raw": {
                    "core_id": item.get("id"),
                    "language": item.get("language"),
                },
            })

    except Exception as exc:
        logger.error("CORE search failed for '%s': %s", query, exc)

    logger.info("CORE returned %d results for: %s", len(results), query)
    return results
