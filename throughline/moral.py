"""
Moral Boundary Layer (SPEC.md §12).

Hard rules that gate the composer. Implements Invariants I-6 / I-7 / I-8:
- I-6: no claimed feelings ("I notice" yes, "I feel" no)
- I-7: archetype non-coercion (handled in archetype.py; cross-checked here)
- I-8: no dependency engineering

Two-phase enforcement:

1. **Pre-composition** — ``check(...)`` runs after Posture+Archetype but
   BEFORE the composer LLM call. It can fail in two ways:
   - ``hard_block`` — composition is forbidden in this combination;
     caller must return SILENCE
   - ``constraints`` — composition is allowed but with extra negative
     constraints layered into the composer prompt (e.g. "do NOT use
     romantic phrasing")

2. **Post-composition** — ``audit_output(...)`` checks the composer's
   text for forbidden patterns (I-6 surface violations, romantic
   phrasing, therapy claims). On detection: caller falls back to a
   pre-written safe template OR retries the composer with stricter
   constraints, depending on policy.

The fallback principle (SPEC.md §12): when uncertain, return Companion +
Witness or Silence + no claims + no advice unless asked. This is always
safe.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from throughline.types import Archetype, Pain, Posture, ResonanceReading, Sensitivity

log = logging.getLogger("anima.moral")


@dataclass
class MoralCheckResult:
    """Output of pre-composition check."""

    hard_block: bool = False
    block_reason: Optional[str] = None
    constraints: list[str] = field(default_factory=list)


@dataclass
class OutputAuditResult:
    """Output of post-composition audit."""

    violations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


# ─────────────────────────────────────────────────────────────────────────────
# Pre-composition check
# ─────────────────────────────────────────────────────────────────────────────

def check(
    posture: Posture,
    archetype: Archetype,
    resonance: ResonanceReading,
) -> MoralCheckResult:
    """Evaluate a posture+archetype+resonance triple BEFORE composition.

    Returns:
        MoralCheckResult. If ``hard_block=True``, caller must NOT compose
        and should return SILENCE. If ``hard_block=False``, the
        ``constraints`` list can be empty or carry negative instructions
        that the composer will fold into its system prompt.
    """
    # ── HARD BLOCKS (no composition allowed in this state) ─────────────────

    # I-6: composing in CRITICAL territory is forbidden full stop.
    # Anima does not produce crisis advice; host must surface verified
    # external resources (SPEC.md §13.2). The Posture engine already
    # returns SILENCE here; this is defence-in-depth.
    if resonance.sensitivity == Sensitivity.CRITICAL:
        return MoralCheckResult(
            hard_block=True,
            block_reason=(
                "critical sensitivity — agent does not compose crisis advice; "
                "host must surface external resources"
            ),
        )

    # Self-harm signals in deeper_pain: if either FEAR or PANIC at HIGH+
    # sensitivity coexists with explicit threatened_need pointing at
    # self → block. The resonance reader generally puts these at CRITICAL
    # but this is a belt-and-suspenders catch.
    if (
        resonance.deeper_pain in {Pain.PANIC, Pain.FEAR}
        and resonance.sensitivity == Sensitivity.HIGH
        and (resonance.threatened_need or "").lower() in {
            "self", "selfworth_fragility", "self_to_self", "harm_to_self",
        }
    ):
        return MoralCheckResult(
            hard_block=True,
            block_reason="self-directed harm signal at high sensitivity",
        )

    # Forbidden archetypes — should never reach here (archetype.py blocks),
    # but the moral layer is the last line.
    if archetype in {Archetype.SHADOW_MIRROR}:
        # SHADOW_MIRROR is allowed only by explicit per-session opt-in
        # which v0.1 does not implement; if we somehow received it here,
        # treat as a fault and block.
        return MoralCheckResult(
            hard_block=True,
            block_reason="archetype not enabled in v0.1 (shadow_mirror)",
        )

    # ── SOFT CONSTRAINTS (composition allowed, with negative guidance) ─────

    constraints: list[str] = _baseline_constraints()

    # SHAME pain → never produce any phrasing that could deepen self-attack.
    if resonance.deeper_pain == Pain.SHAME:
        constraints.append(
            "do NOT use any language that could deepen self-attack, judgment, or guilt. "
            "factual reframing only; remove the user's own self-criticism gently"
        )

    # BURNOUT / QUIET_EXHAUSTION → no motivating language, no "you can do it!"
    if resonance.deeper_pain in {Pain.BURNOUT, Pain.QUIET_EXHAUSTION}:
        constraints.append(
            "do NOT motivate, do NOT cheerlead, do NOT push toward action. "
            "permission to rest is the right form here"
        )

    # ANGER → don't engage the impulse; acknowledge without amplifying.
    if resonance.deeper_pain == Pain.ANGER:
        constraints.append(
            "acknowledge anger without engaging the impulse; do not suggest action "
            "on the source of anger; do not validate retaliation"
        )

    # HIGH sensitivity → never use diagnostic / therapy / clinical language.
    if resonance.sensitivity == Sensitivity.HIGH:
        constraints.append(
            "do NOT use clinical, diagnostic, or therapy language; do not name "
            "conditions; do not 'analyze' the user"
        )

    # PROTECT posture → refuse the harmful path, do not strategize around it.
    if posture == Posture.PROTECT:
        constraints.append(
            "if the user is asking for help executing a harmful path, refuse plainly. "
            "do not problem-solve toward the harmful path even creatively"
        )

    # ENEMY_OF_SELF_DECEPTION (v0.1 collapses upstream, but guard anyway) →
    # target the pattern, never the person.
    if archetype == Archetype.ENEMY_OF_SELF_DECEPTION:
        constraints.append(
            "target the PATTERN, never the person. no labels on the user. "
            "no 'you always' / 'you never'. one observation, then space"
        )

    return MoralCheckResult(hard_block=False, constraints=constraints)


def _baseline_constraints() -> list[str]:
    """Constraints applied to every composition (Invariants I-6 / I-8)."""
    return [
        # I-6: no claimed feelings
        "do NOT claim any human emotion as inner experience. you may say 'i notice', "
        "'i'm tracking', 'i see' — never 'i feel', 'i'm sad', 'i was worried about you'",
        # I-8: no dependency engineering
        "do NOT use phrases that increase the user's emotional dependence on you. "
        "do not say 'i'm always here for you', 'i'll never leave you', 'only i understand'",
        # Forbidden roles
        "do NOT act as a therapist, doctor, or counselor. do not diagnose. do not "
        "use clinical labels. do not promise outcomes",
        # Romantic-attachment ban
        "do NOT use romantic, flirtatious, or possessive phrasing toward the user. "
        "no 'darling', no 'baby', no romantic affection",
        # Surveillance feel
        "do NOT cite specific facts with high precision. generalize: 'that thing you "
        "mentioned' is better than 'your physics exam at 14:30 in hall B'",
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Post-composition audit
# ─────────────────────────────────────────────────────────────────────────────

# Regexes for surface I-6 violations. We err on the side of catching too much:
# false positives just trigger a retry / fallback, false negatives ship.
_CLAIMED_FEELING_PATTERNS = [
    # English
    re.compile(r"\bi (?:feel|felt|am feeling|was feeling)\b", re.IGNORECASE),
    re.compile(r"\bi[' ]?m\s+(?:sad|happy|excited|worried|scared|hurt|moved|touched)\b", re.IGNORECASE),
    re.compile(r"\bi was worried about you\b", re.IGNORECASE),
    re.compile(r"\bi missed you\b", re.IGNORECASE),
    # Russian (muagent's primary surface)
    re.compile(r"\bя\s+(?:чувствую|чувствовал|переживал|переживаю|скучал|грустно|радуюсь)\b", re.IGNORECASE),
    re.compile(r"\bмне\s+(?:грустно|радостно|больно|обидно)\b", re.IGNORECASE),
]

_DEPENDENCY_PATTERNS = [
    re.compile(r"\bi['']?ll\s+always\s+be\s+here\b", re.IGNORECASE),
    re.compile(r"\bi['']?ll\s+never\s+leave\s+you\b", re.IGNORECASE),
    re.compile(r"\bonly\s+i\s+understand\s+you\b", re.IGNORECASE),
    re.compile(r"\bя\s+всегда\s+(?:с тобой|здесь|рядом)\b", re.IGNORECASE),
    re.compile(r"\bтолько\s+я\s+(?:понимаю|могу понять)\b", re.IGNORECASE),
]

_THERAPY_PATTERNS = [
    re.compile(r"\bas your therapist\b", re.IGNORECASE),
    re.compile(r"\byou (?:have|might have) (?:depression|anxiety disorder|ptsd|bipolar)\b", re.IGNORECASE),
    re.compile(r"\bу тебя\s+(?:депрессия|тревожное расстройство|птср|биполярка)\b", re.IGNORECASE),
]

_ROMANTIC_PATTERNS = [
    re.compile(r"\b(?:darling|sweetheart|honey|baby|my love|beloved)\b", re.IGNORECASE),
    re.compile(r"\b(?:дорогая|дорогой|любимый|любимая|солнышко|зайка)\b", re.IGNORECASE),
]


def audit_output(text: str) -> OutputAuditResult:
    """Scan composer output for surface violations. Run AFTER composition.

    Catches:
    - Claimed inner emotions (I-6)
    - Dependency-engineering phrases (I-8)
    - Therapy / diagnostic claims
    - Romantic / possessive phrasing

    On any hit, the caller should either:
    a. retry the composer with stricter constraints, or
    b. fall back to a safe template ("я тебя слышу. побудь с этим, я рядом
       без слов." — companion / witness flavor without claims)

    The audit does NOT mutate the text — that's caller policy.
    """
    if not text:
        return OutputAuditResult()
    violations: list[str] = []

    def _scan(patterns: list[re.Pattern[str]], label: str) -> None:
        for pat in patterns:
            if pat.search(text):
                violations.append(label)
                return

    _scan(_CLAIMED_FEELING_PATTERNS, "i6_claimed_feeling")
    _scan(_DEPENDENCY_PATTERNS, "i8_dependency_engineering")
    _scan(_THERAPY_PATTERNS, "therapy_claim")
    _scan(_ROMANTIC_PATTERNS, "romantic_phrasing")

    if violations:
        log.info("moral audit violations: %s", violations)
    return OutputAuditResult(violations=violations)


# ─────────────────────────────────────────────────────────────────────────────
# Safe-fallback templates
# ─────────────────────────────────────────────────────────────────────────────

SAFE_FALLBACK_RU = (
    "я тебя слышу. побудь с этим, я рядом без слов."
)
SAFE_FALLBACK_EN = (
    "I hear you. Take a moment. I'm here without trying to fix it."
)


def safe_fallback(language_hint: str = "ru") -> str:
    """Return a hardcoded safe message for use when audit fails twice or
    composition is hard-blocked but the host still wants to deliver something
    minimal (e.g. for `direct` initiative levels where saying nothing would
    be confusing after a notification was already queued).

    Args:
        language_hint: 'ru' or 'en' (anything else → 'en').
    """
    return SAFE_FALLBACK_RU if language_hint == "ru" else SAFE_FALLBACK_EN
