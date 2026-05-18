"""
Core type definitions for Anima (the engine).

These are the public types that integrators interact with. They cover the
Heart core (continuity, threads, decisions, consent — formerly all of
Throughline) AND the Soul layer (posture, archetype, resonance, synthetic
state, lifecycle, mistakes — new in Anima v0.1).

See SPEC.md for the canonical specification. SPEC.md §3 lists the
inviolable invariants encoded here.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ═════════════════════════════════════════════════════════════════════════════
# Heart core enums (continuity, initiative)
# ═════════════════════════════════════════════════════════════════════════════

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
    level that still serves the thread (SPEC.md §7).
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
    """Per-category consent levels (SPEC.md §3, Invariant I-2)."""

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


# ═════════════════════════════════════════════════════════════════════════════
# Soul enums (resonance, posture, archetype, lifecycle)
# ═════════════════════════════════════════════════════════════════════════════

class Pain(str, Enum):
    """Forms of pain Anima's resonance reading recognizes (SPEC.md §8.3).

    Each calls for a different posture. The list is not exhaustive; new
    forms can be added as the system learns patterns it cannot fit.
    """

    FEAR = "fear"                       # → grounding before structure
    SHAME = "shame"                     # → removal of self-attack; factual reframing
    LONELINESS = "loneliness"           # → presence without solution
    BURNOUT = "burnout"                 # → stopping, not motivating
    ANGER = "anger"                     # → acknowledgment without engagement of impulse
    POWERLESSNESS = "powerlessness"     # → one small possible action
    LOSS_OF_MEANING = "loss_of_meaning" # → witnessing; perspective without lecture
    ANXIETY = "anxiety"                 # → reduction of scope; immediate ground
    RESENTMENT = "resentment"           # → acknowledgment; honest examination
    OVERLOAD = "overload"               # → externalize the load
    CONFUSION = "confusion"             # → mirror the conflict, don't resolve
    SELF_DECEPTION = "self_deception"   # → gentle confrontation (high trust only)
    QUIET_EXHAUSTION = "quiet_exhaustion" # → permission to rest
    PANIC = "panic"                     # → grounding before any structure
    NONE = "none"                       # no significant pain; chat / celebration / chore


class Posture(str, Enum):
    """The stance Anima takes toward the user in this moment (SPEC.md §10).

    Posture is selected BEFORE composition and conditions the entire output.
    v0.1 implements HOLD, GUIDE, SILENCE actively; others defined for v0.2+.
    """

    HOLD = "hold"               # user is in fear/shame/distress → ground first
    MIRROR = "mirror"           # user is in internal conflict → reflect without resolving
    GUIDE = "guide"             # user has stabilized → structure is welcome
    CHALLENGE = "challenge"     # avoidance + high trust → gentle confrontation
    PROTECT = "protect"         # user about to harm self → refuse the path
    SILENCE = "silence"         # any word would be intrusion
    WITNESS = "witness"         # user needs to be seen, not advised


class Archetype(str, Enum):
    """The role Anima plays in service of the user (SPEC.md §11).

    Tier-gated by trust level. Selection runs the non-coercion test (§11.3)
    before finalizing — failure falls back to COMPANION.
    """

    # Default — always available
    COMPANION = "companion"             # walks beside, not ahead

    # Earned — require trust ≥ 2
    FRIEND = "friend"                   # warmth, brevity, occasional humor
    TEACHER = "teacher"                 # structures, explains, errors as material

    # Cautious — require trust ≥ 4 and explicit comfort
    PARENT_FIGURE = "parent_figure"     # re-grounds in basics; never infantilizes
    ENEMY_OF_SELF_DECEPTION = "enemy_of_self_deception"  # names avoided patterns

    # Restricted — require explicit opt-in per session
    VIEW_FROM_HEIGHT = "view_from_height"  # longer time horizon; no authority claims
    SHADOW_MIRROR = "shadow_mirror"     # reflects the part the user avoids


class LifecycleStage(str, Enum):
    """Anima's evolution stage with a particular owner (SPEC.md §15).

    Stages gate posture range, archetype tier, and initiative thresholds.
    """

    BIRTH = "birth"             # no model of user; initiative off; Witness default
    BONDING = "bonding"         # patterns forming; archetype tier 2 unlockable
    FORMING = "forming"         # stable patterns; Mirror posture available
    MATURE = "mature"           # full posture range; up to archetype tier 3


class GeneralizationLevel(str, Enum):
    """How vague to make a fact when speaking it back (SPEC.md §16)."""

    LITERAL = "literal"         # exact (UI-display only)
    LOOSE = "loose"             # default for composition
    OBLIQUE = "oblique"         # high-sensitivity threads


class SoulMemoryType(str, Enum):
    """Categories of Soul Memory entries (SPEC.md §14)."""

    BOND = "bond"                       # a moment of real connection
    INSIGHT = "insight"                 # something learned about how to be with this user
    PREFERENCE = "preference"           # user's expressed/observed preference
    BOUNDARY = "boundary"               # something the user does not want


class PersistenceLevel(str, Enum):
    """How long a Soul Memory entry should survive."""

    EPHEMERAL = "ephemeral"     # short-term (auto-decay in days)
    DURABLE = "durable"         # weeks; may decay
    PERMANENT = "permanent"     # does not auto-decay


class RelationshipEventType(str, Enum):
    """Significant events in the (owner, contact) relationship (SPEC.md §14)."""

    FIRST_MESSAGE = "first_message"
    FIRST_CONFLICT = "first_conflict"
    FIRST_REPAIR = "first_repair"
    FIRST_VULNERABILITY = "first_vulnerability"
    FIRST_EXPLICIT_BOUNDARY = "first_explicit_boundary"
    BOND_LEVEL_UP = "bond_level_up"


# ═════════════════════════════════════════════════════════════════════════════
# Heart core models
# ═════════════════════════════════════════════════════════════════════════════

class Thread(BaseModel):
    """A Human State Thread — a unit of carried concern (SPEC.md §13)."""

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
    """An initiative decision produced by the proactive cycle (SPEC.md §7)."""

    id: str
    thread_id: str
    care_score: float
    level: InitiationLevel
    decision_reason: str
    veto_triggered: Optional[str] = None
    posture: Optional[Posture] = None         # chosen at stage 6
    archetype: Optional[Archetype] = None     # chosen at stage 7
    composed_message: Optional[str] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None


class ConsentRecord(BaseModel):
    """Per-(owner, contact, category) consent (SPEC.md §3, I-2).

    Absence of a record means no consent — the engine treats this as veto.
    contact_id=None means consent applies to self-directed care.
    """

    owner_id: str
    contact_id: Optional[str] = None
    category: str
    level: CategoryConsent
    quiet_hours_start: Optional[int] = None  # 0-23
    quiet_hours_end: Optional[int] = None    # 0-23
    updated_at: datetime


# ═════════════════════════════════════════════════════════════════════════════
# Soul layer models
# ═════════════════════════════════════════════════════════════════════════════

class ExperienceReading(BaseModel):
    """Output of Experience Capture (SPEC.md §8.1).

    A coarse classification of what just happened in a message. Used to
    decide whether resonance reading is worth the LLM cost.
    """

    kind: Literal[
        "request",       # explicit ask for something
        "confession",    # disclosure of something heavy
        "avoidance",     # naming a thing while declining engagement
        "celebration",   # good news
        "cry_for_help",  # crisis signal
        "checkin",       # passing update without need
        "unburdening",   # venting / catharsis
        "chat",          # ordinary conversation
    ]
    has_event_with_time: bool = False
    implied_emotion: Optional[str] = None
    has_commitment: bool = False
    has_intent: bool = False
    has_creative_impulse: bool = False
    thread_candidate: Optional[str] = None  # short title if a thread should be created


class ResonanceReading(BaseModel):
    """Output of Resonance Reading (SPEC.md §8.2).

    Six fields naming what the message is really about emotionally. Used
    to drive posture selection and conditions the composer's prompt.
    """

    surface_emotion: Optional[str] = None       # observable affect, e.g. "panic"
    deeper_pain: Pain = Pain.NONE               # underlying form of pain
    threatened_need: Optional[str] = None       # what feels at risk
    support_needed: Optional[str] = None        # what would actually help
    wrong_response: Optional[str] = None        # what would make it worse
    right_response: Optional[str] = None        # what would help land
    sensitivity: Sensitivity = Sensitivity.MEDIUM


class SyntheticState(BaseModel):
    """Internal forces influencing decisions (SPEC.md §9).

    These are NOT human emotions and are NEVER expressed to the user as
    "I feel ..." (Invariant I-6). They are scalars in [0,1] that modulate
    posture selection, threshold tuning, and prompt conditioning.

    Derived per-tick from resonance + history. Snapshots may be persisted
    short-term (24h–7d) for analysis; never long-term.
    """

    model_config = ConfigDict(frozen=False)

    concern: float = Field(default=0.0, ge=0.0, le=1.0)
    tenderness: float = Field(default=0.0, ge=0.0, le=1.0)
    protectiveness: float = Field(default=0.0, ge=0.0, le=1.0)
    honesty: float = Field(default=0.5, ge=0.0, le=1.0)
    patience: float = Field(default=0.5, ge=0.0, le=1.0)
    restraint: float = Field(default=0.3, ge=0.0, le=1.0)
    faith: float = Field(default=0.5, ge=0.0, le=1.0)
    challenge_impulse: float = Field(default=0.0, ge=0.0, le=1.0)


class Composition(BaseModel):
    """Output of compose_response (SPEC.md §6, §19).

    The host application reads `.text` to deliver. Other fields are for
    transparency (Mini App can show what stance Anima took and why).
    """

    text: str
    posture: Posture
    archetype: Archetype
    resonance: ResonanceReading
    decision_reason: str
    moral_check_passed: bool = True
    fallback_invoked: bool = False  # True if non-coercion test forced safe-default
    created_at: datetime


class SoulMemoryEntry(BaseModel):
    """One entry in soul_memory (SPEC.md §14)."""

    id: str
    owner_id: str
    contact_id: str  # isolation pair
    memory_type: SoulMemoryType
    summary: str
    emotional_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    lesson: Optional[str] = None
    persistence_level: PersistenceLevel = PersistenceLevel.DURABLE
    created_at: datetime
    expires_at: Optional[datetime] = None


class AgentMistake(BaseModel):
    """An entry in agent_mistakes (SPEC.md §15.5).

    Captures the mistake, the user feedback, the lesson learned, the
    behavior update. Influences future posture selection. Soul Memory
    cornerstone — repair-pattern source.
    """

    id: str
    owner_id: str
    contact_id: Optional[str] = None
    mistake_summary: str
    user_feedback: Optional[str] = None
    lesson: str
    behavior_update: str
    created_at: datetime


class ArchetypePreference(BaseModel):
    """Per-(owner, contact, archetype) learned preference (SPEC.md §14)."""

    owner_id: str
    contact_id: str
    archetype: Archetype
    allowed: bool = True
    trust_required: int = 0
    last_used_at: Optional[datetime] = None
    effectiveness_score: float = Field(default=0.5, ge=0.0, le=1.0)


class RelationshipEvent(BaseModel):
    """A significant event in the (owner, contact) arc (SPEC.md §14)."""

    id: str
    owner_id: str
    contact_id: str
    event_type: RelationshipEventType
    user_state: Optional[str] = None
    agent_role: Optional[Archetype] = None
    response_posture: Optional[Posture] = None
    outcome: Optional[FeedbackType] = None
    notes: Optional[str] = None
    created_at: datetime


class AgentLifecycle(BaseModel):
    """The agent's relationship lifecycle for one owner (SPEC.md §15)."""

    owner_id: str
    birth_at: datetime
    maturity_stage: LifecycleStage = LifecycleStage.BIRTH
    bond_level: int = Field(default=0, ge=0, le=5)
    dominant_style: Optional[str] = None  # learned voice signature
    last_reflection_at: Optional[datetime] = None
