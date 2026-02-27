"""
Research Agent — LangGraph Workflow
Orchestrates all nodes into a stateful, directed graph.

Workflow:
  parse_query
      ↓
  generate_search_plan
      ↓
  retrieve_papers
      ↓
  rank_sources
      ↓
  synthesize_papers
      ↓
  generate_insights
      ↓
  update_memory  (conditional — only when memory_enabled=True)
      ↓
  END
"""
from __future__ import annotations

import logging
from typing import Optional, Iterator

from langgraph.graph import StateGraph, END

from src.agents.state import ResearchState
from src.agents.nodes import (
    parse_query_node,
    generate_search_plan_node,
    retrieve_papers_node,
    rank_sources_node,
    synthesize_papers_node,
    generate_insights_node,
    update_memory_node,
)
from src.agents.nodes.memory_node import ensure_session
from src.memory.sqlite_memory import init_db

logger = logging.getLogger(__name__)


# ── Graph construction ────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    """Construct and compile the LangGraph StateGraph."""
    graph = StateGraph(ResearchState)

    # Register nodes
    graph.add_node("parse_query", parse_query_node)
    graph.add_node("generate_search_plan", generate_search_plan_node)
    graph.add_node("retrieve_papers", retrieve_papers_node)
    graph.add_node("rank_sources", rank_sources_node)
    graph.add_node("synthesize_papers", synthesize_papers_node)
    graph.add_node("generate_insights", generate_insights_node)
    graph.add_node("update_memory", update_memory_node)

    # Linear edges
    graph.set_entry_point("parse_query")
    graph.add_edge("parse_query", "generate_search_plan")
    graph.add_edge("generate_search_plan", "retrieve_papers")
    graph.add_edge("retrieve_papers", "rank_sources")
    graph.add_edge("rank_sources", "synthesize_papers")
    graph.add_edge("synthesize_papers", "generate_insights")

    # Conditional edge: run memory node only if requested
    graph.add_conditional_edges(
        "generate_insights",
        lambda state: "update_memory" if state.get("memory_enabled") else END,
        {"update_memory": "update_memory", END: END},
    )
    graph.add_edge("update_memory", END)

    return graph.compile()


# Compile once at module level
_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


# ── Public API ────────────────────────────────────────────────────────────────

def run_research_agent(
    query: str,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    memory_enabled: bool = False,
    session_id: Optional[str] = None,
) -> dict:
    """
    Run the full research agent pipeline and return the final state.

    Parameters
    ----------
    query : str
        User's research query (keywords, paragraph, abstract, etc.)
    llm_provider : str, optional
        LLM provider override (openai | openrouter | gemini | anthropic | ollama)
    llm_model : str, optional
        Model name override.
    memory_enabled : bool
        If True, persist session and generate follow-up suggestions.
    session_id : str, optional
        Continue an existing session (for memory continuity).

    Returns
    -------
    dict
        Final ResearchState with all populated fields.
    """
    # Initialise DB if memory is involved
    if memory_enabled:
        init_db()
        session_id = ensure_session(session_id, query)

    initial_state: ResearchState = {
        "query": query,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "memory_enabled": memory_enabled,
        "session_id": session_id,
        "parsed_intent": {},
        "search_plan": {},
        "papers": [],
        "ranked_papers": [],
        "synthesized_papers": [],
        "insights": {},
        "memory_suggestions": [],
        "status_message": "Starting...",
        "final_output": None,
        "error": None,
    }

    graph = _get_graph()
    logger.info("Research agent started for query: %s...", query[:80])

    try:
        final_state = graph.invoke(initial_state)
        logger.info(
            "Research agent completed: %d papers synthesized",
            len(final_state.get("synthesized_papers", [])),
        )
        return final_state
    except Exception as exc:
        logger.error("Research agent failed: %s", exc, exc_info=True)
        initial_state["error"] = str(exc)
        initial_state["status_message"] = f"❌ Agent error: {exc}"
        return initial_state


def stream_research_agent(
    query: str,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    memory_enabled: bool = False,
    session_id: Optional[str] = None,
) -> Iterator[dict]:
    """
    Stream intermediate states from the research agent pipeline.
    Yields each state update (after every node execution) for real-time UI updates.

    Yields
    ------
    dict
        Partial ResearchState after each node finishes.
    """
    if memory_enabled:
        init_db()
        session_id = ensure_session(session_id, query)

    initial_state: ResearchState = {
        "query": query,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "memory_enabled": memory_enabled,
        "session_id": session_id,
        "parsed_intent": {},
        "search_plan": {},
        "papers": [],
        "ranked_papers": [],
        "synthesized_papers": [],
        "insights": {},
        "memory_suggestions": [],
        "status_message": "🚀 Starting research agent...",
        "final_output": None,
        "error": None,
    }

    graph = _get_graph()

    try:
        for chunk in graph.stream(initial_state, stream_mode="values"):
            yield chunk
    except Exception as exc:
        logger.error("Stream failed: %s", exc, exc_info=True)
        yield {**initial_state, "error": str(exc),
               "status_message": f"❌ Error: {exc}"}
