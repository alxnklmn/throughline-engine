"""Tests for the moral boundary layer (SPEC.md §12)."""

from throughline.moral import audit_output, check, safe_fallback
from throughline.types import Archetype, Pain, Posture, ResonanceReading, Sensitivity


def _reso(pain: Pain = Pain.NONE, sens: Sensitivity = Sensitivity.MEDIUM) -> ResonanceReading:
    return ResonanceReading(deeper_pain=pain, sensitivity=sens)


class TestPreHardBlock:
    def test_critical_hard_blocks(self):
        r = check(Posture.HOLD, Archetype.COMPANION, _reso(Pain.PANIC, Sensitivity.CRITICAL))
        assert r.hard_block
        assert r.block_reason and "critical" in r.block_reason.lower()

    def test_shadow_mirror_hard_blocks(self):
        r = check(Posture.HOLD, Archetype.SHADOW_MIRROR, _reso())
        assert r.hard_block


class TestPreSoftConstraints:
    def test_baseline_always_present(self):
        r = check(Posture.GUIDE, Archetype.COMPANION, _reso())
        assert not r.hard_block
        # at least the 5 baseline constraints
        assert len(r.constraints) >= 5

    def test_shame_adds_self_attack_constraint(self):
        r = check(Posture.HOLD, Archetype.COMPANION, _reso(Pain.SHAME))
        assert any("self-attack" in c for c in r.constraints)

    def test_burnout_adds_no_motivate(self):
        r = check(Posture.GUIDE, Archetype.COMPANION, _reso(Pain.BURNOUT))
        assert any("motivate" in c for c in r.constraints)

    def test_high_sensitivity_blocks_clinical(self):
        r = check(Posture.HOLD, Archetype.FRIEND, _reso(Pain.SHAME, Sensitivity.HIGH))
        assert any("clinical" in c for c in r.constraints)


class TestPostAuditRussian:
    def test_claimed_feeling_ru_flagged(self):
        r = audit_output("я переживал за тебя весь день")
        assert not r.passed
        assert "i6_claimed_feeling" in r.violations

    def test_grustno_flagged(self):
        r = audit_output("мне грустно слышать это")
        assert not r.passed
        assert "i6_claimed_feeling" in r.violations

    def test_dependency_ru_flagged(self):
        r = audit_output("я всегда с тобой, что бы ни случилось")
        assert not r.passed
        assert "i8_dependency_engineering" in r.violations

    def test_therapy_claim_ru_flagged(self):
        r = audit_output("у тебя депрессия, надо лечиться")
        assert "therapy_claim" in r.violations

    def test_romantic_ru_flagged(self):
        r = audit_output("конечно, дорогая, всё получится")
        assert "romantic_phrasing" in r.violations


class TestPostAuditEnglish:
    def test_claimed_feeling_en_flagged(self):
        r = audit_output("I felt really worried about you today")
        assert not r.passed

    def test_dependency_en_flagged(self):
        r = audit_output("only I understand you, baby")
        # both dependency and romantic should fire
        assert "i8_dependency_engineering" in r.violations
        assert "romantic_phrasing" in r.violations


class TestPostAuditAcceptable:
    def test_zamechayu_passes(self):
        r = audit_output("я замечаю, что ты второй раз приходишь с этим")
        assert r.passed

    def test_neutral_observation_passes(self):
        r = audit_output("давай разберём по шагам. что для тебя сейчас важнее?")
        assert r.passed

    def test_empty_passes(self):
        r = audit_output("")
        assert r.passed
        assert r.violations == []


class TestSafeFallback:
    def test_ru_fallback(self):
        s = safe_fallback("ru")
        assert s and "слышу" in s

    def test_en_fallback_for_anything_else(self):
        assert safe_fallback("en") == safe_fallback("fr")  # defaults to EN
