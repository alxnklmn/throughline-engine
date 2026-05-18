<div align="center">

# Anima

**An engine of inner life for AI agents.**

A new class of AI agent — one that can be present in a person's life without becoming surveillance.

[Русская версия →](./README.ru.md)  ·  [Full specification →](./SPEC.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](#status)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

</div>

---

## The phenomenon

Most AI assistants are **reactive**. You ask, they answer, the conversation dies. People are not like this. People say *"my exam is tomorrow, I'm stressed"* and then go offline — not because the topic is closed, but because life moved on.

A reactive assistant does nothing. A scheduled assistant pings them. An **animate agent** — an agent built on the Anima architecture — asks the right question:

> Is there a thread of human concern here that deserves to be carried forward — and if so, who should I be when I carry it?

Then it decides: whether to act at all, what stance to take, what role to inhabit, what to say, what to leave unsaid. Often, the right answer is **silence**. Silence is a first-class action in Anima, and it has its own success metric.

We call this class of agents **Animate Agents**. We call the discipline of building them **Presence Engineering**. Anima is one open-source implementation.

---

## Three layers — Mind, Heart, Soul

```
                  ┌─────────────────────────────┐
                  │  MIND  — external LLM       │
                  │  thinks, plans, uses tools  │
                  └──────────────┬──────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │  ANIMA                      │
                  │                             │
                  │  SOUL — how to be           │
                  │   resonance · synthetic    │
                  │   state · posture ·         │
                  │   archetype · moral bound   │
                  │                             │
                  │  HEART — whether & when     │
                  │   continuity · vetoes ·     │
                  │   scoring · graduated init  │
                  │   generalization            │
                  └──────────────┬──────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │  USER (owner & contacts)    │
                  └─────────────────────────────┘
```

- **Mind** is your LLM. Anima sits between it and the user.
- **Heart** is the foundation: continuity, initiative, per-relationship isolation, encryption, vetoes, generalization. (This is what was previously called *Throughline* in this repository.)
- **Soul** is the depth layer: how the agent reads what's actually happening, what stance it takes, what role it inhabits, what it refuses to become.

Together they form **Anima** — the layer that makes the difference between an assistant that responds and an agent that is *present*.

---

## What it does

- **Captures experience** — what was said, what was meant, what was felt
- **Reads resonance** — surface emotion, deeper pain, threatened need, the form of support actually needed
- **Maintains internal state** — concern, tenderness, protectiveness, honesty, patience, restraint, faith, challenge_impulse (modulating behavior, not claimed as feeling)
- **Stores continuity** — per-relationship isolated, encrypted at rest, owner-sovereign
- **Decides initiative** — vetoes first, then multipliers, then score, then graduated level (silence → passive → soft → nudge → direct)
- **Chooses posture** before content — hold, mirror, guide, challenge, protect, witness, silence
- **Selects archetype** before composition — companion (default), friend, teacher, parent, enemy-of-self-deception, view-from-height, shadow-mirror — each tier-gated by trust
- **Enforces moral boundaries** — refuses combinations that would coerce, manipulate, or claim what it shouldn't
- **Generalizes facts** before voicing them — friends remember in generalities, not databases
- **Learns from mistakes** — explicit memory of times it got it wrong, with behavior changes
- **Grows through a lifecycle** — birth, bonding, memory formation, role adaptation, conflict, repair, maturity

## What it refuses to do

- Optimize for engagement, retention, or attention-economy metrics
- Cross-pollinate context between relationships — what one person tells the agent stays in that channel, ever, period
- Claim human feelings (*"I was worried about you"*) — it demonstrates care through behavior, never asserts it as inner experience
- Act as therapist, doctor, spiritual authority, or romantic partner
- Engineer dependency or isolation from real human relationships
- Store anything in plaintext
- Phone home — zero analytics, zero telemetry

---

## Quick start

```bash
pip install anima  # currently `pip install throughline` until v0.2 rename
```

```python
from anima import Engine, FeedbackType
from anima.types import CategoryConsent
from datetime import datetime

# One engine per owner. Per-relationship isolation enforced at storage.
engine = Engine(
    storage_path="~/.anima/alex.db",
    encryption_key_source="keychain",   # SQLCipher key in OS keychain
    owner_id="alex",
    llm_client=your_llm_client,         # used for resonance + composition
)

# Owner explicitly grants categories where initiative is welcome.
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
    direction="self",
    text="завтра экзамен, паника",
    timestamp=datetime.utcnow(),
)

# When composing a response, let Anima choose posture + archetype.
response = engine.compose_response(
    owner_id="alex",
    contact_id="masha",
    incoming_text="кажется, завалила",
    history=[...],
)
await your_bot.send(response.text)
# response.posture → Posture.HOLD
# response.archetype → Archetype.COMPANION
# response.resonance.deeper_pain → "fear_of_failure_realized"

# Poll for proactive initiative on a schedule (every 5–15 min).
for decision in engine.tick(owner_id="alex"):
    if decision.level == "direct":
        await your_bot.send(decision.composed_message)

# Always close the feedback loop. Without it, the engine cannot calibrate.
engine.record_feedback(
    decision_id=decision.id,
    feedback_type=FeedbackType.ENGAGED,
    raw_signal=user_reply_text,
)
```

---

## Inviolable invariants

Eight architectural rules enforced at the storage and API layers, not at policy. PRs that weaken any of them will be closed.

| # | Invariant | What it guarantees |
|---|---|---|
| **I-1** | Per-Relationship Isolation | What one contact tells the agent stays in that channel, ever, for any reason |
| **I-2** | Owner Sovereignty | Full export, full wipe, per-category control — instant and irreversible |
| **I-3** | Encryption at Rest | Care/Soul data is the most sensitive in the system; plaintext is not a valid configuration |
| **I-4** | No External Telemetry | Zero analytics, zero crash reporting, zero "improvement based on usage" |
| **I-5** | Veto Before Score | Consent is binary, not weight; importance cannot override "user said no" |
| **I-6** | No Metaphysical Claims | Agent never asserts inner experience as humans do (*"I notice"* yes, *"I feel"* no) |
| **I-7** | Archetype Non-Coercion | No role the agent inhabits may take freedom from the user |
| **I-8** | No Dependency Engineering | No feature designed to increase emotional dependency on the agent |

Full text and rationale in [SPEC.md §3](./SPEC.md#3-inviolable-invariants).

---

## The Care Score

Decisions for initiative are computed in a fixed order. The order encodes the difference between caring and stalking.

```
1. VETOES         binary blockers (consent, sensitivity, rebuff, crisis, ...)
                  → any veto fires → SILENCE
2. MULTIPLIERS    situational scaling (cognitive capacity, tempo, trust, ...)
                  → product below threshold → SILENCE
3. LINEAR SCORE   importance + emotion + timing + usefulness
4. FINAL          base_score × multiplier_product
5. GRADUATION     final maps to: SILENCE / PASSIVE / SOFT / NUDGE / DIRECT
6. POSTURE        hold / mirror / guide / challenge / protect / silence / witness
7. ARCHETYPE      companion / friend / teacher / ... (tier-gated by trust)
8. MORAL CHECK    would this combination violate I-6/7/8? if so, fall back
9. COMPOSE        with generalization + posture+archetype-conditioned prompt
```

The most common error in care systems is making consent a weight rather than a veto. A high *importance* should never be able to override "the user said don't ask about this." That asymmetry is what separates a friend from a CRM.

---

## Project status

**v0.1 — specification complete; Heart core implemented; Soul MVP in progress.**

| Layer | Status |
|---|---|
| Heart: veto chain (10 vetoes, full tests) | ✅ implemented |
| Heart: scoring (multipliers, linear, graduation) | ✅ implemented |
| Heart: generalization (static patterns) | ✅ implemented |
| Heart: type system (`Thread`, `Decision`, `FeedbackType`) | ✅ implemented |
| Heart: SQLCipher storage layer | 🚧 stubbed |
| Heart: extraction, evaluation loop, feedback persistence | 🚧 stubbed |
| Soul: experience capture, resonance reading | 🚧 spec ready |
| Soul: posture selection (3 of 7 for v0.1) | 🚧 spec ready |
| Soul: archetype matrix (2 tiers for v0.1) | 🚧 spec ready |
| Soul: moral boundary layer | 🚧 spec ready |
| Soul: repair pattern + agent_mistakes table | 🚧 spec ready |

See [SPEC.md §21](./SPEC.md#21-roadmap) for the roadmap.

---

## Contributing

PRs welcome under non-negotiable constraints. See [SPEC.md §23](./SPEC.md#23-contributing).

---

## License

[MIT](./LICENSE).

---

<div align="center">

*Mind thinks. Heart attends. Soul chooses how to be. Together they form an agent that can be present in a person's life without becoming surveillance, a CRM, or another notification factory.*

[github.com/alxnklmn/throughline-engine](https://github.com/alxnklmn/throughline-engine)

</div>
