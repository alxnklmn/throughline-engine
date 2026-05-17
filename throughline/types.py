"""
Core type definitions for Throughline.

These are the public types that integrators interact with. They mirror
the data model described in SPEC.md §8 but are designed for Python ergonomics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class Sensitivity(str, Enum):
    """How careful the engine must be with this thread."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"  # crisis-territory; veto by default


class ThreadType(str, Enum):
    """The kind of human-state thread."""

    LIFE_EVENT = "life_event"      # exam, interview, deployment, meeting
    WELLBEING = "wellbeing"        # sleep, appetite, energy, mood
    COMMITMENT = "commitment"      # "I'll do X by Y"
    INTENT = "intent"              # "I want to try X"
    CREATIVE = "creative"          # "I had this idea about Z"


class ThreadStatus(str, Enum):
    """Lifecycle state of a thread."""

    OPEN = "open"              # active, can be initiated upon
    COOLING = "cooling"        # recently initiated, in cooldown
    DORMANT = "dormant"        # past primary window, may revive on trigger
    RESOLVED = "resolved"      # owner closed it
    CLOSED = "closed"          # final state, no further action


class InitiationLevel(str, Enum):
    """Graduated intrusiveness levels for initiative.

    Ordered from least to most intrusive. The engine prefers the lowest
    level that still serves the thread.
    """

    SILENCE = "silence"
    PASSIVE_PROMPT = "passive_prompt"
    SOFT_INJECT = "soft_inject"
    STATUS_NUDGE = "status_nudge"
    DIRECT_MESSAGE = "direct"


class FeedbackType(str, Enum):
    """Owner reaction to a delivered initiative."""

    ENGAGED = "engaged"              # owner responded warmly / continued thread
    APPRECIATED = "appreciated"      # explicit thanks
    IGNORED = "ignored"              # no response within window
    REBUFFED = "rebuffed"            # "don't ask such things" / "stop"
    NEUTRAL = "neutral"              # responded but not engaged with the care aspect


class CategoryConsent(str, Enum):
    """Per-category consent levels."""

    DENIED = "denied"                # never initiate in this category
    TASK = "task"                    # only task/project-related initiation
    EVENT = "event"                  # important life events the owner explicitly mentioned
    WELLBEING = "wellbeing"          # bodily state if owner volunteered it
    FULL = "full"                    # emotional check-ins permitted


Direction = Literal["incoming", "outgoing", "self"]
"""
Direction of a message:
- incoming: from contact to owner
- outgoing: from owner to contact (or from bot on owner's behalf)
- self: between owner and the assistant itself (used for self-directed care)
"""


# ─────────────────────────────────────────────────────────────────────────────
# Core models
# ─────────────────────────────────────────────────────────────────────────────

class Thread(BaseModel):
    """A Human State Thread — a unit of carried concern.

    See SPEC.md §8 for the storage schema.
    """

    id: str
    owner_id: str
    contact_id: str  # part of the isolation pair; for self-care, == owner_id

    category: str
    type: ThreadType
    title: str           # short, already generalized
    summary: str         # pre-generalized for composition use

    emotional_state: Optional[str] = None
    emotional_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    sensitivity: Sensitivity = Sensitivity.MEDIUM
    importance: float = Field(default=0.5, ge=0.0, le=1.0)

    source_message_id: Optional[str] = None
    followup_after: Optional[datetime] = None
    expires_at: datetime
    max_attempts: int = 1
    attempts_count: int = 0
    last_attempt_at: Optional[datetime] = None

    status: ThreadStatus = ThreadStatus.OPEN
    created_at: datetime


class Decision(BaseModel):
    """An initiative decision produced by the engine.

    Hosts react based on `.level`:
    - SILENCE: do nothing
    - PASSIVE_PROMPT: surface in dashboard / Mini App, no notification
    - SOFT_INJECT: weave into next outgoing message naturally
    - STATUS_NUDGE: change visible status without messaging
    - DIRECT_MESSAGE: send the composed message
    """

    id: str
    thread_id: str
    care_score: float
    level: InitiationLevel
    decision_reason: str
    veto_triggered: Optional[str] = None
    composed_message: Optional[str] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None


class ConsentRecord(BaseModel):
    """Per-(owner, contact, category) consent.

    Absence of a record means no consent — the engine treats this as veto.
    """

    owner_id: str
    contact_id: str
    category: str
    level: CategoryConsent
    quiet_hours_start: Optional[int] = None  # 0-23
    quiet_hours_end: Optional[int] = None    # 0-23
    updated_at: datetime
