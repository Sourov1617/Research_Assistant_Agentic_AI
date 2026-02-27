"""
Query Parser Node
Transforms a raw user query (keywords / paragraph / abstract) into a
structured research intent dictionary.
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

if TYPE_CHECKING:
    from src.agents.state import ResearchState

logger = logging.getLogger(__name__)

_PARSE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an expert research assistant specializing in academic literature.
Your task is to analyze a user's research query and extract structured intent.

Return ONLY a valid JSON object with the following fields:
{{
  "domain": "primary research domain/field",
  "sub_domains": ["list", "of", "sub-domains"],
  "methods": ["list of techniques/methods mentioned or implied"],
  "constraints": ["resource/hardware/time/data constraints implied"],
  "application_area": "the real-world application or use case",
  "keywords": ["6-12 refined search keywords"],
  "synonyms": {{"keyword": ["synonym1", "synonym2"]}},
  "research_type": "empirical|survey|theoretical|applied",
  "recency_preference": "last_1_year|last_3_years|last_5_years|any",
  "problem_statement": "concise 1-2 sentence problem statement",
  "search_queries": ["3-5 optimized academic search queries"]
}}

Be precise. Infer implicit constraints from context.""",
    ),
    (
        "human",
        "Research query:\n{query}\n\nReturn only the JSON object, no extra text.",
    ),
])


def parse_query_node(state: "ResearchState") -> "ResearchState":
    """
    LangGraph node: parse raw user query → structured research intent.
    Updates state keys: parsed_intent, status_message.
    """
    from src.models.llm_factory import get_llm

    query = state.get("query", "").strip()
    if not query:
        return {**state, "parsed_intent": {}, "status_message": "⚠️ Empty query received."}

    logger.info("Parsing query: %s...", query[:80])

    llm = get_llm(
        provider=state.get("llm_provider"),
        model=state.get("llm_model"),
    )
    chain = _PARSE_PROMPT | llm | JsonOutputParser()

    try:
        intent = chain.invoke({"query": query})
    except Exception as exc:
        logger.error("Query parsing failed: %s", exc)
        intent = _fallback_intent(query)

    logger.info("Parsed intent: domain=%s, keywords=%s",
                intent.get("domain", "N/A"),
                intent.get("keywords", [])[:3])

    return {
        **state,
        "parsed_intent": intent,
        "status_message": f"✅ Query understood: **{intent.get('domain', 'General')}** — "
                          f"{', '.join(intent.get('keywords', [])[:5])}",
    }


# ── Fallback ──────────────────────────────────────────────────────────────────

def _fallback_intent(query: str) -> dict:
    """Simple keyword extraction as fallback when LLM call fails."""
    words = re.findall(r"\b[a-zA-Z]{4,}\b", query.lower())
    stopwords = {"that", "this", "with", "from", "have", "will", "been",
                 "they", "their", "about", "when", "what", "how", "for",
                 "are", "were", "which", "also", "using", "based"}
    keywords = [w for w in dict.fromkeys(words) if w not in stopwords][:10]
    return {
        "domain": "Research",
        "sub_domains": [],
        "methods": [],
        "constraints": [],
        "application_area": "",
        "keywords": keywords,
        "synonyms": {},
        "research_type": "applied",
        "recency_preference": "last_5_years",
        "problem_statement": query[:200],
        "search_queries": [query],
    }
