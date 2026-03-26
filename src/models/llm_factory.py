"""
LLM Factory — build the correct LangChain LLM instance based on the
provider configured in the .env file.  Supported (active) providers:
    • azure_openai
    • openrouter  (uses ChatOpenAI with a custom base_url)
    • gemini
    • groq

OpenAI and Anthropic providers have been intentionally commented-out /
excluded from automatic selection per user request.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

from config import settings

logger = logging.getLogger(__name__)

_ACTIVE_PROVIDERS = {"azure_openai", "openrouter", "gemini", "groq"}


# ── Provider validation ───────────────────────────────────────────────────────


def _is_provider_configured(p: str) -> bool:
    """Return True if the provider has a real (non-placeholder) API key."""
    if p == "openai":
        k = settings.OPENAI_API_KEY
        return bool(k) and "your_" not in k and k != ""
    if p == "azure_openai":
        k = settings.AZURE_OPENAI_API_KEY
        endpoint = settings.AZURE_OPENAI_ENDPOINT
        return (
            bool(k)
            and "your_" not in k
            and k != ""
            and bool(endpoint)
            and "your_" not in endpoint
        )
    if p == "openrouter":
        k = settings.OPENROUTER_API_KEY
        return bool(k) and "your_" not in k and k != ""
    if p == "gemini":
        k = settings.GOOGLE_API_KEY
        return bool(k) and "your_" not in k and k != ""
    if p == "anthropic":
        k = settings.ANTHROPIC_API_KEY
        return bool(k) and "your_" not in k and k != ""
    if p == "groq":
        k = settings.GROQ_API_KEY
        return bool(k) and "your_" not in k and k != ""
    return False


def _resolve_provider(requested: str) -> str:
    """
    Return the requested provider if its key is configured, otherwise return
    the first available provider in priority order.
    """
    # Prioritise configured providers. OpenAI & Anthropic intentionally
    # excluded from automatic fallback.
    priority = [requested, "azure_openai", "openrouter", "groq", "gemini"]
    seen: set[str] = set()
    for p in priority:
        if p in seen or p not in {"azure_openai", "openrouter", "gemini", "groq"}:
            continue
        seen.add(p)
        if _is_provider_configured(p):
            if p != requested:
                logger.warning(
                    "LLM provider '%s' is not configured (placeholder key?). "
                    "Auto-switching to '%s'.",
                    requested,
                    p,
                )
            return p
    logger.error(
        "No LLM provider is properly configured! Tried: %s. " "Check your .env file.",
        list(seen),
    )
    return requested  # fall through — will fail with a clear auth error


def _is_rate_limit_error(exc: Exception) -> bool:
    """Best-effort detection for quota/rate-limit errors across providers."""
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "429",
            "resource_exhausted",
            "rate limit",
            "rate-limit",
            "quota exceeded",
            "too many requests",
        )
    )


def _extract_retry_after_seconds(exc: Exception) -> float | None:
    """Parse retry-after hints like 'Please retry in 55.1s' or retryDelay='55s'."""
    msg = str(exc)
    patterns = [
        r"retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s",
        r"retrydelay['\"]?\s*[:=]\s*['\"]?([0-9]+(?:\.[0-9]+)?)s",
    ]
    for pat in patterns:
        m = re.search(pat, msg, flags=re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return None
    return None


def _provider_failover_chain(requested: Optional[str]) -> list[str]:
    """Ordered provider candidates for runtime failover."""
    req = (requested or settings.LLM_PROVIDER).lower().strip()
    priority = [req, "azure_openai", "openrouter", "groq", "gemini"]
    out: list[str] = []
    seen: set[str] = set()
    for p in priority:
        if p in seen or p not in _ACTIVE_PROVIDERS:
            continue
        seen.add(p)
        if _is_provider_configured(p):
            out.append(p)
    return out


def invoke_with_provider_failover(
    prompt,
    payload: dict,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    parser=None,
):
    """
    Invoke a prompt pipeline with automatic provider failover on 429/quota errors.

    Notes
    -----
    - Tries configured providers in failover order.
    - Keeps the requested model only on the first attempt (same provider);
      subsequent providers use their own default model unless explicitly set
      for that provider in settings.
    - Re-raises non-rate-limit exceptions immediately to preserve existing
      error handling behavior.
    """
    candidates = _provider_failover_chain(provider)
    if not candidates:
        raise RuntimeError(
            "No configured LLM providers available for failover. "
            "Please check API keys in .env."
        )

    first_provider = (provider or settings.LLM_PROVIDER).lower().strip()
    last_exc: Exception | None = None

    for i, p in enumerate(candidates, start=1):
        try:
            chosen_model = model if p == first_provider else None
            llm = get_llm(provider=p, model=chosen_model, temperature=temperature)
            chain = prompt | llm
            if parser is not None:
                chain = chain | parser
            result = chain.invoke(payload)
            if i > 1:
                logger.warning(
                    "LLM failover succeeded on provider '%s' after prior rate-limit failure(s).",
                    p,
                )
            return result
        except Exception as exc:
            last_exc = exc
            if not _is_rate_limit_error(exc):
                raise

            retry_after = _extract_retry_after_seconds(exc)
            if retry_after is not None:
                logger.warning(
                    "Provider '%s' rate-limited (retry-after ~%.1fs). Trying next provider.",
                    p,
                    retry_after,
                )
            else:
                logger.warning(
                    "Provider '%s' rate-limited. Trying next provider.",
                    p,
                )

    raise RuntimeError(
        "All configured providers were rate-limited. " f"Last error: {last_exc}"
    )


# ── Public API ────────────────────────────────────────────────────────────────


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """
    Return a LangChain chat model for the requested provider.
    If the configured provider has no valid API key, automatically falls back
    to the first properly-configured provider so searches never get stuck.

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

    # Note: openai and anthropic builders intentionally omitted per user
    # request. If you later want to re-enable them, add back the mapping.
    builders = {
        "azure_openai": _build_azure_openai,
        "openrouter": _build_openrouter,
        "gemini": _build_gemini,
        "groq": _build_groq,
    }

    if _provider not in builders:
        logger.warning(
            "Unknown or disabled provider '%s'. Falling back to 'openrouter'.",
            _provider,
        )
        _provider = "openrouter"

    # Only auto-resolve when NO provider was explicitly requested (i.e. using
    # the .env default). When the user picks a provider in the sidebar, honour
    # it exactly — never silently swap it out. If it is misconfigured the
    # builder will raise a clear authentication / connection error.
    if provider is None:
        _provider = _resolve_provider(_provider)

    return builders[_provider](model=model, temperature=_temp)


def get_available_providers() -> list[str]:
    """Return a list of providers that appear to be configured."""
    available = []
    if (
        settings.AZURE_OPENAI_API_KEY
        and "your_" not in settings.AZURE_OPENAI_API_KEY
        and settings.AZURE_OPENAI_ENDPOINT
    ):
        available.append("azure_openai")
    if settings.OPENROUTER_API_KEY and "your_" not in settings.OPENROUTER_API_KEY:
        available.append("openrouter")
    if settings.GROQ_API_KEY and "your_" not in settings.GROQ_API_KEY:
        available.append("groq")
    if settings.GOOGLE_API_KEY and "your_" not in settings.GOOGLE_API_KEY:
        available.append("gemini")
    # Exclude OpenAI/Anthropic from the available list by default per request.
    return available or ["openrouter"]  # ensure at least one provider is present


def get_available_models(provider: Optional[str] = None) -> list[str]:
    """Return model names available for the given provider."""
    _p = (provider or settings.LLM_PROVIDER).lower()
    if _p == "azure_openai":
        return [
            "gpt-4.1-mini",
        ]
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
            "qwen/qwen3-235b-a22b:free",
            "qwen/qwen3-30b-a3b:free",
            "qwen/qwen3-vl-235b-a22b-thinking",
            "qwen/qwen3-vl-30b-a3b-thinking",
            "stepfun/step-3.5-flash:free",
            "arcee-ai/trinity-large-preview:free",
            "upstage/solar-pro-3:free",
            "openai/gpt-oss-120b:free",
            "openai/gpt-oss-20b:free",
        ]
    if _p == "gemini":
        # Keep only Gemini models that are known to be supported by the
        # v1beta API for generateContent in current environments.
        # Avoid gemini-3-* variants that may return 404 NOT_FOUND.
        return [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2-flash",
            "gemini-2-flash-lite",
        ]
    if _p == "anthropic":
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
        ]
    if _p == "groq":
        # Updated per current rate-limits dashboard; includes only active models.
        return [
            "allam-2-7b",
            "canopylabs/orpheus-arabic-saudi",
            "canopylabs/orpheus-v1-english",
            "groq/compound",
            "groq/compound-mini",
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "meta-llama/llama-prompt-guard-2-22m",
            "meta-llama/llama-prompt-guard-2-86m",
            "moonshotai/kimi-k2-instruct",
            "moonshotai/kimi-k2-instruct-0905",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "openai/gpt-oss-safeguard-20b",
            "qwen/qwen3-32b",
            "whisper-large-v3",
            "whisper-large-v3-turbo",
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
        timeout=180,  # 3 min max — prevents indefinite HTTP hang
        max_retries=1,  # fail fast rather than retry a broken key
    )


def _build_azure_openai(model: Optional[str], temperature: float) -> BaseChatModel:
    from langchain_openai import AzureChatOpenAI

    selected_model = model or settings.AZURE_OPENAI_DEFAULT_MODEL
    return AzureChatOpenAI(
        model=selected_model,
        temperature=temperature,
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        timeout=180,
        max_retries=1,
    )


def _build_openrouter(model: Optional[str], temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model or settings.OPENROUTER_DEFAULT_MODEL,
        temperature=temperature,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        timeout=180,  # 3 min max for large/thinking models
        max_retries=1,
        default_headers={
            "HTTP-Referer": "https://research-agent.local",
            "X-Title": "Research Discovery Agent",
        },
    )


def _build_gemini(model: Optional[str], temperature: float) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    selected_model = model or settings.GEMINI_DEFAULT_MODEL
    try:
        return ChatGoogleGenerativeAI(
            model=selected_model,
            temperature=temperature,
            google_api_key=settings.GOOGLE_API_KEY,
            # Gemini client timeout is handled by the polling loop in each node
        )
    except Exception as exc:
        # Common failure: model not found (404). Fall back to stable 2.5 model.
        err = str(exc).lower()
        if "not found" in err or "404" in err:
            logger.warning(
                "Gemini model '%s' not found (%s), falling back to gemini-2.5-flash",
                selected_model,
                exc,
            )
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=temperature,
                google_api_key=settings.GOOGLE_API_KEY,
            )
        raise


def _build_anthropic(model: Optional[str], temperature: float) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model or settings.ANTHROPIC_DEFAULT_MODEL,
        temperature=temperature,
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=180,
    )


def _build_groq(model: Optional[str], temperature: float) -> BaseChatModel:
    """Build a ChatGroq model (requires `langchain-groq`)."""
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=model or settings.GROQ_DEFAULT_MODEL,
        temperature=temperature,
        max_retries=1,
        groq_api_key=settings.GROQ_API_KEY,
        groq_api_base=settings.GROQ_BASE_URL,
        request_timeout=180,
    )
