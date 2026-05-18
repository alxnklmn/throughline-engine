"""Tests for the archetype matrix (SPEC.md §11)."""

import random

from throughline.archetype import V0_1_ARCHETYPES, select_archetype
from throughline.types import Archetype, Pain, Posture, ResonanceReading, Sensitivity


def _reso(pain: Pain = Pain.NONE, sens: Sensitivity = Sensitivity.MEDIUM) -> ResonanceReading:
    return ResonanceReading(deeper_pain=pain, sensitivity=sens)


class TestDefault:
    def test_low_trust_defaults_companion(self):
        c = select_archetype(Posture.GUIDE, _reso(), trust_level=0)
        assert c.archetype == Archetype.COMPANION

    def test_protect_returns_companion(self):
        c = select_archetype(Posture.PROTECT, _reso(Pain.FEAR), trust_level=5)
        assert c.archetype == Archetype.COMPANION


class TestEarnedTier:
    def test_hold_trust3_picks_friend(self):
        c = select_archetype(Posture.HOLD, _reso(Pain.FEAR), trust_level=3)
        assert c.archetype == Archetype.FRIEND

    def test_guide_learning_context_picks_teacher(self):
        c = select_archetype(
            Posture.GUIDE, _reso(), trust_level=3, is_learning_context=True,
        )
        assert c.archetype == Archetype.TEACHER

    def test_guide_trust2_picks_friend(self):
        c = select_archetype(Posture.GUIDE, _reso(), trust_level=2)
        assert c.archetype == Archetype.FRIEND


class TestExplicitRequest:
    def test_teacher_granted_at_trust2(self):
        c = select_archetype(
            Posture.GUIDE, _reso(), trust_level=2,
            explicit_request=Archetype.TEACHER,
        )
        assert c.archetype == Archetype.TEACHER

    def test_parent_denied_at_trust3(self):
        c = select_archetype(
            Posture.GUIDE, _reso(), trust_level=3,
            explicit_request=Archetype.PARENT_FIGURE,
        )
        assert c.archetype == Archetype.COMPANION


class TestNonCoercion:
    def test_critical_sensitivity_forces_companion(self):
        c = select_archetype(
            Posture.HOLD, _reso(Pain.PANIC, Sensitivity.CRITICAL),
            trust_level=5,
        )
        assert c.archetype == Archetype.COMPANION

    def test_enemy_self_deception_blocked_at_high_sensitivity(self):
        # CHALLENGE + trust=5 + HIGH would otherwise pick ENEMY_OF_SELF_DECEPTION
        c = select_archetype(
            Posture.CHALLENGE, _reso(Pain.SELF_DECEPTION, Sensitivity.HIGH),
            trust_level=5,
        )
        assert c.archetype == Archetype.COMPANION
        assert not c.non_coercion_passed


class TestPreferences:
    def test_owner_denied_archetype_returns_companion(self):
        c = select_archetype(
            Posture.GUIDE, _reso(), trust_level=3,
            archetype_preferences={"friend": {"allowed": 0}},
        )
        assert c.archetype == Archetype.COMPANION

    def test_higher_trust_required_blocks(self):
        # owner says teacher needs trust 4 even though tier default is 2
        c = select_archetype(
            Posture.GUIDE, _reso(), trust_level=3, is_learning_context=True,
            archetype_preferences={"teacher": {"allowed": 1, "trust_required": 4}},
        )
        assert c.archetype == Archetype.COMPANION


class TestInvariant:
    def test_no_leaks_outside_v0_1_archetypes(self):
        random.seed(7)
        for _ in range(500):
            posture = random.choice(list(Posture))
            pain = random.choice(list(Pain))
            sens = random.choice(list(Sensitivity))
            trust = random.randint(0, 5)
            c = select_archetype(
                posture, ResonanceReading(deeper_pain=pain, sensitivity=sens),
                trust_level=trust,
            )
            assert c.archetype in V0_1_ARCHETYPES, (c.archetype, c.raw_archetype, posture, pain, sens, trust)
