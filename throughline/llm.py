"""
LLM client protocol for Anima.

Anima needs an LLM for three things:
1. Experience Capture — classify the message
2. Resonance Reading — read the emotional signal
3. Composition — produce the final message

We do not import any specific provider package. Instead, the host
application passes a client object that implements ``LLMClient`` (or its
duck-typed equivalent). In practice this means an ``openai.AsyncOpenAI``
or any LiteLLM-style wrapper works out of the box.

Why a protocol, not a hard dependency:
- Anima users may already have an LLM client configured (proxy, retries,
  logging, rate limits). Re-creating that inside Anima is wasteful.
- Different providers (OpenAI, Anthropic, OpenRouter, local) have
  different SDK shapes; a protocol lets the host pick.
- Tests can pass a tiny in-memory fake.

The required interface mirrors OpenAI's chat.completions.create with
JSON mode, async. That's the lowest-common-denominator across modern
LLM SDKs.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Minimal async chat-completion interface.

    The expected shape is OpenAI v1 SDK style:

        resp = await client.chat.completions.create(
            model="...",
            messages=[...],
            temperature=0,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content

    Anima only uses these arguments. Anything else (tools, streaming) is
    not used in v0.1.
    """

    @property
    def chat(self) -> Any: ...


class JSONParseFailure(Exception):
    """LLM returned non-JSON text where JSON was required."""


async def call_json(
    client: LLMClient,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.0,
    timeout: float | None = None,
) -> dict:
    """One-shot JSON-mode call. Returns parsed dict.

    Raises ``JSONParseFailure`` if the response is not valid JSON.
    Caller is responsible for catching provider errors.

    Models without JSON-mode support: most current Anima callers use
    OpenRouter/OpenAI which support ``response_format={"type":"json_object"}``.
    If the underlying provider rejects this argument, the call surfaces
    the error; the host should switch to a JSON-capable model.
    """
    create_kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    if timeout is not None:
        create_kwargs["timeout"] = timeout

    resp = await client.chat.completions.create(**create_kwargs)
    try:
        raw = (resp.choices[0].message.content or "").strip()
    except (AttributeError, IndexError) as exc:
        raise JSONParseFailure(f"unexpected LLM response shape: {exc!r}")

    if not raw:
        raise JSONParseFailure("LLM returned empty content")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JSONParseFailure(
            f"LLM returned non-JSON: {raw[:200]!r}"
        ) from exc

    if not isinstance(parsed, dict):
        raise JSONParseFailure(
            f"LLM returned JSON that is not an object: {type(parsed).__name__}"
        )
    return parsed
