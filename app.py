"""
Research Discovery & Synthesis Agent — Streamlit Frontend
Run: streamlit run app.py
"""
from __future__ import annotations

import sys
import os
import time
import uuid
import queue
import threading
import traceback
from pathlib import Path

# Ensure project root is on the path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Compatibility shim ────────────────────────────────────────────────────────
# langchain-core ≥0.3.x reads langchain.debug / langchain.verbose as part of a
# backwards-compat shim, but langchain ≥1.x removed those module-level attrs.
# Inject them before any LangChain sub-package is imported so the AttributeError
# ('module langchain has no attribute debug') never occurs.
import langchain as _lc
if not hasattr(_lc, "debug"):
    _lc.debug = False
if not hasattr(_lc, "verbose"):
    _lc.verbose = False

import streamlit as st

from config import settings
from src.utils.ollama_utils import is_ollama_running, list_ollama_models
from src.models.llm_factory import get_available_providers, get_available_models
from src.agents.research_agent import stream_research_agent
from src.utils.formatters import format_full_report, format_parsed_intent, format_insights, format_paper_card

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=settings.APP_TITLE,
    page_icon=settings.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com",
        "About": f"**{settings.APP_TITLE}** — Powered by LangChain & LangGraph",
    },
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ─── Base ─────────────────────────────────────────────────── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1rem; max-width: 1100px; }

/* ─── Hero Header ──────────────────────────────────────────── */
.hero-header {
    background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #0d1b2a 100%);
    border: 1px solid #2a2a5a;
    border-radius: 16px;
    padding: 1.8rem 2rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background: radial-gradient(ellipse at 70% 50%, rgba(108,92,231,0.12) 0%, transparent 70%);
    pointer-events: none;
}
.hero-title {
    font-size: 1.9rem; font-weight: 700;
    background: linear-gradient(90deg, #a29bfe, #74b9ff, #55efc4);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin: 0 0 0.3rem 0;
}
.hero-sub { color: #8888aa; font-size: 0.95rem; font-weight: 400; }

/* ─── Paper cards ──────────────────────────────────────────── */
.paper-card {
    background: linear-gradient(135deg, #13131f 0%, #1a1a2e 100%);
    border: 1px solid #2e2e50;
    border-radius: 14px;
    padding: 1rem 1.4rem;
    margin: 0.6rem 0;
    transition: border-color .2s, box-shadow .2s;
    box-shadow: 0 2px 12px rgba(0,0,0,0.25);
}
.paper-card:hover {
    border-color: #6c5ce7;
    box-shadow: 0 4px 24px rgba(108,92,231,0.18);
}
.paper-number {
    display: inline-flex; align-items: center; justify-content: center;
    width: 24px; height: 24px; border-radius: 50%;
    background: #2a2a5a; color: #a29bfe;
    font-size: 0.72rem; font-weight: 700; margin-right: 6px;
}

/* ─── Progress steps ───────────────────────────────────────── */
.step-row {
    display: flex; align-items: center; gap: 10px;
    padding: 0.45rem 0.8rem;
    border-radius: 8px;
    font-size: 0.88rem;
    margin: 2px 0;
    transition: background .15s;
}
.step-done  { color: #55efc4; background: #00b89408; }
.step-active{ color: #fdcb6e; background: #f9ca2408; font-weight: 600; }
.step-wait  { color: #555577; }
.step-skip  { color: #444466; font-style: italic; }
.step-error { color: #ff7675; background: #ff000010; }
.step-icon  { font-size: 1rem; width: 20px; text-align: center; }

/* ─── Error banner ─────────────────────────────────────────── */
.error-banner {
    background: linear-gradient(135deg, #2d1010, #3a1515);
    border: 1px solid #8b2222;
    border-left: 4px solid #ff4444;
    border-radius: 10px;
    padding: 1rem 1.4rem;
    margin: 0.8rem 0;
}
.error-title { color: #ff7675; font-size: 1rem; font-weight: 600; margin-bottom: 6px; }
.error-body  { color: #ccaaaa; font-size: 0.85rem; }

/* ─── Insight cards ────────────────────────────────────────── */
.insight-card {
    background: rgba(108,92,231,0.06);
    border-left: 3px solid #6c5ce7;
    border-radius: 0 8px 8px 0;
    padding: 0.65rem 1rem;
    margin: 0.35rem 0;
    font-size: 0.9rem;
    line-height: 1.5;
}

/* ─── Source tags ──────────────────────────────────────────── */
.source-tag {
    display: inline-block; border-radius: 6px;
    padding: 2px 8px; font-size: 0.68rem; font-weight: 700;
    letter-spacing: 0.03em; margin-right: 5px; vertical-align: middle;
}
.tag-arxiv       { background: rgba(179,27,27,.15);  color: #ff7675; border: 1px solid rgba(179,27,27,.3); }
.tag-ss          { background: rgba(26,107,153,.15);  color: #74b9ff; border: 1px solid rgba(26,107,153,.3); }
.tag-crossref    { background: rgba(26,155,68,.15);   color: #55efc4; border: 1px solid rgba(26,155,68,.3); }
.tag-web         { background: rgba(155,107,26,.15);  color: #ffeaa7; border: 1px solid rgba(155,107,26,.3); }
.tag-core        { background: rgba(107,26,155,.15);  color: #a29bfe; border: 1px solid rgba(107,26,155,.3); }
.tag-ieee        { background: rgba(0,115,230,.15);   color: #79bcff; border: 1px solid rgba(0,115,230,.3); }
.tag-elsevier    { background: rgba(255,140,0,.12);   color: #ffa94d; border: 1px solid rgba(255,140,0,.3); }
.tag-mdpi        { background: rgba(0,180,150,.12);   color: #51cf66; border: 1px solid rgba(0,180,150,.3); }
.tag-nature      { background: rgba(180,60,120,.12);  color: #f783ac; border: 1px solid rgba(180,60,120,.3); }

/* ─── Sidebar ──────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0e0e1e 0%, #111120 100%);
    border-right: 1px solid #1e1e3a;
}
[data-testid="stSidebar"] .stButton>button {
    border-radius: 8px; font-size: 0.83rem;
}

/* ─── Metrics strip ────────────────────────────────────────── */
.metrics-strip {
    display: flex; gap: 12px; flex-wrap: wrap;
    margin: 0.8rem 0 1rem 0;
}
.metric-pill {
    background: #161628; border: 1px solid #2a2a4a;
    border-radius: 10px; padding: 0.5rem 1rem;
    min-width: 90px; text-align: center;
}
.metric-pill .val { font-size: 1.3rem; font-weight: 700; color: #a29bfe; }
.metric-pill .lbl { font-size: 0.7rem; color: #666688; text-transform: uppercase; }

/* ─── Query area ───────────────────────────────────────────── */
.stTextArea textarea {
    background: #0e0e1e !important;
    border: 1px solid #2e2e50 !important;
    border-radius: 10px !important;
    font-size: 0.93rem !important;
    line-height: 1.6 !important;
    color: #d0d0f0 !important;
}
.stTextArea textarea:focus {
    border-color: #6c5ce7 !important;
    box-shadow: 0 0 0 2px rgba(108,92,231,.15) !important;
}

/* ─── Primary button ───────────────────────────────────────── */
.stButton>button[kind="primary"] {
    background: linear-gradient(135deg, #6c5ce7, #a29bfe) !important;
    border: none !important; border-radius: 10px !important;
    font-weight: 600 !important; letter-spacing: 0.02em !important;
    transition: opacity .2s, transform .1s !important;
}
.stButton>button[kind="primary"]:hover {
    opacity: .9 !important; transform: translateY(-1px) !important;
}

/* ─── Stop button ──────────────────────────────────────────── */
.stop-btn>button {
    background: linear-gradient(135deg, #c0392b, #e74c3c) !important;
    color: #fff !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
}

/* ─── Expanders ────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background: #13131f !important; border-radius: 8px !important;
    font-size: 0.88rem !important;
}

/* ─── Dividers ─────────────────────────────────────────────── */
[data-testid="stDecoration"] { background: #2a2a4a !important; }
hr { border-color: #2a2a4a !important; }
</style>
""", unsafe_allow_html=True)


# ── Session state initialisation ──────────────────────────────────────────────
def _init_session():
    from datetime import datetime as _dt
    _cur_year = _dt.now().year
    defaults = {
        "session_id": str(uuid.uuid4()),
        "research_state": None,
        "query_history": [],
        "is_running": False,
        "selected_provider": settings.LLM_PROVIDER,
        "selected_model": settings.DEFAULT_MODEL,
        "memory_enabled": settings.MEMORY_ENABLED_DEFAULT,
        "year_min_pre": _cur_year - 5,
        "year_max_pre": _cur_year,
        # threading / progress tracking
        "agent_queue": None,
        "stop_event": None,
        "agent_step_idx": 0,
        "agent_last_status": "",
        "agent_error": None,
        "agent_stopped": False,
        # search options
        "fast_mode": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

_init_session()


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown(
            f'<div style="padding:0.8rem 0 0.4rem 0">'
            f'<span style="font-size:1.6rem;font-weight:700;'
            f'background:linear-gradient(90deg,#a29bfe,#74b9ff);'
            f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            f'background-clip:text">'
            f'{settings.APP_ICON} {settings.APP_TITLE}</span><br>'
            f'<span style="color:#666688;font-size:0.78rem">AI-powered research synthesis</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # Running indicator in sidebar
        if st.session_state.is_running:
            st.markdown(
                '<div style="background:#1a1a3e;border:1px solid #3a3a7a;border-radius:8px;'
                'padding:0.4rem 0.8rem;margin:0.4rem 0;color:#a29bfe;font-size:0.82rem">'
                '⏳ Search in progress…</div>',
                unsafe_allow_html=True,
            )
        st.divider()

        # ── LLM Configuration ──────────────────────────────────────────────
        st.subheader("🤖 AI Model")

        available_providers = get_available_providers()
        all_providers = ["openai", "openrouter", "gemini", "anthropic", "ollama"]

        provider_labels = {
            "openai": "🟢 OpenAI",
            "openrouter": "🟣 OpenRouter",
            "gemini": "🔵 Google Gemini",
            "anthropic": "🟠 Anthropic (Claude)",
            "ollama": "⚫ Ollama (Local)",
        }

        # Highlight configured providers
        display_providers = []
        for p in all_providers:
            label = provider_labels.get(p, p)
            if p in available_providers:
                label += " ✓"
            display_providers.append(label)

        provider_index = all_providers.index(st.session_state.selected_provider) \
            if st.session_state.selected_provider in all_providers else 0

        selected_display = st.selectbox(
            "Provider",
            display_providers,
            index=provider_index,
            help="Providers marked ✓ have API keys configured in .env",
        )
        selected_provider = all_providers[display_providers.index(selected_display)]
        st.session_state.selected_provider = selected_provider

        # Model selection
        if selected_provider == "ollama":
            ollama_ok = is_ollama_running()
            if ollama_ok:
                ollama_models = list_ollama_models()
                if ollama_models:
                    st.session_state.selected_model = st.selectbox(
                        "Ollama Model (auto-detected)",
                        ollama_models,
                        index=0,
                        help="Models found in your local Ollama installation",
                    )
                else:
                    st.warning("⚠️ Ollama running but no models found.\n\nRun: `ollama pull llama3.2`")
                    st.session_state.selected_model = settings.OLLAMA_DEFAULT_MODEL
            else:
                st.error("❌ Ollama is not running.\n\nStart with: `ollama serve`")
                st.session_state.selected_model = settings.OLLAMA_DEFAULT_MODEL
        else:
            model_options = get_available_models(selected_provider)
            current_model = st.session_state.selected_model
            model_index = model_options.index(current_model) \
                if current_model in model_options else 0
            st.session_state.selected_model = st.selectbox(
                "Model",
                model_options,
                index=model_index,
            )

        # API key status indicator
        _render_api_status(selected_provider)

        st.divider()

        # ── Memory Settings ────────────────────────────────────────────────
        st.subheader("🧠 Memory & Guidance")
        memory_on = st.toggle(
            "Enable Research Memory",
            value=st.session_state.memory_enabled,
            help=(
                "When ON: saves your queries, papers, and insights locally.\n"
                "Enables follow-up recommendations across sessions."
            ),
        )
        st.session_state.memory_enabled = memory_on

        if memory_on:
            st.success("✅ Memory enabled — session history will be saved")
            db_path = Path(settings.SQLITE_DB_PATH)
            if db_path.exists():
                size_kb = db_path.stat().st_size / 1024
                st.caption(f"💾 DB size: {size_kb:.1f} KB")

            if st.button("🗑️ Clear Current Session", type="secondary", use_container_width=True):
                from src.memory.sqlite_memory import delete_session
                delete_session(st.session_state.session_id)
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.research_state = None
                st.success("Session cleared!")
                st.rerun()

            # Past sessions
            if st.button("📚 View Session History", use_container_width=True):
                st.session_state.show_history = True

        st.divider()

        # ── Sources Configuration ──────────────────────────────────────────
        st.subheader("📡 Sources")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state["src_arxiv"]   = st.checkbox("arXiv",            value=st.session_state.get("src_arxiv", True))
            st.session_state["src_ss"]      = st.checkbox("Semantic Scholar",  value=st.session_state.get("src_ss", True))
            st.session_state["src_core"]    = st.checkbox("CORE",              value=st.session_state.get("src_core", True))
            st.session_state["src_ieee"]    = st.checkbox("IEEE Xplore",       value=st.session_state.get("src_ieee", True))
            st.session_state["src_nature"]  = st.checkbox("Nature / Springer", value=st.session_state.get("src_nature", True))
            st.session_state["src_acm"]     = st.checkbox("ACM Digital Lib.",  value=st.session_state.get("src_acm", True))
        with col2:
            st.session_state["src_crossref"]   = st.checkbox("CrossRef",       value=st.session_state.get("src_crossref", True))
            st.session_state["src_web"]         = st.checkbox("Web Search",     value=st.session_state.get("src_web", True))
            st.session_state["src_scidir"]      = st.checkbox("ScienceDirect",  value=st.session_state.get("src_scidir", True))
            st.session_state["src_mdpi"]        = st.checkbox("MDPI",           value=st.session_state.get("src_mdpi", True))
            st.session_state["src_springer"]    = st.checkbox("Springer Link",  value=st.session_state.get("src_springer", True))
            st.session_state["src_openreview"]  = st.checkbox("OpenReview (NeurIPS/ICLR)", value=st.session_state.get("src_openreview", True))

        st.divider()
        st.subheader("⚡ Speed")
        st.session_state["fast_mode"] = st.toggle(
            "Fast mode",
            value=st.session_state.get("fast_mode", False),
            help=(
                "Reduces per-source timeout to 12 s and skips the rate-limited "
                "Semantic Scholar delay. Results arrive faster but some sources "
                "may time out on slow connections."
            ),
        )
        if st.session_state["fast_mode"]:
            st.caption("⚡ Sources run with short 12 s timeout")
        else:
            st.caption("🐢 Sources run with full 50 s timeout")

        # ── LLM Temperature ───────────────────────────────────────────────
        st.divider()
        st.subheader("🌡️ Temperature")
        st.session_state["llm_temperature"] = st.slider(
            "Creativity / randomness",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.get("llm_temperature", 0.3)),
            step=0.05,
            help=(
                "Higher values produce more varied / creative phrasing in "
                "summaries and insights. Lower values (0.0–0.2) are more "
                "deterministic and consistent across runs."
            ),
        )
        _t = st.session_state["llm_temperature"]
        if _t <= 0.15:
            st.caption("🔒 Deterministic — identical results per run")
        elif _t <= 0.4:
            st.caption("🎯 Balanced — consistent with slight variation")
        elif _t <= 0.7:
            st.caption("🎨 Creative — noticeable variation across runs")
        else:
            st.caption("🌪️ High randomness — very diverse outputs")

        # ── Pre-search Publication Year Filter ────────────────────────────
        st.divider()
        st.subheader("📅 Publication Year")
        from datetime import datetime as _dt2
        _cur_yr = _dt2.now().year
        yr_col1, yr_col2 = st.columns(2)
        with yr_col1:
            st.session_state["year_min_pre"] = st.number_input(
                "From year",
                min_value=1990,
                max_value=_cur_yr,
                value=int(st.session_state.get("year_min_pre", _cur_yr - 5)),
                step=1,
                key="year_min_input",
            )
        with yr_col2:
            st.session_state["year_max_pre"] = st.number_input(
                "To year",
                min_value=1990,
                max_value=_cur_yr,
                value=int(st.session_state.get("year_max_pre", _cur_yr)),
                step=1,
                key="year_max_input",
            )

        st.divider()

        # ── Quick Stats (if results available) ────────────────────────────
        state = st.session_state.research_state
        if state and state.get("synthesized_papers"):
            papers = state["synthesized_papers"]
            st.subheader("📊 Session Stats")
            c1, c2 = st.columns(2)
            c1.metric("Papers Found", len(papers))
            c2.metric("Sources Used", len({p.get("source") for p in papers}))

            years = [p.get("year") for p in papers if p.get("year")]
            if years:
                st.caption(f"📅 Range: {min(years)} – {max(years)}")

        # ── Footer ────────────────────────────────────────────────────────
        st.divider()
        st.caption(
            "Built with [LangChain](https://langchain.com) · "
            "[LangGraph](https://langchain-ai.github.io/langgraph/) · "
            "[Streamlit](https://streamlit.io)"
        )


def _render_api_status(provider: str):
    """Show a small indicator for whether the API key appears configured."""
    key_map = {
        "openai": settings.OPENAI_API_KEY,
        "openrouter": settings.OPENROUTER_API_KEY,
        "gemini": settings.GOOGLE_API_KEY,
        "anthropic": settings.ANTHROPIC_API_KEY,
        "ollama": "local",
    }
    key = key_map.get(provider, "")
    if provider == "ollama":
        status = "🟢 Local — No key needed"
    elif key and "your_" not in key and len(key) > 10:
        status = "🟢 API key configured"
    else:
        status = "🔴 API key missing — check .env"
    st.caption(status)


# ── Main content ──────────────────────────────────────────────────────────────
def render_main():
    # ── Hero header ────────────────────────────────────────────────────────
    st.markdown(
        f"""<div class="hero-header">
        <div class="hero-title">{settings.APP_ICON} Intelligent Research Discovery</div>
        <div class="hero-sub">
            Describe your research idea, problem, or keywords — the agent searches
            top-tier journals &amp; databases, ranks, and synthesises results for you.
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Show agent error if one occurred ──────────────────────────────────
    if st.session_state.agent_error:
        err = st.session_state.agent_error
        st.markdown(
            f'<div class="error-banner">'
            f'<div class="error-title">❌ Search failed</div>'
            f'<div class="error-body">{err["short"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        with st.expander("🔍 Technical details (check CLI for full traceback)"):
            st.code(err["detail"], language=None)
        col_retry, col_dismiss, _ = st.columns([1, 1, 2])
        with col_retry:
            if st.button("🔄 Try Again", type="primary", key="retry_btn"):
                st.session_state.agent_error = None
                st.rerun()
        with col_dismiss:
            if st.button("✖ Dismiss", key="dismiss_err"):
                st.session_state.agent_error = None
                st.rerun()
        st.divider()

    # ── Show stopped notice ────────────────────────────────────────────────
    if st.session_state.agent_stopped:
        st.info("⏹ Search was stopped. You can start a new search below.", icon="ℹ️")
        st.session_state.agent_stopped = False

    # ── Query input (always visible) ───────────────────────────────────────
    running = st.session_state.is_running

    query = st.text_area(
        "📝 Research Query",
        placeholder=(
            "Example: I want to build an IoT-based sleep monitoring system using "
            "CNN + BiLSTM hybrid models optimised with PSO/GWO for real-time inference...\n\n"
            "Tip: include your domain, techniques, and application area for best results."
        ),
        height=150,
        max_chars=settings.MAX_QUERY_LENGTH,
        key="query_input",
        disabled=running,
        help=f"Max {settings.MAX_QUERY_LENGTH} characters. The more context, the better.",
    )

    btn_col, count_col = st.columns([3, 1])
    with btn_col:
        run_clicked = st.button(
            "🚀 Start Research",
            type="primary",
            use_container_width=True,
            disabled=running,
        )
    with count_col:
        q_len = len(query or "")
        pct = int(q_len / settings.MAX_QUERY_LENGTH * 100)
        color = "#55efc4" if pct < 80 else "#fdcb6e" if pct < 95 else "#ff7675"
        st.markdown(
            f"<div style='text-align:right;color:{color};padding-top:0.5rem;font-size:0.82rem'>"
            f"{q_len}/{settings.MAX_QUERY_LENGTH}</div>",
            unsafe_allow_html=True,
        )

    # ── Example queries ────────────────────────────────────────────────────
    if not running:
        with st.expander("💡 Example queries", expanded=False):
            examples = [
                "IoT-based sleep monitoring with CNN/LSTM hybrid and PSO/GWO optimizers for wearable edge devices",
                "Lightweight transformer models for real-time object detection on resource-constrained edge devices",
                "Federated learning for privacy-preserving medical imaging diagnosis using MRI and CT scans",
                "Large language models for automated code generation, testing, and bug-fix suggestions",
                "Multimodal deep learning for crop disease detection using drone NDVI imagery and IoT soil sensors",
            ]
            for ex in examples:
                if st.button(f"↗ {ex[:100]}", key=f"ex_{hash(ex)}", use_container_width=True):
                    st.session_state["query_input"] = ex
                    st.rerun()

    st.divider()

    # ── Start agent ────────────────────────────────────────────────────────
    if run_clicked:
        if query and query.strip():
            _start_agent(query.strip())  # sets is_running=True, calls st.rerun()
        else:
            st.warning("⚠️ Please enter a research query before starting.")

    # ── Live progress panel (fragment — no full-page flicker) ──────────────
    if st.session_state.is_running:
        _progress_fragment()

    # ── Display results ────────────────────────────────────────────────────
    if st.session_state.research_state and not st.session_state.is_running:
        render_results(st.session_state.research_state)


def _start_agent(query: str):
    """
    Kick off the research agent in a background thread.
    Results / errors are communicated via a queue.Queue in session state.
    The progress fragment polls that queue every second independently.
    """
    stop_event = threading.Event()
    agent_queue: queue.Queue = queue.Queue()

    st.session_state.agent_queue        = agent_queue
    st.session_state.stop_event         = stop_event
    st.session_state.agent_step_idx     = 0
    st.session_state.agent_last_status  = "Starting research agent…"
    st.session_state.agent_error        = None
    st.session_state.agent_stopped      = False
    st.session_state.is_running         = True
    st.session_state.research_state     = None
    st.session_state.papers_shown       = 15  # reset pagination for new query

    cfg = dict(
        query=query,
        llm_provider=st.session_state.selected_provider,
        llm_model=st.session_state.selected_model,
        llm_temperature=st.session_state.get("llm_temperature", 0.3),
        memory_enabled=st.session_state.memory_enabled,
        session_id=st.session_state.session_id if st.session_state.memory_enabled else None,
        year_min=st.session_state.get("year_min_pre"),
        year_max=st.session_state.get("year_max_pre"),
        fast_mode=st.session_state.get("fast_mode", False),
        stop_event=stop_event,
        agent_queue=agent_queue,
        enabled_sources=[
            src for src, key in {
                "arxiv":            "src_arxiv",
                "semantic_scholar": "src_ss",
                "crossref":         "src_crossref",
                "core":             "src_core",
                "ieee_web":         "src_ieee",
                "sciencedirect_web":"src_scidir",
                "mdpi_web":         "src_mdpi",
                "nature_web":       "src_nature",
                "acm_web":          "src_acm",
                "springer_web":     "src_springer",
                "openreview_web":   "src_openreview",
            }.items()
            if st.session_state.get(key, True)
        ],
    )

    def _worker():
        final = None
        try:
            first_chunk = True
            for upd in stream_research_agent(**cfg):
                if first_chunk:
                    # LangGraph 1.x always emits the initial state as chunk 0
                    # before any node executes — skip it so step_idx only
                    # advances when a node actually completes.
                    first_chunk = False
                    continue
                if stop_event.is_set():
                    agent_queue.put({"_type": "stopped", "state": final})
                    return
                final = upd
                agent_queue.put({"_type": "update", **upd})
            agent_queue.put({"_type": "complete", "state": final})
        except Exception as exc:
            tb = traceback.format_exc()
            import logging
            logging.getLogger(__name__).error("Agent error:\n%s", tb)
            agent_queue.put({
                "_type": "error",
                "short":  _friendly_error(exc),
                "detail": tb,
            })

    threading.Thread(target=_worker, daemon=True).start()
    st.rerun()


def _friendly_error(exc: Exception) -> str:
    """Convert a raw exception into a short, user-readable message."""
    msg = str(exc)
    lower = msg.lower()
    if "401" in msg or "unauthorized" in lower or "invalid api key" in lower:
        return "API authentication failed (401). Check your API key in .env."
    if "403" in msg or "forbidden" in lower:
        return "Access forbidden (403). Your API key may not have permission."
    if "404" in msg or "not found" in lower:
        return "Endpoint not found (404). Model name or API URL may be wrong."
    if "429" in msg or "rate limit" in lower or "quota" in lower:
        return "Rate limit / quota exceeded (429). Wait a moment or use a different provider."
    if "503" in msg or "service unavailable" in lower:
        return "Service unavailable (503). The remote API is down — try again shortly."
    if "connection" in lower or "timeout" in lower or "timed out" in lower:
        return "Network error — could not reach the API. Check your internet connection."
    if "model" in lower and ("not" in lower or "exist" in lower or "found" in lower):
        return f"Model not found: {msg[:120]}"
    # Generic fallback — show first 200 chars
    return msg[:200] if len(msg) <= 200 else msg[:200] + "…"


# Pipeline steps shown in the progress checklist
_PIPELINE_STEPS = [
    ("parse_query",         "🧠", "Understanding research intent"),
    ("generate_search_plan","📋", "Planning search strategy"),
    ("retrieve_papers",     "🔍", "Searching databases & web"),
    ("rank_sources",        "📊", "Ranking & filtering results"),
    ("synthesize_papers",   "🧪", "Synthesising each paper"),
    ("generate_insights",   "🔬", "Generating research insights"),
    ("update_memory",       "💾", "Updating memory"),
]


@st.fragment(run_every=1)
def _progress_fragment():
    """
    Auto-refreshes every second as a fragment — only this section re-renders,
    so the rest of the page (query box, sidebar) stays perfectly static with
    no dimming, no flickering.  The stop button works reliably because Streamlit
    processes fragment interactions without a full-page rerun.
    """
    aq: "queue.Queue | None" = st.session_state.get("agent_queue")
    stop_event: "threading.Event | None" = st.session_state.get("stop_event")
    step_idx: int = st.session_state.get("agent_step_idx", 0)

    # ── Drain all new queue messages ──────────────────────────────────
    finished = False
    if aq:
        while True:
            try:
                msg = aq.get_nowait()
            except queue.Empty:
                break

            mtype = msg.get("_type", "update")

            if mtype == "interim":
                # Live status pushed directly from inside a running node.
                # Update the status text but do NOT advance the step counter.
                st.session_state.agent_last_status = msg.get("status_message", "")

            elif mtype == "update":
                step_idx += 1
                st.session_state.agent_step_idx     = step_idx
                st.session_state.agent_last_status  = msg.get("status_message", "")

            elif mtype == "complete":
                finished = True
                state = msg.get("state")
                if state:
                    # Strip non-serialisable internal threading objects before
                    # storing in session_state — prevents potential Streamlit
                    # serialisation errors on newer versions.
                    clean_state = {k: v for k, v in state.items()
                                   if not k.startswith("_")}
                    st.session_state.research_state = clean_state
                    if st.session_state.memory_enabled:
                        st.session_state.session_id = clean_state.get(
                            "session_id", st.session_state.session_id
                        )
                    st.session_state.query_history.insert(0, {
                        "query": clean_state.get("query", ""),
                        "paper_count": len(clean_state.get("synthesized_papers", [])),
                    })
                st.session_state.is_running = False
                break

            elif mtype == "stopped":
                finished = True
                st.session_state.is_running    = False
                st.session_state.agent_stopped = True
                raw = msg.get("state")
                if raw:
                    st.session_state.research_state = {
                        k: v for k, v in raw.items() if not k.startswith("_")
                    }
                break

            elif mtype == "error":
                finished = True
                st.session_state.is_running  = False
                st.session_state.agent_error = {
                    "short":  msg.get("short", "Unknown error"),
                    "detail": msg.get("detail", ""),
                }
                break

    # ── Render progress panel ─────────────────────────────────────────
    memory_on = st.session_state.get("memory_enabled", False)
    # Exclude the memory step from the total when memory is disabled,
    # so the progress bar reaches 100 % after generate_insights.
    total = len(_PIPELINE_STEPS) - (0 if memory_on else 1)
    pct   = min(int(step_idx / total * 100), 99) if not finished else 100

    with st.container():
        hdr_col, stop_col = st.columns([4, 1])
        with hdr_col:
            st.markdown(
                '<p style="font-size:1rem;font-weight:600;color:#a29bfe;margin:0">'
                '⚙️ Research in progress…</p>',
                unsafe_allow_html=True,
            )
        with stop_col:
            # Red stop button — inside the fragment so click is processed
            # without a full-page rerun
            stop_clicked = st.button(
                "⏹ Stop",
                key="stop_btn",
                use_container_width=True,
                type="secondary",
            )
            if stop_clicked:
                if stop_event:
                    stop_event.set()
                st.session_state.is_running    = False
                st.session_state.agent_stopped = True
                st.rerun()  # full page rerun to show stopped state

        st.progress(pct, text=st.session_state.get("agent_last_status", "Working…"))

        # Step checklist
        rows = ""
        for i, (node_key, icon, label) in enumerate(_PIPELINE_STEPS):
            is_memory = (node_key == "update_memory")
            if is_memory and not memory_on:
                # Memory disabled — step never runs; show as dimmed/skipped
                css, dot = "step-skip", "─"
            elif finished or i < step_idx:
                css, dot = "step-done",   "✅"
            elif i == step_idx:
                css, dot = "step-active", "⏳"
            else:
                css, dot = "step-wait",   "⬜"
            rows += (
                f'<div class="step-row {css}">'
                f'<span class="step-icon">{dot}</span>'
                f'<span>{icon} {label}</span>'
                f'</div>'
            )
        st.markdown(
            f'<div style="background:#0a0a18;border:1px solid #2a2a4a;'
            f'border-radius:12px;padding:0.7rem 1rem;margin-top:0.5rem">'
            f'{rows}</div>',
            unsafe_allow_html=True,
        )

    # When done, do ONE full-page rerun to show results / errors
    if finished:
        st.rerun()


# ── Results rendering ─────────────────────────────────────────────────────────
def render_results(state: dict):
    if state.get("error"):
        st.error(f"❌ Error: {state['error']}")
        return

    papers = state.get("synthesized_papers") or state.get("ranked_papers", [])
    insights = state.get("insights", {})
    intent = state.get("parsed_intent", {})
    memory_suggestions = state.get("memory_suggestions", [])

    if not papers and not insights:
        st.info("ℹ️ No results found. Try different keywords or enable more sources.")
        return

    # ── Tabs ────────────────────────────────────────────────────────────────
    tab_papers, tab_insights, tab_intent, tab_raw = st.tabs([
        f"📚 Papers ({len(papers)})",
        "🔬 Research Insights",
        "🧠 Query Analysis",
        "📥 Export / Raw",
    ])

    # ── Tab 1: Papers ──────────────────────────────────────────────────────
    with tab_papers:
        if not papers:
            st.info("No papers retrieved. Try broadening your query or enabling more sources.")
        else:
            sources = {p.get("source", "Unknown") for p in papers}
            years = sorted([p.get("year") for p in papers if p.get("year")])
            cited = [p.get("citation_count", 0) or 0 for p in papers]
            yr_range = f"{min(years)}–{max(years)}" if years else "N/A"
            avg_cite = f"{sum(cited)/len(cited):.0f}" if any(cited) else "N/A"

            # Metrics strip (custom HTML pills)
            st.markdown(
                f'<div class="metrics-strip">'
                f'<div class="metric-pill"><div class="val">{len(papers)}</div><div class="lbl">Papers</div></div>'
                f'<div class="metric-pill"><div class="val">{len(sources)}</div><div class="lbl">Sources</div></div>'
                f'<div class="metric-pill"><div class="val">{yr_range}</div><div class="lbl">Years</div></div>'
                f'<div class="metric-pill"><div class="val">{avg_cite}</div><div class="lbl">Avg Citations</div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown("---")

            # Filter controls
            fcol1, fcol2, fcol3 = st.columns([2, 2, 1])
            with fcol1:
                src_filter = st.multiselect(
                    "Filter by source",
                    sorted(sources),
                    default=sorted(sources),
                    key="src_filter",
                )
            with fcol2:
                if years and min(years) < max(years):
                    year_range = st.slider(
                        "Year range",
                        min_value=min(years),
                        max_value=max(years),
                        value=(min(years), max(years)),
                        key="year_range",
                    )
                elif years:
                    year_range = (years[0], years[0])
                    st.caption(f"📅 All papers from {years[0]}")
                else:
                    year_range = (0, 9999)
            with fcol3:
                sort_by = st.selectbox(
                    "Sort by",
                    ["Relevance", "Year (newest)", "Citations"],
                    key="sort_by",
                )

            # Apply filters and sort
            filtered = [
                p for p in papers
                if p.get("source", "") in src_filter
                and (year_range[0] <= (p.get("year") or 0) <= year_range[1])
            ]

            if sort_by == "Year (newest)":
                filtered.sort(key=lambda p: p.get("year") or 0, reverse=True)
            elif sort_by == "Citations":
                filtered.sort(key=lambda p: p.get("citation_count") or 0, reverse=True)
            # default: already sorted by relevance

            st.caption(f"Showing {len(filtered)} of {len(papers)} papers")

            # Pagination — initialise per-query counter
            if "papers_shown" not in st.session_state:
                st.session_state.papers_shown = 15

            page_papers = filtered[: st.session_state.papers_shown]

            # Paper cards
            for i, paper in enumerate(page_papers, 1):
                _render_paper_card(paper, i)

            # Load More button
            remaining = len(filtered) - len(page_papers)
            if remaining > 0:
                st.markdown("---")
                lcol, mcol, rcol = st.columns([1, 2, 1])
                with mcol:
                    if st.button(
                        f"📄 Load more ({remaining} remaining)",
                        use_container_width=True,
                        key="load_more_btn",
                    ):
                        st.session_state.papers_shown += 15
                        st.rerun()
            else:
                if len(filtered) > 15:
                    st.caption(f"✅ All {len(filtered)} papers shown")

    # ── Tab 2: Insights ────────────────────────────────────────────────────
    with tab_insights:
        if not insights:
            st.info("Run the agent to generate insights.")
        else:
            if overview := insights.get("overview"):
                st.info(f"📌 **Overview:** {overview}")

            # Maturity level
            maturity = insights.get("maturity_level", "")
            if maturity:
                maturity_colors = {
                    "emerging": "🟡", "growing": "🟢",
                    "mature": "🔵", "saturated": "🟠",
                }
                st.markdown(f"**Field Maturity:** {maturity_colors.get(maturity, '⚪')} {maturity.title()}")

            st.markdown("---")

            icol1, icol2 = st.columns(2)

            with icol1:
                if trends := insights.get("emerging_trends"):
                    st.markdown("### 📈 Emerging Trends")
                    for t in trends:
                        st.markdown(f"""
                        <div class="insight-card">🔺 {t}</div>
                        """, unsafe_allow_html=True)

                if gaps := insights.get("research_gaps"):
                    st.markdown("### 🧩 Research Gaps")
                    for g in gaps:
                        st.markdown(f"""
                        <div class="insight-card" style="border-left-color:#e17055;">
                        🔍 {g}</div>
                        """, unsafe_allow_html=True)

            with icol2:
                if challenges := insights.get("common_challenges"):
                    st.markdown("### ⚠️ Common Challenges")
                    for c in challenges:
                        st.markdown(f"""
                        <div class="insight-card" style="border-left-color:#fdcb6e;">
                        ⚡ {c}</div>
                        """, unsafe_allow_html=True)

                if directions := insights.get("suggested_directions"):
                    st.markdown("### 💡 Suggested Research Directions")
                    for d in directions:
                        st.markdown(f"""
                        <div class="insight-card" style="border-left-color:#00b894;">
                        🚀 {d}</div>
                        """, unsafe_allow_html=True)

            if interdisc := insights.get("interdisciplinary_connections"):
                st.markdown("### 🔗 Interdisciplinary Connections")
                st.markdown(" · ".join(f"`{c}`" for c in interdisc))

            if rec_papers := insights.get("recommended_papers"):
                st.markdown("### ⭐ Must-Read Papers")
                for rp in rec_papers:
                    st.markdown(f"- {rp}")

            # Memory follow-up suggestions
            if memory_suggestions:
                st.markdown("---")
                st.markdown("### 🧭 Follow-up Recommendations")
                for s in memory_suggestions:
                    st.markdown(f"- {s}")

    # ── Tab 3: Query Analysis ──────────────────────────────────────────────
    with tab_intent:
        if not intent:
            st.info("Query has not been analysed yet.")
        else:
            st.markdown(f"**Original Query:**\n> {state.get('query', '')}")
            st.markdown("---")

            ifields = {
                "🏷️ Domain": intent.get("domain"),
                "📂 Sub-domains": ", ".join(intent.get("sub_domains", [])),
                "🔧 Methods / Techniques": ", ".join(intent.get("methods", [])),
                "📏 Constraints": ", ".join(intent.get("constraints", [])),
                "🎯 Application Area": intent.get("application_area"),
                "🔑 Keywords": ", ".join(intent.get("keywords", [])),
                "🔬 Research Type": intent.get("research_type"),
                "📅 Recency Preference": intent.get("recency_preference"),
            }
            for label, val in ifields.items():
                if val:
                    st.markdown(f"**{label}:** {val}")

            if ps := intent.get("problem_statement"):
                st.markdown("---")
                st.markdown(f"**📌 Problem Statement:**\n> {ps}")

            if sq := intent.get("search_queries"):
                st.markdown("---")
                st.markdown("**🔎 Generated Search Queries:**")
                for q in sq:
                    st.code(q, language=None)

    # ── Tab 4: Export ──────────────────────────────────────────────────────
    with tab_raw:
        st.markdown("#### 📥 Export Research Report")

        report_md = format_full_report(state)

        st.download_button(
            "⬇️ Download Full Report (Markdown)",
            data=report_md,
            file_name=f"research_report_{_slug(state.get('query',''))}.md",
            mime="text/markdown",
            use_container_width=True,
        )

        # JSON export
        import json
        export_data = {
            "query": state.get("query"),
            "parsed_intent": state.get("parsed_intent"),
            "papers": [
                {k: v for k, v in p.items() if k != "raw"}
                for p in papers
            ],
            "insights": state.get("insights"),
        }
        st.download_button(
            "⬇️ Download Data (JSON)",
            data=json.dumps(export_data, indent=2, default=str),
            file_name=f"research_data_{_slug(state.get('query',''))}.json",
            mime="application/json",
            use_container_width=True,
        )

        if settings.DEBUG_MODE:
            with st.expander("🐛 Raw State (Debug)"):
                st.json({k: v for k, v in state.items() if k not in ("papers", "raw")})


# ── Paper card renderer ───────────────────────────────────────────────────────
def _render_paper_card(paper: dict, index: int):
    source = paper.get("source", "Unknown")
    source_class = {
        "arXiv":            "tag-arxiv",
        "Semantic Scholar": "tag-ss",
        "CrossRef":         "tag-crossref",
        "CORE":             "tag-core",
        "IEEE Xplore":      "tag-ieee",
        "Elsevier":         "tag-elsevier",
        "MDPI":             "tag-mdpi",
        "Nature":           "tag-nature",
        "Springer":         "tag-nature",
    }.get(source, "tag-web")

    title      = paper.get("title") or "Untitled"
    year       = paper.get("year") or ""
    citations  = paper.get("citation_count")
    cite_str   = f"{citations:,}" if isinstance(citations, int) else "—"
    relevance  = float(paper.get("relevance_score") or 0.0)
    url        = paper.get("url", "")
    pdf_url    = paper.get("pdf_url", "")
    doi        = paper.get("doi", "")

    authors_raw = paper.get("authors", [])
    if isinstance(authors_raw, list):
        authors = ", ".join(str(a) for a in authors_raw[:4])
        if len(authors_raw) > 4:
            authors += " et al."
    else:
        authors = str(authors_raw)

    synth        = paper.get("synthesis") or {}
    summary      = synth.get("summary") or (paper.get("abstract") or "")[:350] or "_No summary available._"
    methodology  = synth.get("methodology", "")
    contribution = synth.get("contribution", "")
    limitations  = synth.get("limitations", "")
    future_scope = synth.get("future_scope", "")

    # Relevance colour bar
    rel_pct   = min(int(relevance * 100), 100)
    rel_color = "#55efc4" if rel_pct >= 70 else "#fdcb6e" if rel_pct >= 40 else "#ff7675"

    # Compact header card — build pieces then join to avoid nested f-string issues
    icon = "📄" if pdf_url else "🔗"
    title_short = title[:110] + ("…" if len(title) > 110 else "")

    year_span  = (f'<span style="color:#888;font-size:0.78rem">{year}</span>'
                  if year else "")
    cite_span  = (f'<span style="color:#666688;font-size:0.75rem">· {cite_str} citations</span>'
                  if cite_str and cite_str != "—" else "")
    auth_div   = (f'<div style="margin-top:0.3rem;font-size:0.77rem;color:#666688">👥 {authors}</div>'
                  if authors else "")

    header_html = (
        f'<div class="paper-card">'
        f'<div style="display:flex;align-items:flex-start;gap:8px;flex-wrap:wrap">'
        f'  <span class="paper-number">{index}</span>'
        f'  <span class="source-tag {source_class}">{source}</span>'
        f'  {year_span}'
        f'  <span style="margin-left:auto;color:{rel_color};font-size:0.78rem;font-weight:600">★ {relevance:.2f}</span>'
        f'  {cite_span}'
        f'</div>'
        f'<div style="margin-top:0.4rem;font-size:0.93rem;font-weight:500;line-height:1.45;color:#c8c8e8">'
        f'  {icon} {title_short}'
        f'</div>'
        f'{auth_div}'
        f'<div style="margin-top:6px;height:3px;border-radius:2px;background:#1e1e3e">'
        f'  <div style="width:{rel_pct}%;height:100%;border-radius:2px;background:{rel_color};opacity:.6"></div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    with st.expander("▸ Details, synthesis & links", expanded=False):
        # Links row
        links = []
        if url:
            links.append(f"[🔗 View Paper]({url})")
        if pdf_url and pdf_url != url:
            links.append(f"[📄 PDF]({pdf_url})")
        if doi:
            links.append(f"DOI: `{doi}`")
        if links:
            st.markdown("  ·  ".join(links))

        st.markdown("---")

        # Summary
        st.markdown("**📝 Summary**")
        st.markdown(summary)

        # Synthesis grid
        has_synth = any([methodology, contribution, limitations, future_scope])
        if has_synth:
            st.markdown("---")
            scol1, scol2 = st.columns(2)
            with scol1:
                if methodology:
                    st.markdown("**⚙️ Methodology**")
                    st.markdown(methodology)
                if contribution:
                    st.markdown("**⭐ Key Contribution**")
                    st.markdown(contribution)
            with scol2:
                if limitations:
                    st.markdown("**⚠️ Limitations**")
                    st.markdown(limitations)
                if future_scope:
                    st.markdown("**🔮 Future Scope**")
                    st.markdown(future_scope)


# ── History modal ─────────────────────────────────────────────────────────────
def render_history_modal():
    if not st.session_state.get("show_history"):
        return

    with st.sidebar:
        st.subheader("📚 Session History")
        from src.memory.sqlite_memory import list_sessions, get_messages, get_papers_seen
        sessions = list_sessions()
        if not sessions:
            st.info("No saved sessions yet.")
        else:
            for sess in sessions[:10]:
                with st.expander(f"🗓️ {sess.get('title', 'Session')} — {sess['created_at'][:10]}"):
                    msgs = get_messages(sess["session_id"])
                    papers = get_papers_seen(sess["session_id"])
                    st.caption(f"{len(msgs)} messages · {len(papers)} papers reviewed")
                    for m in msgs[-4:]:
                        role_icon = "👤" if m["role"] == "user" else "🤖"
                        st.markdown(f"{role_icon} {m['content'][:120]}...")
        if st.button("✖ Close History"):
            st.session_state.show_history = False
            st.rerun()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _slug(text: str, max_len: int = 30) -> str:
    """Create a filename-safe slug from text."""
    import re
    return re.sub(r"[^a-z0-9]+", "_", (text or "query").lower())[:max_len].strip("_")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__" or True:
    render_sidebar()
    render_main()
    render_history_modal()
