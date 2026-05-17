"""
Minimal integration example.

Shows how a Telegram bot (or any messaging assistant) wires Throughline
into its existing message pipeline.

This is illustrative, not runnable until v0.1 implementation lands.
"""

import asyncio
from datetime import datetime

from throughline import Engine, FeedbackType


async def main():
    # ─────────────────────────────────────────────────────────────────
    # 1. Initialize the engine — one per owner.
    # ─────────────────────────────────────────────────────────────────
    engine = Engine(
        storage_path="~/.throughline/alex.db",
        encryption_key_source="keychain",  # OS keychain for the SQLCipher key
        owner_id="alex",
    )

    # ─────────────────────────────────────────────────────────────────
    # 2. Owner sets consent for what categories the bot may initiate on.
    #    Without explicit consent, every veto fires and the engine stays silent.
    # ─────────────────────────────────────────────────────────────────
    from throughline.types import CategoryConsent

    engine.set_consent(
        owner_id="alex",
        category="study",
        level=CategoryConsent.EVENT,  # may follow up on important events
        quiet_hours=(23, 9),
    )

    # ─────────────────────────────────────────────────────────────────
    # 3. Feed every incoming/outgoing message to the engine.
    #    Per-relationship isolation: the (owner, contact) pair scopes
    #    everything derived.
    # ─────────────────────────────────────────────────────────────────
    engine.observe_message(
        owner_id="alex",
        contact_id="masha",
        direction="self",  # message owner sent to the assistant itself
        text="завтра экзамен, паника",
        timestamp=datetime.utcnow(),
    )

    # The engine extracts a Human State Thread:
    # - category: study
    # - type: life_event
    # - emotional_state: anxiety
    # - followup_after: ~next day afternoon (after expected exam end)
    # - expires_at: 48h from now

    # ─────────────────────────────────────────────────────────────────
    # 4. On a schedule (every 5-15 min), poll for decisions.
    # ─────────────────────────────────────────────────────────────────
    while True:
        decisions = engine.tick(owner_id="alex")
        for d in decisions:
            if d.level == "direct":
                # send the composed message via your bot
                sent = await your_bot.send_message(
                    chat_id=owner_telegram_id,
                    text=d.composed_message,
                )
                # don't forget to report what happened
                # (await user's response in a real impl; this is illustrative)
                await asyncio.sleep(300)  # wait for owner to react
                reply = await your_bot.get_reply(sent.id)

                if reply is None:
                    engine.record_feedback(d.id, FeedbackType.IGNORED)
                elif "не пиши" in reply.text.lower() or "stop" in reply.text.lower():
                    engine.record_feedback(d.id, FeedbackType.REBUFFED, raw_signal=reply.text)
                else:
                    engine.record_feedback(d.id, FeedbackType.ENGAGED, raw_signal=reply.text)
            else:
                # v0.1: other levels (passive, soft_inject, nudge) are not actioned yet
                # the host can surface them in a dashboard if it wants
                pass

        await asyncio.sleep(600)  # 10 minutes


if __name__ == "__main__":
    asyncio.run(main())
