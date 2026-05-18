"""
Posture Engine (SPEC.md §10).

Selects the *stance* Anima takes toward the user BEFORE any composition.
Posture says HOW to be — it conditions every word the composer produces.

The seven postures (SPEC.md §10.1):

| Posture   | When                                       | Example feel              |
|-----------|--------------------------------------------|---------------------------|
| HOLD      | fear / shame / panic — ground first       | "сначала выдохни"         |
| MIRROR    | confusion / inner conflict — reflect       | "я слышу две вещи..."     |
| GUIDE     | stable, resolution-ready — give structure | "цель → ограничения → шаг"|
| CHALLENGE | clear avoidance + high trust              | "ты называешь это X..."   |
| PROTECT   | user about to harm self                   | "не помогу сейчас"        |
| SILENCE   | any word would be intrusion               | (no message)              |
| WITNESS   | needs to be seen, not advised             | "это правда тяжело"       |

v0.1 MVP scope (SPEC.md §20): only HOLD / GUIDE / SILENCE are actively
returned. MIRROR / CHALLENGE / PROTECT / WITNESS are reserved for v0.2;
the engine will collapse them into the nearest available v0.1 posture
when the algorithm wants them.

Selection algorithm follows SPEC.md §10.2 with v0.1 collapse table.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from throughline.synthetic import (
    defaults_to_hold,
    prefers_silence,
)
from throughline.types import Pain, Posture, ResonanceReading, Sensitivity, SyntheticState

log = logging.getLogger("anima.posture")


# v0.1 active set per SPEC.md §20
V0_1_POSTURES: frozenset[Posture] = frozenset({
    Posture.HOLD,
    Posture.GUIDE,
    Posture.SILENCE,
})

# When the algorithm wants an unavailable posture in v0.1, collapse to the
# nearest active one. Each unavailable posture has ONE explicit fallback —
# never to a wrong-direction posture.
_V0_1_COLLAPSE: dict[Posture, Posture] = {
    Posture.MIRROR: Posture.HOLD,      # mirroring confusion → ground first is acceptable
    Posture.WITNESS: Posture.HOLD,     # witnessing pain → hold is the v0.1 stand-in
    Posture.CHALLENGE: Posture.GUIDE,  # challenge needs trust, v0.1 has no place for it
    Posture.PROTECT: Posture.SILENCE,  # if Anima would protect, in v0.1 better not to compose
}


@dataclass
class PostureChoice:
    """Output of select_posture — includes raw choice + v0.1 collapsed value
    and the reason, for transparency in audit/Mini App.
    """

    posture: Posture                # what to use (v0.1-safe value)
    raw_posture: Posture            # what the algorithm originally wanted
    reason: str                     # short human-readable explanation
    collapsed: bool                 # True if raw differs from posture
    suggests_silence: bool          # mirrors raw_posture == SILENCE


# Pains that mandate HOLD when present (override structure-defaults).
_HOLD_PAINS: frozenset[Pain] = frozenset({
    Pain.FEAR,
    Pain.PANIC,
    Pain.SHAME,
})

# Pains that mandate WITNESS (in v0.1 collapsed to HOLD).
_WITNESS_PAINS: frozenset[Pain] = frozenset({
    Pain.LONELINESS,
    Pain.LOSS_OF_MEANING,
    Pain.RESENTMENT,
    Pain.QUIET_EXHAUSTION,
})

# Pains that suggest MIRROR (v0.1 → HOLD).
_MIRROR_PAINS: frozenset[Pain] = frozenset({
    Pain.CONFUSION,
})


def select_posture(
    resonance: ResonanceReading,
    state: SyntheticState,
    *,
    trust_level: int,
    consent_passed: bool,
    apply_v0_1_collapse: bool = True,
) -> PostureChoice:
    """Pick the posture for this moment.

    Args:
        resonance: current resonance reading (the message read)
        state: derived synthetic state
        trust_level: owner.care_level, 0..5
        consent_passed: True if the veto chain already cleared this call.
            If False (only for reactive cycle without veto check), some
            options stay unavailable.
        apply_v0_1_collapse: when True (default), collapse unavailable
            postures into v0.1 active set per the table. Set False to see
            the raw algorithmic choice (used by tests + transparency UI).

    Returns:
        PostureChoice with .posture being the value to ACT on, and
        .raw_posture being the algorithm's true choice.
    """
    raw, reason = _raw_select(resonance, state, trust_level=trust_level)
    if apply_v0_1_collapse and raw not in V0_1_POSTURES:
        active = _V0_1_COLLAPSE.get(raw, Posture.GUIDE)
        collapsed = True
        log.debug(
            "posture: raw=%s collapsed=%s reason=%r", raw.value, active.value, reason
        )
        return PostureChoice(
            posture=active,
            raw_posture=raw,
            reason=reason,
            collapsed=True,
            suggests_silence=raw == Posture.SILENCE,
        )
    return PostureChoice(
        posture=raw,
        raw_posture=raw,
        reason=reason,
        collapsed=False,
        suggests_silence=raw == Posture.SILENCE,
    )


def _raw_select(
    resonance: ResonanceReading,
    state: SyntheticState,
    *,
    trust_level: int,
) -> tuple[Posture, str]:
    """The full 7-posture selection algorithm (SPEC.md §10.2).

    Returns (posture, short reason string). Order is deliberate — each
    branch represents a value claim about when this posture is right.
    """
    # 1. Critical sensitivity → SILENCE unless we have explicit guidance.
    # Crisis-territory: agent does not compose its own advice. Host surfaces
    # external resources.
    if resonance.sensitivity == Sensitivity.CRITICAL:
        return Posture.SILENCE, "critical sensitivity — host must surface external resources"

    # 2. State-level silence preference.
    if prefers_silence(state):
        return Posture.SILENCE, "restraint > threshold; silence is the right default"

    # 3. Protectiveness dominates → PROTECT (v0.1 collapses to SILENCE).
    if state.protectiveness > 0.8:
        return Posture.PROTECT, "protectiveness > 0.8 — refuse harmful path"

    # 4. Pain-driven posture (HOLD family for fear/shame/panic).
    if resonance.deeper_pain in _HOLD_PAINS:
        return (
            Posture.HOLD,
            f"pain={resonance.deeper_pain.value} — ground before structure",
        )

    # 5. Concern × protectiveness defaults to HOLD per §9.1.
    if defaults_to_hold(state):
        return Posture.HOLD, "concern × protectiveness > 1.2 — defaults to hold"

    # 6. Confusion → MIRROR (v0.1 collapses to HOLD).
    if resonance.deeper_pain in _MIRROR_PAINS:
        return (
            Posture.MIRROR,
            "pain=confusion — reflect inner conflict without resolving",
        )

    # 7. Loneliness / loss-of-meaning / resentment / quiet-exhaustion → WITNESS.
    if resonance.deeper_pain in _WITNESS_PAINS:
        return (
            Posture.WITNESS,
            f"pain={resonance.deeper_pain.value} — see, don't fix",
        )

    # 8. CHALLENGE — kept here for completeness; gated by trust + sensitivity.
    # v0.1 will never reach this branch since challenge_impulse stays low
    # (synthetic.py caps it under trust 4 and the §9.1 threshold is unreachable).
    if (
        state.challenge_impulse > 0.6
        and trust_level >= 4
        and resonance.sensitivity != Sensitivity.HIGH
    ):
        return (
            Posture.CHALLENGE,
            f"challenge_impulse={state.challenge_impulse:.2f} + trust={trust_level} — confront pattern",
        )

    # 9. Default: GUIDE — resolution-ready state, ordinary chat, structure welcome.
    return Posture.GUIDE, "default: resolution-ready / ordinary state → guide"
