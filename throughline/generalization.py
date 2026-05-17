"""
Generalization layer — deflects exact-fact citation.

See SPEC.md §7. The reason this exists: precise recall ("your exam at 14:30
just ended") feels uncanny. Friends remember in generalities. The engine
should too.

Three levels:
- literal: exact fact (used only in user-facing data displays like Mini App)
- loose: generalized but still specific to the topic (default for composition)
- oblique: vague reference (high-sensitivity threads only)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class GeneralizationLevel(str, Enum):
    LITERAL = "literal"
    LOOSE = "loose"
    OBLIQUE = "oblique"


# Static fallback patterns. The LLM-based generalizer below is preferred
# when available, but these patterns work without any LLM dependency.
FALLBACK_PATTERNS = {
    ("life_event", "exam"): {
        "loose": "you had something important today",
        "oblique": "today might have been heavy",
    },
    ("life_event", "interview"): {
        "loose": "the conversation you were preparing for",
        "oblique": "the thing you were getting ready for",
    },
    ("life_event", "deployment"): {
        "loose": "the deploy you were planning",
        "oblique": "the work thing",
    },
    ("wellbeing", "sleep"): {
        "loose": "you mentioned sleep wasn't easy",
        "oblique": "you weren't quite rested",
    },
    ("wellbeing", "appetite"): {
        "loose": "you mentioned eating wasn't easy lately",
        "oblique": "things were a bit off lately",
    },
    ("intent", "movie"): {
        "loose": "that movie you were going to watch",
        "oblique": "the thing you were going to check out",
    },
    ("commitment", "task"): {
        "loose": "the thing you wanted to get to",
        "oblique": "what you had in mind",
    },
}


def generalize(
    raw_fact: str,
    thread_type: str,
    topic: Optional[str] = None,
    level: GeneralizationLevel = GeneralizationLevel.LOOSE,
    llm_client: Optional[object] = None,
) -> str:
    """Return a generalized phrasing of a fact.

    Args:
        raw_fact: The original specific fact (e.g., "exam at 14:30 physics Hall B")
        thread_type: The Thread's type (e.g., "life_event")
        topic: Optional subtopic (e.g., "exam", "sleep", "appetite")
        level: How vague to go
        llm_client: Optional LLM for dynamic generalization. If None, uses patterns.

    Returns:
        Generalized string suitable for inclusion in a care message.
    """
    if level == GeneralizationLevel.LITERAL:
        return raw_fact

    # Try LLM-based generalization if available (v0.2+ default).
    if llm_client is not None:
        return _llm_generalize(raw_fact, thread_type, topic, level, llm_client)

    # Fallback to static patterns.
    if topic:
        key = (thread_type, topic)
        if key in FALLBACK_PATTERNS:
            return FALLBACK_PATTERNS[key].get(level.value, raw_fact)

    # Last resort: very vague.
    if level == GeneralizationLevel.OBLIQUE:
        return "something you mentioned"
    return "that thing you mentioned"


def _llm_generalize(
    raw_fact: str,
    thread_type: str,
    topic: Optional[str],
    level: GeneralizationLevel,
    llm_client: object,
) -> str:
    """LLM-driven generalization. Stub for v0.2+."""
    # TODO(v0.2): implement with a tightly-scoped prompt.
    # The prompt should be one-shot, no tools, just text-in/text-out.
    # Suggested system prompt:
    #
    #   You are a generalizer. Given a specific fact about a person's life,
    #   rephrase it to be true but vague enough that it would not feel
    #   surveillant if quoted back. Preserve the topic, lose the precision.
    #   Output only the rephrased fact. No quotes, no preamble.
    #
    raise NotImplementedError("v0.2 stub")
