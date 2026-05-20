"""Tests that the composer's anti-AI-tells baseline style rules are
present in the assembled system prompt."""

from throughline.composer import build_system_prompt
from throughline.types import Archetype, Pain, Posture, ResonanceReading, Sensitivity


def _sys(**overrides):
    defaults = dict(
        posture=Posture.GUIDE,
        archetype=Archetype.COMPANION,
        resonance=ResonanceReading(deeper_pain=Pain.NONE, sensitivity=Sensitivity.MEDIUM),
        constraints=[],
        language_hint="ru",
        learned_style=None,
    )
    defaults.update(overrides)
    return build_system_prompt(**defaults)


class TestBaselineStyle:
    def test_signposting_ban_present(self):
        s = _sys()
        assert "let's break this down" in s.lower() or "давай разберём" in s

    def test_sycophancy_ban_present(self):
        s = _sys()
        assert "great question" in s.lower() or "отличный вопрос" in s

    def test_rule_of_three_ban_present(self):
        s = _sys()
        assert "lists of three" in s.lower()

    def test_em_dash_ban_present(self):
        s = _sys()
        assert "em dash" in s.lower()

    def test_inflated_significance_ban_present(self):
        s = _sys()
        assert "testament" in s.lower()
        assert "pivotal" in s.lower()

    def test_copula_avoidance_ban_present(self):
        s = _sys()
        assert "'serves as'" in s.lower() or "stands as" in s.lower()

    def test_generic_positive_closers_ban_present(self):
        s = _sys()
        assert "exciting times" in s.lower() or "получится" in s

    def test_baseline_applied_even_without_moral_constraints(self):
        # constraints=[] (no moral constraints) — baseline must still be there
        s = _sys(constraints=[])
        assert "sound human, not generated" in s

    def test_baseline_separate_from_moral_constraints(self):
        # When moral constraints are present, both blocks should appear,
        # and the moral block should still be marked HARD.
        s = _sys(constraints=["do NOT claim feelings"])
        assert "sound human, not generated" in s
        assert "HARD" in s
