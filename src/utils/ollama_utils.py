"""
Ollama Utility — auto-detect locally installed Ollama models
and check if the Ollama service is reachable.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from config import settings

logger = logging.getLogger(__name__)


def is_ollama_running(base_url: Optional[str] = None) -> bool:
    """Return True if the Ollama server is reachable."""
    url = base_url or settings.OLLAMA_BASE_URL
    try:
        resp = requests.get(f"{url}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def list_ollama_models(base_url: Optional[str] = None) -> list[str]:
    """
    Return a list of model names available in the local Ollama installation.
    Returns an empty list if Ollama is not running.
    """
    url = base_url or settings.OLLAMA_BASE_URL
    try:
        resp = requests.get(f"{url}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        return sorted(models)
    except Exception as exc:
        logger.debug("Ollama not reachable: %s", exc)
        return []


def get_ollama_model_info(model_name: str, base_url: Optional[str] = None) -> dict:
    """Return metadata for a specific Ollama model (size, family, etc.)."""
    url = base_url or settings.OLLAMA_BASE_URL
    try:
        resp = requests.post(
            f"{url}/api/show",
            json={"name": model_name},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.debug("Could not fetch Ollama model info: %s", exc)
        return {}


def pull_ollama_model(model_name: str, base_url: Optional[str] = None) -> bool:
    """Pull (download) an Ollama model. Returns True on success."""
    url = base_url or settings.OLLAMA_BASE_URL
    try:
        resp = requests.post(
            f"{url}/api/pull",
            json={"name": model_name},
            timeout=300,
            stream=True,
        )
        return resp.status_code == 200
    except Exception as exc:
        logger.error("Failed to pull Ollama model %s: %s", model_name, exc)
        return False
