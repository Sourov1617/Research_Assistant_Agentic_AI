"""
Research Discovery & Synthesis Agent — Streamlit Frontend
Run: streamlit run app.py
"""
from __future__ import annotations

import sys
import os
import time
import uuid
from pathlib import Path

# Ensure project root is on the path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
/* Main container */
.block-container { padding-top: 1.5rem; }

/* Paper cards */
.paper-card {
    background: linear-gradient(135deg, #1e1e2e 0%, #252535 100%);
    border: 1px solid #3d3d5c;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin: 0.8rem 0;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
}
.paper-card:hover { border-color: #6c5ce7; box-shadow: 0 4px 25px rgba(108,92,231,0.2); }

/* Status badge */
.status-badge {
    display: inline-block;
    background: #2d2d4e;
    border: 1px solid #4a4a7a;
    border-radius: 20px;
    padding: 0.2rem 0.8rem;
    font-size: 0.8rem;
    color: #a0a0d0;
}

/* Insight cards */
.insight-card {
    background: #1a1a3e;
    border-left: 4px solid #6c5ce7;
    border-radius: 0 8px 8px 0;
    padding: 0.8rem 1rem;
    margin: 0.4rem 0;
}

/* Metric boxes */
.metric-box {
    background: #1e1e3e;
    border: 1px solid #3a3a5c;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    text-align: center;
}

/* Source tag */
.source-tag {
    display: inline-block;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 0.7rem;
    font-weight: bold;
    margin-right: 4px;
}
.tag-arxiv { background: #b31b1b22; color: #ff6b6b; border: 1px solid #b31b1b44; }
.tag-ss { background: #1a6b9922; color: #74b9ff; border: 1px solid #1a6b9944; }
.tag-crossref { background: #1a9b4422; color: #55efc4; border: 1px solid #1a9b4444; }
.tag-web { background: #9b6b1a22; color: #ffeaa7; border: 1px solid #9b6b1a44; }
.tag-core { background: #6b1a9b22; color: #a29bfe; border: 1px solid #6b1a9b44; }
</style>
""", unsafe_allow_html=True)


# ── Session state initialisation ──────────────────────────────────────────────
def _init_session():
    defaults = {
        "session_id": str(uuid.uuid4()),
        "research_state": None,
        "query_history": [],
        "is_running": False,
        "selected_provider": settings.LLM_PROVIDER,
        "selected_model": settings.DEFAULT_MODEL,
        "memory_enabled": settings.MEMORY_ENABLED_DEFAULT,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

_init_session()


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown(f"# {settings.APP_ICON} {settings.APP_TITLE}")
        st.markdown("*Advanced Research Discovery & Synthesis*")
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
            st.session_state["src_arxiv"] = st.checkbox("arXiv", value=True)
            st.session_state["src_ss"] = st.checkbox("Semantic Scholar", value=True)
            st.session_state["src_core"] = st.checkbox("CORE", value=True)
        with col2:
            st.session_state["src_crossref"] = st.checkbox("CrossRef", value=True)
            st.session_state["src_web"] = st.checkbox("Web Search", value=True)

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
    st.title(f"{settings.APP_ICON} Intelligent Research Discovery")
    st.markdown(
        "_Describe your research idea, problem statement, or keywords — "
        "the agent will find, rank, and synthesize relevant academic & industrial work._"
    )

    # ── Query input ────────────────────────────────────────────────────────
    with st.container():
        query = st.text_area(
            "📝 Research Query",
            placeholder=(
                "Example: I want to work on lightweight deep learning models for "
                "real-time plant disease detection on edge devices using minimal "
                "computational resources...\n\n"
                "You can enter: keywords, a research idea, problem statement, "
                "draft abstract, or research gap description."
            ),
            height=150,
            max_chars=settings.MAX_QUERY_LENGTH,
            key="query_input",
            help=f"Max {settings.MAX_QUERY_LENGTH} characters. The more context, the better.",
        )

        col_btn, col_count = st.columns([3, 1])
        with col_btn:
            run_clicked = st.button(
                "🚀 Start Research",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.is_running,
            )
        with col_count:
            st.markdown(
                f"<div style='text-align:right;color:#888;padding-top:0.5rem'>"
                f"{len(query or '')}/{settings.MAX_QUERY_LENGTH}</div>",
                unsafe_allow_html=True,
            )

    # ── Example queries ────────────────────────────────────────────────────
    with st.expander("💡 Example queries to try", expanded=False):
        examples = [
            "Lightweight transformer models for real-time object detection on edge devices with limited memory",
            "Federated learning for privacy-preserving medical imaging diagnosis",
            "Large language models for code generation and automated software testing",
            "Multimodal AI for crop disease detection using drone imagery and IoT sensors",
            "Quantum computing algorithms for optimization problems in supply chain management",
        ]
        for ex in examples:
            if st.button(f"→ {ex[:80]}...", key=f"ex_{ex[:20]}", use_container_width=False):
                st.session_state.query_input = ex
                st.rerun()

    st.divider()

    # ── Run agent ──────────────────────────────────────────────────────────
    if run_clicked and query and query.strip():
        _run_agent(query.strip())
    elif run_clicked and not (query and query.strip()):
        st.warning("⚠️ Please enter a research query before starting.")

    # ── Display results ────────────────────────────────────────────────────
    if st.session_state.research_state:
        render_results(st.session_state.research_state)


def _run_agent(query: str):
    """Execute the research agent with streaming updates."""
    st.session_state.is_running = True
    st.session_state.research_state = None

    progress_area = st.empty()
    status_area = st.empty()

    # Node display names for progress bar
    node_steps = [
        ("parse_query", "🧠 Understanding research intent..."),
        ("generate_search_plan", "📋 Planning search strategy..."),
        ("retrieve_papers", "🔍 Searching academic databases & web..."),
        ("rank_sources", "📊 Ranking & filtering results..."),
        ("synthesize_papers", "🧪 Synthesizing each paper..."),
        ("generate_insights", "🔬 Generating research insights..."),
        ("update_memory", "💾 Updating research memory..."),
    ]
    total_steps = len(node_steps)
    step_idx = 0

    with st.spinner(""):
        try:
            progress_bar = progress_area.progress(0, text="Starting research agent...")
            final_state = None

            for state_update in stream_research_agent(
                query=query,
                llm_provider=st.session_state.selected_provider,
                llm_model=st.session_state.selected_model,
                memory_enabled=st.session_state.memory_enabled,
                session_id=st.session_state.session_id if st.session_state.memory_enabled else None,
            ):
                final_state = state_update
                status_msg = state_update.get("status_message", "")

                step_idx = min(step_idx + 1, total_steps)
                progress_pct = int((step_idx / total_steps) * 100)
                progress_bar.progress(progress_pct, text=status_msg)
                status_area.markdown(f"**Status:** {status_msg}")

            progress_area.progress(100, text="✅ Research complete!")
            status_area.empty()

            if final_state:
                st.session_state.research_state = final_state
                if st.session_state.memory_enabled:
                    st.session_state.session_id = final_state.get(
                        "session_id", st.session_state.session_id
                    )
                # Add to history
                st.session_state.query_history.insert(0, {
                    "query": query,
                    "paper_count": len(final_state.get("synthesized_papers", [])),
                })

        except Exception as exc:
            progress_area.error(f"❌ Agent failed: {exc}")
            st.exception(exc)
        finally:
            st.session_state.is_running = False

    time.sleep(0.5)
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
            st.info("No papers retrieved.")
        else:
            # Summary bar
            ccol1, ccol2, ccol3, ccol4 = st.columns(4)
            sources = {p.get("source", "Unknown") for p in papers}
            years = [p.get("year") for p in papers if p.get("year")]
            cited = [p.get("citation_count", 0) or 0 for p in papers]

            ccol1.metric("Total Papers", len(papers))
            ccol2.metric("Sources", len(sources))
            ccol3.metric("Year Range", f"{min(years) if years else 'N/A'} – {max(years) if years else 'N/A'}")
            ccol4.metric("Avg Citations", f"{sum(cited)/len(cited):.0f}" if cited else "N/A")

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
                if years:
                    year_range = st.slider(
                        "Year range",
                        min_value=min(years),
                        max_value=max(years),
                        value=(min(years), max(years)),
                        key="year_range",
                    )
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

            # Paper cards
            for i, paper in enumerate(filtered, 1):
                _render_paper_card(paper, i)

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
        "arXiv": "tag-arxiv",
        "Semantic Scholar": "tag-ss",
        "CrossRef": "tag-crossref",
        "CORE": "tag-core",
    }.get(source, "tag-web")

    title = paper.get("title", "Untitled")
    year = paper.get("year", "")
    authors_raw = paper.get("authors", [])
    if isinstance(authors_raw, list):
        authors = ", ".join(str(a) for a in authors_raw[:4])
        if len(authors_raw) > 4:
            authors += " et al."
    else:
        authors = str(authors_raw)

    citations = paper.get("citation_count")
    cite_str = f"{citations:,}" if isinstance(citations, int) else "N/A"
    relevance = paper.get("relevance_score", 0.0)
    url = paper.get("url", "")
    pdf_url = paper.get("pdf_url", "")
    doi = paper.get("doi", "")

    synth = paper.get("synthesis", {})
    summary = synth.get("summary", paper.get("abstract", "")[:300] or "_No summary available._")
    methodology = synth.get("methodology", "")
    contribution = synth.get("contribution", "")
    limitations = synth.get("limitations", "")
    future_scope = synth.get("future_scope", "")

    with st.container():
        st.markdown(
            f"""<div class="paper-card">
            <span class="source-tag {source_class}">{source}</span>
            <strong>#{index} — {title}</strong>
            {'(' + str(year) + ')' if year else ''}
            </div>""",
            unsafe_allow_html=True,
        )

        with st.expander(
            f"{'📄' if pdf_url else '🔗'} {title[:90]}{'...' if len(title)>90 else ''} "
            f"({year or 'Year?'}) | Citations: {cite_str} | Score: {relevance:.2f}",
            expanded=False,
        ):
            # Top row: links and metadata
            link_col, meta_col = st.columns([2, 1])
            with link_col:
                if authors:
                    st.caption(f"👥 **Authors:** {authors}")
                if url:
                    st.markdown(f"[🔗 View Paper]({url})", unsafe_allow_html=False)
                if pdf_url and pdf_url != url:
                    st.markdown(f"[📄 PDF]({pdf_url})")
                if doi:
                    st.caption(f"DOI: `{doi}`")
            with meta_col:
                st.metric("Relevance", f"{relevance:.2f}")
                if citations is not None:
                    st.metric("Citations", cite_str)

            st.markdown("---")

            # Synthesis sections
            if summary:
                st.markdown("**📝 Summary**")
                st.markdown(summary)

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
