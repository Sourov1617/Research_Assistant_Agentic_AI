"""
Research Insight Generator Node
Analyzes all synthesized papers collectively to produce:
  • emerging trends in the field
  • common challenges faced by researchers
  • unexplored research gaps
  • suggested research directions for the user
  • high-level field overview
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
from typing import TYPE_CHECKING

from langchain_core.prompts import ChatPromptTemplate
from src.utils.json_utils import robust_json_parse

if TYPE_CHECKING:
    from src.agents.state import ResearchState

from config import settings

logger = logging.getLogger(__name__)

_INSIGHT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an elite research analyst. You have been given a set of synthesized research papers.
Analyze them collectively and produce a comprehensive research insight report.

Return ONLY valid JSON:
{{
  "overview": "2-3 sentence synthesis of the overall state of this research area",
  "emerging_trends": [
    "trend 1 with evidence from papers",
    "trend 2 ...",
    "trend 3 ..."
  ],
  "common_challenges": [
    "challenge 1 seen across papers",
    "challenge 2 ...",
    "challenge 3 ..."
  ],
  "research_gaps": [
    "gap 1 — what remains unexplored",
    "gap 2 ...",
    "gap 3 ..."
  ],
  "suggested_directions": [
    "specific research direction 1 tailored to user's problem",
    "specific research direction 2 ...",
    "specific research direction 3 ..."
  ],
  "recommended_papers": ["top 3 paper titles from the set to read first"],
  "maturity_level": "emerging|growing|mature|saturated",
  "interdisciplinary_connections": ["related field 1", "related field 2"]
}}""",
    ),
    (
        "human",
        """User's research goal:
{research_goal}

Synthesized papers (summaries):
{papers_json}

Return only the JSON.""",
    ),
])


def generate_insights_node(state: "ResearchState") -> "ResearchState":
    """
    LangGraph node: generate collective research insights from all synthesized papers.
    Updates state keys: insights.
    """
    from src.models.llm_factory import get_llm

    papers = state.get("synthesized_papers") or state.get("ranked_papers", [])
    if not papers:
        return {**state, "insights": {}, "status_message": "⚠️ No papers to generate insights from."}

    intent = state.get("parsed_intent", {})
    research_goal = (
        f"Domain: {intent.get('domain', '')}. "
        f"Problem: {intent.get('problem_statement', state.get('query', ''))[:300]}. "
        f"Constraints: {', '.join(intent.get('constraints', []))}."
    )

    # Build concise paper summaries for the LLM
    paper_summaries = []
    for i, p in enumerate(papers[:12], 1):  # Limit to top 12 to avoid token overflow
        synth = p.get("synthesis", {})
        paper_summaries.append({
            "index": i,
            "title": p.get("title", ""),
            "year": p.get("year"),
            "summary": (synth.get("summary") or (p.get("abstract") or "")[:200]),
            "methodology": synth.get("methodology", ""),
            "contribution": synth.get("contribution", ""),
            "limitations": synth.get("limitations", ""),
        })

    llm = get_llm(
        provider=state.get("llm_provider"),
        model=state.get("llm_model"),
        temperature=state.get("llm_temperature"),
    )
    # Use llm directly (no JsonOutputParser) so we can apply our own
    # trailing-comma-tolerant parser that handles common LLM JSON quirks.
    chain = _INSIGHT_PROMPT | llm
    stop_event = state.get("_stop_event")

    # Push live status immediately.
    _q = state.get("_agent_queue")
    if _q:
        _q.put({"_type": "interim",
                "status_message": "\U0001f52c LLM generating research insights\u2026"})

    # Non-blocking executor so a hung LLM call never freezes the pipeline.
    _INSIGHT_TIMEOUT = 120
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        chain.invoke,
        {"research_goal": research_goal,
         "papers_json": json.dumps(paper_summaries, indent=2)},
    )
    try:
        deadline = _INSIGHT_TIMEOUT
        raw_response = None
        while deadline > 0:
            if stop_event and stop_event.is_set():
                logger.info("Insight generation cancelled by stop_event.")
                executor.shutdown(wait=False)
                return {**state, "insights": _fallback_insights(papers),
                        "status_message": "\U0001f6d1 Search stopped."}
            try:
                raw_response = future.result(timeout=min(1.0, deadline))
                break
            except concurrent.futures.TimeoutError:
                deadline -= 1.0
        else:
            logger.warning("Insight generation timed out after %ss \u2014 using fallback.", _INSIGHT_TIMEOUT)
            insights = _fallback_insights(papers)
            raw_response = None

        if raw_response is not None:
            # raw_response is an AIMessage; extract the text content
            content = getattr(raw_response, "content", "") or str(raw_response)
            insights = robust_json_parse(content)
            if not insights:
                logger.warning("Insight JSON parse returned empty dict — using fallback.")
                insights = _fallback_insights(papers)

    except Exception as exc:
        logger.error("Insight generation failed: %s", exc)
        insights = _fallback_insights(papers)
    finally:
        executor.shutdown(wait=False)  # never block on a hung LLM thread

    logger.info("Insights generated: %d trends, %d gaps",
                len(insights.get("emerging_trends", [])),
                len(insights.get("research_gaps", [])))

    return {
        **state,
        "insights": insights,
        "status_message": "🔬 Research insights generated",
    }


def _fallback_insights(papers: list[dict]) -> dict:
    """Minimal fallback when LLM fails."""
    years = sorted([p.get("year") for p in papers if p.get("year")], reverse=True)
    return {
        "overview": f"Analysis of {len(papers)} papers in this research area.",
        "emerging_trends": ["Recent publications show active research in this area."],
        "common_challenges": ["See individual paper limitations for details."],
        "research_gaps": ["Review the limitations sections of papers for identified gaps."],
        "suggested_directions": ["Consider the most recent papers for current state-of-the-art."],
        "recommended_papers": [p.get("title", "")[:60] for p in papers[:3]],
        "maturity_level": "growing",
        "interdisciplinary_connections": [],
    }
