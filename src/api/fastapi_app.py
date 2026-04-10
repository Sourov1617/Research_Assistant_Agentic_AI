from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from config import settings
from src.api.job_manager import ResearchJobManager
from src.memory.sqlite_memory import (
    create_session,
    delete_session,
    get_messages,
    get_papers_seen,
    get_session_insights,
    init_db,
    list_sessions,
)
from src.models.llm_factory import get_available_models, get_available_providers

logger = logging.getLogger(__name__)

AVAILABLE_SOURCES = [
    {"key": "arxiv", "label": "arXiv", "enabled_by_default": True},
    {"key": "crossref", "label": "Crossref", "enabled_by_default": True},
    {"key": "core", "label": "CORE", "enabled_by_default": True},
    {"key": "ieee_web", "label": "IEEE", "enabled_by_default": True},
    {"key": "sciencedirect_web", "label": "ScienceDirect", "enabled_by_default": True},
    {"key": "mdpi_web", "label": "MDPI", "enabled_by_default": True},
    {"key": "nature_web", "label": "Nature", "enabled_by_default": True},
    {"key": "acm_web", "label": "ACM", "enabled_by_default": True},
    {"key": "springer_web", "label": "Springer", "enabled_by_default": True},
    {"key": "openreview_web", "label": "OpenReview", "enabled_by_default": True},
]

job_manager = ResearchJobManager()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    job_manager.close()


app = FastAPI(
    title="Research Assistant API",
    version="1.0.0",
    description="FastAPI backend for the Research Discovery and Synthesis Agent.",
    lifespan=lifespan,
)

_cors_origins = [
    origin.strip() for origin in settings.API_CORS_ORIGINS.split(",") if origin.strip()
]
_allow_credentials = "*" not in _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartResearchRequest(BaseModel):
    query: str = Field(min_length=1)
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_temperature: float | None = None
    memory_enabled: bool = False
    session_id: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    fast_mode: bool = False
    enabled_sources: list[str] | None = None
    fetch_round: int = 0


class CreateSessionRequest(BaseModel):
    title: str = ""


def _build_request_payload(payload: StartResearchRequest) -> dict[str, Any]:
    enabled_sources = payload.enabled_sources or [
        source["key"] for source in AVAILABLE_SOURCES if source["enabled_by_default"]
    ]
    return {
        "query": payload.query.strip(),
        "llm_provider": payload.llm_provider,
        "llm_model": payload.llm_model,
        "llm_temperature": payload.llm_temperature,
        "memory_enabled": payload.memory_enabled,
        "session_id": payload.session_id,
        "year_min": payload.year_min,
        "year_max": payload.year_max,
        "fast_mode": payload.fast_mode,
        "enabled_sources": enabled_sources,
        "fetch_round": payload.fetch_round,
    }


@app.get("/")
def root():
    return {
        "name": app.title,
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app_title": settings.APP_TITLE,
        "vector_store_type": settings.VECTOR_STORE_TYPE,
        "memory_backend": settings.MEMORY_BACKEND,
        "kafka_enabled": settings.KAFKA_ENABLED,
    }


@app.get("/config")
def config():
    return {
        "app": {
            "title": settings.APP_TITLE,
            "theme": settings.APP_THEME,
            "max_query_length": settings.MAX_QUERY_LENGTH,
        },
        "defaults": {
            "llm_provider": settings.LLM_PROVIDER,
            "llm_model": settings.DEFAULT_MODEL,
            "llm_temperature": settings.LLM_TEMPERATURE,
            "memory_enabled": settings.MEMORY_ENABLED_DEFAULT,
            "fast_mode": False,
            "year_min": None,
            "year_max": None,
        },
        "providers": get_available_providers(),
        "models": {
            provider: get_available_models(provider)
            for provider in get_available_providers()
        },
        "sources": AVAILABLE_SOURCES,
        "streaming": {
            "sse_endpoint_template": "/research/jobs/{job_id}/events",
            "polling_endpoint_template": "/research/jobs/{job_id}",
        },
        "memory": {
            "enabled_default": settings.MEMORY_ENABLED_DEFAULT,
            "backend": settings.MEMORY_BACKEND,
        },
        "kafka": {
            "enabled": settings.KAFKA_ENABLED,
            "topic_prefix": settings.KAFKA_TOPIC_PREFIX,
        },
    }


@app.get("/providers")
def providers():
    return {"providers": get_available_providers()}


@app.get("/models/{provider}")
def models(provider: str):
    return {"models": get_available_models(provider)}


@app.get("/sources")
def sources():
    return {"sources": AVAILABLE_SOURCES}


@app.post("/research/run")
def run_research(payload: StartResearchRequest):
    request_payload = _build_request_payload(payload)
    result = job_manager.run_sync(request_payload)
    return {"status": "complete", "state": result}


@app.post("/research")
@app.post("/research/jobs")
def start_research(payload: StartResearchRequest):
    request_payload = _build_request_payload(payload)
    if not request_payload["query"]:
        raise HTTPException(status_code=400, detail="Query is required")

    job_id = str(uuid.uuid4())
    job = job_manager.create_job(job_id, request_payload)
    job_manager.start_streaming_job(job)
    return {"job_id": job_id, "status": job.status}


@app.get("/research/{job_id}")
@app.get("/research/jobs/{job_id}")
def get_research_job(job_id: str):
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_manager.serialize_job(job)


@app.get("/research/jobs/{job_id}/events/recent")
def get_recent_job_events(job_id: str):
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "events": job_manager.get_recent_events(job_id)}


@app.get("/research/{job_id}/events")
@app.get("/research/jobs/{job_id}/events")
async def stream_job_events(job_id: str):
    if job_manager.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    generator = job_manager.sse_iter(job_id)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/research/{job_id}/stop")
@app.post("/research/jobs/{job_id}/stop")
def stop_research(job_id: str):
    job = job_manager.stop_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "status": job.status}


@app.get("/memory/sessions")
def memory_sessions():
    init_db()
    return {"sessions": list_sessions()}


@app.post("/memory/sessions")
def create_memory_session(payload: CreateSessionRequest):
    init_db()
    session_id = create_session(payload.title)
    return {"session_id": session_id}


@app.get("/memory/sessions/{session_id}")
def memory_session_detail(session_id: str):
    init_db()
    sessions = {session["session_id"]: session for session in list_sessions()}
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session": session,
        "messages": get_messages(session_id),
        "papers": get_papers_seen(session_id),
        "insights": get_session_insights(session_id),
    }


@app.delete("/memory/sessions/{session_id}")
def delete_memory_session(session_id: str):
    init_db()
    sessions = {session["session_id"]: session for session in list_sessions()}
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)
    return JSONResponse({"session_id": session_id, "deleted": True})
