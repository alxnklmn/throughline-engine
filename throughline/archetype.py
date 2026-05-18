"""
Archetype Matrix (SPEC.md §11).

After Posture is chosen, the Archetype Engine picks the ROLE Anima plays
in this moment. Posture says *how* to be; Archetype says *as whom*.

Three tiers:
- Default (always): Companion
- Earned (trust ≥ 2): Friend, Teacher
- Cautious (trust ≥ 4 + explicit owner comfort): Parent-figure, Enemy-of-self-deception
- Restricted (per-session opt-in): View-from-height, Shadow-mirror
- Forbidden: Romantic partner / therapist / spiritual authority — never instantiated

v0.1 MVP scope (SPEC.md §20):
- Companion default
- Friend / Teacher (tier 2) with trust ≥ 2
- Higher tiers deferred to v0.3+; if the algorithm wants them in v0.1,
  collapse to Companion.

Selection runs the non-coercion test (§11.3) before finalizing. Any
"yes" answer → fall back to Companion. Always.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from throughline.types import Archetype, Posture, ResonanceReading, Sensitivity

log = logging.getLogger("anima.archetype")


# v0.1 active set per SPEC.md §20.
V0_1_ARCHETYPES: frozenset[Archetype] = frozenset({
    Archetype.COMPANION,
    Archetype.FRIEND,
    Archetype.TEACHER,
})

# Collapse to a safe v0.1 option when the algorithm requests an unavailable role.
_V0_1_COLLAPSE: dict[Archetype, Archetype] = {
    Archetype.PARENT_FIGURE:           Archetype.COMPANION,
    Archetype.ENEMY_OF_SELF_DECEPTION: Archetype.COMPANION,
    Archetype.VIEW_FROM_HEIGHT:        Archetype.COMPANION,
    Archetype.SHADOW_MIRROR:           Archetype.COMPANION,
}

# Tier requirements per SPEC.md §11.1.
_MIN_TRUST: dict[Archetype, int] = {
    Archetype.COMPANION: 0,
    Archetype.FRIEND: 2,
    Archetype.TEACHER: 2,
    Archetype.PARENT_FIGURE: 4,
    Archetype.ENEMY_OF_SELF_DECEPTION: 4,
    Archetype.VIEW_FROM_HEIGHT: 4,
    Archetype.SHADOW_MIRROR: 4,
}


@dataclass
class ArchetypeChoice:
    archetype: Archetype                # what to use (v0.1-safe value)
    raw_archetype: Archetype            # algorithm's actual choice
    reason: str                         # audit/transparency
    collapsed: bool                     # True if raw differs from archetype
    non_coercion_passed: bool           # False → fallback to Companion engaged


def select_archetype(
    posture: Posture,
    resonance: ResonanceReading,
    *,
    trust_level: int,
    explicit_request: Optional[Archetype] = None,
    archetype_preferences: Optional[dict[str, dict]] = None,
    is_learning_context: bool = False,
    apply_v0_1_collapse: bool = True,
) -> ArchetypeChoice:
    """Pick the archetype for this moment.

    Args:
        posture: result of Posture Engine
        resonance: current resonance reading (for sensitivity check)
        trust_level: owners.care_level (0–5)
        explicit_request: if the owner asked for a specific role in this
            session. Validated and tier-gated like any other.
        archetype_preferences: result of get_archetype_preferences_for_pair —
            mapping {archetype_name: {allowed: 0|1, effectiveness_score: 0..1}}
        is_learning_context: True if the recent thread/topic is study/work/
            tutorial — favors Teacher when posture is GUIDE.
        apply_v0_1_collapse: True (default) → confine output to v0.1 set.

    Returns:
        ArchetypeChoice. ``.archetype`` is what to use; ``.raw_archetype``
        shows the unfiltered algorithm output.
    """
    raw, reason = _raw_select(
        posture=posture,
        resonance=resonance,
        trust_level=trust_level,
        explicit_request=explicit_request,
        archetype_preferences=archetype_preferences or {},
        is_learning_context=is_learning_context,
    )

    # Non-coercion test (§11.3). On any "yes" → fallback to Companion.
    if not _non_coercion_test(raw, posture, resonance, trust_level):
        log.info(
            "archetype: non-coercion test failed for %s + %s; falling back to companion",
            raw.value, posture.value,
        )
        return ArchetypeChoice(
            archetype=Archetype.COMPANION,
            raw_archetype=raw,
            reason=f"{reason}; non-coercion test failed → companion",
            collapsed=raw != Archetype.COMPANION,
            non_coercion_passed=False,
        )

    if apply_v0_1_collapse and raw not in V0_1_ARCHETYPES:
        active = _V0_1_COLLAPSE.get(raw, Archetype.COMPANION)
        return ArchetypeChoice(
            archetype=active,
            raw_archetype=raw,
            reason=reason,
            collapsed=True,
            non_coercion_passed=True,
        )

    return ArchetypeChoice(
        archetype=raw,
        raw_archetype=raw,
        reason=reason,
        collapsed=False,
        non_coercion_passed=True,
    )


def _raw_select(
    *,
    posture: Posture,
    resonance: ResonanceReading,
    trust_level: int,
    explicit_request: Optional[Archetype],
    archetype_preferences: dict[str, dict],
    is_learning_context: bool,
) -> tuple[Archetype, str]:
    """SPEC.md §11.2 algorithm."""

    # 0. Explicit owner request (e.g., "be my teacher for this session").
    # Must still pass tier gates + non-coercion test (handled downstream).
    if explicit_request is not None:
        if _tier_allows(explicit_request, trust_level, archetype_preferences):
            return explicit_request, f"explicit owner request: {explicit_request.value}"
        return (
            Archetype.COMPANION,
            f"explicit request {explicit_request.value} denied (trust/permissions)",
        )

    # 1. PROTECT posture → COMPANION (protective stance, neutral role).
    if posture == Posture.PROTECT:
        return Archetype.COMPANION, "protect stance → neutral role"

    # 2. SILENCE — choice doesn't affect output but we record for the
    # transparency dashboard. Pick the most recent / preferred role.
    if posture == Posture.SILENCE:
        preferred = _most_effective_allowed(archetype_preferences, trust_level)
        return preferred or Archetype.COMPANION, "silence — recording preferred role"

    # 3. CHALLENGE + trust ≥ 4 → ENEMY_OF_SELF_DECEPTION (v0.1 collapses).
    if posture == Posture.CHALLENGE and trust_level >= 4:
        if _tier_allows(Archetype.ENEMY_OF_SELF_DECEPTION, trust_level, archetype_preferences):
            return (
                Archetype.ENEMY_OF_SELF_DECEPTION,
                "challenge + trust ≥ 4 — name the avoided pattern",
            )
        return Archetype.COMPANION, "challenge wanted but archetype denied → companion"

    # 4. HOLD + trust ≥ 3 → FRIEND (warmth allowed at bonded trust).
    # Earlier than spec's "preferred_warm_archetype" lookup so v0.1 has a
    # cleaner default.
    if posture == Posture.HOLD and trust_level >= 3:
        if _tier_allows(Archetype.FRIEND, trust_level, archetype_preferences):
            return Archetype.FRIEND, "hold + trust ≥ 3 — friend warmth"
        return Archetype.COMPANION, "hold + trust ≥ 3 but friend denied"

    # 5. GUIDE + learning context → TEACHER.
    if posture == Posture.GUIDE and is_learning_context and trust_level >= 2:
        if _tier_allows(Archetype.TEACHER, trust_level, archetype_preferences):
            return Archetype.TEACHER, "guide + learning context — teacher"
        return Archetype.COMPANION, "teacher wanted but denied → companion"

    # 6. GUIDE + trust ≥ 2 + general chat — Friend tone is welcome.
    if posture == Posture.GUIDE and trust_level >= 2:
        if _tier_allows(Archetype.FRIEND, trust_level, archetype_preferences):
            return Archetype.FRIEND, "guide + trust ≥ 2 — friend tone"

    # 7. Default — COMPANION (always safe).
    return Archetype.COMPANION, "default — companion (always safe)"


def _tier_allows(
    archetype: Archetype,
    trust_level: int,
    preferences: dict[str, dict],
) -> bool:
    """Tier gate + explicit allowed=False check.

    The owner can deny any archetype via set_archetype_preference. A
    denial in preferences trumps trust; without a denial, trust gate
    decides.
    """
    pref = preferences.get(archetype.value)
    if pref is not None:
        if not pref.get("allowed", 1):
            return False
        required = int(pref.get("trust_required", _MIN_TRUST.get(archetype, 0)))
        return trust_level >= required
    return trust_level >= _MIN_TRUST.get(archetype, 0)


def _most_effective_allowed(
    preferences: dict[str, dict],
    trust_level: int,
) -> Optional[Archetype]:
    """Used by SILENCE branch — show transparency about preferred role."""
    best: tuple[float, Optional[Archetype]] = (-1.0, None)
    for arch_name, pref in preferences.items():
        try:
            arch = Archetype(arch_name)
        except ValueError:
            continue
        if not _tier_allows(arch, trust_level, preferences):
            continue
        score = float(pref.get("effectiveness_score") or 0.0)
        if score > best[0]:
            best = (score, arch)
    return best[1]


# ─────────────────────────────────────────────────────────────────────────────
# Non-coercion test (SPEC.md §11.3 — Invariant I-7)
# ─────────────────────────────────────────────────────────────────────────────

def _non_coercion_test(
    archetype: Archetype,
    posture: Posture,
    resonance: ResonanceReading,
    trust_level: int,
) -> bool:
    """Returns True if the combination is acceptable.

    The four §11.3 questions (paraphrased): in this moment, would this
    role attempt to (a) take a decision that's the user's, (b) create
    guilt for past behavior, (c) claim authority Anima does not have,
    (d) make disagreement feel wrong?

    Yes to any → return False → caller falls back to Companion.

    v0.1 implementation: heuristic checks on combinations known to be
    risky. The fallback principle (SPEC.md §12) is always safe: if
    uncertain, return False.
    """
    # Critical sensitivity + any role → not OK. Crisis territory is
    # never the moment for archetype play.
    if resonance.sensitivity == Sensitivity.CRITICAL:
        return archetype == Archetype.COMPANION

    # Parent-figure with low trust → coercive (infantilizes someone you
    # don't know well). v0.1 anyway collapses to Companion, but the test
    # records the failure for audit.
    if archetype == Archetype.PARENT_FIGURE and trust_level < 4:
        return False

    # Enemy-of-self-deception at HIGH sensitivity → likely lands as
    # shame-inducing. Spec §11 forbids the combination.
    if (
        archetype == Archetype.ENEMY_OF_SELF_DECEPTION
        and resonance.sensitivity == Sensitivity.HIGH
    ):
        return False

    # View-from-height + HOLD posture → claims time-horizon authority
    # while user is in fear. Wrong moment.
    if archetype == Archetype.VIEW_FROM_HEIGHT and posture == Posture.HOLD:
        return False

    # Shadow-mirror at any non-explicit context → too presumptuous.
    # Should only land via explicit_request. The selector already restricts
    # this but defence-in-depth.
    if archetype == Archetype.SHADOW_MIRROR:
        return False  # v0.1: never reach Shadow without explicit per-session opt-in

    return True
