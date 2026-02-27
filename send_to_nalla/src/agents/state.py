"""
ResearchState — shared state schema for the LangGraph workflow.
"""
from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict


class ResearchState(TypedDict, total=False):
    # ── Input ─────────────────────────────────────────────────────────────────
    query: str                     # Raw user query
    llm_provider: Optional[str]    # Override provider for this run
    llm_model: Optional[str]       # Override model for this run
    memory_enabled: bool           # Whether to persist memory
    session_id: Optional[str]      # Active session UUID

    # ── Node outputs ─────────────────────────────────────────────────────────
    parsed_intent: dict            # Structured intent from query_parser
    search_plan: dict              # Multi-source search plan
    papers: list                   # Raw aggregated papers
    ranked_papers: list            # Scored & ranked papers
    synthesized_papers: list       # Papers + LLM synthesis
    insights: dict                 # Collective research insights
    memory_suggestions: list       # Follow-up recommendations (memory mode)

    # ── UI / tracking ─────────────────────────────────────────────────────────
    status_message: str            # Latest status for the UI progress bar
    final_output: Optional[str]    # Pre-rendered Markdown report (optional)
    error: Optional[str]           # Error message if any node fails
