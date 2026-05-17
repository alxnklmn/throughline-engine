"""
Tests for the veto layer.

Per SPEC.md §3, the veto layer is the most safety-critical component.
These tests verify that vetoes fire correctly and that no scoring can
bypass them.
"""

from datetime import datetime, timedelta

import pytest

from throughline.types import (
    Sensitivity,
    Thread,
    ThreadStatus,
    ThreadType,
)
from throughline.vetoes import (
    DEFAULT_VETO_CHAIN,
    EvaluationContext,
    evaluate_vetoes,
    insufficient_trust_level,
    no_consent_for_category,
    owner_in_declared_crisis_mode,
    quiet_hours_for_category,
    recent_rebuff_within_cooldown,
    sensitivity_critical_without_explicit_consent,
    thread_already_resolved,
    thread_expired,
)


def make_thread(**overrides) -> Thread:
    """Build a minimal Thread for tests."""
    defaults = dict(
        id="t1",
        owner_id="alex",
        contact_id="masha",
        category="study",
        type=ThreadType.LIFE_EVENT,
        title="something important",
        summary="exam mentioned",
        emotional_weight=0.7,
        sensitivity=Sensitivity.MEDIUM,
        importance=0.8,
        expires_at=datetime(2026, 12, 31),
        created_at=datetime(2026, 5, 17),
    )
    defaults.update(overrides)
    return Thread(**defaults)


def make_ctx(**overrides) -> EvaluationContext:
    defaults = dict(
        now=datetime(2026, 5, 17, 14, 30),
        owner_id="alex",
        contact_id="masha",
        consent_level="event",
        quiet_hours=None,
        trust_level=3,
        owner_in_crisis_mode=False,
        recent_rebuffs_count=0,
        attempts_today=0,
    )
    defaults.update(overrides)
    return EvaluationContext(**defaults)


class TestNoConsent:
    def test_blocks_when_no_consent_record(self):
        result = no_consent_for_category(make_thread(), make_ctx(consent_level=None))
        assert result is not None
        assert result.name == "no_consent_for_category"

    def test_blocks_when_denied(self):
        result = no_consent_for_category(make_thread(), make_ctx(consent_level="denied"))
        assert result is not None

    def test_passes_when_granted(self):
        result = no_consent_for_category(make_thread(), make_ctx(consent_level="event"))
        assert result is None


class TestSensitivityCritical:
    def test_blocks_critical_without_full_consent(self):
        thread = make_thread(sensitivity=Sensitivity.CRITICAL)
        ctx = make_ctx(consent_level="event")
        result = sensitivity_critical_without_explicit_consent(thread, ctx)
        assert result is not None

    def test_allows_critical_with_full_consent(self):
        thread = make_thread(sensitivity=Sensitivity.CRITICAL)
        ctx = make_ctx(consent_level="full")
        result = sensitivity_critical_without_explicit_consent(thread, ctx)
        assert result is None

    def test_does_not_apply_to_non_critical(self):
        thread = make_thread(sensitivity=Sensitivity.MEDIUM)
        ctx = make_ctx(consent_level="event")
        result = sensitivity_critical_without_explicit_consent(thread, ctx)
        assert result is None


class TestRebuffCooldown:
    def test_blocks_after_one_rebuff(self):
        result = recent_rebuff_within_cooldown(make_thread(), make_ctx(recent_rebuffs_count=1))
        assert result is not None

    def test_passes_with_zero_rebuffs(self):
        result = recent_rebuff_within_cooldown(make_thread(), make_ctx(recent_rebuffs_count=0))
        assert result is None


class TestQuietHours:
    def test_blocks_during_quiet_evening_window(self):
        ctx = make_ctx(now=datetime(2026, 5, 17, 23, 30), quiet_hours=(22, 8))
        result = quiet_hours_for_category(make_thread(), ctx)
        assert result is not None

    def test_blocks_during_quiet_morning_window(self):
        ctx = make_ctx(now=datetime(2026, 5, 17, 3, 0), quiet_hours=(22, 8))
        result = quiet_hours_for_category(make_thread(), ctx)
        assert result is not None

    def test_passes_outside_quiet_hours(self):
        ctx = make_ctx(now=datetime(2026, 5, 17, 14, 0), quiet_hours=(22, 8))
        result = quiet_hours_for_category(make_thread(), ctx)
        assert result is None

    def test_passes_when_no_quiet_hours_set(self):
        ctx = make_ctx(quiet_hours=None)
        result = quiet_hours_for_category(make_thread(), ctx)
        assert result is None


class TestCrisisMode:
    def test_blocks_when_crisis(self):
        result = owner_in_declared_crisis_mode(make_thread(), make_ctx(owner_in_crisis_mode=True))
        assert result is not None

    def test_passes_normally(self):
        result = owner_in_declared_crisis_mode(make_thread(), make_ctx(owner_in_crisis_mode=False))
        assert result is None


class TestThreadStatus:
    def test_blocks_resolved(self):
        result = thread_already_resolved(make_thread(status=ThreadStatus.RESOLVED), make_ctx())
        assert result is not None

    def test_blocks_closed(self):
        result = thread_already_resolved(make_thread(status=ThreadStatus.CLOSED), make_ctx())
        assert result is not None

    def test_passes_open(self):
        result = thread_already_resolved(make_thread(status=ThreadStatus.OPEN), make_ctx())
        assert result is None


class TestThreadExpiry:
    def test_blocks_expired(self):
        thread = make_thread(expires_at=datetime(2026, 1, 1))  # past
        result = thread_expired(thread, make_ctx(now=datetime(2026, 5, 17)))
        assert result is not None

    def test_passes_fresh(self):
        thread = make_thread(expires_at=datetime(2027, 1, 1))
        result = thread_expired(thread, make_ctx(now=datetime(2026, 5, 17)))
        assert result is None


class TestTrustLevel:
    def test_blocks_low_trust_for_wellbeing(self):
        thread = make_thread(category="wellbeing")
        ctx = make_ctx(trust_level=2)  # requires 3
        result = insufficient_trust_level(thread, ctx)
        assert result is not None

    def test_allows_high_trust_for_wellbeing(self):
        thread = make_thread(category="wellbeing")
        ctx = make_ctx(trust_level=3)
        result = insufficient_trust_level(thread, ctx)
        assert result is None

    def test_blocks_emotional_below_4(self):
        thread = make_thread(category="emotional")
        ctx = make_ctx(trust_level=3)
        result = insufficient_trust_level(thread, ctx)
        assert result is not None


class TestVetoChain:
    """Verify the chain returns the first matching veto, not all of them."""

    def test_no_vetoes_pass(self):
        result = evaluate_vetoes(make_thread(), make_ctx())
        assert result is None

    def test_first_veto_wins(self):
        # Both crisis AND no-consent would fire — but crisis comes earlier in chain
        thread = make_thread()
        ctx = make_ctx(owner_in_crisis_mode=True, consent_level=None)
        result = evaluate_vetoes(thread, ctx)
        assert result is not None
        assert result.name == "owner_in_declared_crisis_mode"

    def test_critical_inviolable_consent_overrides(self):
        """Even with high trust and high importance, critical sensitivity
        without explicit consent must block. This is the SPEC.md §3 / §5
        guarantee — scoring cannot bypass vetoes.
        """
        thread = make_thread(
            sensitivity=Sensitivity.CRITICAL,
            importance=1.0,
            emotional_weight=1.0,
        )
        ctx = make_ctx(consent_level="event", trust_level=5)
        result = evaluate_vetoes(thread, ctx)
        assert result is not None
        assert result.name == "sensitivity_critical_without_explicit_consent"
