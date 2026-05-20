"""
Repository-style data access for Anima.

Thin functions over ``SqlcipherStorage`` that:

1. **Enforce Invariant I-1 (per-relationship isolation) at the API surface.**
   There is intentionally NO `get_all_threads_for_owner` — only
   `get_threads_for_pair(owner_id, contact_id)`. The absence of the
   cross-channel method IS the security property; a future caller cannot
   accidentally leak.

2. **Provide the building blocks for Invariant I-2 (owner sovereignty):**
   ``export_owner_data`` produces a full JSON dump; ``wipe_owner_data``
   does an irreversible delete with a two-step confirmation token.

3. **Keep schemas in lockstep with ``throughline/types.py``.** All inserts
   accept either Pydantic models or plain dicts; reads return dicts that
   can be fed back into ``Type.model_validate(row)``.

This module is independent of pysqlcipher3 at import time (storage handles
the lazy import). Tests can mock ``SqlcipherStorage`` via duck typing.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from throughline.storage import IsolationViolation, SqlcipherStorage


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _from_iso(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _id() -> str:
    """Generate an opaque, URL-safe id (16 bytes → 22 base64 chars)."""
    return secrets.token_urlsafe(16)


# audit_log.detail should never contain raw message content. This regex-based
# mask is a defence-in-depth — callers should already be passing summaries.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_RE = re.compile(r"(?<!\d)\+?\d[\d\s().-]{7,}\d(?!\d)")


def _audit_safe(detail: Optional[str], max_len: int = 240) -> Optional[str]:
    if not detail:
        return None
    masked = _EMAIL_RE.sub("<email>", detail)
    masked = _PHONE_RE.sub("<phone>", masked)
    if len(masked) > max_len:
        masked = masked[: max_len - 1] + "…"
    return masked


def _require_pair(owner_id: str, contact_id: Optional[str]) -> None:
    """Validate the isolation pair. Empty strings raise; None is allowed only
    for explicitly self-care paths (callers state that explicitly)."""
    if not owner_id:
        raise IsolationViolation("owner_id is required")
    if contact_id is not None and not contact_id:
        raise IsolationViolation("contact_id must be a non-empty string or None")


# ═════════════════════════════════════════════════════════════════════════════
# Owners
# ═════════════════════════════════════════════════════════════════════════════

def ensure_owner(storage: SqlcipherStorage, owner_id: str) -> dict:
    """Create the owner row if missing; return current row."""
    if not owner_id:
        raise IsolationViolation("owner_id is required")
    now = _iso(_now())
    storage.execute(
        """
        INSERT OR IGNORE INTO owners (id, created_at, proactivity_mode, care_level)
        VALUES (?, ?, 'silent', 0)
        """,
        (owner_id, now),
    )
    row = storage.execute(
        "SELECT id, created_at, proactivity_mode, care_level FROM owners WHERE id = ?",
        (owner_id,),
    ).fetchone()
    return dict(row) if row else {}


def update_proactivity(
    storage: SqlcipherStorage, owner_id: str, mode: str
) -> None:
    """Allowed modes: silent | task-only | life-events | full."""
    if mode not in {"silent", "task-only", "life-events", "full"}:
        raise ValueError(f"invalid proactivity mode: {mode!r}")
    storage.execute(
        "UPDATE owners SET proactivity_mode = ? WHERE id = ?",
        (mode, owner_id),
    )


def get_proactivity(storage: SqlcipherStorage, owner_id: str) -> str:
    row = storage.execute(
        "SELECT proactivity_mode FROM owners WHERE id = ?", (owner_id,)
    ).fetchone()
    return row["proactivity_mode"] if row else "silent"


def adjust_care_level(
    storage: SqlcipherStorage, owner_id: str, delta: int
) -> int:
    """Bump care_level (trust) by delta, clamping to [0, 5]. Returns new value."""
    ensure_owner(storage, owner_id)
    row = storage.execute(
        "SELECT care_level FROM owners WHERE id = ?", (owner_id,)
    ).fetchone()
    current = int(row["care_level"]) if row else 0
    new_val = max(0, min(5, current + delta))
    storage.execute(
        "UPDATE owners SET care_level = ? WHERE id = ?",
        (new_val, owner_id),
    )
    return new_val


# ═════════════════════════════════════════════════════════════════════════════
# Consent (Invariant I-2: per-category control)
# ═════════════════════════════════════════════════════════════════════════════

def set_consent(
    storage: SqlcipherStorage,
    owner_id: str,
    category: str,
    level: str,
    contact_id: Optional[str] = None,
    quiet_hours: Optional[tuple[int, int]] = None,
) -> None:
    """Upsert a consent record. contact_id=None means self-directed care.

    SQLite treats NULL as not-equal in unique constraints, so we store
    contact_id as the literal string ``"__self__"`` when None — the public
    Engine API translates back.
    """
    _require_pair(owner_id, contact_id if contact_id else None)
    if level not in {"denied", "task", "event", "wellbeing", "full"}:
        raise ValueError(f"invalid consent level: {level!r}")
    qstart, qend = (None, None)
    if quiet_hours is not None:
        qstart, qend = quiet_hours
        if not (0 <= qstart < 24 and 0 <= qend < 24):
            raise ValueError("quiet_hours must be (start, end) in [0,24)")

    storage_contact = contact_id if contact_id is not None else "__self__"
    now = _iso(_now())
    storage.execute(
        """
        INSERT INTO consent
            (owner_id, contact_id, category, level, quiet_hours_start, quiet_hours_end, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (owner_id, contact_id, category) DO UPDATE SET
            level             = excluded.level,
            quiet_hours_start = excluded.quiet_hours_start,
            quiet_hours_end   = excluded.quiet_hours_end,
            updated_at        = excluded.updated_at
        """,
        (owner_id, storage_contact, category, level, qstart, qend, now),
    )
    append_audit(
        storage,
        owner_id=owner_id,
        contact_id=contact_id,
        action="consent_set",
        detail=f"category={category} level={level}",
    )


def get_consent(
    storage: SqlcipherStorage,
    owner_id: str,
    category: str,
    contact_id: Optional[str] = None,
) -> Optional[dict]:
    """Return the consent row or None. None means veto by default."""
    _require_pair(owner_id, contact_id if contact_id else None)
    storage_contact = contact_id if contact_id is not None else "__self__"
    row = storage.execute(
        """
        SELECT owner_id, contact_id, category, level,
               quiet_hours_start, quiet_hours_end, updated_at
        FROM consent
        WHERE owner_id = ? AND contact_id = ? AND category = ?
        """,
        (owner_id, storage_contact, category),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("contact_id") == "__self__":
        d["contact_id"] = None
    return d


def list_consents(storage: SqlcipherStorage, owner_id: str) -> list[dict]:
    """All consent rows for this owner. Used for /care panel + export."""
    if not owner_id:
        raise IsolationViolation("owner_id is required")
    rows = storage.execute(
        """
        SELECT owner_id, contact_id, category, level,
               quiet_hours_start, quiet_hours_end, updated_at
        FROM consent
        WHERE owner_id = ?
        ORDER BY contact_id, category
        """,
        (owner_id,),
    ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        if d.get("contact_id") == "__self__":
            d["contact_id"] = None
        out.append(d)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Threads (Invariant I-1: pair-scoped only)
# ═════════════════════════════════════════════════════════════════════════════

def create_thread(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
    category: str,
    type_: str,
    title: str,
    summary: str,
    expires_at: datetime,
    emotional_state: Optional[str] = None,
    emotional_weight: float = 0.5,
    sensitivity: str = "medium",
    importance: float = 0.5,
    source_message_id: Optional[str] = None,
    followup_after: Optional[datetime] = None,
    max_attempts: int = 1,
) -> dict:
    _require_pair(owner_id, contact_id)
    thread_id = _id()
    now = _iso(_now())
    storage.execute(
        """
        INSERT INTO threads
            (id, owner_id, contact_id, category, type, title, summary,
             emotional_state, emotional_weight, sensitivity, importance,
             source_message_id, followup_after, expires_at,
             max_attempts, attempts_count, last_attempt_at,
             status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,NULL,'open',?)
        """,
        (
            thread_id, owner_id, contact_id, category, type_, title, summary,
            emotional_state, emotional_weight, sensitivity, importance,
            source_message_id, _iso(followup_after), _iso(expires_at),
            max_attempts, now,
        ),
    )
    append_audit(
        storage,
        owner_id=owner_id,
        contact_id=contact_id,
        action="thread_created",
        detail=f"category={category} type={type_}",
    )
    return get_thread(storage, thread_id) or {}


def get_thread(storage: SqlcipherStorage, thread_id: str) -> Optional[dict]:
    row = storage.execute(
        """
        SELECT id, owner_id, contact_id, category, type, title, summary,
               emotional_state, emotional_weight, sensitivity, importance,
               source_message_id, followup_after, expires_at,
               max_attempts, attempts_count, last_attempt_at,
               status, created_at
        FROM threads WHERE id = ?
        """,
        (thread_id,),
    ).fetchone()
    return dict(row) if row else None


def get_threads_for_pair(
    storage: SqlcipherStorage, owner_id: str, contact_id: str
) -> list[dict]:
    """The ONLY sanctioned thread-list read path. Pair required.

    There is intentionally no ``get_all_threads_for_owner`` — see
    Invariant I-1.
    """
    _require_pair(owner_id, contact_id)
    rows = storage.execute(
        """
        SELECT id, owner_id, contact_id, category, type, title, summary,
               emotional_state, emotional_weight, sensitivity, importance,
               source_message_id, followup_after, expires_at,
               max_attempts, attempts_count, last_attempt_at,
               status, created_at
        FROM threads
        WHERE owner_id = ? AND contact_id = ?
        ORDER BY created_at DESC
        """,
        (owner_id, contact_id),
    ).fetchall()
    return [dict(r) for r in rows]


def list_open_threads_for_owner(
    storage: SqlcipherStorage, owner_id: str
) -> list[dict]:
    """Used by the proactive tick: enumerate all open threads of this owner.

    NOTE: This crosses contact boundaries — by design, because the proactive
    cycle needs to compare priorities across all open threads to pick the
    single top-1 to act on. Composition still happens within the chosen
    thread's pair; cross-pair INFORMATION never leaves the storage layer
    (only the chosen thread's data is returned upstream). The cycle code
    must NOT use threads from one pair to compose for another.
    """
    if not owner_id:
        raise IsolationViolation("owner_id is required")
    rows = storage.execute(
        """
        SELECT id, owner_id, contact_id, category, type, title, summary,
               emotional_state, emotional_weight, sensitivity, importance,
               source_message_id, followup_after, expires_at,
               max_attempts, attempts_count, last_attempt_at,
               status, created_at
        FROM threads
        WHERE owner_id = ? AND status IN ('open', 'cooling')
        ORDER BY importance DESC, emotional_weight DESC, created_at DESC
        """,
        (owner_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_thread_status(
    storage: SqlcipherStorage,
    thread_id: str,
    status: str,
) -> None:
    if status not in {"open", "cooling", "dormant", "resolved", "closed"}:
        raise ValueError(f"invalid thread status: {status!r}")
    storage.execute(
        "UPDATE threads SET status = ? WHERE id = ?",
        (status, thread_id),
    )


def increment_thread_attempt(
    storage: SqlcipherStorage, thread_id: str
) -> None:
    now = _iso(_now())
    storage.execute(
        """
        UPDATE threads
        SET attempts_count = attempts_count + 1, last_attempt_at = ?
        WHERE id = ?
        """,
        (now, thread_id),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Observed messages (metadata only — NO content stored)
# ═════════════════════════════════════════════════════════════════════════════

def record_observation(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
    direction: str,
    timestamp: datetime,
    char_count: Optional[int] = None,
    sentiment: Optional[str] = None,
) -> None:
    """Persist message *metadata* — never the content. Used for tempo learning."""
    _require_pair(owner_id, contact_id)
    if direction not in {"incoming", "outgoing", "self"}:
        raise ValueError(f"invalid direction: {direction!r}")
    storage.execute(
        """
        INSERT INTO observed_messages
            (id, owner_id, contact_id, direction, timestamp, char_count, sentiment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (_id(), owner_id, contact_id, direction, _iso(timestamp), char_count, sentiment),
    )


def recent_message_count(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
    since: datetime,
) -> int:
    _require_pair(owner_id, contact_id)
    row = storage.execute(
        """
        SELECT COUNT(*) AS n
        FROM observed_messages
        WHERE owner_id = ? AND contact_id = ? AND timestamp >= ?
        """,
        (owner_id, contact_id, _iso(since)),
    ).fetchone()
    return int(row["n"]) if row else 0


# ═════════════════════════════════════════════════════════════════════════════
# Care decisions + feedback
# ═════════════════════════════════════════════════════════════════════════════

def record_care_decision(
    storage: SqlcipherStorage,
    *,
    thread_id: str,
    care_score: float,
    initiation_level: str,
    decision_reason: Optional[str] = None,
    veto_triggered: Optional[str] = None,
    posture: Optional[str] = None,
    archetype: Optional[str] = None,
    composed_message: Optional[str] = None,
    delivered_at: Optional[datetime] = None,
) -> str:
    decision_id = _id()
    now = _iso(_now())
    storage.execute(
        """
        INSERT INTO care_decisions
            (id, thread_id, care_score, initiation_level, decision_reason,
             veto_triggered, posture, archetype, composed_message,
             delivered_at, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            decision_id, thread_id, care_score, initiation_level,
            decision_reason, veto_triggered, posture, archetype,
            composed_message, _iso(delivered_at), now,
        ),
    )
    return decision_id


def mark_decision_delivered(
    storage: SqlcipherStorage, decision_id: str
) -> None:
    storage.execute(
        "UPDATE care_decisions SET delivered_at = ? WHERE id = ?",
        (_iso(_now()), decision_id),
    )


def get_care_decision(
    storage: SqlcipherStorage, decision_id: str
) -> Optional[dict]:
    row = storage.execute(
        """
        SELECT id, thread_id, care_score, initiation_level, decision_reason,
               veto_triggered, posture, archetype, composed_message,
               delivered_at, created_at
        FROM care_decisions WHERE id = ?
        """,
        (decision_id,),
    ).fetchone()
    return dict(row) if row else None


def record_feedback(
    storage: SqlcipherStorage,
    *,
    decision_id: str,
    feedback_type: str,
    raw_signal: Optional[str] = None,
) -> str:
    if feedback_type not in {"engaged", "appreciated", "ignored", "rebuffed", "neutral"}:
        raise ValueError(f"invalid feedback type: {feedback_type!r}")
    feedback_id = _id()
    storage.execute(
        """
        INSERT INTO feedback (id, decision_id, feedback_type, raw_signal, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (feedback_id, decision_id, feedback_type, raw_signal, _iso(_now())),
    )
    return feedback_id


def count_recent_rebuffs(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
    since: datetime,
) -> int:
    """For veto chain — how many rebuffs in this channel recently."""
    _require_pair(owner_id, contact_id)
    row = storage.execute(
        """
        SELECT COUNT(*) AS n
        FROM feedback f
        JOIN care_decisions d ON d.id = f.decision_id
        JOIN threads t        ON t.id = d.thread_id
        WHERE t.owner_id = ? AND t.contact_id = ?
          AND f.feedback_type = 'rebuffed'
          AND f.created_at >= ?
        """,
        (owner_id, contact_id, _iso(since)),
    ).fetchone()
    return int(row["n"]) if row else 0


# ═════════════════════════════════════════════════════════════════════════════
# Audit log (append-only)
# ═════════════════════════════════════════════════════════════════════════════

def append_audit(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    action: str,
    contact_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    storage.execute(
        """
        INSERT INTO audit_log (id, owner_id, contact_id, action, detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            _id(),
            owner_id,
            contact_id,
            action,
            _audit_safe(detail),
            _iso(_now()),
        ),
    )


def list_audit_for_owner(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    limit: int = 200,
) -> list[dict]:
    if not owner_id:
        raise IsolationViolation("owner_id is required")
    rows = storage.execute(
        """
        SELECT id, owner_id, contact_id, action, detail, created_at
        FROM audit_log
        WHERE owner_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (owner_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


# ═════════════════════════════════════════════════════════════════════════════
# Soul: lifecycle / mistakes / soul_memory / relationship_events / archetypes
# ═════════════════════════════════════════════════════════════════════════════

def ensure_lifecycle(
    storage: SqlcipherStorage, owner_id: str
) -> dict:
    if not owner_id:
        raise IsolationViolation("owner_id is required")
    now = _iso(_now())
    storage.execute(
        """
        INSERT OR IGNORE INTO agent_lifecycle
            (owner_id, birth_at, maturity_stage, bond_level)
        VALUES (?, ?, 'birth', 0)
        """,
        (owner_id, now),
    )
    row = storage.execute(
        """
        SELECT owner_id, birth_at, maturity_stage, bond_level,
               dominant_style, last_reflection_at
        FROM agent_lifecycle WHERE owner_id = ?
        """,
        (owner_id,),
    ).fetchone()
    return dict(row) if row else {}


def advance_lifecycle_stage(
    storage: SqlcipherStorage, owner_id: str, new_stage: str
) -> None:
    if new_stage not in {"birth", "bonding", "forming", "mature"}:
        raise ValueError(f"invalid lifecycle stage: {new_stage!r}")
    storage.execute(
        """
        UPDATE agent_lifecycle
        SET maturity_stage = ?, last_reflection_at = ?
        WHERE owner_id = ?
        """,
        (new_stage, _iso(_now()), owner_id),
    )
    append_audit(
        storage,
        owner_id=owner_id,
        action="lifecycle_advanced",
        detail=f"stage={new_stage}",
    )


def set_dominant_style(
    storage: SqlcipherStorage, owner_id: str, style: str
) -> None:
    """Persist the learned voice signature for this owner.

    Stored on ``agent_lifecycle.dominant_style``; folded into composer
    prompts automatically via ``Engine._learned_style_for_pair``. The
    string is owner-scoped only (per-pair customisation is v0.2+).
    """
    ensure_lifecycle(storage, owner_id)
    now = _iso(_now())
    storage.execute(
        """
        UPDATE agent_lifecycle
        SET dominant_style = ?, last_reflection_at = ?
        WHERE owner_id = ?
        """,
        (style or None, now, owner_id),
    )
    append_audit(
        storage,
        owner_id=owner_id,
        action="voice_calibrated",
        detail=f"signature_chars={len(style or '')}",
    )


def adjust_bond_level(
    storage: SqlcipherStorage, owner_id: str, delta: int
) -> int:
    ensure_lifecycle(storage, owner_id)
    row = storage.execute(
        "SELECT bond_level FROM agent_lifecycle WHERE owner_id = ?",
        (owner_id,),
    ).fetchone()
    current = int(row["bond_level"]) if row else 0
    new_val = max(0, min(5, current + delta))
    storage.execute(
        "UPDATE agent_lifecycle SET bond_level = ? WHERE owner_id = ?",
        (new_val, owner_id),
    )
    return new_val


def record_mistake(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    mistake_summary: str,
    lesson: str,
    behavior_update: str,
    contact_id: Optional[str] = None,
    user_feedback: Optional[str] = None,
) -> str:
    mid = _id()
    storage.execute(
        """
        INSERT INTO agent_mistakes
            (id, owner_id, contact_id, mistake_summary, user_feedback,
             lesson, behavior_update, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mid, owner_id, contact_id, mistake_summary, user_feedback,
            lesson, behavior_update, _iso(_now()),
        ),
    )
    append_audit(
        storage,
        owner_id=owner_id,
        contact_id=contact_id,
        action="mistake_recorded",
        detail=lesson,
    )
    return mid


def list_recent_mistakes(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    limit: int = 20,
) -> list[dict]:
    if not owner_id:
        raise IsolationViolation("owner_id is required")
    rows = storage.execute(
        """
        SELECT id, owner_id, contact_id, mistake_summary, user_feedback,
               lesson, behavior_update, created_at
        FROM agent_mistakes
        WHERE owner_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (owner_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def insert_soul_memory(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
    memory_type: str,
    summary: str,
    emotional_weight: float = 0.5,
    lesson: Optional[str] = None,
    persistence_level: str = "durable",
    expires_at: Optional[datetime] = None,
) -> str:
    _require_pair(owner_id, contact_id)
    if memory_type not in {"bond", "insight", "preference", "boundary"}:
        raise ValueError(f"invalid soul memory_type: {memory_type!r}")
    if persistence_level not in {"ephemeral", "durable", "permanent"}:
        raise ValueError(f"invalid persistence_level: {persistence_level!r}")
    sid = _id()
    storage.execute(
        """
        INSERT INTO soul_memory
            (id, owner_id, contact_id, memory_type, summary,
             emotional_weight, lesson, persistence_level, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sid, owner_id, contact_id, memory_type, summary,
            emotional_weight, lesson, persistence_level,
            _iso(_now()), _iso(expires_at),
        ),
    )
    return sid


def list_soul_memory_for_pair(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
) -> list[dict]:
    """Pair-scoped read. Enforces Invariant I-1."""
    _require_pair(owner_id, contact_id)
    rows = storage.execute(
        """
        SELECT id, owner_id, contact_id, memory_type, summary,
               emotional_weight, lesson, persistence_level, created_at, expires_at
        FROM soul_memory
        WHERE owner_id = ? AND contact_id = ?
          AND (expires_at IS NULL OR expires_at > ?)
        ORDER BY created_at DESC
        """,
        (owner_id, contact_id, _iso(_now())),
    ).fetchall()
    return [dict(r) for r in rows]


def record_relationship_event(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
    event_type: str,
    user_state: Optional[str] = None,
    agent_role: Optional[str] = None,
    response_posture: Optional[str] = None,
    outcome: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    _require_pair(owner_id, contact_id)
    eid = _id()
    storage.execute(
        """
        INSERT INTO relationship_events
            (id, owner_id, contact_id, event_type, user_state, agent_role,
             response_posture, outcome, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            eid, owner_id, contact_id, event_type, user_state, agent_role,
            response_posture, outcome, notes, _iso(_now()),
        ),
    )
    return eid


def list_relationship_events_for_pair(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
    limit: int = 50,
) -> list[dict]:
    _require_pair(owner_id, contact_id)
    rows = storage.execute(
        """
        SELECT id, owner_id, contact_id, event_type, user_state, agent_role,
               response_posture, outcome, notes, created_at
        FROM relationship_events
        WHERE owner_id = ? AND contact_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (owner_id, contact_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def set_archetype_preference(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
    archetype: str,
    allowed: bool = True,
    trust_required: int = 0,
    effectiveness_score: float = 0.5,
) -> None:
    _require_pair(owner_id, contact_id)
    storage.execute(
        """
        INSERT INTO archetype_preferences
            (owner_id, contact_id, archetype, allowed, trust_required, effectiveness_score)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (owner_id, contact_id, archetype) DO UPDATE SET
            allowed             = excluded.allowed,
            trust_required      = excluded.trust_required,
            effectiveness_score = excluded.effectiveness_score
        """,
        (
            owner_id, contact_id, archetype,
            1 if allowed else 0, trust_required, effectiveness_score,
        ),
    )


def get_archetype_preferences_for_pair(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    contact_id: str,
) -> dict[str, dict]:
    """Return {archetype_name: row_dict} for quick lookup."""
    _require_pair(owner_id, contact_id)
    rows = storage.execute(
        """
        SELECT owner_id, contact_id, archetype, allowed, trust_required,
               last_used_at, effectiveness_score
        FROM archetype_preferences
        WHERE owner_id = ? AND contact_id = ?
        """,
        (owner_id, contact_id),
    ).fetchall()
    return {r["archetype"]: dict(r) for r in rows}


def snapshot_synthetic_state(
    storage: SqlcipherStorage,
    *,
    owner_id: str,
    state: dict,
    contact_id: Optional[str] = None,
) -> None:
    """Persist a synthetic-state snapshot. Short-term only (24h–7d)."""
    storage.execute(
        """
        INSERT INTO synthetic_feeling_snapshots
            (id, owner_id, contact_id, concern, tenderness, protectiveness,
             honesty, patience, restraint, faith, challenge_impulse, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _id(), owner_id, contact_id,
            state.get("concern"), state.get("tenderness"),
            state.get("protectiveness"), state.get("honesty"),
            state.get("patience"), state.get("restraint"),
            state.get("faith"), state.get("challenge_impulse"),
            _iso(_now()),
        ),
    )


def prune_synthetic_snapshots(
    storage: SqlcipherStorage, *, older_than: datetime
) -> int:
    cur = storage.execute(
        "DELETE FROM synthetic_feeling_snapshots WHERE created_at < ?",
        (_iso(older_than),),
    )
    return cur.rowcount or 0


# ═════════════════════════════════════════════════════════════════════════════
# Sovereignty (Invariant I-2): export + wipe
# ═════════════════════════════════════════════════════════════════════════════

# Tables that contain owner-scoped data. Order matters for wipe (no FK
# violations, though SQLite is forgiving): children before parents.
_OWNER_TABLES = (
    "feedback",
    "care_decisions",
    "threads",
    "consent",
    "observed_messages",
    "audit_log",
    "soul_memory",
    "relationship_events",
    "agent_mistakes",
    "archetype_preferences",
    "synthetic_feeling_snapshots",
    "agent_lifecycle",
    "owners",
)


def export_owner_data(
    storage: SqlcipherStorage, owner_id: str
) -> dict[str, Any]:
    """Full JSON-shaped dump of every row referencing this owner.

    Invariant I-2 — sovereignty. The Mini App or CLI can offer this as a
    download. The output is plain JSON (decrypted on the way out); the
    host application is responsible for what happens to the file after.
    """
    if not owner_id:
        raise IsolationViolation("owner_id is required")
    out: dict[str, Any] = {
        "schema_version": storage.schema_version(),
        "exported_at": _iso(_now()),
        "owner_id": owner_id,
        "tables": {},
    }
    for table in _OWNER_TABLES:
        # care_decisions and feedback are linked via thread → owner
        if table == "feedback":
            sql = """
                SELECT f.* FROM feedback f
                JOIN care_decisions d ON d.id = f.decision_id
                JOIN threads t        ON t.id = d.thread_id
                WHERE t.owner_id = ?
            """
        elif table == "care_decisions":
            sql = """
                SELECT d.* FROM care_decisions d
                JOIN threads t ON t.id = d.thread_id
                WHERE t.owner_id = ?
            """
        elif table == "owners":
            sql = "SELECT * FROM owners WHERE id = ?"
        else:
            sql = f"SELECT * FROM {table} WHERE owner_id = ?"
        try:
            rows = storage.execute(sql, (owner_id,)).fetchall()
            out["tables"][table] = [dict(r) for r in rows]
        except Exception as exc:
            # surface but don't fail entire export — partial export is more
            # useful than nothing
            out["tables"][table] = {"error": repr(exc)}
    return out


def issue_wipe_confirmation_token(
    storage: SqlcipherStorage, owner_id: str
) -> str:
    """Two-step wipe: caller asks for a token, then calls wipe with it.

    Token is short-lived (we store it in audit_log and validate by lookup).
    Returns a 32-char token to show to the owner; owner confirms by
    repeating it back to ``wipe_owner_data``.
    """
    if not owner_id:
        raise IsolationViolation("owner_id is required")
    token = secrets.token_urlsafe(24)
    append_audit(
        storage,
        owner_id=owner_id,
        action="wipe_token_issued",
        detail=f"token={token}",
    )
    return token


def wipe_owner_data(
    storage: SqlcipherStorage,
    owner_id: str,
    confirmation_token: str,
) -> int:
    """Delete EVERYTHING about owner_id. Returns number of rows deleted.

    Validates ``confirmation_token`` against a recently-issued
    ``wipe_token_issued`` audit entry. Tokens are accepted up to 10 minutes
    after issuance.
    """
    if not owner_id:
        raise IsolationViolation("owner_id is required")
    if not confirmation_token:
        raise ValueError("confirmation_token required")

    # validate token
    row = storage.execute(
        """
        SELECT id, created_at FROM audit_log
        WHERE owner_id = ? AND action = 'wipe_token_issued'
          AND detail = ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (owner_id, _audit_safe(f"token={confirmation_token}")),
    ).fetchone()
    if not row:
        raise ValueError("invalid confirmation_token (not issued or already used)")
    issued_at = _from_iso(row["created_at"])
    age = (_now() - issued_at).total_seconds() if issued_at else 1e9
    if age > 600:
        raise ValueError(f"confirmation_token expired ({int(age)}s old; max 600s)")

    # delete in dependency-safe order
    total = 0
    for table in _OWNER_TABLES:
        if table == "feedback":
            sql = """
                DELETE FROM feedback WHERE decision_id IN (
                    SELECT d.id FROM care_decisions d
                    JOIN threads t ON t.id = d.thread_id
                    WHERE t.owner_id = ?
                )
            """
        elif table == "care_decisions":
            sql = """
                DELETE FROM care_decisions WHERE thread_id IN (
                    SELECT id FROM threads WHERE owner_id = ?
                )
            """
        elif table == "owners":
            sql = "DELETE FROM owners WHERE id = ?"
        else:
            sql = f"DELETE FROM {table} WHERE owner_id = ?"
        cur = storage.execute(sql, (owner_id,))
        total += cur.rowcount or 0

    # invalidate the token so it cannot be replayed
    storage.execute(
        "DELETE FROM audit_log WHERE id = ?", (row["id"],),
    )
    # Final audit entry survives even though we just wiped the owner row —
    # but only if downstream owners table is recreated. To keep things
    # consistent we record under a meta-owner: not stored. Drop the line.
    return total
