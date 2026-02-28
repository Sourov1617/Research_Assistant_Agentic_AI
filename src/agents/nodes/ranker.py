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

    # Split keywords into two pools:
    #   topic_kws   — what the paper must be ABOUT (application domain, subject)
    #   method_kws  — techniques it should USE (model names, optimizers, algorithms)
    #
    # This split allows two-tier scoring: topic match is a gate (papers that
    # don't cover the subject domain at all are capped near zero regardless
    # of how many method terms they contain), method match is an additive boost.
    topic_kws = list(dict.fromkeys(
        k.lower() for k in (
            intent.get("topic_keywords", [])
            + ([intent.get("primary_topic", "")] if intent.get("primary_topic") else [])
            + ([intent.get("application_area", "")] if intent.get("application_area") else [])
            + intent.get("platforms", [])
            + intent.get("sub_domains", [])
        )
        if k
    ))
    method_kws = list(dict.fromkeys(
        k.lower() for k in (
            intent.get("method_keywords", [])
            + intent.get("named_models", [])
            + intent.get("named_optimizers", [])
            + intent.get("methods", [])
            + intent.get("discriminating_terms", [])
            + intent.get("keywords", [])
            + plan.get("primary_keywords", [])
        )
        if k
    ))

    date_filter_year = plan.get("date_filter_year", 0)
    max_ranked = settings.MAX_RANKED_PAPERS
    min_score = settings.MIN_RELEVANCE_SCORE

    scored = []
    for paper in papers:
        score = _score_paper(paper, topic_kws, method_kws, date_filter_year)
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

def _score_paper(paper: dict, topic_kws: list[str], method_kws: list[str], date_filter_year: int) -> float:
    weights = {
        "relevance":   0.55,   # increased — topic+method relevance is the primary signal
        "recency":     0.20,   # decreased — don't let new-but-irrelevant papers win
        "citations":   0.15,   # decreased — don't let old famous papers crowd out on-topic papers
        "credibility": 0.10,
    }

    relevance   = _keyword_relevance(paper, topic_kws, method_kws)

    # Hard gate: _keyword_relevance returns 0.04 as the "off-topic" sentinel.
    # Short-circuit here so recency + citations + credibility cannot compensate.
    # 0.04 < MIN_RELEVANCE_SCORE (0.05) → paper is always filtered out.
    if relevance <= 0.04 and topic_kws:
        return relevance

    recency     = _recency_score(paper.get("year"), date_filter_year)
    citations   = _citation_score(paper.get("citation_count"))
    credibility = SOURCE_CREDIBILITY.get(paper.get("source", ""), 0.5)

    score = (
        weights["relevance"]   * relevance
        + weights["recency"]     * recency
        + weights["citations"]   * citations
        + weights["credibility"] * credibility
    )
    return min(score, 1.0)


def _keyword_relevance(paper: dict, topic_kws: list[str], method_kws: list[str]) -> float:
    """
    Two-tier relevance scoring.

    Tier 1 — TOPIC GATE (65% of score):
        Does the paper cover the required subject/application domain?
        If ZERO topic terms match the paper is Off-Topic and capped at 0.04 —
        it will fall below MIN_RELEVANCE_SCORE and be filtered out.
        This prevents generic DL papers from outranking on-topic papers that
        happen to match fewer method keywords.

    Tier 2 — METHOD BOOST (35% of score):
        How many of the requested techniques (models, optimizers) does the
        paper mention?  Adds on top of the topic score.

    When no topic keywords are available (e.g. simple keyword query / fallback
    intent) we fall back to treating all keywords equally.
    """
    text = " ".join([
        str(paper.get("title") or ""),
        str(paper.get("abstract") or ""),
        " ".join(str(a) for a in (paper.get("authors") or [])),
    ]).lower()

    # ── Tier 1: topic gate ────────────────────────────────────────────────────
    if topic_kws:
        topic_hits = sum(
            1 for kw in topic_kws
            if re.search(r"\b" + re.escape(kw) + r"\b", text)
        )
        topic_score = topic_hits / len(topic_kws)

        # Hard gate: zero topic matches → off-topic, nearly zero relevance.
        # The paper might be technically excellent but it's about the wrong subject.
        if topic_hits == 0:
            return 0.04
    else:
        # No topic information — fall back to flat keyword scoring
        all_kws = list(dict.fromkeys(topic_kws + method_kws))
        if not all_kws:
            return 0.5
        hits = sum(1 for kw in all_kws if re.search(r"\b" + re.escape(kw) + r"\b", text))
        return min(hits / len(all_kws), 1.0)

    # ── Tier 2: method boost ──────────────────────────────────────────────────
    if method_kws:
        method_hits = sum(
            1 for kw in method_kws
            if re.search(r"\b" + re.escape(kw) + r"\b", text)
        )
        method_score = min(method_hits / len(method_kws), 1.0)
    else:
        method_score = topic_score  # no method info → use topic score only

    # Topic is primary (65%), methods are secondary (35%)
    return min(topic_score * 0.65 + method_score * 0.35, 1.0)


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
