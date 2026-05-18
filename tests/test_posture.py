"""Tests for the posture engine (SPEC.md §10)."""

import random

from throughline.posture import V0_1_POSTURES, select_posture
from throughline.synthetic import RelationshipContext, derive_state
from throughline.types import Pain, Posture, ResonanceReading, Sensitivity


def _reso(pain: Pain = Pain.NONE, sens: Sensitivity = Sensitivity.MEDIUM) -> ResonanceReading:
    return ResonanceReading(deeper_pain=pain, sensitivity=sens)


def _state(reso, **ctx_overrides):
    ctx = RelationshipContext(trust_level=3, bond_level=2, **ctx_overrides)
    return derive_state(reso, ctx)


class TestHardSilence:
    def test_critical_sensitivity_silences(self):
        r = _reso(Pain.PANIC, Sensitivity.CRITICAL)
        c = select_posture(r, _state(r), trust_level=3, consent_passed=True)
        assert c.posture == Posture.SILENCE

    def test_state_restraint_silences(self):
        # crisis mode pushes restraint past threshold
        r = _reso(Pain.FEAR, Sensitivity.HIGH)
        s = _state(r, owner_in_crisis_mode=True)
        c = select_posture(r, s, trust_level=3, consent_passed=True)
        assert c.posture == Posture.SILENCE


class TestPainRouting:
    def test_fear_routes_to_hold(self):
        r = _reso(Pain.FEAR)
        c = select_posture(r, _state(r), trust_level=3, consent_passed=True)
        assert c.posture == Posture.HOLD

    def test_shame_routes_to_hold(self):
        r = _reso(Pain.SHAME)
        c = select_posture(r, _state(r), trust_level=3, consent_passed=True)
        assert c.posture == Posture.HOLD

    def test_panic_routes_to_hold(self):
        r = _reso(Pain.PANIC, Sensitivity.HIGH)
        c = select_posture(r, _state(r), trust_level=3, consent_passed=True)
        assert c.posture == Posture.HOLD


class TestCollapse:
    def test_confusion_mirror_collapses_to_hold(self):
        r = _reso(Pain.CONFUSION)
        c = select_posture(r, _state(r), trust_level=3, consent_passed=True)
        assert c.raw_posture == Posture.MIRROR
        assert c.posture == Posture.HOLD
        assert c.collapsed

    def test_loneliness_witness_collapses_to_hold(self):
        r = _reso(Pain.LONELINESS)
        c = select_posture(r, _state(r), trust_level=3, consent_passed=True)
        assert c.raw_posture == Posture.WITNESS
        assert c.posture == Posture.HOLD
        assert c.collapsed


class TestDefault:
    def test_ordinary_chat_is_guide(self):
        r = _reso(Pain.NONE, Sensitivity.LOW)
        c = select_posture(r, _state(r), trust_level=3, consent_passed=True)
        assert c.posture == Posture.GUIDE
        assert not c.collapsed


class TestInvariant:
    def test_no_leaks_outside_v0_1_postures(self):
        random.seed(123)
        for _ in range(500):
            pain = random.choice(list(Pain))
            sens = random.choice(list(Sensitivity))
            trust = random.randint(0, 5)
            ctx = RelationshipContext(
                trust_level=trust, bond_level=random.randint(0, 5),
                recent_rebuffs=random.randint(0, 3),
                recent_mistakes=random.randint(0, 3),
                consecutive_avoidance=random.randint(0, 5),
                owner_in_crisis_mode=random.random() < 0.1,
            )
            r = ResonanceReading(deeper_pain=pain, sensitivity=sens)
            c = select_posture(r, derive_state(r, ctx), trust_level=trust, consent_passed=True)
            assert c.posture in V0_1_POSTURES, (c.posture, c.raw_posture, pain, sens, trust)
