"""
Retrieval package — academic and web source connectors.
"""

from src.retrieval.arxiv_retriever import search_arxiv

# from src.retrieval.semantic_scholar import search_semantic_scholar
from src.retrieval.crossref_retriever import search_crossref
from src.retrieval.core_retriever import search_core
from src.retrieval.web_retriever import search_web

__all__ = [
    "search_arxiv",
    # "search_semantic_scholar",
    "search_crossref",
    "search_core",
    "search_web",
]
