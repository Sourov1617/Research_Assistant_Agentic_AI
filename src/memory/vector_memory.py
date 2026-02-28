"""
Vector Memory — store paper abstracts as embeddings for semantic similarity
search across past sessions.  Backed by FAISS or ChromaDB based on .env config.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


# ── Embedding helper ──────────────────────────────────────────────────────────

def _get_embeddings():
    """Return the configured LangChain embedding model."""
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )
    elif provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=settings.EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )
    else:  # huggingface (default, free)
        try:
            from langchain_huggingface import HuggingFaceEmbeddings  # preferred ≥0.2
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)


# ── FAISS Store ───────────────────────────────────────────────────────────────

class PaperVectorStore:
    """
    Maintains a persistent FAISS or ChromaDB vector store of paper abstracts.
    Enables semantic similarity search across all papers ever seen.
    """

    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = Path(persist_dir or settings.VECTOR_STORE_PATH)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._store = None
        self._embeddings = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = _get_embeddings()
        return self._embeddings

    def _load_or_create(self):
        """Load existing store from disk or create a new one."""
        if self._store is not None:
            return

        vs_type = settings.VECTOR_STORE_TYPE.lower()

        if vs_type == "chroma":
            self._store = self._init_chroma()
        else:
            self._store = self._init_faiss()

    def _init_faiss(self):
        from langchain_community.vectorstores import FAISS

        index_path = self.persist_dir / "faiss_index"
        try:
            if (index_path / "index.faiss").exists():
                store = FAISS.load_local(
                    str(index_path),
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
                logger.info("Loaded existing FAISS store from %s", index_path)
                return store
        except Exception as exc:
            logger.warning("Could not load FAISS store — creating new: %s", exc)

        # Create a minimal empty store with a placeholder
        store = FAISS.from_texts(
            ["Research paper vector store initialized."],
            self.embeddings,
        )
        store.save_local(str(index_path))
        return store

    def _init_chroma(self):
        from langchain_community.vectorstores import Chroma

        return Chroma(
            collection_name="research_papers",
            embedding_function=self.embeddings,
            persist_directory=str(self.persist_dir / "chroma"),
        )

    # ── Public API ─────────────────────────────────────────────────────────

    def add_papers(self, papers: list[dict]) -> None:
        """Embed and store a list of paper dicts."""
        if not papers:
            return
        self._load_or_create()

        texts, metadatas = [], []
        for p in papers:
            text = f"{p.get('title','')}. {p.get('abstract','')[:500]}"
            metadata = {
                "title": p.get("title", ""),
                "year": str(p.get("year") or ""),
                "url": p.get("url", ""),
                "source": p.get("source", ""),
                "citation_count": str(p.get("citation_count") or ""),
            }
            texts.append(text)
            metadatas.append(metadata)

        try:
            self._store.add_texts(texts, metadatas=metadatas)
            self._persist()
            logger.info("Added %d papers to vector store", len(papers))
        except Exception as exc:
            logger.error("Failed to add papers to vector store: %s", exc)

    def search_similar(self, query: str, k: int = 5) -> list[dict]:
        """Find the k most semantically similar papers to the query."""
        self._load_or_create()
        try:
            docs = self._store.similarity_search_with_score(query, k=k)
            results = []
            for doc, score in docs:
                results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": float(score),
                })
            return results
        except Exception as exc:
            logger.error("Vector similarity search failed: %s", exc)
            return []

    def _persist(self):
        """Persist FAISS index to disk (Chroma auto-persists)."""
        if settings.VECTOR_STORE_TYPE.lower() == "faiss" and self._store:
            try:
                index_path = self.persist_dir / "faiss_index"
                self._store.save_local(str(index_path))
            except Exception as exc:
                logger.warning("FAISS persist failed: %s", exc)


# ── Singleton ─────────────────────────────────────────────────────────────────
_default_store: Optional[PaperVectorStore] = None


def get_vector_store() -> PaperVectorStore:
    """Return the global singleton PaperVectorStore."""
    global _default_store
    if _default_store is None:
        _default_store = PaperVectorStore()
    return _default_store
