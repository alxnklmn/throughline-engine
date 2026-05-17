# Throughline

**An open-source engine of human continuity for AI assistants.**

Throughline is an architectural layer that gives any LLM-powered assistant the capacity to attend to a person across time — to remember what mattered, to notice unfinished states, and to initiate care-appropriate follow-ups without becoming a stalker, a spammer, or a CRM in disguise.

It is not a chatbot. It is not a scheduler. It is the layer that sits between memory and intention — the thing that turns "the assistant knows you mentioned an exam yesterday" into "the assistant asks how it went, at the right moment, in the right tone, only if it has the right to."

This document is the canonical specification, v0.1. Released MIT for everyone who wants their assistant to be more human and less invasive.

---

## Table of Contents

1. [The Problem](#1-the-problem)
2. [Core Principles](#2-core-principles)
3. [Inviolable Invariants](#3-inviolable-invariants)
4. [Architecture Overview](#4-architecture-overview)
5. [The Care Score](#5-the-care-score)
6. [Graduated Initiation](#6-graduated-initiation)
7. [Generalization Layer](#7-generalization-layer)
8. [Data Model](#8-data-model)
9. [Per-Relationship Isolation](#9-per-relationship-isolation)
10. [API Surface](#10-api-surface)
11. [Integration Guide](#11-integration-guide)
12. [Metrics & Calibration](#12-metrics--calibration)
13. [Privacy & Safety](#13-privacy--safety)
14. [MVP Scope (v0.1)](#14-mvp-scope-v01)
15. [Roadmap](#15-roadmap)
16. [Open Questions](#16-open-questions)
17. [Contributing](#17-contributing)

---

## 1. The Problem

Modern AI assistants are reactive. The user sends a message, the assistant responds, and the conversation dies. But a human life is not a series of isolated requests. People say things like:

- "My exam is tomorrow, I'm stressed."
- "Barely ate yesterday."
- "Scared about the interview."
- "I'll watch that movie tonight."
- "Going to try the deployment tomorrow."

…and then they go offline. Not because the topic is closed, but because life moved on.

A reactive assistant does nothing. A scheduled assistant pings them. A Throughline-equipped assistant asks the right question:

> Is there a thread of human concern here that deserves to be carried forward — gently, appropriately, with permission?

If yes, it returns to it. If no, it stays silent. **Silence is also action.**

This is not "engagement." Engagement is a metric used by products that want your attention. Throughline is a metric used by products that want to be useful to a person. The two often look the same but never feel the same.

---

## 2. Core Principles

These principles are not aspirational. They are encoded in the engine's behavior. Implementations that violate them are not valid Throughline implementations.

1. **Privacy between two people is sacred and never crossed.** Information that person X shares only enters the bot's interactions with X. It never reaches anyone else. (See Section 3 and Section 9.)

2. **Care, not engagement.** The metric of success is whether the human felt remembered without feeling tracked. Open rate, message volume, and session length are *not* indicators of value.

3. **Silence is also an action — and often the right one.** A correctly-not-sent message is as valuable as a correctly-sent one. The engine measures this.

4. **Consent is veto, not weight.** The user's stated permissions and boundaries are binary blockers, not factors to be outweighed by other signals.

5. **Demonstrate care through behavior, never claim feelings.** The engine never produces text in which the AI asserts emotions ("I was worried about you," "I missed you"). It produces text that *shows* attentiveness through structure and timing.

6. **Imperfect remembering is more human than perfect.** Citing precise facts ("your exam at 14:30 just ended") feels uncanny. The engine *generalizes* facts before composing messages.

7. **Initiative is the most expensive action and must justify itself.** The default is silence. Initiative requires passing through every layer of justification.

---

## 3. Inviolable Invariants

These are the architectural rules that cannot be relaxed. They are enforced at the storage layer, not at the policy layer, so that bugs in upper layers cannot break them.

### Invariant I-1: Per-Relationship Isolation

All Human State Threads and Continuity Memory are scoped to a `(owner_id, contact_id)` pair. Information shared by contact X with owner Y never enters the bot's interactions with any other contact Z. The storage layer indexes by this pair and the query layer refuses queries that would cross the boundary.

**Concrete forbidden behavior:**

> Masha told the bot (acting as owner Alex) that she got divorced last week. Three days later, the bot is helping Alex draft a message to Vasya. The bot **must not** reference Masha's divorce, even obliquely, even helpfully, even if Alex asked "what's new with my contacts." Information from the Alex-Masha channel does not exist in the Alex-Vasya channel.

This is the inviolable line. A product that crosses it is no longer Throughline-compliant.

### Invariant I-2: Owner Sovereignty

The owner of an assistant (the human being served) has absolute, instant, irreversible authority over all stored continuity data about them. Includes:
- Full export (JSON) at any moment
- Full wipe (one click, no recovery) at any moment
- Per-thread, per-category deletion
- Right to deny any specific category permanently

### Invariant I-3: Encryption at Rest

Continuity data is highly sensitive — it contains the user's emotional patterns, vulnerabilities, anxieties, and intimate concerns. All Throughline-managed tables MUST be encrypted at rest (SQLCipher or equivalent), with the key in the operating system's secure store (Keychain, KeyStore, etc.). Plaintext storage is not a valid configuration.

### Invariant I-4: No External Telemetry

Throughline does not phone home. The reference implementation contains zero analytics, zero crash reporting to external services, and zero "improvement based on usage" reporting. Implementations that add such features are not Throughline-compliant.

### Invariant I-5: Veto Before Score

No care initiative is sent without first passing through the complete veto layer. Scoring optimizations cannot bypass vetoes. (See Section 5.)

---

## 4. Architecture Overview

Throughline is a layered engine that integrates *alongside* a conversational AI, not inside it. The host application (Telegram bot, mobile assistant, desktop tool) feeds Throughline conversational events and queries it for initiative decisions.

```
                ┌────────────────────────────────────┐
                │      Host Application (your bot)   │
                └──────────────┬─────────────────────┘
                               │
                               ▼ (incoming/outgoing events)
        ┌──────────────────────────────────────────┐
        │            Throughline Engine            │
        │                                          │
        │  Extraction Layer                        │
        │  ──> identifies Human State Threads      │
        │                                          │
        │  Continuity Memory                       │
        │  ──> per-relationship isolated storage   │
        │                                          │
        │  Initiative Evaluator                    │
        │   ├─ Veto Layer       (binary blockers)  │
        │   ├─ Multiplier Layer (situational)      │
        │   └─ Score Layer      (linear addends)   │
        │                                          │
        │  Generalization Layer                    │
        │  ──> deflects exact-fact citation        │
        │                                          │
        │  Composer                                │
        │  ──> drafts the message                  │
        │                                          │
        │  Feedback Loop                           │
        │  ──> learns from owner reactions         │
        └────────────────┬─────────────────────────┘
                         │
                         ▼ (initiative decisions)
                ┌────────────────────────────────────┐
                │      Host Application              │
                └────────────────────────────────────┘
```

The host application is responsible for:
- Feeding Throughline conversation events
- Acting on initiative decisions (sending the message, showing the prompt)
- Collecting and passing back feedback

Throughline is responsible for:
- Extracting meaningful threads from conversation
- Storing them with per-relationship isolation
- Deciding when, what, and how (or whether) to initiate
- Generalizing facts so messages feel like a friend, not a database
- Learning calibration from owner reactions

---

## 5. The Care Score

The decision to initiate is computed in three stages. The order is non-negotiable.

### Stage 1: Vetoes (binary blockers)

Each veto is a hard stop. If any veto fires, the result is `Silence`. No further computation happens.

```python
VETOES = [
    NoConsentForCategory,
    SensitivityCriticalWithoutExplicitConsent,
    RecentRebuffWithinCooldown,
    QuietHoursForCategory,
    OwnerInDeclaredCrisisMode,
    ThreadAlreadyResolved,
    AttemptCountExceeded,
    InsufficientTrustLevel,
]
```

### Stage 2: Multipliers (situational scaling)

If all vetoes pass, situational multipliers are computed. Each is in `[0.0, 1.0]`. They multiply together. If the product is below a minimum threshold (default `0.3`), the result is `Silence`.

```python
cognitive_capacity = read_capacity(owner)        # how much can owner take now?
conversation_tempo  = tempo_match(thread)        # is this in conversational rhythm?
trust_level         = trust(category) / 5        # progression-gated
attempt_decay       = 0.5 ** thread.attempts_today

multipliers = cognitive_capacity * conversation_tempo * trust_level * attempt_decay
if multipliers < 0.3:
    return Silence(reason="multipliers below threshold")
```

### Stage 3: Linear Addends (importance-weighted scoring)

Only now does the linear score compute, and it's then *multiplied* by the multipliers from Stage 2.

```python
base_score = (
    thread.importance       * 0.30 +
    thread.emotional_weight * 0.25 +
    timing_fit(thread)      * 0.25 +
    usefulness(thread)      * 0.20
)

final_score = base_score * multipliers
```

### Stage 4: Graduated Initiation

The `final_score` does not just decide send/no-send. It picks the *level* of initiation.

```python
if final_score >= 0.85:  return DirectMessage
elif final_score >= 0.70: return StatusNudge
elif final_score >= 0.55: return SoftInject
elif final_score >= 0.40: return PassivePrompt
else:                    return Silence
```

(See Section 6 for what these mean.)

### Why this order matters

A common mistake in care-systems is to make consent a *factor* in a score. If consent is `-0.30` in the score, a high `importance` of `+0.50` can override it. The system then sends a care message in a category the user explicitly declined.

This is not a math bug. It is a category error: consent is a property of the *relationship*, not a feature to be traded against. Vetoes encode this correctly.

---

## 6. Graduated Initiation

The engine does not see initiation as binary (send / silence). It sees a spectrum of intrusiveness, and picks the lowest level that still serves the thread.

### Level 0 — Silence
Do nothing. The thread is observed and may be reconsidered on next tick.

### Level 1 — Passive Prompt
A subtle marker visible only if the owner opens the assistant's surface (Mini App, dashboard, side panel). No push. No notification. "Something you might want to come back to."

### Level 2 — Soft Inject
Wait for the owner to send a message to the assistant for any reason. When they do, the response weaves the open thread into the answer naturally. ("…also, you mentioned the exam — but later, no rush.")

### Level 3 — Status Nudge
Modify a visible status (assistant presence, mood indicator, badge) without sending a message. The owner sees it peripherally.

### Level 4 — Direct Message
The most intrusive option. A direct message from the assistant to the owner, on the primary channel, with notification.

### Default behavior
The engine prefers lower levels. A `final_score` of `0.95` may still result in a `PassivePrompt` if the timing is bad. A `final_score` of `0.55` will never result in a `DirectMessage`.

---

## 7. Generalization Layer

Before any care message is composed, the underlying facts are passed through generalization. This makes the assistant feel like a friend with reasonable memory, not a database with perfect recall.

### Examples

| Raw fact | Generalized |
|---|---|
| "Exam at 14:30, physics, Hall B" | "you had something important today" |
| "Lost appetite, last meal Wednesday 11pm" | "you mentioned eating wasn't easy lately" |
| "Worked 14 hours yesterday on deployment" | "you were pushing hard yesterday" |
| "Said you'd watch The Brutalist at 8pm" | "you were going to watch that movie" |
| "Sister has stage-2 diagnosis" | *(generalization not applied — sensitivity = critical; veto governs)* |

### Implementation

`generalize(fact, level)` where `level` ∈ {`literal`, `loose`, `oblique`}.

- `literal` is only used in user-facing contexts where exactness is required (e.g., showing the data in the Mini App)
- `loose` is the default for care messages
- `oblique` is for high-sensitivity threads where even loose phrasing risks intrusion

Generalization is performed by a small dedicated prompt, not by the main composition prompt. This keeps the composition stage free to focus on tone.

---

## 8. Data Model

The schema below uses SQLite syntax. All tables MUST be encrypted at rest (SQLCipher). Indices noted are not optional — they enforce isolation and performance simultaneously.

```sql
-- Owner: the human served by the assistant
CREATE TABLE owners (
    id              TEXT PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL,
    proactivity_mode TEXT NOT NULL DEFAULT 'silent',  -- silent|task-only|life-events|full
    care_level      INTEGER NOT NULL DEFAULT 0        -- trust progression 0-5
);

-- Per-category consent. Absence of row = no consent.
CREATE TABLE consent (
    owner_id        TEXT NOT NULL,
    contact_id      TEXT NOT NULL,                    -- NULL = applies to self-directed care
    category        TEXT NOT NULL,                    -- work|study|wellbeing|sleep|food|...
    level           TEXT NOT NULL,                    -- denied|task|event|wellbeing|full
    quiet_hours_start INTEGER,
    quiet_hours_end INTEGER,
    updated_at      TIMESTAMP NOT NULL,
    PRIMARY KEY (owner_id, contact_id, category)
);

-- Human State Threads — the core unit
CREATE TABLE threads (
    id                  TEXT PRIMARY KEY,
    owner_id            TEXT NOT NULL,
    contact_id          TEXT NOT NULL,                -- isolation pair
    category            TEXT NOT NULL,
    type                TEXT NOT NULL,                -- life_event|wellbeing|commitment|intent
    title               TEXT NOT NULL,                -- short, generalized
    summary             TEXT NOT NULL,                -- pre-generalized for composition
    emotional_state     TEXT,                         -- detected affect
    emotional_weight    REAL DEFAULT 0.5,             -- 0-1
    sensitivity         TEXT NOT NULL DEFAULT 'medium', -- low|medium|high|critical
    importance          REAL DEFAULT 0.5,             -- 0-1
    source_message_id   TEXT,
    followup_after      TIMESTAMP,                    -- earliest reasonable initiation
    expires_at          TIMESTAMP NOT NULL,
    max_attempts        INTEGER DEFAULT 1,
    attempts_count      INTEGER DEFAULT 0,
    last_attempt_at     TIMESTAMP,
    status              TEXT NOT NULL DEFAULT 'open', -- open|cooling|dormant|resolved|closed
    created_at          TIMESTAMP NOT NULL
);
CREATE INDEX idx_threads_isolation ON threads(owner_id, contact_id, status);
CREATE INDEX idx_threads_followup ON threads(status, followup_after);

-- Care opportunities — evaluated decisions
CREATE TABLE care_decisions (
    id                  TEXT PRIMARY KEY,
    thread_id           TEXT NOT NULL,
    care_score          REAL NOT NULL,
    initiation_level    TEXT NOT NULL,                -- silence|passive|soft_inject|nudge|direct
    decision_reason     TEXT,
    veto_triggered      TEXT,                         -- name of veto if applicable
    composed_message    TEXT,                         -- only if level >= soft_inject
    delivered_at        TIMESTAMP,
    created_at          TIMESTAMP NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES threads(id)
);

-- Feedback loop
CREATE TABLE feedback (
    id              TEXT PRIMARY KEY,
    decision_id     TEXT NOT NULL,
    feedback_type   TEXT NOT NULL,                    -- engaged|ignored|rebuffed|appreciated
    raw_signal      TEXT,
    created_at      TIMESTAMP NOT NULL,
    FOREIGN KEY (decision_id) REFERENCES care_decisions(id)
);

-- Audit log — never deleted, append-only
CREATE TABLE audit_log (
    id          TEXT PRIMARY KEY,
    owner_id    TEXT NOT NULL,
    contact_id  TEXT,
    action      TEXT NOT NULL,                        -- thread_created|decision_made|silence|...
    detail      TEXT,
    created_at  TIMESTAMP NOT NULL
);
```

---

## 9. Per-Relationship Isolation

This deserves its own section because it is the single most important architectural property.

### The rule

For each `(owner, contact)` pair, the bot maintains an isolated **channel** of continuity. Information stored in that channel is queryable only when the bot is acting in the context of that exact pair.

### Enforcement

1. **Storage**: Every thread row carries `(owner_id, contact_id)`. The primary access function `get_threads(owner_id, contact_id)` is the *only* sanctioned way to read threads. There is no `get_all_threads_for_owner(owner_id)` exposed in the public API.

2. **Composition**: When composing a message to be sent in context of pair `(owner, X)`, the composer is provided only threads from channel `(owner, X)`. There is no "augmentation" step that pulls related context from other channels.

3. **Self-directed care**: When the bot writes to the owner *themselves* (not on behalf of), the relevant `contact_id` is the owner's own ID. Threads in `(owner, owner)` channel are the only ones accessible in self-directed care.

4. **Audit**: Every access to a channel is logged. Periodic auditing can surface any attempted cross-channel access (which should be zero — the API doesn't allow it, so a non-zero count means a bug).

### Why this matters

If the bot leaks personal context from one relationship to another:
- The owner loses trust in the bot's discretion
- The third party (whose secret was leaked) is harmed
- The product's core promise is broken
- The damage is often irreversible (you can't un-tell a thing)

There is no growth hack worth this. There is no AI helpfulness worth this. This is the line.

### What about acting on behalf of the owner?

When the bot replies *to* Masha *as* the owner, the bot draws from:
- The `(owner, Masha)` continuity channel — yes
- General memory shared between owner and Masha — yes
- Information from `(owner, Vasya)` channel — **no**
- Information from `(owner, owner)` self-channel — **no, unless the owner has explicitly opted into "act with my full context" mode, which is off by default and clearly explained**

---

## 10. API Surface

The reference Python implementation exposes the following public interface.

```python
from throughline import Engine, Thread, Decision, FeedbackType

# Initialize
engine = Engine(
    storage_path="~/.throughline/state.db",
    encryption_key_source="keychain",
    owner_id="alex"
)

# Feed an event
engine.observe_message(
    owner_id="alex",
    contact_id="masha",
    direction="incoming",         # incoming|outgoing|self
    text="завтра экзамен, паника",
    timestamp=datetime.utcnow()
)

# Periodically poll for initiative decisions
decisions = engine.tick(owner_id="alex")
# returns list of Decision objects

for decision in decisions:
    if decision.level == "direct":
        host.send_message(decision.composed_message)
    elif decision.level == "passive":
        host.surface_in_dashboard(decision.thread.title)
    # etc.

# Report back what happened
engine.record_feedback(
    decision_id=decision.id,
    feedback_type=FeedbackType.ENGAGED,
    raw_signal=user_reply_text
)

# Owner controls
engine.set_consent(
    owner_id="alex",
    category="wellbeing",
    level="task",                 # denied|task|event|wellbeing|full
    quiet_hours=(23, 9)
)

# Export / wipe
data = engine.export_owner_data(owner_id="alex")
engine.wipe_owner_data(owner_id="alex", confirmation_token="...")
```

---

## 11. Integration Guide

To integrate Throughline into an existing assistant:

1. **Add the dependency**
   ```
   pip install throughline
   ```

2. **Wire into your message pipeline**
   Every incoming and outgoing message in your bot must be fed to `engine.observe_message()`. This is what populates threads.

3. **Run the initiative loop**
   On a schedule appropriate to your bot (every 5-15 minutes is reasonable for most cases), call `engine.tick()`. Act on the returned `Decision` objects according to their `level`.

4. **Expose owner controls**
   At minimum: the ability to grant/deny consent per category, the ability to export, the ability to wipe. These are not optional. A bot that integrates Throughline without giving the owner these controls is misusing the library.

5. **Feed back signals**
   Every decision that produces user-visible output should have its outcome reported back via `record_feedback()`. Without this, calibration cannot happen and the system degrades to noise.

6. **Configure encryption**
   On first run, `engine` will generate a key and store it in your OS keychain. If you prefer a different key source, pass `encryption_key_source` with a custom provider.

---

## 12. Metrics & Calibration

### Primary metric: Silence Correctness

Of all moments where the engine *could have* initiated and did not, what fraction were correct silences (i.e., the owner did not later signal disappointment that the bot didn't reach out)?

This is the inverse of most engagement metrics. Aim high.

### Secondary metrics

- **Comfort Reply Rate** — fraction of direct messages that received a non-frustrated response
- **Negative Feedback Rate** — explicit "don't ask such things" / "stop" responses, per 100 initiatives
- **Trust Retention** — does `care_level` (trust progression) increase over time per owner?
- **Care Usefulness** — fraction of initiatives the owner marks helpful (explicit feedback)
- **Ignored Initiative Ratio** — fraction of initiatives with no response within 24h
- **Opt-out by Category** — counts of permission downgrades, broken out by category
- **Initiative Tone Match** — sampled human review of whether tone fit the situation

### What you must NOT optimize for

- Daily Active Users
- Session length
- Number of messages per day
- Time to first message
- Return rate

These are the metrics of products that want your attention. Throughline is the protocol of products that want to be useful. Conflating them ruins the product.

---

## 13. Privacy & Safety

### Threat Model

Throughline protects against:
- **Passive observation** by host server operators (via encryption at rest)
- **LLM provider data retention** (by routing initiative-generation through a configurable LLM client; users can choose providers that do not retain)
- **Database theft** (via SQLCipher)
- **Cross-relationship leakage** (via Invariant I-1, enforced architecturally)

Throughline does not protect against:
- A compromised host device with the encryption key extracted
- The host application logging plaintext outside Throughline's storage
- Targeted state-level adversaries

These limits are stated honestly and not glossed over.

### Sensitive Categories

The following categories receive elevated protection:
- `health`, `mental_health`, `crisis` — `sensitivity=critical` by default; veto applies unless explicit opt-in
- `relationships`, `finances` — `sensitivity=high` by default
- `food`, `sleep` — `sensitivity=medium` but extra care patterns apply (no pressure, no advice unless asked)

Crisis detection (suicidal ideation, severe distress signals) triggers a special pathway: the engine does NOT compose its own response. Instead, it surfaces a clear notification to the host application's crisis handler. The host application is responsible for the appropriate human-escalation flow.

### What Throughline never does

- Send crisis advice from the LLM
- Diagnose any condition
- Pretend to be a therapist, doctor, or trained counselor
- Use sensitive states for any retention or monetization purpose
- Cross-share data between owners (in multi-owner deployments)

---

## 14. MVP Scope (v0.1)

The first releasable version is deliberately small. It does one pattern well rather than many patterns poorly.

### In scope

- **One care pattern**: After Event Care. The owner mentioned an event with a discernible end-time; the engine checks in after.
- **One initiation level**: Direct Message only. Graduated initiation arrives in v0.2.
- **One thread at a time**: No multi-thread composition. If multiple threads compete, pick highest score; the others wait.
- **Short-lived threads only**: 24h–72h TTL. No long-term Soul Graph yet.
- **Veto layer**: Complete and enforced.
- **Multipliers**: Cognitive capacity, attempt decay, trust level. Conversation tempo deferred.
- **Linear score**: Implemented with default weights; tunable per-deployment via config.
- **Generalization**: `loose` level implemented; `oblique` deferred.
- **SQLCipher storage**: Mandatory.
- **Feedback loop**: Active from day one.
- **Per-relationship isolation**: Enforced at storage API level.
- **Owner controls**: Per-category consent (denied/task/event/wellbeing/full), quiet hours, export, wipe.
- **Audit log**: Append-only, queryable.

### Out of scope for v0.1

- All care patterns except After Event Care
- Passive prompt, soft inject, status nudge initiation levels
- Soul Graph / long-term personality
- Multi-thread composition
- Self-directed care for owner (i.e., the bot caring for the owner *about the owner* — v0.2)
- Cross-platform sync
- Multi-owner shared deployments (planned for v0.3)

---

## 15. Roadmap

### v0.1 (MVP — this release)
After Event Care, direct message only, foundational layers.

### v0.2 — Graduated Initiation
Passive prompts, soft injects, status nudges. Adds the lower-intrusiveness rungs.

### v0.3 — Pattern Library
Gentle Check-in (wellbeing), No Pressure Continuation (intent), Tiny Action Support, Joy Continuation, Protective Silence as deliberate pattern. Each with thorough tests.

### v0.4 — Soul Graph (Long-Term Personality)
Temporal knowledge graph for recurring patterns, preferences, communication style learned over time. Inspired by Letta and Zep. Per-relationship isolated.

### v0.5 — Multi-Owner Deployments
Shared infrastructure, per-owner isolation, owner-to-owner zero-leakage guarantees. For deployments serving multiple humans on shared infrastructure.

### v0.6 — Integration Kits
Reference adapters for: Telegram (Pyrofork), Discord (discord.py), Slack (Bolt), WhatsApp (via OpenClaw), web chat (Vercel AI SDK).

### v1.0 — Stability
API stability guarantees, formal documentation site, security audit, governance model.

---

## 16. Open Questions

Items worth wider discussion before they get hardcoded:

1. **Cultural calibration**: Care styles vary by culture. The default tone is restrained; should the engine offer culture-detection or simply require explicit per-deployment configuration?

2. **Cost budget**: Each initiative costs LLM tokens. Should the engine enforce a per-owner monthly budget, or leave that to the host application?

3. **Negative care (deliberately not mentioning)**: Sometimes the loving thing is to *not* bring up a topic the owner already knows is going badly. Current Silence Gate is "don't write because risk," not "deliberately avoid X because mentioning would hurt." v0.4 territory.

4. **Cross-owner learning** (in multi-owner deployments): If 3 owners reject a pattern, should the 4th owner pre-emptively not get it? Tension between privacy and shared calibration.

5. **Conversation as participant**: Should "time itself" be modeled as a participant (Sunday morning vs. Tuesday 2am affecting tone)? Currently encoded as `timing_fit`; could be richer.

6. **Initiative as a graph problem**: Are conversations better modeled as graphs (topics as nodes, edges as connections, bot navigating)? Currently linear queue.

These are open. PRs and issues welcome.

---

## 17. Contributing

Throughline is MIT-licensed. Contributions welcome, with these constraints:

- **No invariant relaxations.** Section 3 is not negotiable. PRs that weaken any invariant will be closed.
- **Privacy-affecting changes require explicit review.** Any change to consent, storage, isolation, or audit requires sign-off from project maintainers and a written justification.
- **No engagement-optimization features.** PRs that add features whose stated purpose is increasing message volume, session length, or "stickiness" will be closed.
- **Style**: black + ruff. Conventional commits.
- **Tests**: critical paths (vetoes, isolation, feedback) require tests. Other code encouraged but not blocked.

### Code of Conduct

Throughline touches the most personal corners of users' lives. Contributors are expected to take that seriously. Disrespectful behavior toward users (including via PRs that disrespect the user) is grounds for permanent removal.

---

## License

MIT.

## Project Status

v0.1 — specification complete, MVP implementation in progress.

## Contact

Issues and discussions: [github.com/alxnklmn/throughline-engine](https://github.com/alxnklmn/throughline-engine)

---

*Throughline exists because someone has to build the layer that lets AI be present in a human's life without becoming surveillance. If that's what you're building too, let's compare notes.*
