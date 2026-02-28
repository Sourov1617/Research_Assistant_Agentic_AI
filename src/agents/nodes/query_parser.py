"""
Query Parser Node
Transforms a raw user query (keywords / paragraph / abstract) into a
structured research intent dictionary.
"""
from __future__ import annotations

import concurrent.futures
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

CRITICAL DISTINCTION you must make:
- "topic" = WHAT the paper is ABOUT (the subject/application domain)
- "methods" = the TOOLS/TECHNIQUES used inside the paper

A paper about "activity recognition using LSTM" is ABOUT activity recognition — LSTM is just a tool.
A paper about "LSTM optimization with PSO" is ABOUT LSTM optimization — PSO is just fine-tuning.

Always identify the PRIMARY SUBJECT first, then the methods.

Return ONLY a valid JSON object with the following fields:
{{
  "domain": "primary research domain/field",
  "sub_domains": ["list", "of", "sub-domains"],
  "primary_topic": "the non-negotiable subject — papers MUST be about this to be relevant (e.g. 'IoT-based sleep monitoring', 'wearable ECG classification')",
  "topic_keywords": ["6-10 keywords about the APPLICATION DOMAIN / SUBJECT ONLY — what the paper must be about. E.g. for IoT sleep monitoring: sleep, monitoring, IoT, wearable, sensor, sleep assistant, sleep stage, polysomnography. Do NOT put model names here."],
  "method_keywords": ["4-8 keywords about TECHNIQUES ONLY — model architectures, optimizer names, algorithms. E.g. BiLSTM, GRU, PSO, CNN, LSTM. Do NOT put application domain terms here."],
  "methods": ["ALL techniques/methods mentioned or implied — include EXACT names like BiLSTM, GRU, CNN-LSTM, PSO, GWO, etc."],
  "named_models": ["EXACT model/architecture names verbatim from query: BiLSTM, BiGRU, CNN-LSTM, Transformer, etc."],
  "named_optimizers": ["EXACT optimizer names verbatim from query: PSO, GWO, SVO, MOPSO, MOGWO, GA, DE, etc."],
  "platforms": ["hardware/deployment platforms: IoT, wearable, edge device, Raspberry Pi, Arduino, mobile, embedded"],
  "constraints": ["resource/hardware/time/data constraints implied"],
  "application_area": "the real-world application or use case",
  "keywords": ["8-14 refined search keywords — ALWAYS put topic/domain terms first, methods second"],
  "discriminating_terms": ["6-10 most domain-specific terms that UNIQUELY identify this research area"],
  "synonyms": {{"keyword": ["synonym1", "synonym2"]}},
  "research_type": "empirical|survey|theoretical|applied",
  "recency_preference": "last_1_year|last_3_years|last_5_years|any",
  "problem_statement": "concise 1-2 sentence problem statement",
  "search_queries": ["3-5 optimized academic search queries — ALWAYS start with primary_topic terms, THEN append method names"]
}}

Critical rules:
- primary_topic describes the SUBJECT, e.g. 'IoT-based sleep monitoring and assistant' not 'BiLSTM optimization'
- topic_keywords are about the subject domain — never include model/optimizer names in topic_keywords
- method_keywords are technique names only — never include subject terms in method_keywords
- Extract optimizer/model names verbatim (PSO not 'particle swarm', BiLSTM not 'bidirectional LSTM')
- search_queries: ALWAYS lead with primary_topic + application area, THEN add method names""",
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
        temperature=state.get("llm_temperature"),
    )
    chain = _PARSE_PROMPT | llm | JsonOutputParser()
    stop_event = state.get("_stop_event")

    # Push a live status update so the UI shows activity immediately,
    # before we even start the (potentially slow) LLM call.
    _q = state.get("_agent_queue")
    if _q:
        _q.put({"_type": "interim",
                "status_message": "\U0001f9e0 LLM analysing research intent\u2026"})

    # Run LLM in a thread with a hard timeout so a completely broken provider
    # never hangs the pipeline (and stop_event can cancel it quickly).
    # 120 s is generous enough for large reasoning models (qwen 235B, etc.).
    #
    # IMPORTANT: do NOT use 'with ThreadPoolExecutor() as ex:' here — that
    # context manager calls shutdown(wait=True) on exit, which blocks until the
    # spawned thread finishes even after we've already timed out.  Instead we
    # call shutdown(wait=False) explicitly so the hung thread is discarded and
    # execution continues immediately.
    _LLM_TIMEOUT = 120  # seconds
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(chain.invoke, {"query": query})
    try:
        # Poll so stop_event can abort during the wait
        deadline = _LLM_TIMEOUT
        while deadline > 0:
            if stop_event and stop_event.is_set():
                logger.info("Query parsing cancelled by stop_event.")
                executor.shutdown(wait=False)
                return {**state, "parsed_intent": _fallback_intent(query),
                        "status_message": "🛑 Search stopped."}
            try:
                intent = future.result(timeout=min(1.0, deadline))
                break
            except concurrent.futures.TimeoutError:
                deadline -= 1.0
        else:
            logger.warning("Query parsing timed out after %ss — using fallback.", _LLM_TIMEOUT)
            intent = _fallback_intent(query)
    except Exception as exc:
        logger.error("Query parsing failed: %s", exc)
        intent = _fallback_intent(query)
    finally:
        executor.shutdown(wait=False)  # never block on a hung LLM thread

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
    words = re.findall(r"\b[a-zA-Z]{2,}\b", query)   # preserve case for acronyms
    stopwords = {"that", "this", "with", "from", "have", "will", "been",
                 "they", "their", "about", "when", "what", "how", "for",
                 "are", "were", "which", "also", "using", "based", "want",
                 "build", "further", "advanced", "like", "such", "etc",
                 "main", "area", "focus", "and", "the", "its", "our"}
    seen: dict = {}
    for w in words:
        lw = w.lower()
        if lw not in stopwords and lw not in seen:
            seen[lw] = w  # keep original case for acronyms
    keywords = list(seen.values())[:14]

    # Heuristic split: uppercase tokens are likely acronyms/model/optimizer names
    upper_tokens = [w for w in words if w.isupper() and len(w) >= 2]
    lower_tokens  = [w.lower() for w in words if not w.isupper() and len(w) >= 4
                     and w.lower() not in stopwords]

    return {
        "domain": "Research",
        "sub_domains": [],
        "primary_topic": " ".join(lower_tokens[:4]),
        "topic_keywords": lower_tokens[:8],
        "method_keywords": upper_tokens[:8],
        "methods": keywords,
        "named_models": [],
        "named_optimizers": upper_tokens[:6],
        "platforms": [],
        "constraints": [],
        "application_area": "",
        "keywords": keywords,
        "discriminating_terms": upper_tokens[:4] + lower_tokens[:4],
        "synonyms": {},
        "research_type": "applied",
        "recency_preference": "last_5_years",
        "problem_statement": query[:200],
        "search_queries": [query],
    }
