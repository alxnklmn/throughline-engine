"""Tests for voice calibration (throughline/voice.py).

End-to-end uses a fake LLM client (no network). Defensive parse +
input-handling tests are deterministic.
"""

import asyncio
import json

from throughline.voice import calibrate_voice, _strip_multiword_quotes


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


class TestPrivacyStrip:
    """Defence-in-depth: multi-word quoted fragments must be stripped.
    Single-word vocabulary stays. v0.1.0a7 live discovery."""

    def test_single_word_quotes_preserved(self):
        s = "часто использует «просто», «ну», «вроде»"
        assert _strip_multiword_quotes(s) == s

    def test_multiword_russian_guillemet_stripped(self):
        # The exact pattern that leaked in production
        s = "иногда обрывает мысль («Убери скоро буду»)"
        out = _strip_multiword_quotes(s)
        assert "Убери" not in out
        assert "скоро буду" not in out

    def test_multiword_straight_quotes_stripped(self):
        s = 'often says \"see you later\" instead of bye'
        out = _strip_multiword_quotes(s)
        assert "see you later" not in out

    def test_multiword_typographic_english_stripped(self):
        s = "пишет “I will be back soon” перед отъездами"
        out = _strip_multiword_quotes(s)
        assert "I will be back soon" not in out

    def test_full_signature_with_mixed_quotes(self):
        # The exact leaky production signature
        s = (
            "очень короткие фразы, часто команды или инструкции. "
            "использует slash-команды («/start»). "
            "иногда обрывает мысль («Убери скоро буду»)."
        )
        out = _strip_multiword_quotes(s)
        # Single-word slash-command quote kept
        assert "/start" in out
        # Multi-word message quote stripped
        assert "Убери скоро буду" not in out

    def test_calibrate_returns_stripped_signature(self):
        # End-to-end: even if LLM produces leaky output, returned signature
        # has the multi-word quote replaced with […]
        leaky = (
            "короткие фразы. иногда говорит «убери скоро буду» когда уходит. "
            "часто использует «ок»."
        )
        client = FakeLLMClient(json.dumps({"voice_signature": leaky}))
        r = asyncio.run(calibrate_voice(["sample"], client=client, model="t"))
        assert "убери скоро буду" not in r
        # vocabulary marker preserved
        assert "«ок»" in r


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
