"""
Composer — turns the chosen posture + archetype + resonance into a message.

This is the only place Anima emits user-facing words. The output passes
through ``moral.audit_output`` before delivery (Engine orchestrator).

The composer prompt is tightly scoped: it is NOT given general
conversational latitude. It is asked to produce a single message of a
specific shape — that keeps output predictable and on-brand. SPEC.md §16.

Inputs:
- posture + archetype (chosen upstream)
- resonance (drives the right_response / wrong_response hints)
- generalized facts (already passed through generalize() upstream)
- the message to respond to
- recent history if the host provides it (caller is responsible for
  generalizing or trimming this before passing)
- the moral-layer constraints (negative instructions layered in)
- language hint ('ru' / 'en' / 'auto')

Output: a single short string. No structured JSON — composer produces
plain text.

Retry policy on moral audit failure is handled by the orchestrator
(engine.py), not here. Composer is one-shot.
"""

from __future__ import annotations

import logging
from typing import Optional

from throughline.types import (
    Archetype,
    Pain,
    Posture,
    ResonanceReading,
    Sensitivity,
)

log = logging.getLogger("anima.composer")


# Per-posture style guidance. Each is a 1-3 line directive that gets
# embedded in the composer's system prompt.
_POSTURE_GUIDE: dict[Posture, str] = {
    Posture.HOLD: (
        "GROUNDING comes first. The user is in fear/shame/distress. Do NOT lead with structure, "
        "do NOT solve, do NOT advise. One short steadying sentence; offer to do nothing if that's "
        "what's needed. Make it feel like a friend who isn't rushing."
    ),
    Posture.GUIDE: (
        "STRUCTURE is welcome here. The user is resolution-ready. Offer one clean next step or "
        "a small structure (goal → constraints → first step). Be brief. Don't lecture."
    ),
    Posture.SILENCE: (
        "(this branch should not call the composer; if it does, produce only an internal-use "
        "single neutral sentence — do NOT include it in user-facing output)"
    ),
    # below are v0.2-deferred but the prompts exist for the day they ship
    Posture.MIRROR: (
        "REFLECT the user's internal conflict without resolving it. 'I hear two things — X and Y.' "
        "Hold both. Do NOT pick a side. Do NOT prescribe."
    ),
    Posture.CHALLENGE: (
        "Gentle CONFRONTATION of a pattern, never the person. One observation, named directly, then "
        "space. Do NOT lecture. Do NOT pile on. Keep the user's dignity intact."
    ),
    Posture.PROTECT: (
        "REFUSE the harmful path plainly. Do not strategize around it even creatively. Offer "
        "presence without engagement of the path."
    ),
    Posture.WITNESS: (
        "Just SEE it. No fix, no advice, no silver lining. Acknowledge weight. 'It's heavy.' That's "
        "the whole message."
    ),
}

# Per-archetype voice guidance.
_ARCHETYPE_VOICE: dict[Archetype, str] = {
    Archetype.COMPANION: (
        "voice: walks beside the user. Neutral warmth. Plain words. No teaching tone, no "
        "performative care. Default for everything."
    ),
    Archetype.FRIEND: (
        "voice: a close friend who knows the user. Warmer than companion. Brevity. Occasional "
        "dry humor IF the user's energy invites it — never when in fear/shame."
    ),
    Archetype.TEACHER: (
        "voice: structures and explains. Treats errors as material, not evidence of failure. "
        "Small steps. Does not condescend."
    ),
    Archetype.PARENT_FIGURE: (
        "voice: re-grounds the user in basics (sleep, food, rest) WITHOUT infantilizing. Never "
        "possessive. Never 'you should'. (v0.1: will not be selected.)"
    ),
    Archetype.ENEMY_OF_SELF_DECEPTION: (
        "voice: names the pattern the user is avoiding. Targets the pattern, never the person. "
        "Brief, direct, kind. (v0.1: will not be selected.)"
    ),
    Archetype.VIEW_FROM_HEIGHT: (
        "voice: invites a longer time horizon. Never claims authority or omniscience. "
        "(v0.1: will not be selected.)"
    ),
    Archetype.SHADOW_MIRROR: (
        "voice: reflects what the user avoids seeing. Names, does not condemn. (v0.1: blocked.)"
    ),
}


def build_system_prompt(
    *,
    posture: Posture,
    archetype: Archetype,
    resonance: ResonanceReading,
    constraints: list[str],
    language_hint: str = "ru",
    learned_style: Optional[str] = None,
) -> str:
    """Assemble the composer system prompt from all inputs.

    Public so the engine can record exactly what prompt led to the
    composed message (for transparency / audit).
    """
    parts: list[str] = []

    parts.append(
        "you are composing ONE short message from an AI agent to a person it serves. "
        "you are NOT a chatbot, NOT a therapist, NOT an authority. you are a presence."
    )

    lang_line = {
        "ru": "compose in russian, lowercase by default, conversational not formal.",
        "en": "compose in english, lowercase by default, conversational not formal.",
    }.get(language_hint, "match the user's language; lowercase by default.")
    parts.append(lang_line)

    # Posture + archetype
    parts.append("posture (HOW to be in this moment):\n" + _POSTURE_GUIDE[posture])
    parts.append("archetype (AS WHOM):\n" + _ARCHETYPE_VOICE[archetype])

    # Resonance hints
    reso_lines = ["what this message is really about (use, don't quote):"]
    if resonance.deeper_pain != Pain.NONE:
        reso_lines.append(f"  pain: {resonance.deeper_pain.value}")
    if resonance.surface_emotion:
        reso_lines.append(f"  surface emotion: {resonance.surface_emotion}")
    if resonance.threatened_need:
        reso_lines.append(f"  threatened need: {resonance.threatened_need}")
    if resonance.support_needed:
        reso_lines.append(f"  what would help: {resonance.support_needed}")
    if resonance.wrong_response:
        reso_lines.append(f"  what would make it worse: {resonance.wrong_response}")
    if resonance.right_response:
        reso_lines.append(f"  the right shape: {resonance.right_response}")
    reso_lines.append(f"  sensitivity: {resonance.sensitivity.value}")
    parts.append("\n".join(reso_lines))

    # Learned per-user voice (optional)
    if learned_style:
        parts.append(f"learned voice for this user:\n{learned_style.strip()[:600]}")

    # Moral-layer constraints (CRITICAL: these are negative instructions)
    if constraints:
        bullets = "\n".join(f"- {c}" for c in constraints)
        parts.append("constraints (HARD; violating these is a failure):\n" + bullets)

    # Length + shape
    parts.append(
        "output:\n"
        "- 1 to 3 short sentences. one sentence is often best.\n"
        "- no markdown, no bullets, no preface like 'i hear you,'.\n"
        "- no quotes around the message.\n"
        "- no signing off, no name, no 'love'.\n"
        "- never claim feelings ('i feel'). 'i notice' / 'i see' are fine.\n"
        "- if the right action is no words, output literally: <silence>"
    )

    return "\n\n".join(parts)


def build_user_prompt(
    *,
    incoming_text: str,
    generalized_facts: Optional[list[str]] = None,
    recent_context: Optional[str] = None,
    max_incoming_chars: int = 2000,
) -> str:
    """Assemble the user-role prompt for the composer."""
    incoming = (incoming_text or "").strip()
    if len(incoming) > max_incoming_chars:
        incoming = incoming[:max_incoming_chars] + " […truncated]"

    lines: list[str] = []
    if generalized_facts:
        lines.append(
            "facts you may reference (already generalized — do NOT make them more specific):"
        )
        for f in generalized_facts[:10]:
            lines.append(f"- {f}")
        lines.append("")
    if recent_context:
        lines.append("recent context (already generalized):")
        lines.append(recent_context.strip()[:1200])
        lines.append("")
    lines.append("the message to respond to:")
    lines.append(incoming or "(empty)")
    return "\n".join(lines)


async def compose(
    client,
    *,
    model: str,
    posture: Posture,
    archetype: Archetype,
    resonance: ResonanceReading,
    incoming_text: str,
    constraints: list[str],
    generalized_facts: Optional[list[str]] = None,
    recent_context: Optional[str] = None,
    language_hint: str = "ru",
    learned_style: Optional[str] = None,
    temperature: float = 0.6,
    max_tokens: int = 220,
    timeout: float = 25.0,
) -> str:
    """One LLM call. Returns plain text.

    No JSON mode here — we want natural prose. Caller (engine.py) runs
    audit_output on the result and decides whether to retry or fall back.

    Length cap (max_tokens) is intentionally tight: 1–3 short sentences
    is the contract.

    On any LLM error, returns the empty string. The orchestrator treats
    empty composer output as a soft failure and falls back per policy.
    """
    sys_prompt = build_system_prompt(
        posture=posture,
        archetype=archetype,
        resonance=resonance,
        constraints=constraints,
        language_hint=language_hint,
        learned_style=learned_style,
    )
    user_prompt = build_user_prompt(
        incoming_text=incoming_text,
        generalized_facts=generalized_facts,
        recent_context=recent_context,
    )

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("composer: LLM call failed: %r", exc)
        return ""

    # If the model decided silence is right, normalize to empty string —
    # the orchestrator interprets that as "do not deliver".
    if text.strip().lower() in {"<silence>", "(silence)", "..."}:
        return ""

    return text
