"""Tests for voice calibration (throughline/voice.py).

End-to-end uses a fake LLM client (no network). Defensive parse +
input-handling tests are deterministic.
"""

import asyncio
import json

from throughline.voice import calibrate_voice


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


class TestEmptyInput:
    def test_empty_list_returns_empty(self):
        client = FakeLLMClient("should not be called")
        r = asyncio.run(calibrate_voice([], client=client, model="t"))
        assert r == ""

    def test_blank_strings_filtered(self):
        client = FakeLLMClient("should not be called")
        r = asyncio.run(calibrate_voice(["   ", "\n", ""], client=client, model="t"))
        assert r == ""


class TestSuccessfulCalibration:
    def test_signature_returned(self):
        signature = (
            "короткие фразы, 4-7 слов. lowercase почти всегда.\n"
            "тире вместо запятых. не дописывает мысли — переходит дальше."
        )
        client = FakeLLMClient(json.dumps({
            "voice_signature": signature,
            "samples_observed": 5,
        }))
        r = asyncio.run(calibrate_voice(
            ["короче", "ну блин", "ок", "нормально", "пойдёт"],
            client=client, model="t",
        ))
        assert r == signature

    def test_signature_capped_at_800(self):
        long_sig = "x" * 2000
        client = FakeLLMClient(json.dumps({"voice_signature": long_sig}))
        r = asyncio.run(calibrate_voice(
            ["sample message"], client=client, model="t",
        ))
        assert len(r) <= 800


class TestFailureModes:
    def test_non_json_returns_empty(self):
        client = FakeLLMClient("just plain text not json")
        r = asyncio.run(calibrate_voice(
            ["sample"], client=client, model="t",
        ))
        assert r == ""

    def test_missing_field_returns_empty(self):
        client = FakeLLMClient(json.dumps({"samples_observed": 3}))
        r = asyncio.run(calibrate_voice(
            ["sample"], client=client, model="t",
        ))
        assert r == ""

    def test_non_string_field_returns_empty(self):
        client = FakeLLMClient(json.dumps({"voice_signature": ["a", "b"]}))
        r = asyncio.run(calibrate_voice(
            ["sample"], client=client, model="t",
        ))
        assert r == ""

    def test_llm_crash_returns_empty(self):
        class CrashClient:
            class chat:
                class completions:
                    @staticmethod
                    async def create(**kw): raise RuntimeError("api down")
        r = asyncio.run(calibrate_voice(
            ["sample"], client=CrashClient(), model="t",
        ))
        assert r == ""


class TestInputCap:
    def test_large_sample_capped(self):
        # Each sample is capped to 600 chars; we just verify the call completes
        # gracefully on oversized input.
        client = FakeLLMClient(json.dumps({"voice_signature": "ok"}))
        big_sample = "x" * 5000
        r = asyncio.run(calibrate_voice(
            [big_sample] * 50, client=client, model="t",
        ))
        assert r == "ok"
