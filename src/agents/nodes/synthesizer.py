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
    )
    chain = _SYNTH_PROMPT | llm | JsonOutputParser()

    synthesized = []
    total = len(papers)

    for i, paper in enumerate(papers):
        logger.info("Synthesizing paper %d/%d: %s", i + 1, total,
                    (paper.get("title") or "")[:60])
        try:
            abstract = (paper.get("abstract") or "")[:1500]
            if not abstract:
                abstract = "No abstract available."

            synthesis = chain.invoke({
                "title": paper.get("title", ""),
                "authors": ", ".join(str(a) for a in (paper.get("authors") or [])[:5]),
                "year": paper.get("year", "Unknown"),
                "source": paper.get("source", ""),
                "abstract": abstract,
                "research_context": research_context,
            })
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
