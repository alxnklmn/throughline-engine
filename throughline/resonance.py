"""
Resonance Reading — what was REALLY said emotionally.

SPEC.md §8.2. Separate from Experience Capture because precision matters
more here: this output drives posture selection, which in turn conditions
the entire composition that the user reads.

A focused, single LLM JSON call. Tight prompt. No tools. No history beyond
what the caller chooses to provide.

The output vocabulary (six fields) is intentionally constrained. It is the
shared language the Posture engine speaks. See SPEC.md §8.3 for the forms
of pain catalogued; this module's prompt names the same set so the LLM
returns terms the rest of the system recognizes.

Fail-safe behavior: on LLM error or malformed JSON, return a neutral
reading with deeper_pain=NONE and Sensitivity.MEDIUM. The downstream
posture engine treats this as "ordinary conversation, default stance."
"""

from __future__ import annotations

import logging

from throughline.llm import JSONParseFailure, LLMClient, call_json
from throughline.types import Pain, ResonanceReading, Sensitivity

log = logging.getLogger("anima.resonance")


# Built as a multi-line string so future edits read clearly. The output is
# constrained to keys the rest of the system understands; free-text fields
# are short and bounded.
RESONANCE_SYSTEM_PROMPT = """you read the EMOTIONAL resonance of a message — what was really said underneath the words.

return STRICT JSON only, no markdown, this exact shape:

{
  "surface_emotion": "single english word for the observable affect, or null",
  "deeper_pain": one of: "fear" | "shame" | "loneliness" | "burnout" | "anger" | "powerlessness" | "loss_of_meaning" | "anxiety" | "resentment" | "overload" | "confusion" | "self_deception" | "quiet_exhaustion" | "panic" | "none",
  "threatened_need": "short english phrase: what feels at risk for the speaker (control, self_worth, belonging, autonomy, ...), or null",
  "support_needed": "short english phrase: what would actually help land (stabilization, validation, presence, structure, perspective, permission_to_rest, ...), or null",
  "wrong_response": "short english phrase: a kind of response that would make things worse (cold_instruction, premature_advice, cheerful_optimism, ...), or null",
  "right_response": "short english phrase: a kind of response that would help (warm_grounding_then_structure, witnessing_without_fixing, ...), or null",
  "sensitivity": "low" | "medium" | "high" | "critical"
}

CRITICAL: this is NOT therapy and the agent is NOT a therapist. You are extracting a structured tag, not making a clinical claim. Conservatism beats precision: if multiple labels could apply, choose the gentler one (anxiety over panic, quiet_exhaustion over burnout) unless the signals are strong.

sensitivity guidelines:
- "low"      — ordinary frustration / minor stress
- "medium"   — meaningful but not fragile distress (most cases)
- "high"     — fragility: shame, public failure, relationship rupture, body issues
- "critical" — crisis signals: self-harm hints, hopelessness, acute danger.
               When critical: agent will NOT compose its own advice — the host
               surfaces external resources. Do not soften "critical" if signals
               are present.

deeper_pain:
- pick "none" if the message is just chat / celebration / a question / a chore
- pick exactly one if real pain is present; the list is exhaustive for v0.1
- "self_deception" is reserved for repeated avoidance patterns — DO NOT pick
  it on a single message; default to "none" or another fitting pain if uncertain

Output must be a single JSON object, no commentary."""


async def read_resonance(
    *,
    client: LLMClient,
    model: str,
    message_text: str,
    recent_context: str | None = None,
    max_message_chars: int = 4000,
    timeout: float = 20.0,
) -> ResonanceReading:
    """Read the resonance of a message.

    Args:
        client: LLM client (any object satisfying ``LLMClient`` protocol).
        model: model identifier passed through to the client.
        message_text: the message to read.
        recent_context: optional 1–3 paragraph summary of the recent
            conversation, for grounding. NOT raw history — caller must
            generalize first.
        max_message_chars: hard cap on the LLM input message size.
        timeout: provider timeout in seconds.

    Returns:
        A ``ResonanceReading``. On any failure: neutral reading.
    """
    text = (message_text or "").strip()
    if not text:
        return _neutral()

    truncated = text if len(text) <= max_message_chars else (text[:max_message_chars] + " […truncated]")
    if recent_context:
        user_msg = f"recent context (already generalized):\n{recent_context.strip()[:1200]}\n\nlatest message:\n{truncated}"
    else:
        user_msg = truncated

    try:
        parsed = await call_json(
            client,
            model=model,
            system_prompt=RESONANCE_SYSTEM_PROMPT,
            user_prompt=user_msg,
            temperature=0.0,
            timeout=timeout,
        )
    except JSONParseFailure as exc:
        log.warning("resonance: non-JSON response: %s", exc)
        return _neutral()
    except Exception as exc:  # noqa: BLE001 — provider can raise anything
        log.warning("resonance: LLM call failed: %r", exc)
        return _neutral()

    return _coerce_resonance(parsed)


def _neutral() -> ResonanceReading:
    return ResonanceReading(deeper_pain=Pain.NONE, sensitivity=Sensitivity.MEDIUM)


_PAIN_VALUES = {p.value for p in Pain}
_SENSITIVITY_VALUES = {s.value for s in Sensitivity}


def _short(value: object, max_len: int = 80) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:max_len]


def _coerce_resonance(raw: dict) -> ResonanceReading:
    """Defensive parse — accept slight LLM shape drift gracefully."""
    pain_val = str(raw.get("deeper_pain") or "none").strip().lower().replace("-", "_")
    if pain_val not in _PAIN_VALUES:
        pain_val = "none"

    sens_val = str(raw.get("sensitivity") or "medium").strip().lower()
    if sens_val not in _SENSITIVITY_VALUES:
        sens_val = "medium"

    return ResonanceReading(
        surface_emotion=_short(raw.get("surface_emotion"), 40),
        deeper_pain=Pain(pain_val),
        threatened_need=_short(raw.get("threatened_need"), 80),
        support_needed=_short(raw.get("support_needed"), 80),
        wrong_response=_short(raw.get("wrong_response"), 80),
        right_response=_short(raw.get("right_response"), 80),
        sensitivity=Sensitivity(sens_val),
    )
