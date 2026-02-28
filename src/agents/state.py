"""
ResearchState — shared state schema for the LangGraph workflow.
"""
from __future__ import annotations

from typing import Optional, Any
from typing_extensions import TypedDict


class ResearchState(TypedDict, total=False):
    # ── Input ─────────────────────────────────────────────────────────────────
    query: str                     # Raw user query
    llm_provider: Optional[str]    # Override provider for this run
    llm_model: Optional[str]       # Override model for this run
    llm_temperature: Optional[float]  # LLM temperature (0.0–1.0); None → settings default
    memory_enabled: bool           # Whether to persist memory
    session_id: Optional[str]      # Active session UUID
    year_min: Optional[int]        # Pre-search min publication year filter
    year_max: Optional[int]        # Pre-search max publication year filter
    fast_mode: Optional[bool]      # If True, use short timeouts for speed
    enabled_sources: Optional[list]  # List of source keys the user enabled; None → all
    fetch_round: Optional[int]     # 0=initial search, 1=first fetch-more, 2=second, …
    _stop_event: Optional[Any]     # threading.Event passed from UI for immediate cancellation
    _agent_queue: Optional[Any]    # queue.Queue passed from UI for real-time node status pushes

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
