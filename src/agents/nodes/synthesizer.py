"""
Paper Synthesizer Node
For each ranked paper, generates a structured synthesis using the LLM:
  • 3-5 line summary
  • methodology used
  • key contribution
  • limitations / drawbacks
  • future scope
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
from typing import TYPE_CHECKING

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

if TYPE_CHECKING:
    from src.agents.state import ResearchState

from config import settings

logger = logging.getLogger(__name__)

_SYNTH_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a research synthesis expert. Analyze the given paper metadata and abstract,
then produce a concise structured analysis.

Return ONLY a valid JSON object:
{{
  "summary": "3-5 sentences describing the core idea, approach, and findings",
  "methodology": "specific techniques, algorithms, architectures, or methods used",
  "contribution": "what is novel or unique about this work",
  "limitations": "dataset limitations, computational costs, generalization issues, etc.",
  "future_scope": "what remains unsolved or what the authors suggest as next steps"
}}

If information is unavailable, state "Not specified in abstract." Be specific and technical.""",
    ),
    (
        "human",
        """Paper to analyze:
Title: {title}
Authors: {authors}
Year: {year}
Source: {source}
Abstract: {abstract}

Research context: {research_context}

Return only the JSON object.""",
    ),
])


def synthesize_papers_node(state: "ResearchState") -> "ResearchState":
    """
    LangGraph node: generate structured synthesis for each ranked paper.
    Updates state keys: synthesized_papers.
    """
    from src.models.llm_factory import get_llm

    papers = state.get("ranked_papers", [])
    if not papers:
        return {**state, "synthesized_papers": [],
                "status_message": "⚠️ No papers to synthesize."}

    intent = state.get("parsed_intent", {})
    research_context = (
        f"Domain: {intent.get('domain', 'N/A')}. "
        f"Problem: {intent.get('problem_statement', state.get('query', ''))[:200]}"
    )

    llm = get_llm(
        provider=state.get("llm_provider"),
        model=state.get("llm_model"),
        temperature=state.get("llm_temperature"),
    )
    chain = _SYNTH_PROMPT | llm | JsonOutputParser()

    synthesized = []
    total = len(papers)
    stop_event = state.get("_stop_event")
    _q = state.get("_agent_queue")

    # Per-paper LLM timeout — generous for slow/large models, but
    # still lets stop_event abort cleanly mid-synthesis.
    _SYNTH_TIMEOUT = 120  # seconds per paper

    for i, paper in enumerate(papers):
        # Respect user-initiated stop — return whatever has been synthesized so far
        if stop_event and stop_event.is_set():
            logger.info("Synthesis stopped early by user after %d/%d papers", i, total)
            break

        logger.info("Synthesizing paper %d/%d: %s", i + 1, total,
                    (paper.get("title") or "")[:60])
        if _q:
            _q.put({"_type": "interim",
                    "status_message": f"🧪 Synthesising paper {i + 1}/{total}: "
                                      f"{(paper.get('title') or '')[:50]}…"})
        try:
            abstract = (paper.get("abstract") or "")[:1500]
            if not abstract:
                abstract = "No abstract available."

            payload = {
                "title": paper.get("title", ""),
                "authors": ", ".join(str(a) for a in (paper.get("authors") or [])[:5]),
                "year": paper.get("year", "Unknown"),
                "source": paper.get("source", ""),
                "abstract": abstract,
                "research_context": research_context,
            }

            # Run in a thread so stop_event can interrupt a hanging LLM call.
            # Use shutdown(wait=False) instead of 'with' context manager so a
            # timed-out thread is discarded immediately rather than blocking.
            ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = ex.submit(chain.invoke, payload)
            synthesis = None
            stop_fired = False
            try:
                remaining = _SYNTH_TIMEOUT
                while remaining > 0:
                    if stop_event and stop_event.is_set():
                        logger.info("Synthesis cancelled mid-paper by stop_event.")
                        synthesized.append({**paper, "synthesis": _fallback_synthesis(paper)})
                        stop_fired = True
                        break
                    try:
                        synthesis = future.result(timeout=min(1.0, remaining))
                        break
                    except concurrent.futures.TimeoutError:
                        remaining -= 1.0
                if synthesis is None and not stop_fired:
                    logger.warning("Synthesis timed out for paper %d — using fallback.", i + 1)
                    synthesis = _fallback_synthesis(paper)
            finally:
                ex.shutdown(wait=False)  # never block on a hung LLM thread
            if stop_fired:
                break  # exit paper loop
        except Exception as exc:
            logger.warning("Synthesis failed for paper %d: %s", i + 1, exc)
            synthesis = _fallback_synthesis(paper)

        enriched_paper = {**paper, "synthesis": synthesis}
        synthesized.append(enriched_paper)

    logger.info("Synthesized %d papers", len(synthesized))

    return {
        **state,
        "synthesized_papers": synthesized,
        "status_message": f"🧠 Synthesized **{len(synthesized)}** papers",
    }


def _fallback_synthesis(paper: dict) -> dict:
    """Generate minimal synthesis when LLM fails."""
    abstract = (paper.get("abstract") or "")[:300]
    return {
        "summary": abstract or "No abstract available.",
        "methodology": "Not specified.",
        "contribution": "See original paper for details.",
        "limitations": "Not available.",
        "future_scope": "Not specified.",
    }
