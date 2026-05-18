"""Tests for the synthetic state derivation (SPEC.md §9)."""

from throughline.synthetic import (
    RelationshipContext,
    TRUST_REQUIRED_FOR_CHALLENGE,
    THRESH_RESTRAINT_PREFER_SILENCE,
    THRESH_TENDERNESS_SOFT_PHRASING,
    derive_state,
    defaults_to_hold,
    prefers_silence,
    soft_phrasing_modifier,
    allowed_to_remind_of_capacity,
)
from throughline.types import Pain, ResonanceReading, Sensitivity


def _resonance(pain: Pain = Pain.NONE, sensitivity: Sensitivity = Sensitivity.MEDIUM) -> ResonanceReading:
    return ResonanceReading(deeper_pain=pain, sensitivity=sensitivity)


class TestPanicShape:
    def test_panic_high_sens_raises_concern_and_tenderness(self):
        s = derive_state(_resonance(Pain.PANIC, Sensitivity.HIGH),
                         RelationshipContext(trust_level=3, bond_level=2))
        assert s.concern >= 0.7
        assert s.tenderness >= 0.7
        assert s.challenge_impulse == 0.0
        assert soft_phrasing_modifier(s)

    def test_panic_critical_zeros_challenge(self):
        s = derive_state(_resonance(Pain.PANIC, Sensitivity.CRITICAL),
                         RelationshipContext(trust_level=5, bond_level=4))
        assert s.challenge_impulse == 0.0
        assert s.protectiveness >= 0.4


class TestShape:
    def test_shame_adds_tenderness_and_restraint(self):
        s = derive_state(_resonance(Pain.SHAME, Sensitivity.MEDIUM),
                         RelationshipContext(trust_level=3))
        assert s.tenderness >= 0.6
        assert s.restraint >= 0.4

    def test_burnout_quiet_exhaustion_pushes_restraint(self):
        for p in (Pain.BURNOUT, Pain.QUIET_EXHAUSTION):
            s = derive_state(_resonance(p),
                             RelationshipContext(trust_level=3))
            assert s.patience >= 0.7

    def test_anger_raises_patience(self):
        s = derive_state(_resonance(Pain.ANGER),
                         RelationshipContext(trust_level=3))
        assert s.patience >= 0.7


class TestCrisisMode:
    def test_crisis_mode_forces_silence_and_zero_challenge(self):
        s = derive_state(_resonance(Pain.FEAR),
                         RelationshipContext(trust_level=5, owner_in_crisis_mode=True))
        assert s.protectiveness >= 0.9
        assert s.restraint >= 0.8
        assert s.challenge_impulse == 0.0
        assert prefers_silence(s)


class TestRebuffs:
    def test_two_rebuffs_increase_restraint(self):
        baseline = derive_state(_resonance(),
                                 RelationshipContext(trust_level=3, recent_rebuffs=0))
        rebuffed = derive_state(_resonance(),
                                 RelationshipContext(trust_level=3, recent_rebuffs=2))
        assert rebuffed.restraint > baseline.restraint

    def test_rebuffs_lower_challenge_impulse(self):
        # start with self_deception + trust 5 to potentially raise challenge
        baseline = derive_state(_resonance(Pain.SELF_DECEPTION),
                                 RelationshipContext(trust_level=5,
                                                     consecutive_avoidance=4))
        rebuffed = derive_state(_resonance(Pain.SELF_DECEPTION),
                                 RelationshipContext(trust_level=5,
                                                     consecutive_avoidance=4,
                                                     recent_rebuffs=2))
        assert rebuffed.challenge_impulse < baseline.challenge_impulse


class TestTrust:
    def test_low_trust_zeros_challenge(self):
        s = derive_state(_resonance(Pain.SELF_DECEPTION),
                         RelationshipContext(trust_level=1, consecutive_avoidance=5))
        assert s.challenge_impulse == 0.0

    def test_high_trust_keeps_challenge_higher(self):
        low = derive_state(_resonance(Pain.SELF_DECEPTION),
                           RelationshipContext(trust_level=3, consecutive_avoidance=4))
        high = derive_state(_resonance(Pain.SELF_DECEPTION),
                            RelationshipContext(trust_level=5, consecutive_avoidance=4))
        assert high.challenge_impulse >= low.challenge_impulse


class TestPredicates:
    def test_prefers_silence_threshold(self):
        # crafted state at boundary
        from throughline.types import SyntheticState
        assert not prefers_silence(SyntheticState(restraint=THRESH_RESTRAINT_PREFER_SILENCE))
        assert prefers_silence(SyntheticState(restraint=THRESH_RESTRAINT_PREFER_SILENCE + 0.01))

    def test_soft_phrasing_threshold(self):
        from throughline.types import SyntheticState
        assert not soft_phrasing_modifier(SyntheticState(tenderness=THRESH_TENDERNESS_SOFT_PHRASING))
        assert soft_phrasing_modifier(SyntheticState(tenderness=THRESH_TENDERNESS_SOFT_PHRASING + 0.01))


class TestClamping:
    def test_all_fields_stay_in_bounds(self):
        # extreme inputs designed to push everything to the limits
        for trust in (0, 5):
            for rebuffs in (0, 5):
                s = derive_state(
                    _resonance(Pain.PANIC, Sensitivity.CRITICAL),
                    RelationshipContext(
                        trust_level=trust, bond_level=5,
                        recent_rebuffs=rebuffs, recent_mistakes=5,
                        consecutive_avoidance=10,
                        owner_in_crisis_mode=True,
                    ),
                )
                for field in ("concern", "tenderness", "protectiveness", "honesty",
                              "patience", "restraint", "faith", "challenge_impulse"):
                    val = getattr(s, field)
                    assert 0.0 <= val <= 1.0, f"{field}={val}"
