"""
Throughline — an engine of human continuity for AI assistants.

See SPEC.md for the canonical specification.

Quick start:

    from throughline import Engine, FeedbackType

    engine = Engine(
        storage_path="~/.throughline/state.db",
        encryption_key_source="keychain",
        owner_id="alex",
    )

    engine.observe_message(...)
    decisions = engine.tick(owner_id="alex")
    engine.record_feedback(...)
"""

from throughline.engine import Engine
from throughline.types import (
    Decision,
    FeedbackType,
    InitiationLevel,
    Sensitivity,
    Thread,
    ThreadType,
)

__version__ = "0.1.0a0"

__all__ = [
    "Engine",
    "Decision",
    "FeedbackType",
    "InitiationLevel",
    "Sensitivity",
    "Thread",
    "ThreadType",
    "__version__",
]
