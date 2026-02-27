"""
SQLite Memory — persistent conversation & paper history storage.

Stores:
  • sessions      — metadata per research session
  • messages      — conversation turns per session
  • papers_seen   — papers the user has been shown
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or settings.SQLITE_DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Create tables if they do not yet exist."""
    conn = _get_conn(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id   TEXT PRIMARY KEY,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            title        TEXT,
            meta_json    TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT NOT NULL,
            role         TEXT NOT NULL,
            content      TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS papers_seen (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT NOT NULL,
            title        TEXT,
            authors      TEXT,
            year         INTEGER,
            url          TEXT,
            source       TEXT,
            citation_count INTEGER,
            added_at     TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE TABLE IF NOT EXISTS research_insights (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT NOT NULL,
            query        TEXT,
            insights_json TEXT,
            created_at   TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );
        """
    )
    conn.commit()
    conn.close()


# ── Session management ────────────────────────────────────────────────────────

def create_session(title: str = "", db_path: Optional[str] = None) -> str:
    """Create a new session and return its session_id."""
    init_db(db_path)
    conn = _get_conn(db_path)
    session_id = str(uuid.uuid4())
    now = _now()
    conn.execute(
        "INSERT INTO sessions (session_id, created_at, updated_at, title) VALUES (?,?,?,?)",
        (session_id, now, now, title or f"Session {now[:10]}"),
    )
    conn.commit()
    conn.close()
    logger.debug("Created session: %s", session_id)
    return session_id


def list_sessions(db_path: Optional[str] = None) -> list[dict]:
    """Return all sessions sorted by most recent first."""
    init_db(db_path)
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM sessions ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_session(session_id: str, db_path: Optional[str] = None) -> None:
    """Delete a session and all its associated data."""
    conn = _get_conn(db_path)
    for table in ("messages", "papers_seen", "research_insights", "sessions"):
        conn.execute(f"DELETE FROM {table} WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()


# ── Message management ────────────────────────────────────────────────────────

def add_message(
    session_id: str,
    role: str,
    content: str,
    db_path: Optional[str] = None,
) -> None:
    """Append a message to the conversation history."""
    conn = _get_conn(db_path)
    now = _now()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
        (session_id, role, content, now),
    )
    conn.execute(
        "UPDATE sessions SET updated_at=? WHERE session_id=?",
        (now, session_id),
    )
    conn.commit()
    conn.close()


def get_messages(
    session_id: str,
    max_turns: Optional[int] = None,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Return conversation history for a session (most recent last)."""
    limit = max_turns or settings.MAX_MEMORY_TURNS
    conn = _get_conn(db_path)
    rows = conn.execute(
        """
        SELECT role, content, created_at FROM messages
        WHERE session_id=?
        ORDER BY id DESC LIMIT ?
        """,
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


# ── Paper tracking ────────────────────────────────────────────────────────────

def save_papers(
    session_id: str,
    papers: list[dict],
    db_path: Optional[str] = None,
) -> None:
    """Persist a batch of papers shown in this session."""
    conn = _get_conn(db_path)
    now = _now()
    for p in papers:
        conn.execute(
            """
            INSERT INTO papers_seen
              (session_id, title, authors, year, url, source, citation_count, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                p.get("title", ""),
                json.dumps(p.get("authors", [])),
                p.get("year"),
                p.get("url", ""),
                p.get("source", ""),
                p.get("citation_count"),
                now,
            ),
        )
    conn.commit()
    conn.close()


def get_papers_seen(
    session_id: str,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Return all papers seen in a session."""
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM papers_seen WHERE session_id=? ORDER BY added_at DESC",
        (session_id,),
    ).fetchall()
    conn.close()
    data = []
    for r in rows:
        item = dict(r)
        try:
            item["authors"] = json.loads(item.get("authors", "[]"))
        except Exception:
            pass
        data.append(item)
    return data


# ── Insights tracking ─────────────────────────────────────────────────────────

def save_insights(
    session_id: str,
    query: str,
    insights: dict,
    db_path: Optional[str] = None,
) -> None:
    """Persist research insights for a session query."""
    conn = _get_conn(db_path)
    conn.execute(
        """
        INSERT INTO research_insights
          (session_id, query, insights_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, query, json.dumps(insights), _now()),
    )
    conn.commit()
    conn.close()


def get_session_insights(
    session_id: str,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Return all insight records for a session."""
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM research_insights WHERE session_id=? ORDER BY created_at DESC",
        (session_id,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        try:
            item["insights"] = json.loads(item.get("insights_json", "{}"))
        except Exception:
            item["insights"] = {}
        result.append(item)
    return result


def get_session_summary(session_id: str, db_path: Optional[str] = None) -> str:
    """Build a condensed textual summary of a session for passing to the LLM."""
    msgs = get_messages(session_id, db_path=db_path)
    papers = get_papers_seen(session_id, db_path=db_path)
    insights = get_session_insights(session_id, db_path=db_path)

    lines = [
        f"Session has {len(msgs)} past messages.",
        f"{len(papers)} papers have been reviewed.",
    ]

    if msgs:
        user_queries = [m["content"][:100] for m in msgs if m["role"] == "user"]
        if user_queries:
            lines.append(f"Past queries: {' | '.join(user_queries[-5:])}")

    if papers:
        titles = [p["title"] for p in papers[:5]]
        lines.append(f"Recent papers: {'; '.join(titles)}")

    if insights:
        last = insights[0].get("insights", {})
        if gaps := last.get("research_gaps"):
            if isinstance(gaps, list):
                lines.append(f"Identified gaps: {', '.join(gaps[:3])}")

    return "\n".join(lines)


# ── Helper ────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().isoformat()
