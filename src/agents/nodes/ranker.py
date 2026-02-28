"""
Ranker Node
Scores and ranks retrieved papers using a multi-factor heuristic:
  • Relevance to query keywords (TF-IDF-like keyword overlap)
  • Recency (year — newest scores highest)
  • Citation influence (log-normalised)
  • Venue/source credibility
  • Availability of abstract (quality signal)
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.state import ResearchState

from config import settings

logger = logging.getLogger(__name__)

CURRENT_YEAR = datetime.now().year

# Credibility weights per source
SOURCE_CREDIBILITY = {
    # Curated academic databases
    "Semantic Scholar": 0.95,
    "arXiv": 0.90,
    "CrossRef": 0.88,
    "CORE": 0.85,
    # Top-tier journals / publishers (web-scraped)
    "IEEE Xplore": 0.95,
    "Elsevier": 0.93,
    "ScienceDirect": 0.93,
    "Nature": 0.97,
    "Springer": 0.92,
    "MDPI": 0.88,
    "ACM Digital Library": 0.93,
    "PubMed": 0.92,
    "OpenReview": 0.91,  # NeurIPS / ICLR / ICML pre-prints with reviews
    # Conference proceedings (web-scraped)
    "CVPR": 0.94,
    "NeurIPS": 0.96,
    "ICML": 0.95,
    "AAAI": 0.93,
    "ICCV": 0.94,
    # Generic web search fallbacks
    "Tavily": 0.60,
    "DuckDuckGo": 0.50,
}

# Recency decay — full score for current year, decays linearly
MAX_YEAR_SCORE = 1.0
YEAR_DECAY_PER_YEAR = 0.08  # lose 8% per year of age


def rank_sources_node(state: "ResearchState") -> "ResearchState":
    """
    LangGraph node: score and rank all retrieved papers.
    Updates state keys: ranked_papers.
    """
    papers = state.get("papers", [])
    intent = state.get("parsed_intent", {})
    plan = state.get("search_plan", {})

    if not papers:
        return {**state, "ranked_papers": [],
                "status_message": "⚠️ No papers to rank."}

    keywords = intent.get("keywords", [])
    keywords += plan.get("primary_keywords", [])
    keywords = list(dict.fromkeys(k.lower() for k in keywords if k))

    date_filter_year = plan.get("date_filter_year", 0)
    max_ranked = settings.MAX_RANKED_PAPERS
    min_score = settings.MIN_RELEVANCE_SCORE

    scored = []
    for paper in papers:
        score = _score_paper(paper, keywords, date_filter_year)
        paper["relevance_score"] = round(score, 4)
        scored.append(paper)

    # Sort by composite score descending, then by year descending
    scored.sort(
        key=lambda p: (p["relevance_score"], p.get("year") or 0),
        reverse=True,
    )

    # Apply minimum relevance filter
    ranked = [p for p in scored if p["relevance_score"] >= min_score]
    ranked = ranked[:max_ranked]

    logger.info("Ranked %d papers (from %d total)", len(ranked), len(papers))

    return {
        **state,
        "ranked_papers": ranked,
        "status_message": f"📊 Ranked **{len(ranked)}** most relevant papers",
    }


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score_paper(paper: dict, keywords: list[str], date_filter_year: int) -> float:
    weights = {
        "relevance": 0.40,
        "recency": 0.30,
        "citations": 0.20,
        "credibility": 0.10,
    }

    relevance = _keyword_relevance(paper, keywords)
    recency = _recency_score(paper.get("year"), date_filter_year)
    citations = _citation_score(paper.get("citation_count"))
    credibility = SOURCE_CREDIBILITY.get(paper.get("source", ""), 0.5)

    score = (
        weights["relevance"] * relevance
        + weights["recency"] * recency
        + weights["citations"] * citations
        + weights["credibility"] * credibility
    )
    return min(score, 1.0)


def _keyword_relevance(paper: dict, keywords: list[str]) -> float:
    if not keywords:
        return 0.5

    text = " ".join([
        str(paper.get("title") or ""),
        str(paper.get("abstract") or ""),
        " ".join(str(a) for a in (paper.get("authors") or [])),
    ]).lower()

    matches = sum(1 for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", text))
    return min(matches / max(len(keywords), 1), 1.0)


def _recency_score(year, date_filter_year: int) -> float:
    if not year:
        return 0.3
    try:
        year = int(year)
    except (ValueError, TypeError):
        return 0.3

    age = CURRENT_YEAR - year
    if age < 0:
        return MAX_YEAR_SCORE  # future date — likely correct

    score = MAX_YEAR_SCORE - age * YEAR_DECAY_PER_YEAR
    # Bonus for papers at or after the date filter
    if date_filter_year and year >= date_filter_year:
        score += 0.1
    return max(0.0, min(score, MAX_YEAR_SCORE))


def _citation_score(citation_count) -> float:
    if citation_count is None:
        return 0.5  # neutral for unknown
    try:
        count = int(citation_count)
    except (ValueError, TypeError):
        return 0.5
    if count <= 0:
        return 0.05
    # log-normalise: 1000 citations → ~1.0
    return min(math.log1p(count) / math.log1p(1000), 1.0)
