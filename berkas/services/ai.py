from __future__ import annotations

import json
import time
from dataclasses import dataclass

from berkas.security import SafeHttpError, safe_request

GROQ_BASE = "https://api.groq.com/openai/v1"
OPENAI_BASE = "https://api.openai.com/v1"
DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-20b",
    "openai": "gpt-4o-mini",
}
RETRY_STATUS = {429, 500, 502, 503, 504}


class AiUnavailable(RuntimeError):
    """Raised when no provider is configured or every attempt failed."""


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class Completion:
    content: str
    provider: str
    model: str


def resolve_provider(settings) -> Provider | None:
    requested = (getattr(settings, "ai_provider", "auto") or "auto").strip().lower()
    if requested in {"none", "off", "disabled"}:
        return None
    if requested in {"auto", ""}:
        if settings.groq_api_key:
            requested = "groq"
        elif settings.openai_api_key:
            requested = "openai"
        else:
            return None
    if requested == "groq":
        if not settings.groq_api_key:
            return None
        return Provider(
            name="groq",
            base_url=(settings.ai_base_url or GROQ_BASE).rstrip("/"),
            api_key=settings.groq_api_key,
            model=settings.ai_model or DEFAULT_MODELS["groq"],
        )
    if requested in {"openai", "openai_compatible", "compatible"}:
        if not settings.openai_api_key:
            return None
        compatible = requested != "openai"
        if compatible and (not settings.ai_base_url or not settings.ai_model):
            return None
        return Provider(
            name="openai" if not compatible else "compatible",
            base_url=(settings.ai_base_url or OPENAI_BASE).rstrip("/"),
            api_key=settings.openai_api_key,
            model=settings.ai_model or DEFAULT_MODELS["openai"],
        )
    return None


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Model tidak mengembalikan objek JSON.")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("JSON dari model bukan objek.")
    return payload


def complete_json(settings, system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 1600) -> Completion:
    provider = resolve_provider(settings)
    if provider is None:
        raise AiUnavailable("Tidak ada provider AI yang siap dipakai.")
    base_payload = {
        "model": provider.model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    timeout = max(5, int(getattr(settings, "ai_timeout_s", 30)))
    last_error = "unknown"
    # Some providers reject JSON mode for specific models. Try it first, then
    # retry once without it and parse the JSON object from the text response.
    for json_mode in (True, False):
        payload = dict(base_payload)
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        attempts = 3 if json_mode else 1
        for attempt in range(attempts):
            try:
                response = safe_request(
                    "POST",
                    f"{provider.base_url}/chat/completions",
                    timeout=timeout,
                    headers=headers,
                    json=payload,
                    allow_http=False,
                )
            except SafeHttpError as exc:
                last_error = exc.message
            else:
                if response.status == 200:
                    try:
                        body = response.json()
                        content = str(body["choices"][0]["message"]["content"])
                        _extract_json(content)
                    except (ValueError, KeyError, IndexError, TypeError):
                        last_error = "respons model bukan JSON yang valid"
                        break
                    return Completion(content=content, provider=provider.name, model=provider.model)
                last_error = f"status {response.status}"
                if response.status not in RETRY_STATUS:
                    break
            if attempt < attempts - 1:
                time.sleep(0.6 * (2**attempt))
    raise AiUnavailable(f"Provider tidak bisa dipakai ({last_error}).")


def parse_completion(completion: Completion) -> dict:
    return _extract_json(completion.content)
