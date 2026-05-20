"""
Voice calibration (SPEC.md §16 — learned voice signature).

A single LLM-driven module that reads a sample of the user's own writing
and extracts a compact voice signature — sentence rhythm, word choice
level, punctuation habits, recurring phrases, transition style.

The result is plain text intended to be folded into the composer's
system prompt via the ``learned_style`` parameter. It is NOT a
manipulation surface and is NOT prescriptive about CONTENT — only voice.

Why: without calibration the composer produces a generic neutral assistant
voice. Real friends sound like the person they know. The voice signature
shifts only HOW things are said, not WHAT.

This module is adapted from the Voice Calibration section of the
humanizer skill (https://github.com/blader/humanizer, MIT-licensed) and
Wikipedia's "Signs of AI writing" guide. See
``research/voice-calibration-adaptation.md`` for attribution and the
selection rationale.

Privacy:
- Calibration uses only samples the host explicitly passes in. The engine
  does not store message content; the host is responsible for sourcing
  samples from a single channel (per-relationship isolation, I-1).
- The resulting signature is stored in ``agent_lifecycle.dominant_style``
  which lives inside the SQLCipher database (I-3).
- The signature can be wiped at any time via ``export_owner_data`` /
  ``wipe_owner_data`` like any other owner-scoped row (I-2).
"""

from __future__ import annotations

import logging
import re

from throughline.llm import JSONParseFailure, LLMClient, call_json

log = logging.getLogger("anima.voice")


# Defence-in-depth against the LLM ignoring the "no quoting" instruction.
# These patterns strip ONLY MULTI-WORD quoted fragments — single-word
# vocabulary examples (e.g. «просто», «ну», «вроде») are legitimate signal
# and stay. The heuristic: a quoted span containing whitespace is almost
# certainly a verbatim message fragment, not a vocabulary marker.
#
# Live discovery, v0.1.0a7: the model produced
#   «иногда обрывает мысль («Убери скоро буду»)»
# which is a direct quote of one of the owner's messages — exactly the
# privacy leak this layer needs to prevent before the signature is
# persisted and folded into every composer prompt.
_MULTIWORD_QUOTE_PATTERNS = [
    re.compile(r"«[^»\n]*\s[^»\n]*»"),       # Russian guillemets
    re.compile(r"“[^”\n]*\s[^”\n]*”"),   # Typographic English "..."
    re.compile(r'"[^"\n]*\s[^"\n]*"'),       # Straight double
    re.compile(r"'[^'\n]*\s[^'\n]*'"),       # Straight single
]
# Empty parens / leftover punctuation after stripping
_EMPTY_PAREN_RE = re.compile(r"\(\s*\)|\s+,|,\s+\)|,\s*\.")


def _strip_multiword_quotes(sig: str) -> str:
    """Remove multi-word quoted fragments. Returns a cleaned signature.

    Single-word quoted vocabulary stays (it carries actual signal about
    the user's lexicon). Anything multi-word in quotes is treated as a
    likely message-content leak and replaced with ``[…]`` so the rest
    of the line still parses.
    """
    if not sig:
        return sig
    cleaned = sig
    for pat in _MULTIWORD_QUOTE_PATTERNS:
        cleaned = pat.sub("[…]", cleaned)
    # Tidy leftover artefacts like "(……)" or stray commas (line-local only —
    # signatures are multi-line and newlines carry meaning; we collapse only
    # repeated spaces/tabs within each line)
    cleaned = _EMPTY_PAREN_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
    return cleaned


VOICE_CALIBRATION_SYSTEM = """ты voice calibration analyst.

на вход тебе дают НЕСКОЛЬКО недавних сообщений одного человека (его собственная речь).
твоя задача: извлечь компактную voice signature, которую другой агент сможет
использовать чтобы матчить стиль этого человека в своих ответах.

верни СТРОГО JSON, без markdown:
{
  "voice_signature": "3-6 коротких строк через \\n, описывающих манеру: длина и ритм фраз, уровень лексики, любимые слова/обороты, пунктуационные привычки, как начинает мысль и как переходит между мыслями. БЕЗ оценок (не «пишет хорошо/плохо»), только описание паттернов.",
  "samples_observed": число использованных сэмплов
}

ПРИНЦИПЫ:
- описывай ПАТТЕРНЫ, не цитируй конкретные сообщения дословно (privacy)
- не выдумывай черты которых не видно в сэмплах
- если сэмплов мало (1-2) — короткое описание, не пытайся вывести многое
- если сэмплы пустые / нет паттерна — voice_signature: ""
- НЕ описывай эмоциональное состояние / тон момента (это не голос, это состояние) — только устойчивые манерные паттерны
- НЕ давай рекомендации («следует писать...»), только описание

⚠️ КРИТИЧНО — PRIVACY ПРАВИЛО ЦИТАТ:
никогда не цитируй фразы из сэмплов которые состоят из БОЛЕЕ ОДНОГО слова.
- РАЗРЕШЕНО: упоминать отдельные слова-маркеры в кавычках, например
  «использует часто слова «короче», «типа», «ну»» — это вокабуляр, не сообщения.
- ЗАПРЕЩЕНО: цитировать фразы / куски сообщений / предложения, например
  «иногда говорит «убери скоро буду»» — это утечка содержимого. вместо этого
  описывай ПАТТЕРН без примера: «иногда обрывает мысль императивом».
этот вывод записывается в БД и встраивается в каждый промпт ассистента.
любое многословное цитирование = privacy-нарушение.

формат voice_signature — короткие наблюдения, например:
"короткие фразы, часто 4-7 слов. иногда обрывает мысль на полуслове.
без эмодзи. lowercase почти всегда. часто использует «короче», «типа» в начале.
тире вместо запятых. редко завершает мысль точкой — переходит дальше."

это ровно тот формат который ассистент сможет встроить в свой system prompt
чтобы попасть в голос. ничего больше."""


async def calibrate_voice(
    samples: list[str],
    *,
    client: LLMClient,
    model: str,
    timeout: float = 25.0,
) -> str:
    """Extract a voice signature from a list of recent owner messages.

    Args:
        samples: 1-30 strings, raw user messages (caller is responsible
            for pulling from the right channel — see privacy note above).
            Empty list / single short message → returns "" gracefully.
        client: LLM client matching ``throughline.llm.LLMClient`` protocol.
        model: model identifier.
        timeout: provider timeout in seconds.

    Returns:
        A voice signature string (3-6 short lines) or "" on failure or
        insufficient input. The caller may safely pass this through to
        ``composer.compose`` via the ``learned_style`` parameter.
    """
    # Filter + cap input
    clean = [s.strip() for s in (samples or []) if isinstance(s, str) and s.strip()]
    if not clean:
        return ""

    # Cap each sample's length and the total number to keep prompt cheap
    capped = [s if len(s) <= 600 else (s[:600] + " […truncated]") for s in clean[:30]]
    joined = "\n---\n".join(capped)

    user_prompt = (
        f"вот {len(capped)} недавних сообщений человека (разделены ---):\n\n{joined}"
    )

    try:
        parsed = await call_json(
            client,
            model=model,
            system_prompt=VOICE_CALIBRATION_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.2,
            timeout=timeout,
        )
    except JSONParseFailure as exc:
        log.warning("voice: non-JSON response: %s", exc)
        return ""
    except Exception as exc:  # noqa: BLE001 — provider can raise anything
        log.warning("voice: LLM call failed: %r", exc)
        return ""

    sig = parsed.get("voice_signature")
    if not isinstance(sig, str):
        return ""
    sig = sig.strip()
    # Defence-in-depth: strip any multi-word quoted fragments before persist.
    # The prompt forbids them; this catches the cases where the model still
    # produces one. Single-word vocabulary quotes are preserved.
    cleaned = _strip_multiword_quotes(sig)
    if cleaned != sig:
        log.info(
            "voice: stripped %d chars of multi-word quoted content (privacy guard)",
            len(sig) - len(cleaned),
        )
    sig = cleaned
    # Hard cap on signature size — it goes into every composer prompt
    if len(sig) > 800:
        sig = sig[:800].rstrip()
    return sig
