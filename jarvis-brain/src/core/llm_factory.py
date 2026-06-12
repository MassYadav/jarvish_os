"""
jarvis-brain/src/core/llm_factory.py

Production-grade LLM factory with deterministic failover routing.

Architecture:
  get_llm_client(config)  ← NEW primary API — called by graph nodes
  select_and_build_llm()  ← LEGACY shim kept for backward compat with any external callers

Cascade contract (per spec):
  requested provider → opposite cloud provider → Ollama local fallback
  e.g.  groq → gemini → ollama
        gemini → groq → ollama
        anything else → groq → gemini → ollama
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

# Typed exceptions for isolated failure handling (no generic catch-alls)
from groq import AuthenticationError as GroqAuthError
from groq import RateLimitError as GroqRateLimitError
from groq import APIStatusError as GroqAPIStatusError
from groq import APIConnectionError as GroqConnectionError
from google.genai.errors import ClientError as GeminiClientError
from google.genai.errors import APIError as GeminiAPIError

from src.core.config import settings
from src.core.logger import logger

# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class LLMResult:
    """
    Immutable result returned by get_llm_client().

    Attributes:
        provider:         The provider that was actually engaged ("groq", "gemini", "ollama").
        model:            The exact model string passed to the LangChain constructor.
        client:           The ready-to-call LangChain chat model.
        slow_model_active: True when Ollama local fallback was engaged.
                           Propagate into AgentState so the Gateway can surface a
                           performance-warning toast on the frontend.
    """
    provider: str
    model: str
    client: Any
    slow_model_active: bool = False


# ---------------------------------------------------------------------------
# O(1) environment-variable fallback table
# Keys are the provider names; values are env-var names to look up.
# ---------------------------------------------------------------------------

_ENV_KEY_MAP: dict[str, str] = {
    "groq":   "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

# Default models per provider — overridden by execution_config.active_model
_DEFAULT_MODELS: dict[str, str] = {
    "groq":   settings.GROQ_MODEL,
    "gemini": settings.GEMINI_MODEL,
    "ollama": settings.OLLAMA_MODEL,
}

# Deterministic cascade: primary → cloud-fallback → local-fallback
_CASCADE_MAP: dict[str, tuple[str, ...]] = {
    "groq":    ("groq",    "gemini", "ollama"),
    "gemini":  ("gemini",  "groq",   "ollama"),
    # Any unknown provider defaults to this order
    "__default__": ("groq", "gemini", "ollama"),
}


# ---------------------------------------------------------------------------
# Key resolution — O(1) lookup: payload first, then env
# ---------------------------------------------------------------------------

def _resolve_key(provider: str, payload_keys: dict[str, str | None]) -> str | None:
    """
    Return the API key for *provider*, checking the request payload before os.getenv().
    Falls back to the environment variable named in _ENV_KEY_MAP.
    Returns None if neither source has a non-empty value.
    """
    # 1. Payload (highest priority — user-supplied or vault-decrypted)
    payload_value = payload_keys.get(f"{provider}_api_key") or payload_keys.get(f"{provider}_key")
    if payload_value and payload_value.strip():
        return payload_value.strip()

    # 2. Environment variable — O(1) dict lookup for the var name, then os.getenv
    env_var = _ENV_KEY_MAP.get(provider)
    if env_var:
        env_value = os.getenv(env_var, "")
        if env_value.strip():
            return env_value.strip()

    return None


# ---------------------------------------------------------------------------
# Individual provider builders — each raises only typed exceptions
# ---------------------------------------------------------------------------

def _build_groq(key: str, model: str) -> ChatGroq:
    """
    Instantiate ChatGroq. Raises GroqAuthError / GroqRateLimitError /
    GroqAPIStatusError on key/API problems — never a bare Exception.
    """
    return ChatGroq(
        groq_api_key=key,
        model_name=model,
        temperature=0,
        max_retries=1,      # one internal retry is enough; we handle failover here
    )


def _build_gemini(key: str, model: str) -> ChatGoogleGenerativeAI:
    """
    Instantiate ChatGoogleGenerativeAI. Raises GeminiClientError /
    GeminiAPIError on auth or service problems.
    """
    return ChatGoogleGenerativeAI(
        google_api_key=key,
        model=model,
        temperature=0,
        max_retries=1,
    )


def _build_ollama(model: str) -> ChatOllama:
    """
    Instantiate ChatOllama pointed at the local daemon.
    No auth errors possible; connection errors are caught at call-time.
    """
    return ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=model,
        temperature=0,
        format="json",
    )


# ---------------------------------------------------------------------------
# PRIMARY PUBLIC API
# ---------------------------------------------------------------------------

def get_llm_client(config: dict) -> LLMResult:
    """
    Resolve and initialise the best available LLM for this request.

    Args:
        config: The merged execution context dict.  Expected keys (all optional):
                  active_provider    — "groq" | "gemini" | "ollama" | …
                  active_model       — model override string
                  groq_api_key       — inline key from frontend ExecutionConfig
                  gemini_api_key     — inline key from frontend ExecutionConfig
                  groq_key           — vault-decrypted alias (gateway normalises to this)
                  gemini_key         — vault-decrypted alias
                  failed_providers   — list[str] already tried this session

    Returns:
        LLMResult with (provider, model, client, slow_model_active).
        slow_model_active=True signals that Ollama local fallback was engaged —
        the caller must propagate this into AgentState so the Gateway can push
        a performance-warning toast to the UI.

    Raises:
        RuntimeError: Only when all three cascade stages are exhausted.
    """
    active_provider: str = config.get("active_provider", "groq") or "groq"
    active_model:    str = config.get("active_model", "") or ""
    already_failed:  list[str] = list(config.get("failed_providers", []))

    # Build the cascade sequence for the requested provider
    cascade: tuple[str, ...] = _CASCADE_MAP.get(active_provider, _CASCADE_MAP["__default__"])

    logger.info(
        "llm_factory_cascade_start",
        requested_provider=active_provider,
        cascade=cascade,
        has_active_model=bool(active_model),
    )

    for provider in cascade:
        if provider in already_failed:
            logger.debug("llm_factory_skip_failed", provider=provider)
            continue

        # ── OLLAMA LOCAL FALLBACK ────────────────────────────────────────────
        if provider == "ollama":
            model = active_model if active_model and active_provider == "ollama" else _DEFAULT_MODELS["ollama"]
            logger.warning(
                "llm_factory_ollama_fallback",
                reason="all cloud providers exhausted or missing keys",
                model=model,
            )
            client = _build_ollama(model)
            return LLMResult(
                provider="ollama",
                model=model,
                client=client,
                slow_model_active=True,   # ← spec requirement: signal slow model
            )

        # ── CLOUD PROVIDERS ──────────────────────────────────────────────────
        key = _resolve_key(provider, config)

        if not key:
            logger.info("llm_factory_no_key", provider=provider, action="skip_to_next")
            continue

        # Resolve the model: use active_model only when this IS the user's chosen provider
        model = (
            active_model
            if active_model and provider == active_provider
            else _DEFAULT_MODELS.get(provider, "")
        )
        if not model:
            model = _DEFAULT_MODELS.get(provider, "llama-3.3-70b-versatile")

        # ── GROQ ─────────────────────────────────────────────────────────────
        if provider == "groq":
            # Intercept and upgrade decommissioned models to their active replacements
            if model in ("llama3-70b-8192", "llama-3.1-70b-versatile"):
                model = "llama-3.3-70b-versatile"
            elif model == "llama3-8b-8192":
                model = "llama-3.1-8b-instant"

            try:
                client = _build_groq(key, model)
                logger.info("llm_factory_selected", provider="groq", model=model)
                return LLMResult(provider="groq", model=model, client=client)

            except GroqAuthError as e:
                # 401 — key is invalid or revoked
                logger.warning("llm_factory_groq_auth_error", error=str(e), action="cascade_to_next")

            except GroqRateLimitError as e:
                # 429 — quota exhausted; cascade rather than wait
                logger.warning("llm_factory_groq_rate_limit", error=str(e), action="cascade_to_next")

            except GroqAPIStatusError as e:
                # 4xx/5xx service errors (model not found, server error, etc.)
                logger.warning("llm_factory_groq_api_status", status=e.status_code, error=str(e), action="cascade_to_next")

            except GroqConnectionError as e:
                logger.warning("llm_factory_groq_connection", error=str(e), action="cascade_to_next")

        # ── GEMINI ───────────────────────────────────────────────────────────
        elif provider == "gemini":
            try:
                client = _build_gemini(key, model)
                logger.info("llm_factory_selected", provider="gemini", model=model)
                return LLMResult(provider="gemini", model=model, client=client)

            except GeminiClientError as e:
                # 4xx client errors — bad key, quota exceeded, model not found
                logger.warning("llm_factory_gemini_client_error", error=str(e), action="cascade_to_next")

            except GeminiAPIError as e:
                # Base API error — covers 5xx and unexpected server-side failures
                logger.warning("llm_factory_gemini_api_error", error=str(e), action="cascade_to_next")

        # Mark this provider as failed so we don't retry it in the inner-graph retry loop
        already_failed.append(provider)

    # ── TOTAL EXHAUSTION ─────────────────────────────────────────────────────
    logger.error("llm_factory_all_exhausted", cascade=cascade, failed=already_failed)
    raise RuntimeError(
        f"JARVIS: All LLM providers exhausted. Cascade attempted: {cascade}. "
        f"Check your API keys and Ollama daemon status."
    )


# ---------------------------------------------------------------------------
# LEGACY SHIM — preserves backward compatibility with planner/synthesizer
# callers that still use select_and_build_llm(api_keys, failed, active_model)
# ---------------------------------------------------------------------------

def select_and_build_llm(
    api_keys: dict,
    failed_providers: list,
    active_model: str = "",
) -> tuple[str, Any]:
    """
    Legacy wrapper around get_llm_client().

    Returns (provider_name, llm_client) — the same tuple shape the existing
    planner.py and synthesizer.py callers expect.

    Note: slow_model_active is intentionally dropped here.  Graph nodes that need
    it should migrate to get_llm_client() and propagate the flag into state.
    """
    config = {
        **api_keys,                                  # groq_key, gemini_key, preferred_provider, etc.
        "active_provider": api_keys.get("preferred_provider", "groq"),
        "active_model":    active_model,
        "failed_providers": failed_providers or [],
    }
    result = get_llm_client(config)
    return result.provider, result.client