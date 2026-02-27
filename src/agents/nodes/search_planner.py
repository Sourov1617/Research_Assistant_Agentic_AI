"""
Search Planner Node
Decides which sources to query and generates optimized search strings
for each source based on the parsed research intent.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

if TYPE_CHECKING:
    from src.agents.state import ResearchState

logger = logging.getLogger(__name__)

_PLAN_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a research librarian who creates targeted search strategies.
Given a parsed research intent, produce an optimal multi-source search plan.

Return ONLY a valid JSON object:
{{
  "sources": {{
    "arxiv": {{
      "enabled": true,
      "queries": ["query1", "query2"],
      "categories": ["cs.CV", "cs.LG"]
    }},
    "semantic_scholar": {{
      "enabled": true,
      "queries": ["query1", "query2"]
    }},
    "crossref": {{
      "enabled": true,
      "queries": ["query1"]
    }},
    "core": {{
      "enabled": true,
      "queries": ["query1"]
    }},
    "web": {{
      "enabled": true,
      "queries": ["query1 site:github.com OR site:arxiv.org", "query2 implementation"],
      "focus": "industry implementations blogs github"
    }}
  }},
  "primary_keywords": ["kw1", "kw2"],
  "date_filter_year": 2020,
  "rationale": "brief explanation of strategy"
}}

For web queries, craft queries that find GitHub repos, blogs, implementation guides.
Set date_filter_year to 3 years ago for recency focus.""",
    ),
    (
        "human",
        "Parsed intent:\n{intent_json}\n\nReturn only the JSON.",
    ),
])


def generate_search_plan_node(state: "ResearchState") -> "ResearchState":
    """
    LangGraph node: produce a structured search plan from parsed intent.
    Updates state keys: search_plan, status_message.
    """
    from src.models.llm_factory import get_llm

    intent = state.get("parsed_intent", {})
    if not intent:
        return {**state, "search_plan": _default_plan(state.get("query", "")),
                "status_message": "⚠️ Using default search plan."}

    import json
    llm = get_llm(
        provider=state.get("llm_provider"),
        model=state.get("llm_model"),
    )
    chain = _PLAN_PROMPT | llm | JsonOutputParser()

    try:
        plan = chain.invoke({"intent_json": json.dumps(intent, indent=2)})
    except Exception as exc:
        logger.error("Search plan generation failed: %s", exc)
        plan = _default_plan(state.get("query", ""), intent)

    source_count = sum(
        1 for v in plan.get("sources", {}).values()
        if v.get("enabled", False)
    )
    logger.info("Search plan generated: %d sources enabled", source_count)

    return {
        **state,
        "search_plan": plan,
        "status_message": f"📋 Search plan ready — querying {source_count} sources",
    }


def _default_plan(query: str, intent: dict = None) -> dict:
    """Fallback plan when LLM call fails."""
    keywords = (intent or {}).get("keywords", [query])
    primary = " ".join(keywords[:4]) if keywords else query

    return {
        "sources": {
            "arxiv": {"enabled": True, "queries": [primary], "categories": []},
            "semantic_scholar": {"enabled": True, "queries": [primary]},
            "crossref": {"enabled": True, "queries": [primary]},
            "core": {"enabled": True, "queries": [primary]},
            "web": {"enabled": True, "queries": [f"{primary} research implementation"],
                    "focus": ""},
        },
        "primary_keywords": keywords[:6],
        "date_filter_year": 2020,
        "rationale": "Default search plan",
    }
