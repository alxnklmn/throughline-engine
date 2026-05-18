"""
Anima — an engine of human continuity and presence for AI assistants.

Package name remains ``throughline`` until v0.2 rename for PyPI compatibility;
the philosophy and architecture are referred to as Anima throughout the code.

See SPEC.md for the canonical specification.

Quick start:

    from throughline import Engine, FeedbackType, Posture, Archetype

    engine = Engine(
        storage_path="~/.anima/state.db",
        encryption_key_source="env:ANIMA_DB_KEY",
        owner_id="alex",
        llm_client=your_llm_client,
    )

    engine.observe_message(...)
    response = engine.compose_response(...)   # reactive
    decisions = engine.tick(owner_id="alex")  # proactive
    engine.record_feedback(...)
"""

from throughline.engine import Engine
from throughline.types import (
    # Heart core
    CategoryConsent,
    ConsentRecord,
    Decision,
    Direction,
    FeedbackType,
    GeneralizationLevel,
    InitiationLevel,
    Sensitivity,
    Thread,
    ThreadStatus,
    ThreadType,
    # Soul layer
    AgentLifecycle,
    AgentMistake,
    Archetype,
    ArchetypePreference,
    Composition,
    ExperienceReading,
    LifecycleStage,
    Pain,
    PersistenceLevel,
    Posture,
    RelationshipEvent,
    RelationshipEventType,
    ResonanceReading,
    SoulMemoryEntry,
    SoulMemoryType,
    SyntheticState,
)

__version__ = "0.1.0a1"

__all__ = [
    "Engine",
    "__version__",
    # Heart
    "CategoryConsent",
    "ConsentRecord",
    "Decision",
    "Direction",
    "FeedbackType",
    "GeneralizationLevel",
    "InitiationLevel",
    "Sensitivity",
    "Thread",
    "ThreadStatus",
    "ThreadType",
    # Soul
    "AgentLifecycle",
    "AgentMistake",
    "Archetype",
    "ArchetypePreference",
    "Composition",
    "ExperienceReading",
    "LifecycleStage",
    "Pain",
    "PersistenceLevel",
    "Posture",
    "RelationshipEvent",
    "RelationshipEventType",
    "ResonanceReading",
    "SoulMemoryEntry",
    "SoulMemoryType",
    "SyntheticState",
]
