"""
Memory package — SQLite conversation history + vector paper store.
"""
from src.memory.sqlite_memory import (
    init_db,
    create_session,
    list_sessions,
    delete_session,
    add_message,
    get_messages,
    save_papers,
    get_papers_seen,
    save_insights,
    get_session_insights,
    get_session_summary,
)
from src.memory.vector_memory import PaperVectorStore, get_vector_store

__all__ = [
    "init_db",
    "create_session",
    "list_sessions",
    "delete_session",
    "add_message",
    "get_messages",
    "save_papers",
    "get_papers_seen",
    "save_insights",
    "get_session_insights",
    "get_session_summary",
    "PaperVectorStore",
    "get_vector_store",
]
