"""
Repair pattern + lifecycle transitions (SPEC.md §15).

Repair:
The agent WILL make mistakes — misjudged tone, misread state, presumption
where listening was needed. Anima treats this as a milestone, not a failure
(SPEC.md §15.5). The pattern:

    1. Detect the mistake (explicit user feedback OR signal of withdrawal).
    2. Acknowledge — short, behavior-changing, not abject. "я слишком
       уверенно полез туда. учту." NOT theatrical guilt.
    3. Record into ``agent_mistakes`` with lesson + behavior_update.
    4. The lesson influences future posture/synthetic-state decisions
       (synthetic.derive_state already reads recent_mistakes).

This module exposes:
- ``observe_rebuff_as_mistake`` — called from record_feedback when the
  feedback_type is REBUFFED.
- ``record_mistake_with_lesson`` — exposed via Engine for the host to call
  when it sees an explicit "you got it wrong" signal.
- ``maybe_advance_lifecycle`` — called after every successful interaction;
  transitions birth → bonding once stable engagement is observed.

Lifecycle stages (SPEC.md §15):
- birth: no model; initiative off; defaults Witness/Silence + Companion
- bonding: patterns forming; tier-2 archetypes unlock with explicit invite
- forming: stable patterns; Mirror posture available (v0.2)
- mature: full range (v0.2+)

v0.1 scope: only birth → bonding transition is implemented. Forming and
Mature are reserved for v0.2.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from throughline import repos
from throughline.storage import SqlcipherStorage
from throughline.types import LifecycleStage

log = logging.getLogger("anima.repair")


# ─────────────────────────────────────────────────────────────────────────────
# Repair
# ─────────────────────────────────────────────────────────────────────────────

# Default lesson / behavior_update strings for auto-recorded mistakes from
# rebuffs. These are intentionally generic — when the host has more context
# (the rebuff text itself), it can call record_mistake_with_lesson directly
# with richer fields.
_DEFAULT_REBUFF_LESSON = (
    "owner rebuffed an initiative — the moment or framing was wrong"
)
_DEFAULT_REBUFF_BEHAVIOR = (
    "increase restraint for this pair for 7 days; lower trust in pattern-recognition "
    "until next positive engagement; do not initiate similar threads soon"
)


def observe_rebuff_as_mistake(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: Optional[str],
    decision_id: str,
    raw_signal: Optional[str] = None,
) -> str:
    """Auto-record an agent_mistake when feedback is REBUFFED.

    Returns the mistake_id. Used by Engine.record_feedback to close the
    learn-from-rebuff loop without the host having to explicitly call
    record_mistake.
    """
    summary = (
        f"initiative led to rebuff (decision={decision_id})"
        + (f": {raw_signal[:120]!r}" if raw_signal else "")
    )
    return repos.record_mistake(
        storage,
        owner_id=owner_id,
        contact_id=contact_id,
        mistake_summary=summary,
        user_feedback=raw_signal,
        lesson=_DEFAULT_REBUFF_LESSON,
        behavior_update=_DEFAULT_REBUFF_BEHAVIOR,
    )


def record_mistake_with_lesson(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    mistake_summary: str,
    lesson: str,
    behavior_update: str,
    contact_id: Optional[str] = None,
    user_feedback: Optional[str] = None,
) -> str:
    """Host-driven mistake record. Used when explicit feedback names what
    went wrong. The lesson + behavior_update propagate forward via
    synthetic.derive_state (which reads recent_mistakes)."""
    return repos.record_mistake(
        storage,
        owner_id=owner_id,
        contact_id=contact_id,
        mistake_summary=mistake_summary,
        user_feedback=user_feedback,
        lesson=lesson,
        behavior_update=behavior_update,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle transitions
# ─────────────────────────────────────────────────────────────────────────────

# Thresholds for birth → bonding (v0.1 only).
# A relationship moves into "bonding" once we have evidence of sustained,
# non-rebuffed engagement. The exact thresholds are conservative — the spec's
# stated direction is "patterns begin forming".
BONDING_MIN_DAYS = 3                # at least N days since birth
BONDING_MIN_OBSERVATIONS = 8        # at least N observed messages
BONDING_MAX_REBUFFS = 1             # ≤ N rebuffs in last 7 days


def maybe_advance_lifecycle(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    now: Optional[datetime] = None,
) -> Optional[LifecycleStage]:
    """Check whether the owner's lifecycle should advance; if so, advance.

    v0.1 only knows birth → bonding. Returns the new stage if it advanced,
    or None if no change. Safe to call frequently — idempotent.
    """
    now = now or datetime.now(timezone.utc)
    lc = repos.ensure_lifecycle(storage, owner_id)
    current = lc.get("maturity_stage", "birth")

    if current != LifecycleStage.BIRTH.value:
        return None  # v0.1 only handles birth→bonding

    birth_str = lc.get("birth_at")
    try:
        birth = datetime.fromisoformat(birth_str) if birth_str else now
    except (TypeError, ValueError):
        birth = now

    days_since_birth = (now - birth).total_seconds() / 86400.0
    if days_since_birth < BONDING_MIN_DAYS:
        return None

    # Count observed messages for this owner (across all contacts — that's
    # an owner-level lifecycle, not pair-level)
    obs = storage.execute(
        "SELECT COUNT(*) AS n FROM observed_messages WHERE owner_id = ?",
        (owner_id,),
    ).fetchone()
    if not obs or int(obs["n"]) < BONDING_MIN_OBSERVATIONS:
        return None

    # Recent rebuffs across all pairs
    rebuffs_row = storage.execute(
        """
        SELECT COUNT(*) AS n FROM feedback f
        JOIN care_decisions d ON d.id = f.decision_id
        JOIN threads t        ON t.id = d.thread_id
        WHERE t.owner_id = ?
          AND f.feedback_type = 'rebuffed'
          AND f.created_at >= ?
        """,
        (owner_id, (now - timedelta(days=7)).isoformat()),
    ).fetchone()
    recent_rebuffs = int(rebuffs_row["n"]) if rebuffs_row else 0
    if recent_rebuffs > BONDING_MAX_REBUFFS:
        return None

    # All gates passed — advance.
    repos.advance_lifecycle_stage(storage, owner_id, LifecycleStage.BONDING.value)
    log.info(
        "lifecycle: owner=%s advanced birth → bonding (days=%.1f obs=%s rebuffs=%s)",
        owner_id, days_since_birth, int(obs["n"]), recent_rebuffs,
    )
    return LifecycleStage.BONDING


def record_first_message_event(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
) -> None:
    """Insert a FIRST_MESSAGE relationship event ONCE per pair.

    Cheap idempotent check: skip if any FIRST_MESSAGE row exists for the
    pair. Used by Engine.observe_message on first contact.
    """
    existing = storage.execute(
        """
        SELECT id FROM relationship_events
        WHERE owner_id = ? AND contact_id = ? AND event_type = 'first_message'
        LIMIT 1
        """,
        (owner_id, contact_id),
    ).fetchone()
    if existing:
        return
    repos.record_relationship_event(
        storage,
        owner_id=owner_id,
        contact_id=contact_id,
        event_type="first_message",
    )
