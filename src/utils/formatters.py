"""
Formatters — Convert agent output to Markdown / plain text for display.
"""

from __future__ import annotations

from typing import Any


# ── Paper Card ────────────────────────────────────────────────────────────────


def format_paper_card(paper: dict, index: int) -> str:
    """Render a single paper as a formatted Markdown card."""
    title = paper.get("title", "Untitled")
    year = paper.get("year", "Unknown Year")
    authors = _format_authors(paper.get("authors", []))
    source = paper.get("source", "Unknown Source")
    url = paper.get("url", "")
    doi = paper.get("doi", "")
    citations = paper.get("citation_count", "N/A")
    relevance = float(paper.get("relevance_score", 0.0))
    # Represent relevance both as 0.0-1.0 internal score and 1-5 star scale for display
    relevance_5 = relevance * 5.0

    summary = paper.get("synthesis", {}).get("summary", "_Not synthesized yet._")
    methodology = paper.get("synthesis", {}).get("methodology", "")
    contribution = paper.get("synthesis", {}).get("contribution", "")
    limitations = paper.get("synthesis", {}).get("limitations", "")
    future_scope = paper.get("synthesis", {}).get("future_scope", "")

    link_section = ""
    if url:
        link_section += f"[📄 Full Paper]({url})"
    if doi:
        link_section += f" | DOI: `{doi}`"

    card = f"""---
### {index}. {title} ({year})

**Authors:** {authors}  
**Source:** {source} | **Citations:** {citations} | **Relevance:** {relevance_5:.1f}/5  
{link_section}

**📝 Summary:**  
{summary}
"""
    if methodology:
        card += f"\n**⚙️ Methodology:**  \n{methodology}\n"
    if contribution:
        card += f"\n**⭐ Key Contribution:**  \n{contribution}\n"
    if limitations:
        card += f"\n**⚠️ Limitations:**  \n{limitations}\n"
    if future_scope:
        card += f"\n**🔮 Future Scope:**  \n{future_scope}\n"

    return card


def _format_authors(authors: list | str) -> str:
    if isinstance(authors, str):
        return authors
    if not authors:
        return "Unknown Authors"
    display = authors[:4]
    suffix = " et al." if len(authors) > 4 else ""
    return ", ".join(str(a) for a in display) + suffix


# ── Insights Block ────────────────────────────────────────────────────────────


def format_insights(insights: dict) -> str:
    """Render the research insights section as Markdown."""
    if not insights:
        return ""

    lines = ["## 🔬 Research Insights\n"]

    if trends := insights.get("emerging_trends"):
        lines.append("### 📈 Emerging Trends")
        for t in _ensure_list(trends):
            lines.append(f"- {t}")
        lines.append("")

    if challenges := insights.get("common_challenges"):
        lines.append("### ⚠️ Common Challenges")
        for c in _ensure_list(challenges):
            lines.append(f"- {c}")
        lines.append("")

    if gaps := insights.get("research_gaps"):
        lines.append("### 🧩 Research Gaps")
        for g in _ensure_list(gaps):
            lines.append(f"- {g}")
        lines.append("")

    if directions := insights.get("suggested_directions"):
        lines.append("### 💡 Suggested Research Directions")
        for d in _ensure_list(directions):
            lines.append(f"- {d}")
        lines.append("")

    if overview := insights.get("overview"):
        lines.append(f"**Overview:** {overview}\n")

    return "\n".join(lines)


# ── Query Intent Block ────────────────────────────────────────────────────────


def format_parsed_intent(intent: dict) -> str:
    """Render the parsed query intent as Markdown."""
    if not intent:
        return ""
    lines = ["### 🧠 Understood Research Intent\n"]
    mappings = {
        "domain": "🏷️ Domain",
        "methods": "🔧 Methods / Techniques",
        "constraints": "📏 Constraints",
        "application_area": "🎯 Application Area",
        "keywords": "🔑 Keywords",
    }
    for key, label in mappings.items():
        if val := intent.get(key):
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            lines.append(f"**{label}:** {val}")
    return "\n".join(lines)


# ── Full Report ────────────────────────────────────────────────────────────────


def format_full_report(state: dict) -> str:
    """Build the complete Markdown research report from agent state."""
    sections: list[str] = []

    # Header
    query = state.get("query", "")
    sections.append(f"# 🔬 Research Report\n\n**Query:** {query}\n")

    # Parsed Intent
    if intent := state.get("parsed_intent"):
        sections.append(format_parsed_intent(intent))

    # Papers
    papers = state.get("synthesized_papers") or state.get("ranked_papers", [])
    if papers:
        sections.append(f"\n## 📚 Relevant Research (Sorted by Recency)\n")
        for i, p in enumerate(papers, 1):
            sections.append(format_paper_card(p, i))
    else:
        sections.append(
            "\n_No papers retrieved. Try a different query or select more sources._\n"
        )

    # Insights
    if insights := state.get("insights"):
        sections.append(format_insights(insights))

    # Memory suggestions
    if suggestions := state.get("memory_suggestions"):
        sections.append("---\n## 🧭 Follow-up Recommendations\n")
        for s in _ensure_list(suggestions):
            sections.append(f"- {s}")

    return "\n".join(sections)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ensure_list(val: Any) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [val]
    return [str(val)]


def truncate(text: str, max_chars: int = 300) -> str:
    """Truncate text and append ellipsis if needed."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"
