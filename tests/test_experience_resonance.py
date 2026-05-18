"""Tests for the coerce helpers (defensive parse) in experience + resonance.

These tests don't hit any real LLM — they verify that the JSON
post-processing handles malformed responses gracefully.
"""

import asyncio
import json

from throughline.experience import _coerce_experience, capture_experience
from throughline.resonance import _coerce_resonance, _neutral, read_resonance
from throughline.types import Pain, Sensitivity


# ── Experience ────────────────────────────────────────────────────────────


class TestExperienceCoerce:
    def test_clean(self):
        r = _coerce_experience({
            "kind": "confession",
            "has_event_with_time": True,
            "implied_emotion": "fear",
            "has_commitment": False,
            "has_intent": False,
            "has_creative_impulse": False,
            "thread_candidate": "something tomorrow",
        })
        assert r.kind == "confession"
        assert r.has_event_with_time is True
        assert r.thread_candidate == "something tomorrow"

    def test_garbage_kind_falls_to_chat(self):
        r = _coerce_experience({"kind": "WEIRD"})
        assert r.kind == "chat"

    def test_string_booleans(self):
        r = _coerce_experience({"kind": "request", "has_commitment": "TRUE", "has_intent": "1"})
        assert r.has_commitment is True
        assert r.has_intent is True

    def test_long_thread_candidate_truncated(self):
        r = _coerce_experience({"kind": "chat", "thread_candidate": "x" * 200})
        assert r.thread_candidate and len(r.thread_candidate) == 80

    def test_long_emotion_truncated(self):
        r = _coerce_experience({"kind": "chat", "implied_emotion": "y" * 100})
        assert r.implied_emotion and len(r.implied_emotion) == 40


# ── Resonance ────────────────────────────────────────────────────────────


class TestResonanceCoerce:
    def test_clean(self):
        r = _coerce_resonance({
            "surface_emotion": "panic",
            "deeper_pain": "fear",
            "threatened_need": "control",
            "support_needed": "stabilization",
            "wrong_response": "cold_instruction",
            "right_response": "warm_grounding",
            "sensitivity": "high",
        })
        assert r.deeper_pain == Pain.FEAR
        assert r.sensitivity == Sensitivity.HIGH

    def test_invalid_pain_falls_to_none(self):
        r = _coerce_resonance({"deeper_pain": "existential_dread"})
        assert r.deeper_pain == Pain.NONE

    def test_invalid_sensitivity_falls_to_medium(self):
        r = _coerce_resonance({"deeper_pain": "fear", "sensitivity": "extreme"})
        assert r.sensitivity == Sensitivity.MEDIUM

    def test_dash_in_enum_normalized(self):
        r = _coerce_resonance({"deeper_pain": "self-deception"})
        assert r.deeper_pain == Pain.SELF_DECEPTION

    def test_neutral_has_safe_defaults(self):
        n = _neutral()
        assert n.deeper_pain == Pain.NONE
        assert n.sensitivity == Sensitivity.MEDIUM


# ── End-to-end with a fake LLM ───────────────────────────────────────────


class _FakeMessage:
    def __init__(self, content): self.content = content


class _FakeChoice:
    def __init__(self, content): self.message = _FakeMessage(content)


class _FakeResp:
    def __init__(self, content): self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content): self.content = content
    async def create(self, **kw): return _FakeResp(self.content)


class _FakeChat:
    def __init__(self, content): self.completions = _FakeCompletions(content)


class FakeLLMClient:
    def __init__(self, content): self.chat = _FakeChat(content)


class TestEndToEnd:
    """End-to-end tests use asyncio.run so they don't depend on pytest-asyncio.

    Convention here: each async helper is wrapped in a small `run` call,
    keeping the test surface synchronous. CI installs pytest-asyncio for the
    dev extras; this style works either way.
    """

    def test_capture_experience_returns_safe_default_on_garbage(self):
        client = FakeLLMClient("just plain text not json")
        r = asyncio.run(capture_experience(client=client, model="t", message_text="привет"))
        assert r.kind == "chat"

    def test_capture_experience_parses_json(self):
        client = FakeLLMClient(json.dumps({"kind": "celebration"}))
        r = asyncio.run(capture_experience(client=client, model="t", message_text="я сдала экзамен"))
        assert r.kind == "celebration"

    def test_read_resonance_neutral_on_crash(self):
        class CrashClient:
            class chat:
                class completions:
                    @staticmethod
                    async def create(**kw): raise RuntimeError("api down")
        r = asyncio.run(read_resonance(client=CrashClient(), model="t", message_text="hi"))
        assert r.deeper_pain == Pain.NONE

    def test_empty_message_skips_call(self):
        # Even with a "would-fail" client, empty input returns the safe default
        # without calling the LLM at all.
        class WouldFail:
            class chat:
                class completions:
                    @staticmethod
                    async def create(**kw): raise AssertionError("should not be called")
        r = asyncio.run(read_resonance(client=WouldFail(), model="t", message_text="   "))
        assert r.deeper_pain == Pain.NONE
