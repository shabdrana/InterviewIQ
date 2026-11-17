"""Provider abstraction. Anthropic and any OpenAI-compatible endpoint are supported.
`get_provider()` returns None when nothing is configured: callers must then use the
clearly labelled rule-based fallback and never present it as an LLM result."""
from __future__ import annotations

import json
import re

import requests

from . import config


class LLMError(Exception):
    pass


class Provider:
    name = "base"
    model = ""

    def complete(self, system: str, user: str, max_tokens: int = 1800) -> str:  # pragma: no cover
        raise NotImplementedError

    @property
    def label(self) -> str:
        return f"{self.name} · {self.model}"


class AnthropicProvider(Provider):
    name = "Anthropic"

    def __init__(self, key: str, model: str):
        self.key, self.model = key, model

    def complete(self, system, user, max_tokens=1800):
        try:
            r = requests.post("https://api.anthropic.com/v1/messages", timeout=90,
                              headers={"x-api-key": self.key, "anthropic-version": "2023-06-01",
                                       "content-type": "application/json"},
                              json={"model": self.model, "max_tokens": max_tokens, "system": system,
                                    "messages": [{"role": "user", "content": user}]})
        except requests.RequestException as e:
            raise LLMError(f"Network error: {e}") from e
        if r.status_code != 200:
            raise LLMError(f"Anthropic API {r.status_code}: {r.text[:200]}")
        return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")


class OpenAICompatProvider(Provider):
    name = "OpenAI-compatible"

    def __init__(self, key: str, model: str, base_url: str):
        self.key, self.model, self.base = key, model, base_url.rstrip("/")

    def complete(self, system, user, max_tokens=1800):
        try:
            r = requests.post(f"{self.base}/chat/completions", timeout=90,
                              headers={"Authorization": f"Bearer {self.key}", "content-type": "application/json"},
                              json={"model": self.model, "max_tokens": max_tokens, "temperature": 0.2,
                                    "messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": user}]})
        except requests.RequestException as e:
            raise LLMError(f"Network error: {e}") from e
        if r.status_code != 200:
            raise LLMError(f"API {r.status_code}: {r.text[:200]}")
 
        data = r.json()
        message = data.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "")

        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )

        if not content:
            raise LLMError(f"Unexpected API response: {data}")

        return content



def get_provider(disabled: bool = False) -> Provider | None:
    if disabled:
        return None
    choice = config.env("LLM_PROVIDER", "auto").lower()
    a_key, o_key = config.env("ANTHROPIC_API_KEY"), config.env("OPENAI_API_KEY")
    if choice in ("auto", "anthropic") and a_key:
        return AnthropicProvider(a_key, config.env("ANTHROPIC_MODEL", "claude-haiku-5-5"))
    if choice in ("auto", "openai") and o_key:
        return OpenAICompatProvider(o_key, config.env("OPENAI_MODEL", "gpt-4o-mini"),
                                    config.env("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    return None


def extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise LLMError("The model did not return JSON.")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"Invalid JSON from model: {e}") from e


def complete_json(provider: Provider, system: str, user: str, max_tokens: int = 1800) -> dict:
    """One automatic retry if the reply is not valid JSON."""
    system += "\nReturn ONLY one valid JSON object. No markdown fences, no commentary."
    try:
        return extract_json(provider.complete(system, user, max_tokens))
    except LLMError as first:
        if "API" in str(first) or "Network" in str(first):
            raise
        return extract_json(provider.complete(system, user + "\n\nYour previous reply was not valid JSON. "
                                                              "Reply with the JSON object only.", max_tokens))
