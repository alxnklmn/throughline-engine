"""
Experience Capture — what *kind* of thing was just said.

SPEC.md §8.1. Runs on every observed incoming message. Produces an
``ExperienceReading`` that downstream layers use to decide:
- whether resonance reading is worth its cost
- whether a thread should be created
- what the rough emotional weight is

Single LLM JSON call. The prompt is intentionally narrow — this is
classification, not interpretation. Resonance Reading does interpretation.

Cost discipline: cheap model, tiny output, hard length cap on the message.
"""

from __future__ import annotations

import logging

from throughline.llm import JSONParseFailure, LLMClient, call_json
from throughline.types import ExperienceReading

log = logging.getLogger("anima.experience")


EXPERIENCE_SYSTEM_PROMPT = """you classify what KIND of thing was just said in a message between an owner and the agent that serves them, or between an owner and one of the owner's contacts.

return STRICT JSON only, no markdown, this exact shape:

{
  "kind": "request" | "confession" | "avoidance" | "celebration" | "cry_for_help" | "checkin" | "unburdening" | "chat",
  "has_event_with_time": true | false,
  "implied_emotion": "single word in english (optional) or null",
  "has_commitment": true | false,
  "has_intent": true | false,
  "has_creative_impulse": true | false,
  "thread_candidate": "short title in english under 60 chars if a Human State Thread should be created, else null"
}

kind taxonomy (pick exactly ONE — the dominant flavor):

- "request"     — explicit ask for the agent or contact to do something
- "confession"  — disclosing something heavy: failure, regret, hidden struggle
- "avoidance"   — naming a topic while declining to engage with it ("I just don't want to think about it")
- "celebration" — good news, sharing a win
- "cry_for_help"— acute distress, panic, crisis signals — ANY hint of self-harm goes here
- "checkin"     — passing update, no need attached ("just so you know, I'm at the office")
- "unburdening" — venting, catharsis, no specific ask
- "chat"        — ordinary conversation with no emotional load (default fallback)

guidance:
- has_event_with_time = true when a discernible upcoming or recent event is mentioned with a time anchor (today, tomorrow, this Friday, in 2 hours, exam at 14:30, ...)
- has_commitment = true when the speaker says they WILL do X
- has_intent = true when they say they WANT to do X
- has_creative_impulse = true when an idea / inspiration / project is mentioned
- thread_candidate: ONLY if this message gives you enough to track a follow-up later. Title should be vague, friend-style ("something important today", "the exam tomorrow"). NEVER include precise PII / addresses / numbers. Null if no thread.

if uncertain — kind="chat", everything else false/null. Conservative > eager."""


async def capture_experience(
    *,
    client: LLMClient,
    model: str,
    message_text: str,
    max_message_chars: int = 4000,
    timeout: float = 15.0,
) -> ExperienceReading:
    """Run Experience Capture. Returns an ``ExperienceReading``.

    On any LLM failure or parse failure, returns a safe default:
    ``kind="chat"`` with all flags False, ``thread_candidate=None``.
    The agent then proceeds as if nothing special happened — fail-safe,
    not fail-loud.
    """
    text = (message_text or "").strip()
    if not text:
        return ExperienceReading(kind="chat")

    # hard cap input to keep this call cheap
    truncated = text if len(text) <= max_message_chars else (text[:max_message_chars] + " […truncated]")

    try:
        parsed = await call_json(
            client,
            model=model,
            system_prompt=EXPERIENCE_SYSTEM_PROMPT,
            user_prompt=truncated,
            temperature=0.0,
            timeout=timeout,
        )
    except JSONParseFailure as exc:
        log.warning("experience: non-JSON response: %s", exc)
        return ExperienceReading(kind="chat")
    except Exception as exc:  # noqa: BLE001 — provider can raise anything
        log.warning("experience: LLM call failed: %r", exc)
        return ExperienceReading(kind="chat")

    return _coerce_experience(parsed)


_VALID_KINDS = {
    "request", "confession", "avoidance", "celebration",
    "cry_for_help", "checkin", "unburdening", "chat",
}


def _coerce_experience(raw: dict) -> ExperienceReading:
    """Defensive parse — LLM might return slightly wrong shape."""
    kind = str(raw.get("kind") or "chat").strip().lower()
    if kind not in _VALID_KINDS:
        kind = "chat"

    def _bool(name: str) -> bool:
        v = raw.get(name)
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in {"true", "yes", "1"}
        return False

    implied = raw.get("implied_emotion")
    if implied is not None:
        implied = str(implied).strip() or None
        if implied and len(implied) > 40:
            implied = implied[:40]

    candidate = raw.get("thread_candidate")
    if candidate is not None:
        candidate = str(candidate).strip() or None
        if candidate and len(candidate) > 80:
            candidate = candidate[:80]

    return ExperienceReading(
        kind=kind,  # type: ignore[arg-type]  # validated above
        has_event_with_time=_bool("has_event_with_time"),
        implied_emotion=implied,
        has_commitment=_bool("has_commitment"),
        has_intent=_bool("has_intent"),
        has_creative_impulse=_bool("has_creative_impulse"),
        thread_candidate=candidate,
    )
