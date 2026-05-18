"""
Minimal Anima integration example.

Shows how a chat/messaging assistant wires Anima into its existing
message pipeline:

- observe every relevant message → engine.observe_message(...)
- when composing a reply → await engine.compose_response(...)
- periodically poll for proactive initiative → await engine.tick()
- always close the loop → engine.record_feedback(...)

This file is illustrative, not runnable as-is — replace ``your_llm_client``
and ``your_bot.send`` with your provider integration.
"""

import asyncio

from throughline import (
    Engine,
    FeedbackType,
    InitiationLevel,
)


# Pretend we have an OpenAI-compatible async client and a Telegram-style bot.
# Replace these with real ones (openai.AsyncOpenAI, aiogram.Bot, ...).
your_llm_client = ...
your_bot = ...
owner_telegram_id = 12345


async def main():
    # ─────────────────────────────────────────────────────────────────
    # 1. Initialize the engine — one per owner.
    # ─────────────────────────────────────────────────────────────────
    engine = Engine(
        storage_path="~/.anima/alex.db",
        key_source="env:ANIMA_DB_KEY",      # 32+ bytes in env var
        owner_id="alex",
        llm_client=your_llm_client,
        model="gpt-4o-mini",                # or your provider's model id
        default_language_hint="ru",
    )

    # ─────────────────────────────────────────────────────────────────
    # 2. Owner sets consent for what categories Anima may initiate on.
    #    Without explicit consent, every proactive veto fires and tick
    #    stays silent. Reactive responses (compose_response) work without
    #    consent — the user is sending TO the agent.
    # ─────────────────────────────────────────────────────────────────
    engine.set_consent(category="study", level="event", quiet_hours=(23, 9))
    engine.set_consent(category="wellbeing", level="wellbeing", quiet_hours=(23, 9))

    # ─────────────────────────────────────────────────────────────────
    # 3. Reactive cycle: owner says something heavy, host wants Anima's reply.
    # ─────────────────────────────────────────────────────────────────
    incoming = "завтра экзамен, паника"

    response = await engine.compose_response(
        contact_id="alex",                  # self-care channel
        incoming_text=incoming,
        history_for_resonance="we talked about exam prep two days ago",
        generalized_facts=["something important tomorrow"],
        language_hint="ru",
    )

    # response is a Composition with:
    # - .text            (the message to deliver; empty = do not deliver)
    # - .posture         (HOLD/GUIDE/SILENCE in v0.1)
    # - .archetype       (COMPANION/FRIEND/TEACHER in v0.1)
    # - .resonance       (full resonance reading for transparency)
    # - .decision_reason (audit string)
    # - .fallback_invoked (True if moral audit triggered safe_fallback)

    if response.text:
        await your_bot.send(chat_id=owner_telegram_id, text=response.text)
        print(f"sent: posture={response.posture.value} archetype={response.archetype.value}")
    else:
        # SILENCE — host may surface external resources if sensitivity is
        # critical (resonance reading tells you).
        if response.resonance.sensitivity.value == "critical":
            await your_bot.send(
                chat_id=owner_telegram_id,
                text="если сейчас плохо — позвони 8-800-2000-122 (бесплатно, 24/7).",
            )

    # ─────────────────────────────────────────────────────────────────
    # 4. Proactive cycle: periodic check for follow-ups worth reaching
    #    back about. Typical cadence: every 10–15 minutes.
    # ─────────────────────────────────────────────────────────────────
    while True:
        decisions = await engine.tick()
        for d in decisions:
            if d.level == InitiationLevel.DIRECT_MESSAGE and d.composed_message:
                sent = await your_bot.send(
                    chat_id=owner_telegram_id,
                    text=d.composed_message,
                )
                # Wait for owner's reply, then close the loop.
                reply = await your_bot.wait_for_reply(sent.id, timeout=300)

                if reply is None:
                    engine.record_feedback(
                        decision_id=d.id,
                        feedback_type=FeedbackType.IGNORED,
                    )
                elif "не пиши" in reply.text.lower() or "stop" in reply.text.lower():
                    engine.record_feedback(
                        decision_id=d.id,
                        feedback_type=FeedbackType.REBUFFED,
                        raw_signal=reply.text,
                    )
                    # ← REBUFFED auto-records an agent_mistake;
                    #   future synthetic state tilts cautious.
                else:
                    engine.record_feedback(
                        decision_id=d.id,
                        feedback_type=FeedbackType.ENGAGED,
                        raw_signal=reply.text,
                    )
            elif d.level == InitiationLevel.SILENCE:
                pass  # default — Anima preferred silence; nothing to do
            # other levels (PASSIVE_PROMPT, SOFT_INJECT, STATUS_NUDGE) are
            # defined for v0.2 and may be surfaced in a Mini App dashboard

        await asyncio.sleep(600)  # 10 minutes


if __name__ == "__main__":
    asyncio.run(main())
