"""
Vector Memory — store paper abstracts as embeddings for semantic similarity
search across past sessions.  Supports local llamaindex indexes or remote
LlamaCloud; legacy FAISS/Chroma support is retained for backwards
compatibility but not recommended.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


# NOTE: llama-index handles embeddings internally so the previous helper
# that built LangChain embedding objects is no longer required.  We keep the
# function around in case some other part of the project still needs it, but
# all new vector backends ignore it.


def _get_embeddings():
    """Return the configured LangChain embedding model.

    This is only used by the legacy FAISS/Chroma code paths; new llamaindex
    backends use ``ServiceContext`` to manage embeddings automatically.
    """
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY,
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
    Generic paper store abstraction.  The concrete backend is selected via
    ``VECTOR_STORE_TYPE`` in the configuration:

    * ``llamaindex`` – local llama-index on‑disk index (recommended)
    * ``llamacloud`` – remote index stored in LlamaCloud service
    * ``chroma``/``faiss`` – legacy LangChain stores (kept for backward
      compatibility, not used by default anymore).
    """

    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = Path(persist_dir or settings.VECTOR_STORE_PATH)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._store = None
        self._backend = settings.VECTOR_STORE_TYPE.lower()
        # Log chosen backend and path so it's visible in app logs
        logger.info(
            "Vector store backend: %s (persist_dir=%s)", self._backend, self.persist_dir
        )

    def _load_or_create(self):
        """Instantiate the underlying store or load an existing index."""
        if self._store is not None:
            return

        if self._backend in ("llamaindex", "llamacloud"):
            self._store = self._init_llama()
        elif self._backend == "chroma":
            self._store = self._init_chroma()
        else:
            # fallback to faiss for older configurations
            self._store = self._init_faiss()

    # -------- llama‑index backends ------------------------------------------------

    def _init_llama(self):
        try:
            from llama_index.core import (
                StorageContext,
                VectorStoreIndex,
                load_index_from_storage,
            )
        except ImportError as exc:
            raise RuntimeError(
                "llama_index must be installed to use llamaindex/llamacloud "
                "vector stores"
            ) from exc

        if self._backend == "llamacloud":
            from llama_index.indices.managed.llama_cloud import LlamaCloudIndex

            api_key = settings.LLAMA_CLOUD_API_KEY
            index_name = settings.LLAMA_CLOUD_INDEX_NAME or "research_papers"
            project_name = getattr(settings, "LLAMA_CLOUD_PROJECT_NAME", "Default")

            if not api_key:
                logger.error("LlamaCloud requested but LLAMA_CLOUD_API_KEY is missing")
                raise ValueError("LLAMA_CLOUD_API_KEY is required for llamacloud")

            logger.info(
                "Initializing LlamaCloud backend (index=%s, project=%s)",
                index_name,
                project_name,
            )
            try:
                idx = LlamaCloudIndex(
                    name=index_name,
                    project_name=project_name,
                    api_key=api_key,
                )
                logger.info("Loaded existing LlamaCloud index '%s'", index_name)
            except Exception as exc_get:
                logger.warning(
                    "Could not load LlamaCloud index '%s' (will attempt create): %s",
                    index_name,
                    exc_get,
                )
                try:
                    idx = LlamaCloudIndex.create_index(
                        name=index_name,
                        project_name=project_name,
                        api_key=api_key,
                    )
                    logger.info("Created new LlamaCloud index '%s'", index_name)
                except Exception as exc_create:
                    logger.error(
                        "Failed to create LlamaCloud index '%s': %s",
                        index_name,
                        exc_create,
                    )
                    raise
            return idx

        # local llama-index persisted to disk
        storage_context = StorageContext.from_defaults(
            persist_dir=str(self.persist_dir)
        )
        try:
            idx = load_index_from_storage(storage_context)
            logger.info("Loaded existing LlamaIndex index from %s", self.persist_dir)
            return idx
        except Exception as exc:
            logger.info(
                "Creating new LlamaIndex index at %s (%s)", self.persist_dir, exc
            )
            idx = VectorStoreIndex.from_documents([], storage_context=storage_context)
            storage_context.persist()
            return idx

    def _add_papers_llama(self, papers: list[dict]) -> None:
        from llama_index.core import Document

        docs = []
        for p in papers:
            text = f"{p.get('title','')}. {p.get('abstract','')[:500]}"
            metadata = {
                "title": p.get("title", ""),
                "year": str(p.get("year") or ""),
                "url": p.get("url", ""),
                "source": p.get("source", ""),
                "citation_count": str(p.get("citation_count") or ""),
            }
            docs.append(Document(text=text, metadata=metadata))

        try:
            if hasattr(self._store, "insert_documents"):
                self._store.insert_documents(docs)
            elif hasattr(self._store, "insert"):
                for doc in docs:
                    self._store.insert(doc)
            elif hasattr(self._store, "add_documents"):
                self._store.add_documents(docs)
            else:
                # fall back to generic ``add_texts`` if available (legacy stores)
                texts = [d.text for d in docs]
                metadatas = [d.metadata for d in docs]
                self._store.add_texts(texts, metadatas=metadatas)

            # persist local index
            if self._backend == "llamaindex":
                try:
                    self._store.storage_context.persist()
                except Exception:
                    pass

            logger.info("Added %d papers to vector store", len(papers))
        except Exception as exc:
            logger.error("Failed to add papers to vector store: %s", exc)

    def _search_llama(self, query: str, k: int = 5) -> list[dict]:
        try:
            qengine = self._store.as_query_engine(similarity_top_k=k)
            resp = qengine.query(query)
            nodes = getattr(resp, "source_nodes", [])
            results = []
            for node in nodes:
                # nodes may be wrapped in a ``NodeWithScore``
                raw = getattr(node, "node", node)
                content = getattr(raw, "get_text", lambda: raw.text)()
                metadata = getattr(raw, "metadata", getattr(raw, "extra_info", {}))
                score = getattr(node, "score", getattr(raw, "score", 0.0))
                results.append(
                    {
                        "content": content,
                        "metadata": metadata,
                        "similarity_score": float(score or 0.0),
                    }
                )
            return results
        except Exception as exc:
            logger.error("Llama index similarity search failed: %s", exc)
            return []

    # -------- legacy faiss/chroma -------------------------------------------------

    def _init_faiss(self):
        from langchain_community.vectorstores import FAISS

        index_path = self.persist_dir / "faiss_index"
        try:
            if (index_path / "index.faiss").exists():
                store = FAISS.load_local(
                    str(index_path),
                    _get_embeddings(),
                    allow_dangerous_deserialization=True,
                )
                logger.info("Loaded existing FAISS store from %s", index_path)
                return store
        except Exception as exc:
            logger.warning("Could not load FAISS store — creating new: %s", exc)

        store = FAISS.from_texts(
            ["Research paper vector store initialized."],
            _get_embeddings(),
        )
        store.save_local(str(index_path))
        return store

    def _init_chroma(self):
        from langchain_community.vectorstores import Chroma

        return Chroma(
            collection_name="research_papers",
            embedding_function=_get_embeddings(),
            persist_directory=str(self.persist_dir / "chroma"),
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def add_papers(self, papers: list[dict]) -> None:
        """Embed and store a list of paper dicts."""
        if not papers:
            return
        self._load_or_create()

        if self._backend in ("llamaindex", "llamacloud"):
            return self._add_papers_llama(papers)

        # legacy path (texts/metadata handled above)
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
        if self._backend in ("llamaindex", "llamacloud"):
            return self._search_llama(query, k)

        try:
            docs = self._store.similarity_search_with_score(query, k=k)
            results = []
            for doc, score in docs:
                results.append(
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "similarity_score": float(score),
                    }
                )
            return results
        except Exception as exc:
            logger.error("Vector similarity search failed: %s", exc)
            return []

    def _persist(self):
        """Persist FAISS index to disk (Chroma auto-persists)."""
        if self._backend == "faiss" and self._store:
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
