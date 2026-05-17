<div align="center">

# Throughline

**An engine of human continuity for AI assistants.**

Built so AI can be present in someone's life without becoming surveillance.

[Русская версия →](./README.ru.md)  ·  [Full specification →](./SPEC.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](#project-status)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

</div>

---

## The shift

Most AI assistants are **reactive**. You ask, they answer, the conversation dies. But people are not streams of isolated requests. They say things like *"my exam is tomorrow, I'm stressed"* and then they go offline — not because the topic is closed, but because life moved on.

A reactive assistant does nothing. A scheduled assistant pings them. A **Throughline-equipped** assistant asks the right question:

> Is there a thread of human concern here that deserves to be carried forward — gently, appropriately, with permission?

If yes, it returns to it. If no, **it stays silent.**

This silence is not a bug. It is a feature with a metric attached to it (Silence Correctness). Throughline is the layer that lets your assistant be *present* in someone's life without becoming surveillance, a CRM, or another notification factory.

---

## What it does

- **Extracts** Human State Threads from conversation — anxieties, commitments, life events, intents, creative impulses
- **Scores** opportunities for follow-up against a strict **veto-first** model — consent is binary, never traded against importance
- **Composes** care messages that feel like a friend with reasonable memory, not a database with perfect recall (via deliberate generalization)
- **Calibrates** through feedback — learns when initiation was welcome and when it wasn't, per user, per category
- **Stays silent** correctly — and measures this as a primary success metric, not a side effect

## What it refuses to do

- Optimize for engagement, retention, session length, or any other attention-economy metric
- Cross-pollinate context between relationships — what Masha tells the bot stays in the Masha channel, never leaking to anyone else (see [Inviolable Invariants](#the-three-inviolable-invariants))
- Claim human feelings — no *"I was worried about you"*, no *"I missed you"*. It demonstrates attentiveness through behavior, never asserts emotion
- Store anything in plaintext — care data is the most sensitive data in the system
- Send messages in high-sensitivity categories without explicit consent
- Phone home — zero analytics, zero telemetry, zero "improvement based on usage"

---

## Quick start

```bash
pip install throughline
```

```python
from throughline import Engine, FeedbackType
from throughline.types import CategoryConsent
from datetime import datetime

# One engine per owner. Per-relationship isolation is enforced at the storage layer.
engine = Engine(
    storage_path="~/.throughline/alex.db",
    encryption_key_source="keychain",   # SQLCipher key lives in OS keychain
    owner_id="alex",
)

# Owner explicitly grants what categories may trigger follow-ups.
# Without consent, every veto fires — the engine stays silent.
engine.set_consent(
    owner_id="alex",
    category="study",
    level=CategoryConsent.EVENT,
    quiet_hours=(23, 9),
)

# Feed every message in your bot's pipeline to the engine.
engine.observe_message(
    owner_id="alex",
    contact_id="masha",
    direction="self",                   # owner → assistant
    text="завтра экзамен, паника",
    timestamp=datetime.utcnow(),
)

# Periodically poll for initiative decisions (every 5–15 minutes is typical).
for decision in engine.tick(owner_id="alex"):
    if decision.level == "direct":
        await your_bot.send(decision.composed_message)
    # Other levels (passive_prompt, soft_inject, status_nudge) arrive in v0.2.

# Always close the feedback loop. Without it, the engine cannot calibrate.
engine.record_feedback(
    decision_id=decision.id,
    feedback_type=FeedbackType.ENGAGED,
    raw_signal=user_reply_text,
)
```

---

## The three inviolable invariants

These are not aspirational principles. They are architectural rules enforced at the storage layer, not at the policy layer, so that bugs in upper layers cannot break them. Implementations that violate any of them are not valid Throughline implementations.

### I-1. Per-Relationship Isolation

Information shared by person X with owner Y enters and stays in the `(Y, X)` channel. It never reaches anyone else, ever, for any reason.

> *Masha told the bot that she got divorced. Three days later, the bot is helping Alex draft a message to Vasya. The bot must not reference Masha's divorce — even obliquely, even helpfully, even if Alex asked "what's new with my contacts." Information from the Alex-Masha channel does not exist in the Alex-Vasya channel.*

This line is the line. The public API has no method that would let you cross it.

### I-2. Owner Sovereignty

The human being served has absolute, instant, irreversible authority over all stored continuity data about them:

- Full export (JSON) at any moment
- Full wipe (one click, no recovery) at any moment
- Per-thread, per-category deletion
- Right to deny any specific category permanently

### I-3. Encryption at Rest

Continuity data contains the user's emotional patterns, vulnerabilities, anxieties, intimate concerns. All Throughline-managed tables MUST be encrypted at rest (SQLCipher or equivalent), with the key in the operating system's secure store. Plaintext storage is not a valid configuration.

---

## Architecture at a glance

```
                ┌────────────────────────────────────┐
                │      Host Application (your bot)   │
                └──────────────┬─────────────────────┘
                               │
                               ▼ (events)
        ┌──────────────────────────────────────────┐
        │            Throughline Engine            │
        │                                          │
        │  Extraction        — finds threads       │
        │  Continuity Memory — per-pair isolated   │
        │  Initiative Eval   — vetoes → multi → +  │
        │  Generalization    — defuses precision   │
        │  Composer          — drafts messages     │
        │  Feedback Loop     — learns calibration  │
        └────────────────┬─────────────────────────┘
                         │
                         ▼ (decisions)
                ┌────────────────────────────────────┐
                │      Host Application              │
                └────────────────────────────────────┘
```

The host application owns:
- The message pipeline (feeding events in)
- The delivery surface (acting on decisions out)
- The owner-facing controls (consent UI, export/wipe buttons)

Throughline owns:
- Whether, when, and at what intrusiveness level to initiate
- How to express care without crossing into surveillance
- The per-relationship isolation guarantee
- The calibration that keeps the system from degrading to noise

Full architectural detail in [SPEC.md](./SPEC.md).

---

## The Care Score

Decisions are computed in a fixed order. Stage order is non-negotiable — it encodes the difference between caring and stalking.

```
1. VETOES         — binary blockers (consent, sensitivity, rebuff, crisis, ...)
                   → any veto fires → SILENCE, no further computation
2. MULTIPLIERS    — situational scaling (cognitive capacity, tempo, trust, ...)
                   → product below threshold → SILENCE
3. LINEAR SCORE   — importance + emotion + timing + usefulness
4. FINAL          — base_score × multiplier_product
5. GRADUATION     — final maps to one of five intrusiveness levels:
                   SILENCE / PASSIVE / SOFT_INJECT / NUDGE / DIRECT
```

The most common error in care systems is making consent a weight rather than a veto. A high importance value should never be able to override "the user said don't ask about this." That asymmetry is what separates a friend from a CRM. See [SPEC.md §5](./SPEC.md#5-the-care-score) for the rationale.

---

## Graduated initiation

The engine does not treat initiation as binary. It picks the *lowest* intrusiveness level that still serves the thread:

| Level | What it does | Used when |
|---|---|---|
| **Silence** | nothing | default; preferred over uncertain action |
| **Passive prompt** | visible only if owner opens dashboard/Mini App | score ≥ 0.40 |
| **Soft inject** | weaves into next outgoing message naturally | score ≥ 0.55 |
| **Status nudge** | changes visible status, no message | score ≥ 0.70 |
| **Direct message** | full message with notification | score ≥ 0.85 |

v0.1 implements direct messages only. Lower levels arrive with v0.2.

---

## Generalization, or: why precise recall feels uncanny

A friend remembers in generalities. *"Your physics exam at 14:30 just ended — how was it?"* is the sentence of a stalker. *"You had something important today — how did it go?"* is the sentence of a friend.

Throughline runs every fact through a `generalize()` layer before composition:

| Raw | Generalized |
|---|---|
| `exam at 14:30 physics Hall B` | *you had something important today* |
| `lost appetite, last meal Wednesday 11pm` | *you mentioned eating wasn't easy lately* |
| `said you'd watch The Brutalist at 8pm` | *that movie you were going to watch* |

Three levels available: `literal` (only for UI displays), `loose` (default), `oblique` (for high-sensitivity threads).

---

## Project status

**v0.1 — specification complete, MVP implementation in progress.**

What works today:
- Complete veto layer (10 vetoes, full test coverage) — `throughline/vetoes.py`
- Complete scoring layer (multipliers, linear addends, graduated initiation) — `throughline/scoring.py`
- Generalization with static patterns — `throughline/generalization.py`
- Public type system (`Thread`, `Decision`, `FeedbackType`, etc.) — `throughline/types.py`
- Full architectural spec — `SPEC.md`

What's stubbed (next implementation work):
- `Engine` façade — SQLCipher storage, message extraction, evaluation loop, feedback persistence
- LLM-based generalization (v0.2)
- Lower-intrusiveness initiation levels (v0.2)
- Soul Graph / long-term personality (v0.4)

See [SPEC.md §15](./SPEC.md#15-roadmap) for the full roadmap.

---

## Contributing

PRs welcome under non-negotiable constraints:

- **No relaxation of inviolable invariants.** [SPEC.md §3](./SPEC.md#3-inviolable-invariants) is the line. PRs that weaken any invariant will be closed.
- **No engagement-optimization features.** Any PR whose stated purpose is "increase message volume / session length / stickiness" is the wrong project.
- **Privacy-affecting changes require explicit review** with a written justification.
- **Style**: `black` + `ruff`, conventional commits.
- **Tests** required for: vetoes, isolation enforcement, feedback loop.

Throughline touches the most personal corners of users' lives. Contributors are expected to take that seriously. Full details in [SPEC.md §17](./SPEC.md#17-contributing).

---

## License

[MIT](./LICENSE).

---

<div align="center">

*If you are building an assistant that should feel present in someone's life without becoming surveillance, this is for you. If you are building a notification machine optimized for retention, this is not.*

[github.com/alxnklmn/throughline-engine](https://github.com/alxnklmn/throughline-engine)

</div>
