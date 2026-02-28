"""
Search Planner Node
Generates ONE highly-targeted query per source based on parsed research intent.
Fewer, more precise requests = better relevance + lower rate-limit pressure.
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

if TYPE_CHECKING:
    from src.agents.state import ResearchState

logger = logging.getLogger(__name__)
CURRENT_YEAR = datetime.now().year

_PLAN_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a specialist research librarian. Craft ONE maximally precise search
query per source so every result is DIRECTLY relevant to the research topic.

Rules for every query:
- Combine: SPECIFIC_DOMAIN_TOPIC + SPECIFIC_METHODS + APPLICATION_AREA
- NEVER use generic terms alone ("deep learning", "AI", "IoT") without the domain topic
- Always pair method names with the topic (e.g., "sleep monitoring LSTM", not just "LSTM")
- Use the most discriminating keywords from the intent
- For site-specific web queries use: key_terms site:domain.com

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "sources": {{
    "arxiv": {{
      "enabled": true,
      "query": "<single precise arxiv query>",
      "categories": ["cs.LG", "eess.SP"]
    }},
    "semantic_scholar": {{
      "enabled": true,
      "query": "<single precise S2 query>"
    }},
    "crossref": {{
      "enabled": true,
      "query": "<single precise CrossRef query>"
    }},
    "core": {{
      "enabled": true,
      "query": "<single precise CORE query>"
    }},
    "ieee_web": {{
      "enabled": true,
      "query": "<topic_terms> site:ieeexplore.ieee.org"
    }},
    "sciencedirect_web": {{
      "enabled": true,
      "query": "<topic_terms> site:sciencedirect.com"
    }},
    "mdpi_web": {{
      "enabled": true,
      "query": "<topic_terms> site:mdpi.com"
    }},
    "nature_web": {{
      "enabled": true,
      "query": "<topic_terms> site:nature.com OR site:springer.com"
    }},
    "acm_web": {{
      "enabled": true,
      "query": "<topic_terms> site:dl.acm.org"
    }},
    "springer_web": {{
      "enabled": true,
      "query": "<topic_terms> site:link.springer.com"
    }},
    "pubmed_web": {{
      "enabled": true,
      "query": "<topic_terms> site:pubmed.ncbi.nlm.nih.gov"
    }},
    "openreview_web": {{
      "enabled": true,
      "query": "<topic_terms> site:openreview.net"
    }}
  }},
  "primary_keywords": ["kw1", "kw2", "kw3", "kw4", "kw5"],
  "year_after": {year_after},
  "rationale": "one sentence explaining the strategy"
}}

EXAMPLE for query "IoT sleep monitoring with BiLSTM GRU PSO optimizer":
  arxiv             : "sleep monitoring IoT wearable BiLSTM GRU deep learning EEG"
  semantic_scholar  : "IoT sleep staging deep learning LSTM GRU wearable sensor"
  crossref          : "IoT sleep monitoring deep learning optimization"
  core              : "sleep apnea detection IoT LSTM GRU wearable"
  ieee_web          : "IoT sleep monitoring LSTM deep learning site:ieeexplore.ieee.org"
  sciencedirect_web : "sleep detection IoT deep learning BiLSTM site:sciencedirect.com"
  mdpi_web          : "wearable sleep quality deep learning IoT site:mdpi.com"
  nature_web        : "sleep monitoring neural network wearable device site:nature.com"
  acm_web           : "sleep monitoring deep learning wearable IoT site:dl.acm.org"
  springer_web      : "sleep quality monitoring neural network IoT site:link.springer.com"
  pubmed_web        : "sleep disorder detection wearable sensor machine learning site:pubmed.ncbi.nlm.nih.gov"
  openreview_web    : "sleep monitoring deep learning wearable site:openreview.net"
  NOT acceptable    : "deep learning optimization IoT"  (too vague)""",
    ),
    (
        "human",
        "Parsed research intent:\n{intent_json}\n\nReturn the JSON only.",
    ),
])


def generate_search_plan_node(state: "ResearchState") -> "ResearchState":
    """
    LangGraph node: produce one precise query per source from parsed intent.
    Updates state keys: search_plan, status_message.
    """
    from src.models.llm_factory import get_llm

    intent = state.get("parsed_intent", {})
    year_min = state.get("year_min")

    # Derive year_after from pre-search filter or recency preference
    if year_min:
        year_after = year_min
    else:
        recency_map = {
            "last_1_year": CURRENT_YEAR - 1,
            "last_3_years": CURRENT_YEAR - 3,
            "last_5_years": CURRENT_YEAR - 5,
            "any": 2000,
        }
        year_after = recency_map.get(
            intent.get("recency_preference", "last_5_years"),
            CURRENT_YEAR - 5,
        )

    if not intent:
        plan = _default_plan(state.get("query", ""), year_after=year_after)
        _apply_enabled_sources(plan, state.get("enabled_sources"))
        return {**state, "search_plan": plan,
                "status_message": "⚠️ Using default search plan."}

    llm = get_llm(
        provider=state.get("llm_provider"),
        model=state.get("llm_model"),
        temperature=state.get("llm_temperature"),
    )
    chain = _PLAN_PROMPT | llm | JsonOutputParser()
    stop_event = state.get("_stop_event")

    # Push live status so user sees activity immediately while LLM thinks.
    _q = state.get("_agent_queue")
    if _q:
        _q.put({"_type": "interim",
                "status_message": "📋 LLM building search plan — may take 1–2 min for large models…"})

    # Run with a hard timeout so a completely broken provider never blocks the
    # pipeline. 120 s is generous enough for large reasoning models.
    #
    # IMPORTANT: do NOT use 'with ThreadPoolExecutor() as ex:' here — that
    # context manager calls shutdown(wait=True) on exit, which blocks until the
    # spawned thread finishes even after we've already timed out.  Instead we
    # call shutdown(wait=False) explicitly so the hung thread is discarded.
    _LLM_TIMEOUT = 120  # seconds
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        chain.invoke,
        {"intent_json": json.dumps(intent, indent=2), "year_after": year_after},
    )
    try:
        deadline = _LLM_TIMEOUT
        while deadline > 0:
            if stop_event and stop_event.is_set():
                logger.info("Search planning cancelled by stop_event.")
                executor.shutdown(wait=False)
                fallback = _default_plan(state.get("query", ""), intent, year_after=year_after)
                _apply_enabled_sources(fallback, state.get("enabled_sources"))
                return {**state, "search_plan": fallback,
                        "status_message": "🛑 Search stopped."}
            try:
                plan = future.result(timeout=min(1.0, deadline))
                plan["year_after"] = year_after
                if state.get("year_max"):
                    plan["year_max"] = state["year_max"]
                break
            except concurrent.futures.TimeoutError:
                deadline -= 1.0
        else:
            logger.warning("Search plan generation timed out after %ss — using default plan.", _LLM_TIMEOUT)
            plan = _default_plan(state.get("query", ""), intent, year_after=year_after)
    except Exception as exc:
        logger.error("Search plan generation failed: %s", exc)
        plan = _default_plan(state.get("query", ""), intent, year_after=year_after)
    finally:
        executor.shutdown(wait=False)  # never block on a hung LLM thread

    # Honour user source selections from the sidebar
    _apply_enabled_sources(plan, state.get("enabled_sources"))

    enabled_count = sum(
        1 for v in plan.get("sources", {}).values()
        if isinstance(v, dict) and v.get("enabled", False)
    )
    logger.info("Search plan: %d sources, year_after=%d", enabled_count, year_after)

    return {
        **state,
        "search_plan": plan,
        "status_message": (
            f"📋 Search plan ready — querying {enabled_count} sources "
            f"(publications from {year_after}+)"
        ),
    }


def _apply_enabled_sources(plan: dict, enabled_sources) -> None:
    """
    Disable sources in the plan that are either:
    1. Deselected by the user in the sidebar, OR
    2. Require an API key that is not configured (placeholder / empty).
    """
    from src.agents.nodes.retriever import _is_source_configured

    for src_key, src_cfg in plan.get("sources", {}).items():
        if not isinstance(src_cfg, dict):
            continue
        # User unchecked this source
        if enabled_sources is not None and src_key not in enabled_sources:
            src_cfg["enabled"] = False
            continue
        # API key missing → auto-disable so the retriever never gets a 401/hang
        if not _is_source_configured(src_key):
            src_cfg["enabled"] = False
            logger.info("Auto-disabling '%s': API key not configured.", src_key)


def _default_plan(query: str, intent: dict = None, year_after: int = 2019) -> dict:
    """Fallback plan that uses raw query terms directly."""
    kws = (intent or {}).get("keywords", [])
    primary = " ".join(kws[:5]) if kws else query[:80]

    return {
        "sources": {
            "arxiv":            {"enabled": True, "query": primary, "categories": []},
            "semantic_scholar": {"enabled": True, "query": primary},
            "crossref":         {"enabled": True, "query": primary},
            "core":             {"enabled": True, "query": primary},
            "ieee_web":         {"enabled": True,  "query": f"{primary} site:ieeexplore.ieee.org"},
            "sciencedirect_web":{"enabled": True,  "query": f"{primary} site:sciencedirect.com"},
            "mdpi_web":         {"enabled": True,  "query": f"{primary} site:mdpi.com"},
            "nature_web":       {"enabled": True,  "query": f"{primary} site:nature.com"},
            "acm_web":          {"enabled": True,  "query": f"{primary} site:dl.acm.org"},
            "springer_web":     {"enabled": True,  "query": f"{primary} site:link.springer.com"},
            "pubmed_web":       {"enabled": False, "query": f"{primary} site:pubmed.ncbi.nlm.nih.gov"},
            "openreview_web":   {"enabled": True,  "query": f"{primary} site:openreview.net"},
        },
        "primary_keywords": kws[:8],
        "year_after": year_after,
        "rationale": "Default fallback plan",
    }
