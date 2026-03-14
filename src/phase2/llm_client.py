"""
Local LLM client (Ollama).

Calls Ollama API for chat/completion. No streaming in v1.
Uses httpx if available, else requests.
"""

from __future__ import annotations

import json
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

try:
    import requests
except ImportError:
    requests = None  # type: ignore


def _post(url: str, json_payload: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    if httpx is not None:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=json_payload)
        resp.raise_for_status()
        return resp.json()
    if requests is not None:
        resp = requests.post(url, json=json_payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("Install httpx or requests for LLM client: pip install httpx")


def generate(
    messages: list[dict[str, str]],
    *,
    base_url: str = "http://localhost:11434",
    model: str = "llama3.2",
    max_tokens: int = 1024,
) -> str:
    """
    Send messages to Ollama chat API and return the assistant reply.
    messages: [{"role": "user"|"assistant"|"system", "content": "..."}]
    """
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    data = _post(url, payload)
    msg = data.get("message") or {}
    return msg.get("response", "").strip()


def generate_simple(
    prompt: str,
    *,
    base_url: str = "http://localhost:11434",
    model: str = "llama3.2",
    max_tokens: int = 1024,
    system: str | None = None,
) -> str:
    """One-shot generate: system (optional) + user prompt."""
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return generate(messages, base_url=base_url, model=model, max_tokens=max_tokens)
