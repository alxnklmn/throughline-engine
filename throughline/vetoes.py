"""
Veto layer — binary blockers that run BEFORE any scoring.

See SPEC.md §5 (The Care Score, Stage 1) and §3 (Invariant I-5: Veto Before Score).

Each veto is a callable that takes (thread, context) and returns either:
- None: this veto does not apply, continue evaluation
- VetoFired(reason: str): this veto blocks, stop evaluation, decision is SILENCE

Vetoes are evaluated in order. The first one to fire wins. Order is significant
because earlier vetoes are typically cheaper to compute.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from throughline.types import Sensitivity, Thread


@dataclass
class VetoFired:
    """Returned by a veto when it blocks initiation."""

    name: str
    detail: str = ""


@dataclass
class EvaluationContext:
    """Snapshot of state at the moment of evaluation.

    Populated by the engine and passed to each veto. Stays free of any
    cross-channel data — only includes information about the specific
    (owner, contact) pair being evaluated.
    """

    now: datetime
    owner_id: str
    contact_id: str
    consent_level: Optional[str]  # CategoryConsent.value or None
    quiet_hours: Optional[tuple[int, int]]  # (start_hour, end_hour) or None
    trust_level: int  # 0-5
    owner_in_crisis_mode: bool
    recent_rebuffs_count: int  # rebuffs in last 7 days for this (owner, contact)
    attempts_today: int  # for this specific thread


VetoFn = Callable[[Thread, EvaluationContext], Optional[VetoFired]]


# ─────────────────────────────────────────────────────────────────────────────
# Veto implementations
# ─────────────────────────────────────────────────────────────────────────────

def no_consent_for_category(thread: Thread, ctx: EvaluationContext) -> Optional[VetoFired]:
    """If no consent record exists for this category, block."""
    if ctx.consent_level is None or ctx.consent_level == "denied":
        return VetoFired(
            name="no_consent_for_category",
            detail=f"category={thread.category}",
        )
    return None


def sensitivity_critical_without_explicit_consent(
    thread: Thread, ctx: EvaluationContext
) -> Optional[VetoFired]:
    """Critical-sensitivity threads require 'full' consent."""
    if thread.sensitivity == Sensitivity.CRITICAL and ctx.consent_level != "full":
        return VetoFired(
            name="sensitivity_critical_without_explicit_consent",
            detail=f"sensitivity=critical consent={ctx.consent_level}",
        )
    return None


def recent_rebuff_within_cooldown(
    thread: Thread, ctx: EvaluationContext
) -> Optional[VetoFired]:
    """If owner recently said 'stop / don't ask such things', cool down."""
    if ctx.recent_rebuffs_count >= 1:
        return VetoFired(
            name="recent_rebuff_within_cooldown",
            detail=f"rebuffs_7d={ctx.recent_rebuffs_count}",
        )
    return None


def quiet_hours_for_category(thread: Thread, ctx: EvaluationContext) -> Optional[VetoFired]:
    """Block during owner's quiet hours unless thread is marked emergency."""
    if ctx.quiet_hours is None:
        return None
    start, end = ctx.quiet_hours
    hour = ctx.now.hour
    in_quiet = (start <= hour < end) if start < end else (hour >= start or hour < end)
    if in_quiet:
        return VetoFired(
            name="quiet_hours_for_category",
            detail=f"hour={hour} quiet={start}-{end}",
        )
    return None


def owner_in_declared_crisis_mode(
    thread: Thread, ctx: EvaluationContext
) -> Optional[VetoFired]:
    """If owner has explicitly entered crisis mode, suppress all initiative."""
    if ctx.owner_in_crisis_mode:
        return VetoFired(name="owner_in_declared_crisis_mode")
    return None


def thread_already_resolved(thread: Thread, ctx: EvaluationContext) -> Optional[VetoFired]:
    """Closed/resolved threads are never re-initiated upon."""
    if thread.status.value in ("resolved", "closed"):
        return VetoFired(name="thread_already_resolved", detail=f"status={thread.status.value}")
    return None


def attempt_count_exceeded(thread: Thread, ctx: EvaluationContext) -> Optional[VetoFired]:
    """One direct attempt per thread (v0.1 rule)."""
    if thread.attempts_count >= thread.max_attempts:
        return VetoFired(
            name="attempt_count_exceeded",
            detail=f"attempts={thread.attempts_count} max={thread.max_attempts}",
        )
    return None


def insufficient_trust_level(thread: Thread, ctx: EvaluationContext) -> Optional[VetoFired]:
    """Different categories require minimum trust levels.

    Trust progression maps:
    - Level 0: respond only to direct requests (no initiative at all)
    - Level 1: tasks/projects
    - Level 2: important life events (life_event threads)
    - Level 3: wellbeing (sleep, food, fatigue)
    - Level 4: emotional check-ins (only with explicit consent)
    - Level 5: deep accompaniment (only with explicit consent, strict limits)
    """
    required_levels = {
        "study": 2,
        "work": 1,
        "wellbeing": 3,
        "sleep": 3,
        "food": 3,
        "emotional": 4,
        "relationships": 4,
        "health": 4,
        "creative": 1,
    }
    required = required_levels.get(thread.category, 2)
    if ctx.trust_level < required:
        return VetoFired(
            name="insufficient_trust_level",
            detail=f"category={thread.category} required={required} current={ctx.trust_level}",
        )
    return None


def thread_expired(thread: Thread, ctx: EvaluationContext) -> Optional[VetoFired]:
    """Past TTL — let it die."""
    if thread.expires_at < ctx.now:
        return VetoFired(name="thread_expired")
    return None


def too_early(thread: Thread, ctx: EvaluationContext) -> Optional[VetoFired]:
    """Before the earliest reasonable followup time."""
    if thread.followup_after and thread.followup_after > ctx.now:
        wait = thread.followup_after - ctx.now
        return VetoFired(
            name="too_early",
            detail=f"wait={wait}",
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# The default veto chain — evaluated in order
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_VETO_CHAIN: list[VetoFn] = [
    thread_already_resolved,
    thread_expired,
    attempt_count_exceeded,
    too_early,
    owner_in_declared_crisis_mode,
    no_consent_for_category,
    sensitivity_critical_without_explicit_consent,
    insufficient_trust_level,
    recent_rebuff_within_cooldown,
    quiet_hours_for_category,
]


def evaluate_vetoes(
    thread: Thread,
    ctx: EvaluationContext,
    chain: Optional[list[VetoFn]] = None,
) -> Optional[VetoFired]:
    """Run the veto chain. Return the first veto that fires, or None if all pass."""
    for veto in chain or DEFAULT_VETO_CHAIN:
        result = veto(thread, ctx)
        if result is not None:
            return result
    return None
