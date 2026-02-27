"""
Memory Node — store session history and generate follow-up recommendations.
Active only when the user has toggled memory on.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

if TYPE_CHECKING:
    from src.agents.state import ResearchState

from src.memory.sqlite_memory import (
    add_message,
    save_papers,
    save_insights,
    get_session_summary,
    create_session,
)

logger = logging.getLogger(__name__)

_FOLLOWUP_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a personalized research advisor with memory of the user's past work.
Based on the session history and current findings, suggest next steps and follow-up reading.

Return ONLY valid JSON:
{{
  "suggestions": [
    "Specific actionable follow-up suggestion 1",
    "Specific follow-up suggestion 2",
    "Follow-up suggestion 3"
  ],
  "next_queries": [
    "Recommended next search query 1",
    "Recommended next search query 2"
  ],
  "progress_note": "Brief note on how the research is evolving across sessions"
}}""",
    ),
    (
        "human",
        """Session history summary:
{history_summary}

Current query: {current_query}
Current insights: {insights_json}

Return only the JSON.""",
    ),
])


def update_memory_node(state: "ResearchState") -> "ResearchState":
    """
    LangGraph node: persist session data and generate follow-up recommendations.
    Only runs when memory_enabled=True in state.
    """
    if not state.get("memory_enabled", False):
        return {**state, "memory_suggestions": []}

    from src.models.llm_factory import get_llm

    session_id = state.get("session_id") or ""
    query = state.get("query", "")
    papers = state.get("synthesized_papers") or state.get("ranked_papers", [])
    insights = state.get("insights", {})

    try:
        # Persist conversation turn
        add_message(session_id, "user", query)

        report_summary = (
            f"Retrieved {len(papers)} papers. "
            f"Domain: {state.get('parsed_intent', {}).get('domain', 'N/A')}."
        )
        add_message(session_id, "assistant", report_summary)

        # Persist papers
        if papers:
            save_papers(session_id, papers)

        # Persist insights
        if insights:
            save_insights(session_id, query, insights)

        # Store papers in vector memory for semantic search
        try:
            from src.memory.vector_memory import get_vector_store
            get_vector_store().add_papers(papers)
        except Exception as ve:
            logger.warning("Vector store update failed: %s", ve)

        # Generate personalised follow-up suggestions
        history_summary = get_session_summary(session_id)

        llm = get_llm(
            provider=state.get("llm_provider"),
            model=state.get("llm_model"),
        )
        chain = _FOLLOWUP_PROMPT | llm | JsonOutputParser()

        followup = chain.invoke({
            "history_summary": history_summary,
            "current_query": query,
            "insights_json": json.dumps(insights, indent=2)[:1000],
        })
        suggestions = followup.get("suggestions", []) + [
            f"Try searching: '{q}'" for q in followup.get("next_queries", [])
        ]
        if note := followup.get("progress_note"):
            suggestions.insert(0, f"📈 {note}")

    except Exception as exc:
        logger.error("Memory node failed: %s", exc)
        suggestions = []

    logger.info("Memory updated for session %s; %d suggestions", session_id, len(suggestions))

    return {
        **state,
        "memory_suggestions": suggestions,
        "status_message": "💾 Memory updated with current session",
    }


def ensure_session(session_id: str | None, query: str = "") -> str:
    """Return existing session_id or create a new one."""
    if session_id:
        return session_id
    return create_session(title=query[:60] if query else "")
