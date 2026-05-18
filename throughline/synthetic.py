"""
Synthetic State derivation (SPEC.md §9).

The agent maintains 8 "forces" in [0,1] that modulate posture selection,
threshold tuning, and prompt conditioning. They are NOT human emotions
and are NEVER expressed to the user as "I feel ..." (Invariant I-6).

This module computes the synthetic state from:
- the current resonance reading
- the relationship's recent history (rebuffs, bond level, mistakes)
- known triggers per force

The state is derived per-decision, not persistent. Snapshots may be
written to ``synthetic_feeling_snapshots`` short-term (24h–7d) for
introspection / Mini App display; never long-term.

Forces (SPEC.md §9):
- concern         — gentler check-ins, lower thresholds
- tenderness      — softer phrasing, no challenge
- protectiveness  — refuse harmful actions, gate behavior
- honesty         — name what's actually happening
- patience        — longer waits, smaller next steps
- restraint       — silence preferred
- faith           — belief in capacity, not pity
- challenge_impulse — nudge toward action

§9.1 interaction rules:
- concern × protectiveness > 1.2 → posture defaults to *hold*
- honesty × challenge_impulse > 1.4 AND trust ≥ 4 → posture *challenge* available
- restraint > 0.7 → silence threshold drops; default action becomes wait
- tenderness > 0.6 → composer prompt receives "soft phrasing" modifier
- faith > patience → composer allowed to remind user of their capacity

The thresholds above are encoded as constants here so downstream code can
import and use them rather than hardcoding.
"""

from __future__ import annotations

from dataclasses import dataclass

from throughline.types import Pain, ResonanceReading, Sensitivity, SyntheticState


# ─────────────────────────────────────────────────────────────────────────────
# Thresholds from SPEC.md §9.1 — referenced by posture.py / composer.py
# ─────────────────────────────────────────────────────────────────────────────

THRESH_HOLD_FROM_CONCERN_PROTECTION = 1.2  # concern × protectiveness
THRESH_CHALLENGE_AVAILABLE = 1.4            # honesty × challenge_impulse
TRUST_REQUIRED_FOR_CHALLENGE = 4
THRESH_RESTRAINT_PREFER_SILENCE = 0.7
THRESH_TENDERNESS_SOFT_PHRASING = 0.6


# ─────────────────────────────────────────────────────────────────────────────
# Inputs
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RelationshipContext:
    """Compact view of the relationship — what derivation needs to know.

    Caller (engine.py) populates this from repos before calling derive_state.
    Stays free of any cross-channel data.
    """

    trust_level: int = 0  # 0-5; from owners.care_level
    bond_level: int = 0   # 0-5; from agent_lifecycle.bond_level
    recent_rebuffs: int = 0  # 7-day window, this pair only
    recent_mistakes: int = 0  # last 30 days, this owner (cross-pair OK; agent learns)
    consecutive_avoidance: int = 0  # for challenge_impulse — pattern of declining engagement
    owner_in_crisis_mode: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Derivation
# ─────────────────────────────────────────────────────────────────────────────

# Pain → starting tilts. Each pain has a primary force it elevates.
# Multipliers are blended with resonance.sensitivity below.
_PAIN_TILTS: dict[Pain, dict[str, float]] = {
    Pain.FEAR:             {"concern": 0.6, "tenderness": 0.5, "patience": 0.6},
    Pain.PANIC:            {"concern": 0.9, "tenderness": 0.7, "patience": 0.8, "protectiveness": 0.4},
    Pain.SHAME:            {"tenderness": 0.8, "patience": 0.5, "restraint": 0.4},
    Pain.LONELINESS:       {"concern": 0.5, "tenderness": 0.6, "faith": 0.4},
    Pain.BURNOUT:          {"concern": 0.6, "patience": 0.8, "restraint": 0.3},
    Pain.QUIET_EXHAUSTION: {"tenderness": 0.5, "patience": 0.8, "restraint": 0.5},
    Pain.ANGER:            {"patience": 0.7, "restraint": 0.6, "honesty": 0.4},
    Pain.RESENTMENT:       {"honesty": 0.5, "patience": 0.6, "restraint": 0.4},
    Pain.POWERLESSNESS:    {"faith": 0.6, "patience": 0.5, "tenderness": 0.4},
    Pain.LOSS_OF_MEANING:  {"patience": 0.6, "restraint": 0.5, "faith": 0.3},
    Pain.ANXIETY:          {"concern": 0.5, "patience": 0.6, "tenderness": 0.4},
    Pain.OVERLOAD:         {"patience": 0.7, "concern": 0.4, "restraint": 0.3},
    Pain.CONFUSION:        {"patience": 0.5, "honesty": 0.4},
    Pain.SELF_DECEPTION:   {"honesty": 0.8, "challenge_impulse": 0.5, "restraint": 0.5},
    Pain.NONE:             {},
}


def derive_state(
    resonance: ResonanceReading,
    context: RelationshipContext,
) -> SyntheticState:
    """Compute the synthetic state for this decision moment.

    Pure function — same inputs always produce same output. Easy to test
    and reason about. The 8 fields are independently clamped to [0,1].
    """
    # Start from neutral baselines (SPEC.md §9 implicit defaults).
    concern = 0.0
    tenderness = 0.0
    protectiveness = 0.0
    honesty = 0.5
    patience = 0.5
    restraint = 0.3
    faith = 0.5
    challenge_impulse = 0.0

    # Pain-driven tilts.
    tilts = _PAIN_TILTS.get(resonance.deeper_pain, {})
    concern += tilts.get("concern", 0.0)
    tenderness += tilts.get("tenderness", 0.0)
    protectiveness += tilts.get("protectiveness", 0.0)
    honesty += tilts.get("honesty", 0.0)
    patience += tilts.get("patience", 0.0)
    restraint += tilts.get("restraint", 0.0)
    faith += tilts.get("faith", 0.0)
    challenge_impulse += tilts.get("challenge_impulse", 0.0)

    # Sensitivity scaling — higher sensitivity → more tenderness, more restraint,
    # less challenge_impulse.
    if resonance.sensitivity == Sensitivity.HIGH:
        tenderness += 0.2
        restraint += 0.2
        challenge_impulse *= 0.5
    elif resonance.sensitivity == Sensitivity.CRITICAL:
        tenderness += 0.3
        restraint += 0.4
        protectiveness += 0.5  # crisis → protect
        challenge_impulse = 0.0  # always off in crisis

    # Owner in crisis mode → everything is protective + restrained
    if context.owner_in_crisis_mode:
        protectiveness = max(protectiveness, 0.9)
        restraint = max(restraint, 0.8)
        challenge_impulse = 0.0

    # Recent rebuffs → restraint up, challenge_impulse down
    if context.recent_rebuffs >= 1:
        restraint = min(1.0, restraint + 0.2 * context.recent_rebuffs)
        challenge_impulse *= 0.3

    # Bond level → faith + tenderness grow with the relationship
    bond_factor = context.bond_level / 5.0
    faith += 0.2 * bond_factor
    tenderness += 0.1 * bond_factor

    # Trust gate for challenge_impulse — even if pain calls for it, trust < 4
    # caps it hard. Encoded here so posture.py can read challenge_impulse
    # without re-checking trust.
    if context.trust_level < TRUST_REQUIRED_FOR_CHALLENGE:
        challenge_impulse *= 0.5
        if context.trust_level < 2:
            challenge_impulse = 0.0

    # Avoidance pattern → challenge_impulse up (only if trust gate allows)
    if context.consecutive_avoidance >= 3 and context.trust_level >= TRUST_REQUIRED_FOR_CHALLENGE:
        challenge_impulse = min(1.0, challenge_impulse + 0.3)

    # Recent mistakes → restraint up, challenge_impulse down (agent should be
    # quieter for a while after getting it wrong).
    if context.recent_mistakes >= 1:
        restraint = min(1.0, restraint + 0.1 * min(context.recent_mistakes, 3))
        challenge_impulse *= 0.5

    return SyntheticState(
        concern=_clamp(concern),
        tenderness=_clamp(tenderness),
        protectiveness=_clamp(protectiveness),
        honesty=_clamp(honesty),
        patience=_clamp(patience),
        restraint=_clamp(restraint),
        faith=_clamp(faith),
        challenge_impulse=_clamp(challenge_impulse),
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


# ─────────────────────────────────────────────────────────────────────────────
# Convenience predicates (SPEC.md §9.1 interaction rules)
# ─────────────────────────────────────────────────────────────────────────────

def defaults_to_hold(state: SyntheticState) -> bool:
    """concern × protectiveness > 1.2 → posture defaults to *hold*."""
    return state.concern * state.protectiveness > THRESH_HOLD_FROM_CONCERN_PROTECTION


def challenge_available(state: SyntheticState, trust_level: int) -> bool:
    """honesty × challenge_impulse > 1.4 AND trust ≥ 4 → *challenge* available."""
    return (
        state.honesty * state.challenge_impulse > THRESH_CHALLENGE_AVAILABLE
        and trust_level >= TRUST_REQUIRED_FOR_CHALLENGE
    )


def prefers_silence(state: SyntheticState) -> bool:
    """restraint > 0.7 → default action becomes wait."""
    return state.restraint > THRESH_RESTRAINT_PREFER_SILENCE


def soft_phrasing_modifier(state: SyntheticState) -> bool:
    """tenderness > 0.6 → composer gets soft-phrasing flag."""
    return state.tenderness > THRESH_TENDERNESS_SOFT_PHRASING


def allowed_to_remind_of_capacity(state: SyntheticState) -> bool:
    """faith > patience → composer may remind the user of their capacity."""
    return state.faith > state.patience
