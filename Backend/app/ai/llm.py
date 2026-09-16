"""Unified LLM gateway for all backend AI features."""

from __future__ import annotations

import contextvars
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings

try:
    from langfuse import Langfuse
except Exception:  # pragma: no cover - optional dependency safety
    Langfuse = None


logger = logging.getLogger("acufy.ai.llm")
settings = get_settings()

Message = dict[str, str]
TraceObject = Any
ObservationObject = Any


class LLMProviderError(Exception):
    """Raised when a configured LLM provider call fails."""


@dataclass
class TraceScope:
    """Best-effort Langfuse root trace context."""

    trace: TraceObject | None
    root_span: ObservationObject | None
    client: Any | None
    token: contextvars.Token[Any] | None

    def finish(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        status_message: str | None = None,
    ) -> None:
        if self.root_span is not None:
            _safe_end_observation(
                self.root_span,
                output=output,
                metadata=metadata,
                status_message=status_message,
            )
        if self.token is not None:
            _CURRENT_TRACE.reset(self.token)
        _safe_flush(self.client)


@dataclass
class OperationSpan:
    """Best-effort Langfuse child span context."""

    span: ObservationObject | None
    client: Any | None

    def finish(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        status_message: str | None = None,
    ) -> None:
        if self.span is not None:
            _safe_end_observation(
                self.span,
                output=output,
                metadata=metadata,
                status_message=status_message,
            )
        _safe_flush(self.client)


_LANGFUSE_CLIENT: Any | None = None
_LANGFUSE_CLIENT_READY = False
_CURRENT_TRACE: contextvars.ContextVar[TraceObject | None] = contextvars.ContextVar(
    "acufy_langfuse_trace",
    default=None,
)


async def chat(
    messages: list[Message],
    purpose: str | None = None,
    temperature: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Send a chat request through the configured provider gateway."""
    request_temperature = 0.2 if temperature is None else temperature
    provider_chain = _provider_chain()
    last_error: str | None = None

    for attempt_index, provider_config in enumerate(provider_chain):
        provider = provider_config["provider"]
        model = provider_config["model"]
        started = time.perf_counter()
        usage: dict[str, Any] | None = None
        fallback_used = attempt_index > 0
        request_metadata = {
            **(metadata or {}),
            "provider": provider,
            "model": model,
            "purpose": purpose or "unspecified",
            "fallback_used": fallback_used,
            "attempt": attempt_index,
        }
        trace_span = start_operation_span(
            "llm_request",
            metadata=request_metadata,
            input_payload={"messages": messages, "temperature": request_temperature},
        )

        try:
            text, usage = await _dispatch_chat(
                provider=provider,
                model=model,
                messages=messages,
                temperature=request_temperature,
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            trace_span.finish(
                output=text,
                metadata={
                    **request_metadata,
                    "latency_ms": latency_ms,
                    "success": True,
                    "token_usage": usage or {},
                },
                status_message="success",
            )
            _log_request(
                provider=provider,
                model=model,
                purpose=purpose,
                latency_ms=latency_ms,
                success=True,
                fallback_used=fallback_used,
                metadata=metadata,
                usage=usage,
                attempt=attempt_index,
            )
            return text
        except LLMProviderError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            last_error = str(exc)
            trace_span.finish(
                output={"error": last_error},
                metadata={
                    **request_metadata,
                    "latency_ms": latency_ms,
                    "success": False,
                    "token_usage": usage or {},
                },
                status_message="failure",
            )
            _log_request(
                provider=provider,
                model=model,
                purpose=purpose,
                latency_ms=latency_ms,
                success=False,
                fallback_used=fallback_used,
                metadata=metadata,
                usage=usage,
                attempt=attempt_index,
                error=last_error,
            )
            continue

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=last_error or "All configured LLM providers failed.",
    )


async def completion(
    prompt: str,
    *,
    system_prompt: str | None = None,
    purpose: str | None = None,
    temperature: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Convenience wrapper for prompt-style completions via chat."""
    messages: list[Message] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return await chat(
        messages,
        purpose=purpose,
        temperature=temperature,
        metadata=metadata,
    )


def healthcheck() -> dict[str, str]:
    """Return the active provider configuration for health endpoints."""
    return {
        "status": "ok",
        "provider": settings.llm_provider.lower(),
        "model": settings.llm_model,
    }


def get_ai_health() -> dict[str, str]:
    """Backward-compatible health helper."""
    return healthcheck()


def start_trace_scope(
    name: str,
    *,
    metadata: dict[str, Any] | None = None,
    input_payload: Any | None = None,
) -> TraceScope:
    """Start a root trace scope that groups child spans when Langfuse is enabled."""
    client = _get_langfuse_client()
    if client is None:
        return TraceScope(trace=None, root_span=None, client=None, token=None)

    cleaned_metadata = _json_safe(metadata or {})
    try:
        trace = client.trace(
            name=name,
            input=_json_safe(input_payload),
            metadata=cleaned_metadata,
            user_id=_string_value(cleaned_metadata.get("user_id")),
            session_id=_string_value(cleaned_metadata.get("team_id")),
        )
        root_span = trace.span(
            name=name,
            input=_json_safe(input_payload),
            metadata=cleaned_metadata,
        )
        token = _CURRENT_TRACE.set(trace)
        return TraceScope(trace=trace, root_span=root_span, client=client, token=token)
    except Exception:
        logger.debug("langfuse_trace_scope_unavailable", exc_info=True)
        return TraceScope(trace=None, root_span=None, client=None, token=None)


def start_operation_span(
    name: str,
    *,
    metadata: dict[str, Any] | None = None,
    input_payload: Any | None = None,
) -> OperationSpan:
    """Start a child span under the current trace when possible."""
    client = _get_langfuse_client()
    if client is None:
        return OperationSpan(span=None, client=None)

    cleaned_metadata = _json_safe(metadata or {})
    active_trace = _CURRENT_TRACE.get()
    try:
        if active_trace is not None:
            span = active_trace.span(
                name=name,
                input=_json_safe(input_payload),
                metadata=cleaned_metadata,
            )
            return OperationSpan(span=span, client=None)

        trace = client.trace(
            name=name,
            input=_json_safe(input_payload),
            metadata=cleaned_metadata,
            user_id=_string_value(cleaned_metadata.get("user_id")),
            session_id=_string_value(cleaned_metadata.get("team_id")),
        )
        span = trace.span(
            name=name,
            input=_json_safe(input_payload),
            metadata=cleaned_metadata,
        )
        return OperationSpan(span=span, client=client)
    except Exception:
        logger.debug("langfuse_operation_span_unavailable", exc_info=True)
        return OperationSpan(span=None, client=None)


def _provider_chain() -> list[dict[str, str]]:
    providers = [
        {
            "provider": settings.llm_provider.lower(),
            "model": settings.llm_model,
        }
    ]
    if settings.fallback_provider and settings.fallback_model:
        providers.append(
            {
                "provider": settings.fallback_provider.lower(),
                "model": settings.fallback_model,
            }
        )
    return providers


async def _dispatch_chat(
    *,
    provider: str,
    model: str,
    messages: list[Message],
    temperature: float,
) -> tuple[str, dict[str, Any] | None]:
    if provider == "groq":
        return await _chat_openai_compatible(
            api_base="https://api.groq.com/openai/v1",
            api_key=_require_secret(settings.groq_api_key, "GROQ_API_KEY"),
            model=model,
            messages=messages,
            temperature=temperature,
            provider_label="Groq",
        )
    if provider == "openai":
        return await _chat_openai_compatible(
            api_base="https://api.openai.com/v1",
            api_key=_require_secret(settings.openai_api_key, "OPENAI_API_KEY"),
            model=model,
            messages=messages,
            temperature=temperature,
            provider_label="OpenAI",
        )
    if provider == "anthropic":
        return await _chat_anthropic(
            model=model,
            messages=messages,
            temperature=temperature,
        )
    if provider == "gemini":
        return await _chat_gemini(
            model=model,
            messages=messages,
            temperature=temperature,
        )
    if provider == "ollama":
        return await _chat_ollama(
            model=model,
            messages=messages,
            temperature=temperature,
        )

    raise LLMProviderError(f"Unsupported LLM provider: {provider}")


async def _chat_openai_compatible(
    *,
    api_base: str,
    api_key: str,
    model: str,
    messages: list[Message],
    temperature: float,
    provider_label: str,
) -> tuple[str, dict[str, Any] | None]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{api_base.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )

    if response.status_code >= 400:
        raise LLMProviderError(f"{provider_label} request failed: {response.text}")

    data = response.json()
    text = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage")
    return text, usage


async def _chat_anthropic(
    *,
    model: str,
    messages: list[Message],
    temperature: float,
) -> tuple[str, dict[str, Any] | None]:
    api_key = _require_secret(settings.anthropic_api_key, "ANTHROPIC_API_KEY")
    system_prompt = "\n".join(
        message["content"] for message in messages if message.get("role") == "system" and message.get("content")
    ).strip()
    anthropic_messages = [
        {"role": "assistant" if message["role"] == "assistant" else "user", "content": message["content"]}
        for message in messages
        if message.get("role") != "system"
    ]
    payload: dict[str, Any] = {
        "model": model,
        "messages": anthropic_messages,
        "temperature": temperature,
        "max_tokens": 1024,
    }
    if system_prompt:
        payload["system"] = system_prompt

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        )

    if response.status_code >= 400:
        raise LLMProviderError(f"Anthropic request failed: {response.text}")

    data = response.json()
    content_blocks = data.get("content", [])
    text = "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text").strip()
    usage = data.get("usage")
    return text, usage


async def _chat_gemini(
    *,
    model: str,
    messages: list[Message],
    temperature: float,
) -> tuple[str, dict[str, Any] | None]:
    api_key = _require_secret(settings.gemini_api_key, "GEMINI_API_KEY")
    system_prompt = "\n".join(
        message["content"] for message in messages if message.get("role") == "system" and message.get("content")
    ).strip()
    contents = [
        {
            "role": "model" if message["role"] == "assistant" else "user",
            "parts": [{"text": message["content"]}],
        }
        for message in messages
        if message.get("role") != "system"
    ]
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"temperature": temperature},
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={api_key}"
            ),
            json=payload,
        )

    if response.status_code >= 400:
        raise LLMProviderError(f"Gemini request failed: {response.text}")

    data = response.json()
    candidates = data.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    text = "".join(part.get("text", "") for part in parts).strip()
    usage = data.get("usageMetadata")
    return text, usage


async def _chat_ollama(
    *,
    model: str,
    messages: list[Message],
    temperature: float,
) -> tuple[str, dict[str, Any] | None]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json=payload,
        )

    if response.status_code >= 400:
        raise LLMProviderError(f"Ollama request failed: {response.text}")

    data = response.json()
    text = data["message"]["content"].strip()
    usage = {
        "prompt_eval_count": data.get("prompt_eval_count"),
        "eval_count": data.get("eval_count"),
    }
    return text, usage


def _get_langfuse_client() -> Any | None:
    global _LANGFUSE_CLIENT, _LANGFUSE_CLIENT_READY

    if _LANGFUSE_CLIENT_READY:
        return _LANGFUSE_CLIENT

    _LANGFUSE_CLIENT_READY = True
    if (
        Langfuse is None
        or settings.langfuse_public_key is None
        or settings.langfuse_secret_key is None
        or not settings.langfuse_base_url
    ):
        return None

    try:
        _LANGFUSE_CLIENT = Langfuse(
            public_key=settings.langfuse_public_key.get_secret_value(),
            secret_key=settings.langfuse_secret_key.get_secret_value(),
            host=settings.langfuse_base_url,
        )
    except Exception:
        logger.debug("langfuse_client_unavailable", exc_info=True)
        _LANGFUSE_CLIENT = None
    return _LANGFUSE_CLIENT


def _safe_end_observation(
    observation: ObservationObject,
    *,
    output: Any | None = None,
    metadata: dict[str, Any] | None = None,
    status_message: str | None = None,
) -> None:
    try:
        observation.end(
            output=_json_safe(output),
            metadata=_json_safe(metadata or {}),
            status_message=status_message,
        )
    except Exception:
        logger.debug("langfuse_observation_end_failed", exc_info=True)


def _safe_flush(client: Any | None) -> None:
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        logger.debug("langfuse_flush_failed", exc_info=True)


def _require_secret(secret: Any, env_name: str) -> str:
    if secret is None:
        raise LLMProviderError(f"{env_name} is not configured.")
    return secret.get_secret_value()


def _log_request(
    *,
    provider: str,
    model: str,
    purpose: str | None,
    latency_ms: float,
    success: bool,
    fallback_used: bool,
    metadata: dict[str, Any] | None,
    usage: dict[str, Any] | None,
    attempt: int,
    error: str | None = None,
) -> None:
    logger.info(
        "llm_request provider=%s model=%s latency_ms=%s success=%s purpose=%s attempt=%s fallback_used=%s usage=%s metadata=%s error=%s",
        provider,
        model,
        latency_ms,
        success,
        purpose or "unspecified",
        attempt,
        fallback_used,
        json.dumps(usage or {}),
        json.dumps(_json_safe(metadata or {})),
        error or "",
    )


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [_json_safe(item) for item in value]
        return str(value)


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
