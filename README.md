# 🔬 Intelligent Research Discovery & Synthesis Agent

> **Advanced AI-powered academic literature discovery** — far beyond Google
> Scholar. Understands your research intent, searches multiple academic
> databases, ranks results, synthesizes each paper, and generates research
> insights automatically.

Built with **LangChain**, **LangGraph**, and **Streamlit**.

---

## 🌟 Features

| Feature                          | Description                                                               |
| -------------------------------- | ------------------------------------------------------------------------- |
| 🧠 **Smart Query Understanding** | Understands paragraphs, problem statements, abstracts — not just keywords |
| 🔍 **Multi-Source Search**       | arXiv, Semantic Scholar, CrossRef, CORE, Web (Tavily/DuckDuckGo)          |
| 📊 **Intelligent Ranking**       | Scores by relevance, recency, citations, and source credibility           |
| 🧪 **Paper Synthesis**           | Summary, methodology, key contribution, limitations, future scope         |
| 🔬 **Research Insights**         | Emerging trends, research gaps, unexplored areas, suggested directions    |
| 💾 **Optional Memory**           | Remembers past sessions, tracks research evolution, suggests next steps   |
| 🤖 **Multi-LLM Support**         | OpenAI, OpenRouter, Gemini, or Anthropic                                  |
| 📥 **Export**                    | Download results as Markdown or JSON                                      |

---

## 🏗️ Architecture

```
User Query
   ↓
parse_query          ← Extracts domain, methods, keywords, constraints
   ↓
generate_search_plan ← Decides which sources & query strings to use
   ↓
retrieve_papers      ← Parallel fetch from arXiv, S2, CrossRef, CORE, Web
   ↓
rank_sources         ← Multi-factor scoring (relevance, recency, citations)
   ↓
synthesize_papers    ← LLM synthesis for each paper
   ↓
generate_insights    ← Collective trend/gap/direction analysis
   ↓
update_memory        ← (optional) Persist & generate follow-up suggestions
   ↓
Structured Report
```

---

## 📁 Project Structure

```
Research_Assistant_Agentic_AI/
├── app.py                          # Streamlit frontend (entry point)
├── .env                            # ← YOUR CREDENTIALS (fill this in)
├── .env.example                    # Template with all config keys explained
├── requirements.txt
├── config/
│   └── settings.py                 # Central config loader (reads from .env)
├── src/
│   ├── agents/
│   │   ├── research_agent.py       # LangGraph StateGraph workflow
│   │   ├── state.py                # ResearchState TypedDict
│   │   └── nodes/
│   │       ├── query_parser.py     # Node 1: parse research intent
│   │       ├── search_planner.py   # Node 2: plan multi-source search
│   │       ├── retriever.py        # Node 3: parallel paper retrieval
│   │       ├── ranker.py           # Node 4: score & rank papers
│   │       ├── synthesizer.py      # Node 5: LLM synthesis per paper
│   │       ├── insight_generator.py# Node 6: research insights
│   │       └── memory_node.py      # Node 7: persist & follow-up
│   ├── retrieval/
│   │   ├── arxiv_retriever.py      # arXiv API (free)
│   │   ├── semantic_scholar.py     # Semantic Scholar API (free)
│   │   ├── crossref_retriever.py   # CrossRef API (free)
│   │   ├── core_retriever.py       # CORE Open Access API
│   │   └── web_retriever.py        # Tavily / DuckDuckGo web search
│   ├── memory/
│   │   ├── sqlite_memory.py        # SQLite session & paper history
│   │   └── vector_memory.py        # llama-index / LlamaCloud paper embeddings
│   ├── models/
│   │   └── llm_factory.py          # Multi-provider LLM builder
│   └── utils/
│       └── formatters.py           # Markdown report formatters
└── data/
    ├── memory/                     # SQLite DB + JSON session files
    └── vector_store/               # persisted llama-index or legacy stores
```

---

## ⚙️ Setup

### 1. Clone & install dependencies

```bash
cd d:\Projects\Research_Assistant_Agentic_AI
pip install -r requirements.txt
```

### 2. Configure credentials

Copy `.env.example` → `.env` (already created) and fill in your keys:

```bash
# Required: choose at least ONE LLM provider
OPENAI_API_KEY=sk-...
# OR
OPENROUTER_API_KEY=sk-or-...
# OR
GOOGLE_API_KEY=AIza...

# For web search (optional but recommended)
TAVILY_API_KEY=tvly-...     # https://tavily.com (free tier available)

# For higher rate limits on academic APIs (optional)
SEMANTIC_SCHOLAR_API_KEY=...
CORE_API_KEY=...
```

### 3. Run

```bash
streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

---

## 🤖 LLM Provider Setup

| Provider          | Where to get key              | Free tier?          |
| ----------------- | ----------------------------- | ------------------- |
| **OpenAI**        | https://platform.openai.com   | Paid                |
| **OpenRouter**    | https://openrouter.ai/keys    | ✅ Many free models |
| **Google Gemini** | https://aistudio.google.com   | ✅ Free tier        |
| **Anthropic**     | https://console.anthropic.com | Paid                |

> 💡 **Tip:** For a fully free setup, use **OpenRouter** (free models like Llama
> 3.1, Gemma 2) on OpenRouter.

## 📡 Data Sources

| Source               | Type               | Key Required               | Notes                           |
| -------------------- | ------------------ | -------------------------- | ------------------------------- |
| **arXiv**            | Academic preprints | No                         | 2M+ papers, CS/Math/Physics/Bio |
| **Semantic Scholar** | Academic papers    | Optional                   | 200M+ papers, citation data     |
| **CrossRef**         | DOI metadata       | No (email for polite pool) | Journal articles                |
| **CORE**             | Open access        | Yes (free)                 | 200M+ open access papers        |
| **Tavily**           | Web + industry     | Yes (free tier)            | Blogs, GitHub, industry sites   |
| **DuckDuckGo**       | Web fallback       | No                         | Always available                |

---

## 🔬 Example Output

```
🔬 Research Report
Query: Lightweight deep learning for plant disease detection on edge devices

🧠 Understood Research Intent
Domain: Computer Vision / Precision Agriculture
Methods: CNN, MobileNet, Transformer, Quantization
Keywords: plant disease, edge computing, lightweight CNN, MobileNet, real-time

📚 Relevant Research (Sorted by Recency)

1. EfficientPlant: Edge-Optimized Vision Transformer (2024)
   Summary: Introduces a novel ViT variant achieving 94% accuracy with 3MB model size...
   Methodology: Hybrid CNN-ViT with depthwise convolutions and knowledge distillation
   Contribution: 40% faster inference vs. baseline on Raspberry Pi 4
   Limitations: Evaluated only on PlantVillage — limited real-field diversity
   Future Scope: Multi-disease detection and continual learning

🔬 Research Insights
📈 Trends: Shift from CNNs to hybrid transformer architectures
⚠️ Challenges: Dataset diversity, real-time constraints on microcontrollers
🧩 Gaps: Field-condition datasets, on-device training
💡 Directions: Hybrid CNN-ViT for sub-1MB deployment
```

---

## 🧰 Tech Stack

- **LangChain** — LLM chains, prompts, output parsers
- **LangGraph** — Stateful multi-node agent workflow
- **Streamlit** — Interactive web UI
- **llama-index / LlamaCloud** — Vector memory & embeddings (replaces
  FAISS/Chroma)
- **SQLite** — Conversation & session persistence
- **arXiv / Semantic Scholar / CrossRef / CORE** — Academic paper sources
- **Tavily / DuckDuckGo** — Web & industry search

---

## 🔧 Configuration Reference

All configuration is via `.env`.  
See [`.env.example`](.env.example) for the full annotated reference.

Key settings:

| Variable                 | Default       | Description                                              |
| ------------------------ | ------------- | -------------------------------------------------------- |
| `LLM_PROVIDER`           | `openai`      | Active LLM provider                                      |
| `MAX_PAPERS_PER_SOURCE`  | `10`          | Papers fetched per source                                |
| `MAX_RANKED_PAPERS`      | `15`          | Papers after ranking                                     |
| `MEMORY_ENABLED_DEFAULT` | `false`       | Default memory toggle state                              |
| `VECTOR_STORE_TYPE`      | `llamaindex`  | `llamaindex`, `llamacloud`, `faiss`, or `chroma`         |
| `EMBEDDING_PROVIDER`     | `huggingface` | `huggingface` or `openai` (only used by legacy backends) |

---

## 📄 License

MIT — free to use, modify, and distribute.
