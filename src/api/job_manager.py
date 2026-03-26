from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from config import settings
from src.agents.research_agent import run_research_agent, stream_research_agent

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_for_json(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, BaseModel):
        return _sanitize_for_json(value.model_dump())
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).startswith("_"):
                continue
            clean[str(key)] = _sanitize_for_json(item)
        return clean
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_for_json(item) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


class KafkaEventPublisher:
    def __init__(self) -> None:
        self._enabled = settings.KAFKA_ENABLED
        self._producer = None
        if not self._enabled:
            return

        try:
            from kafka import KafkaProducer
        except ImportError:
            logger.warning(
                "KAFKA_ENABLED=true but kafka-python is not installed. "
                "Kafka publishing is disabled."
            )
            self._enabled = False
            return

        try:
            self._producer = KafkaProducer(
                bootstrap_servers=[
                    item.strip()
                    for item in settings.KAFKA_BOOTSTRAP_SERVERS.split(",")
                    if item.strip()
                ],
                value_serializer=lambda payload: json.dumps(payload).encode("utf-8"),
            )
        except Exception as exc:
            logger.warning("Kafka producer initialization failed: %s", exc)
            self._enabled = False
            self._producer = None

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        if not self._enabled or self._producer is None:
            return
        try:
            self._producer.send(topic, payload)
        except Exception as exc:
            logger.warning("Kafka publish failed for topic %s: %s", topic, exc)

    def close(self) -> None:
        if self._producer is None:
            return
        try:
            self._producer.flush(timeout=2)
            self._producer.close(timeout=2)
        except Exception as exc:
            logger.warning("Kafka producer close failed: %s", exc)


class JobEventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[queue.Queue[dict[str, Any]]]] = {}
        self._lock = threading.Lock()
        self._kafka = KafkaEventPublisher()

    def subscribe(self, job_id: str) -> queue.Queue[dict[str, Any]]:
        subscriber: queue.Queue[dict[str, Any]] = queue.Queue()
        with self._lock:
            self._subscribers.setdefault(job_id, set()).add(subscriber)
        return subscriber

    def unsubscribe(self, job_id: str, subscriber: queue.Queue[dict[str, Any]]) -> None:
        with self._lock:
            subscribers = self._subscribers.get(job_id)
            if not subscribers:
                return
            subscribers.discard(subscriber)
            if not subscribers:
                self._subscribers.pop(job_id, None)

    def publish(self, job_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        envelope = {
            "job_id": job_id,
            "event": event_type,
            "timestamp": _utc_now(),
            "data": _sanitize_for_json(payload),
        }

        with self._lock:
            subscribers = list(self._subscribers.get(job_id, set()))

        for subscriber in subscribers:
            try:
                subscriber.put_nowait(envelope)
            except Exception:
                logger.debug("Dropping event for slow subscriber on job %s", job_id)

        self._kafka.publish(f"{settings.KAFKA_TOPIC_PREFIX}.research.jobs", envelope)
        return envelope

    def close(self) -> None:
        self._kafka.close()


@dataclass
class ResearchJob:
    id: str
    request: dict[str, Any]
    status: str = "queued"
    latest_state: dict[str, Any] | None = None
    error: str | None = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    history: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=200))


class ResearchJobManager:
    TERMINAL_STATUSES = {"complete", "error", "stopped"}

    def __init__(self) -> None:
        self._jobs: dict[str, ResearchJob] = {}
        self._lock = threading.Lock()
        self._events = JobEventBroker()

    def close(self) -> None:
        self._events.close()

    def create_job(self, job_id: str, request_payload: dict[str, Any]) -> ResearchJob:
        job = ResearchJob(id=job_id, request=_sanitize_for_json(request_payload))
        with self._lock:
            self._jobs[job_id] = job
        self._publish(job, "queued", {"status": "queued", "request": job.request})
        return job

    def get_job(self, job_id: str) -> ResearchJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def subscribe(self, job_id: str) -> queue.Queue[dict[str, Any]]:
        return self._events.subscribe(job_id)

    def unsubscribe(self, job_id: str, subscriber: queue.Queue[dict[str, Any]]) -> None:
        self._events.unsubscribe(job_id, subscriber)

    def stop_job(self, job_id: str) -> ResearchJob | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        job.stop_event.set()
        self._set_status(job, "stopping")
        self._publish(job, "stopping", {"status": "stopping"})
        return job

    def get_recent_events(self, job_id: str) -> list[dict[str, Any]]:
        job = self.get_job(job_id)
        if job is None:
            return []
        return list(job.history)

    def run_sync(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        result = run_research_agent(**request_payload)
        return _sanitize_for_json(result)

    def start_streaming_job(self, job: ResearchJob) -> None:
        agent_queue: queue.Queue[dict[str, Any]] = queue.Queue()

        def _drain_agent_queue() -> None:
            while True:
                try:
                    item = agent_queue.get(timeout=0.5)
                except queue.Empty:
                    if job.status in self.TERMINAL_STATUSES:
                        return
                    continue
                if item is None:
                    return
                self._publish(job, "interim", item)

        def _worker() -> None:
            self._set_status(job, "running")
            self._publish(job, "started", {"status": "running", "request": job.request})

            drain_thread = threading.Thread(target=_drain_agent_queue, daemon=True)
            drain_thread.start()

            try:
                first_chunk = True
                final_state: dict[str, Any] | None = None
                for update in stream_research_agent(
                    **job.request,
                    stop_event=job.stop_event,
                    agent_queue=agent_queue,
                ):
                    if first_chunk:
                        first_chunk = False
                        continue
                    if job.stop_event.is_set():
                        self._set_status(job, "stopped")
                        self._publish(job, "stopped", {"status": "stopped"})
                        return

                    clean_update = _sanitize_for_json(update)
                    final_state = clean_update
                    self._set_state(job, clean_update)
                    self._publish(
                        job,
                        "state",
                        {
                            "status": job.status,
                            "state": clean_update,
                            "status_message": clean_update.get("status_message"),
                        },
                    )

                if job.stop_event.is_set():
                    self._set_status(job, "stopped")
                    self._publish(job, "stopped", {"status": "stopped"})
                else:
                    self._set_status(job, "complete")
                    self._publish(
                        job,
                        "complete",
                        {"status": "complete", "state": final_state or job.latest_state},
                    )
            except Exception as exc:
                logger.exception("Research job %s failed", job.id)
                self._set_status(job, "error")
                job.error = str(exc)
                self._publish(job, "error", {"status": "error", "error": str(exc)})
            finally:
                try:
                    agent_queue.put_nowait(None)
                except Exception:
                    pass

        thread = threading.Thread(target=_worker, daemon=True, name=f"research-job-{job.id}")
        job.thread = thread
        thread.start()

    def serialize_job(self, job: ResearchJob) -> dict[str, Any]:
        return {
            "id": job.id,
            "status": job.status,
            "state": job.latest_state,
            "error": job.error,
            "request": job.request,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }

    async def sse_iter(self, job_id: str):
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(job_id)

        subscriber = self.subscribe(job_id)
        # Send a snapshot first so a frontend gets an immediate state.
        initial_snapshot = {
            "job_id": job.id,
            "event": "snapshot",
            "timestamp": _utc_now(),
            "data": self.serialize_job(job),
        }
        yield _format_sse("snapshot", initial_snapshot)

        try:
            while True:
                try:
                    event = await asyncio.to_thread(subscriber.get, True, 15)
                except queue.Empty:
                    heartbeat = {
                        "job_id": job.id,
                        "event": "heartbeat",
                        "timestamp": _utc_now(),
                        "data": {"status": self.get_job(job_id).status if self.get_job(job_id) else "unknown"},
                    }
                    yield _format_sse("heartbeat", heartbeat)
                    continue

                yield _format_sse(event["event"], event)
                if event["event"] in {"complete", "error", "stopped"}:
                    break
        finally:
            self.unsubscribe(job_id, subscriber)

    def _publish(self, job: ResearchJob, event_type: str, payload: dict[str, Any]) -> None:
        envelope = self._events.publish(job.id, event_type, payload)
        job.history.append(envelope)

    def _set_state(self, job: ResearchJob, state: dict[str, Any]) -> None:
        job.latest_state = state
        job.updated_at = _utc_now()

    def _set_status(self, job: ResearchJob, status: str) -> None:
        job.status = status
        job.updated_at = _utc_now()


def _format_sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"

