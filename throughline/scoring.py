"""
Scoring layer — multipliers and linear addends.

Called only after the veto chain (see vetoes.py) has passed. Implements
Stages 2-4 of SPEC.md §5.

Order of computation:
1. Multipliers (situational, 0.0-1.0, multiplied together)
2. If product < threshold → silence
3. Linear addends (importance-weighted sum)
4. Final = base_score * multipliers
5. Map to graduated initiation level (SPEC.md §6)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from throughline.types import InitiationLevel, Thread
from throughline.vetoes import EvaluationContext


# Multiplier threshold below which any score is forced to silence.
# Even if importance is high, if owner can't handle it now, we wait.
MIN_MULTIPLIER_PRODUCT = 0.3

# Graduated initiation thresholds — see SPEC.md §6.
# These are tunable per deployment but the *order* (lower threshold → less
# intrusive) is invariant.
THRESHOLD_DIRECT = 0.85
THRESHOLD_NUDGE = 0.70
THRESHOLD_SOFT = 0.55
THRESHOLD_PASSIVE = 0.40

# Default weights for the linear addend stage. Sum to 1.0.
WEIGHT_IMPORTANCE = 0.30
WEIGHT_EMOTIONAL = 0.25
WEIGHT_TIMING = 0.25
WEIGHT_USEFULNESS = 0.20


@dataclass
class ScoreResult:
    final_score: float
    level: InitiationLevel
    breakdown: dict


def compute_multipliers(thread: Thread, ctx: EvaluationContext) -> dict[str, float]:
    """Compute situational multipliers. Each in [0.0, 1.0]."""
    return {
        "cognitive_capacity": _cognitive_capacity(ctx),
        "conversation_tempo": _conversation_tempo(thread, ctx),
        "trust_level": ctx.trust_level / 5.0,
        "attempt_decay": 0.5 ** ctx.attempts_today,
    }


def _cognitive_capacity(ctx: EvaluationContext) -> float:
    """How much can the owner take right now?

    v0.1: simple heuristic based on quiet hours and crisis mode.
    v0.2+: incorporates last-activity time, response length trend,
           number of parallel active chats, time-of-day vs known sleep pattern.
    """
    if ctx.owner_in_crisis_mode:
        return 0.0
    # TODO(v0.2): real implementation
    return 0.7


def _conversation_tempo(thread: Thread, ctx: EvaluationContext) -> float:
    """Is the timing in the natural rhythm of this relationship?

    v0.1: returns 1.0 (neutral).
    v0.2+: learns per-contact response patterns.
    """
    # TODO(v0.2): real implementation
    return 1.0


def timing_fit(thread: Thread, ctx: EvaluationContext) -> float:
    """How well does the current moment match the thread's expected window?

    Returns 1.0 if right at the optimal followup time, decays if too early
    or too late within the still-valid window.
    """
    if thread.followup_after is None:
        return 0.5
    if thread.expires_at <= thread.followup_after:
        return 0.5

    total_window = (thread.expires_at - thread.followup_after).total_seconds()
    elapsed = (ctx.now - thread.followup_after).total_seconds()
    if elapsed < 0:
        return 0.0
    if elapsed > total_window:
        return 0.0
    # Triangular: peaks at 25-50% into the window
    position = elapsed / total_window
    if position < 0.25:
        return position / 0.25
    elif position < 0.5:
        return 1.0
    else:
        return max(0.0, 1.0 - (position - 0.5) / 0.5)


def usefulness(thread: Thread, ctx: EvaluationContext) -> float:
    """Heuristic for how useful this follow-up will be.

    v0.1: derived from importance and emotional_weight.
    v0.2+: incorporates historical engagement rate for similar threads.
    """
    return min(1.0, (thread.importance + thread.emotional_weight) / 2.0)


def compute_score(thread: Thread, ctx: EvaluationContext) -> ScoreResult:
    """Full scoring pipeline. Assumes vetoes have already passed."""
    multipliers = compute_multipliers(thread, ctx)
    multiplier_product = 1.0
    for m in multipliers.values():
        multiplier_product *= m

    breakdown = {
        "multipliers": multipliers,
        "multiplier_product": multiplier_product,
    }

    if multiplier_product < MIN_MULTIPLIER_PRODUCT:
        return ScoreResult(
            final_score=0.0,
            level=InitiationLevel.SILENCE,
            breakdown={**breakdown, "reason": "multipliers below threshold"},
        )

    tf = timing_fit(thread, ctx)
    u = usefulness(thread, ctx)

    base_score = (
        thread.importance * WEIGHT_IMPORTANCE
        + thread.emotional_weight * WEIGHT_EMOTIONAL
        + tf * WEIGHT_TIMING
        + u * WEIGHT_USEFULNESS
    )

    final = base_score * multiplier_product

    breakdown.update(
        {
            "importance": thread.importance,
            "emotional_weight": thread.emotional_weight,
            "timing_fit": tf,
            "usefulness": u,
            "base_score": base_score,
            "final_score": final,
        }
    )

    level = _map_to_level(final)
    return ScoreResult(final_score=final, level=level, breakdown=breakdown)


def _map_to_level(score: float) -> InitiationLevel:
    """Graduated initiation — SPEC.md §6.

    v0.1 only acts on DIRECT_MESSAGE (others mapped but not actioned by host).
    """
    if score >= THRESHOLD_DIRECT:
        return InitiationLevel.DIRECT_MESSAGE
    elif score >= THRESHOLD_NUDGE:
        return InitiationLevel.STATUS_NUDGE
    elif score >= THRESHOLD_SOFT:
        return InitiationLevel.SOFT_INJECT
    elif score >= THRESHOLD_PASSIVE:
        return InitiationLevel.PASSIVE_PROMPT
    else:
        return InitiationLevel.SILENCE
