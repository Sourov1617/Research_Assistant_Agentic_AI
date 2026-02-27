"""
LLM Factory — build the correct LangChain LLM instance based on the
provider configured in the .env file.  Supports:
  • openai
  • openrouter  (uses ChatOpenAI with a custom base_url)
  • gemini
  • anthropic
  • ollama      (local, no key required)
"""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

from config import settings
from src.utils.ollama_utils import is_ollama_running, list_ollama_models

logger = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """
    Return a LangChain chat model for the requested provider.

    Parameters
    ----------
    provider : str, optional
        Override LLM_PROVIDER from .env.
    model : str, optional
        Override the default model name for that provider.
    temperature : float, optional
        Override LLM_TEMPERATURE from .env.
    """
    _provider = (provider or settings.LLM_PROVIDER).lower().strip()
    _temp = temperature if temperature is not None else settings.LLM_TEMPERATURE

    builders = {
        "openai": _build_openai,
        "openrouter": _build_openrouter,
        "gemini": _build_gemini,
        "anthropic": _build_anthropic,
        "ollama": _build_ollama,
    }

    if _provider not in builders:
        logger.warning(
            "Unknown provider '%s'. Falling back to 'openai'.", _provider
        )
        _provider = "openai"

    return builders[_provider](model=model, temperature=_temp)


def get_available_providers() -> list[str]:
    """Return a list of providers that appear to be configured."""
    available = []
    if settings.OPENAI_API_KEY and "your_" not in settings.OPENAI_API_KEY:
        available.append("openai")
    if settings.OPENROUTER_API_KEY and "your_" not in settings.OPENROUTER_API_KEY:
        available.append("openrouter")
    if settings.GOOGLE_API_KEY and "your_" not in settings.GOOGLE_API_KEY:
        available.append("gemini")
    if settings.ANTHROPIC_API_KEY and "your_" not in settings.ANTHROPIC_API_KEY:
        available.append("anthropic")
    if is_ollama_running():
        available.append("ollama")
    return available or ["openai"]  # always include at least one


def get_available_models(provider: Optional[str] = None) -> list[str]:
    """Return model names available for the given provider."""
    _p = (provider or settings.LLM_PROVIDER).lower()
    if _p == "ollama":
        models = list_ollama_models()
        return models if models else [settings.OLLAMA_DEFAULT_MODEL]
    if _p == "openai":
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ]
    if _p == "openrouter":
        return [
            "meta-llama/llama-3.1-8b-instruct:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-2-9b-it:free",
            "mistralai/mistral-7b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "deepseek/deepseek-r1:free",
            "anthropic/claude-3-haiku",
            "openai/gpt-4o-mini",
            "stepfun/step-3.5-flash:free",
            "arcee-ai/trinity-large-preview:free",
            "upstage/solar-pro-3:free",
            "qwen/qwen3-vl-235b-a22b-thinking",
            "qwen/qwen3-vl-30b-a3b-thinking",
            "openai/gpt-oss-120b:free",
            "openai/gpt-oss-20b:free",
            "qwen/qwen3-vl-30b-a3b-thinking",
        ]
    if _p == "gemini":
        return [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.0-pro",
        ]
    if _p == "anthropic":
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
        ]
    return [settings.DEFAULT_MODEL]


# ── Private builders ──────────────────────────────────────────────────────────

def _build_openai(model: Optional[str], temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model or settings.OPENAI_DEFAULT_MODEL,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )


def _build_openrouter(model: Optional[str], temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model or settings.OPENROUTER_DEFAULT_MODEL,
        temperature=temperature,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://research-agent.local",
            "X-Title": "Research Discovery Agent",
        },
    )


def _build_gemini(model: Optional[str], temperature: float) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model or settings.GEMINI_DEFAULT_MODEL,
        temperature=temperature,
        google_api_key=settings.GOOGLE_API_KEY,
    )


def _build_anthropic(model: Optional[str], temperature: float) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model or settings.ANTHROPIC_DEFAULT_MODEL,
        temperature=temperature,
        api_key=settings.ANTHROPIC_API_KEY,
    )


def _build_ollama(model: Optional[str], temperature: float) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=model or settings.OLLAMA_DEFAULT_MODEL,
        temperature=temperature,
        base_url=settings.OLLAMA_BASE_URL,
    )
