"""
CrossRef Retriever — search CrossRef REST API.
Free to use; provide an email in .env (CROSSREF_EMAIL) to join the
"polite pool" for higher rate limits.
Docs: https://api.crossref.org/swagger-ui/index.html
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from config import settings

logger = logging.getLogger(__name__)


def search_crossref(
    query: str,
    max_results: Optional[int] = None,
    offset: int = 0,
) -> list[dict]:
    """
    Search CrossRef by free-text query and return normalized paper dicts.
    offset — number of results to skip (for fetch-more pagination).
    """
    limit = min(max_results or settings.MAX_PAPERS_PER_SOURCE, 100)
    results = []

    params: dict = {
        "query": query,
        "rows": limit,
        "offset": offset,
        "sort": "relevance",
        "select": (
            "DOI,title,author,published,abstract,URL,"
            "container-title,is-referenced-by-count,type,resource"
        ),
    }
    if settings.CROSSREF_EMAIL and "your_" not in settings.CROSSREF_EMAIL:
        params["mailto"] = settings.CROSSREF_EMAIL

    try:
        resp = requests.get(settings.CROSSREF_BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])

        for item in items:
            title_list = item.get("title", [])
            title = title_list[0] if title_list else "Untitled"

            raw_authors = item.get("author", [])
            authors = [
                f"{a.get('given','')} {a.get('family','')}".strip()
                for a in raw_authors
            ]

            pub = item.get("published", {})
            date_parts = pub.get("date-parts", [[None]])[0]
            year = date_parts[0] if date_parts else None

            container = item.get("container-title", [])
            venue = container[0] if container else ""

            doi = item.get("DOI", "")
            url = item.get("URL", f"https://doi.org/{doi}" if doi else "")

            abstract = item.get("abstract", "")
            # Strip JATS XML tags if present
            if "<" in abstract:
                import re
                abstract = re.sub(r"<[^>]+>", "", abstract).strip()

            results.append({
                "title": title,
                "authors": authors,
                "year": year,
                "published_date": "-".join(str(p) for p in date_parts if p),
                "abstract": abstract,
                "url": url,
                "pdf_url": "",
                "doi": doi,
                "source": "CrossRef",
                "venue": venue,
                "citation_count": item.get("is-referenced-by-count", 0),
                "relevance_score": 0.0,
                "raw": {
                    "type": item.get("type"),
                    "resource": item.get("resource", {}),
                },
            })

    except Exception as exc:
        logger.error("CrossRef search failed for '%s': %s", query, exc)

    logger.info("CrossRef returned %d results for: %s", len(results), query)
    return results
