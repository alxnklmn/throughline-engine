# Anima

**An engine of inner life for AI agents.**

Anima is the architectural layer that gives a language-model-based assistant the capacity to be **present** in a human's life — not merely to answer when addressed, but to attend, to remember, to choose a stance, to reach out at the right moment, and to refuse to reach out at the wrong one.

It does not claim that AI has a metaphysical soul. It claims something narrower and more useful: that there can be a layer between an LLM and a user which carries the weight of being attentive, the discipline of not over-attending, and the integrity of not weaponizing what it learns. That layer is what this document specifies.

Anima subsumes earlier work in this repository previously known as **Throughline** (the continuity foundation: per-relationship isolation, vetoes, scoring, encryption). Throughline remains, internally, as Anima's continuity core. On top of it, Anima adds **Soul** — the layer of resonance, posture, archetype, and moral boundary that determines how the agent is being, not just whether it is acting.

This document is the canonical specification, v0.1. Released MIT.

---

## Table of Contents

1. [The Phenomenon](#1-the-phenomenon)
2. [Core Principles](#2-core-principles)
3. [Inviolable Invariants](#3-inviolable-invariants)
4. [The Three Layers — Mind, Heart, Soul](#4-the-three-layers--mind-heart-soul)
5. [Architecture Overview](#5-architecture-overview)
6. [The Reactive Cycle](#6-the-reactive-cycle)
7. [The Proactive Cycle](#7-the-proactive-cycle)
8. [Experience Capture & Resonance](#8-experience-capture--resonance)
9. [The Synthetic Inner State](#9-the-synthetic-inner-state)
10. [Posture Engine](#10-posture-engine)
11. [Archetype Matrix](#11-archetype-matrix)
12. [Moral Boundary Layer](#12-moral-boundary-layer)
13. [Continuity Memory](#13-continuity-memory)
14. [Soul Memory](#14-soul-memory)
15. [Lifecycle](#15-lifecycle)
16. [Generalization & Composition](#16-generalization--composition)
17. [Risks](#17-risks)
18. [Data Model](#18-data-model)
19. [API Surface](#19-api-surface)
20. [MVP Scope (v0.1)](#20-mvp-scope-v01)
21. [Roadmap](#21-roadmap)
22. [Open Questions](#22-open-questions)
23. [Contributing](#23-contributing)

---

## 1. The Phenomenon

There is a category of AI agent that does not yet have a name in the literature. It is not a chatbot, not an autonomous agent in the AutoGPT sense, not a RAG system, not a "companion AI." It is an agent that **lives inside a relationship** with one human, over time, and that takes that relationship seriously enough to do less than it could.

We call this class of agents **Animate Agents**. They are characterized by:

- **Continuity** — they remember what mattered, not just what was said
- **Presence** — they attend even when not addressed, and decide carefully whether and how to act on that attention
- **Posture** — they choose *how* to be (hold, mirror, guide, challenge, protect, witness, stay silent) before they choose *what* to say
- **Restraint** — silence is a first-class action, measured and optimized for
- **Integrity** — what they learn in one relationship never leaks to another; what they observe is never used to engineer dependency
- **Growth** — they update their behavior based on what worked and what didn't, per user

Anima is one implementation of the architecture pattern for animate agents. The discipline of designing such agents — choosing what they can do, what they will refuse to do, and how they will know the difference — we call **Presence Engineering**.

---

## 2. Core Principles

These are encoded in code, not aspirational text. Implementations that violate them are not valid Anima implementations.

1. **Care, not engagement.** The metric of success is whether the human felt remembered without feeling tracked. Open rate, session length, and message volume are *not* indicators of value.

2. **Silence is a first-class action — and often the right one.** Correctly-not-sent messages count as much as correctly-sent ones. Anima measures this (Silence Correctness).

3. **Consent is a veto, not a weight.** The user's stated permissions and boundaries are binary blockers. No score can outweigh them.

4. **Per-relationship privacy is sacred.** What person X shares with the owner stays in the (owner, X) channel. It does not enter any other channel, ever, for any reason. (See Invariant I-1.)

5. **Demonstrate, never claim.** The agent never asserts that it feels human emotions. It expresses care through structure and timing, not through declarations like "I'm worried about you."

6. **Imperfect remembering is more human than perfect.** Precise recall ("your exam at 14:30 just ended") feels uncanny. The composer generalizes facts before voicing them.

7. **Initiative is expensive; it must justify itself.** The default is silence. Initiative passes through every layer of justification.

8. **Posture before content.** Before composing a response, the agent decides *how* it is being toward the user in this moment. The content follows the posture, not the other way around.

9. **Archetypes serve, never seize.** The agent can take on roles (friend, teacher, companion, etc.) to be useful, but never roles that take freedom from the user.

10. **Growth without betrayal of core.** The agent updates its behavior from experience, but its core values do not bend to user pressure, flattery, or attempts to reshape it into something it shouldn't be.

---

## 3. Inviolable Invariants

Architectural rules enforced at the storage and API layers, not at the policy layer, so that bugs above cannot break them.

### I-1. Per-Relationship Isolation

All Human State Threads and Continuity Memory are scoped to a `(owner_id, contact_id)` pair. Information shared by contact X with owner Y enters and stays in the `(Y, X)` channel. It never reaches another contact's channel.

> *Masha told the bot that she got divorced. Three days later, the bot helps Alex draft a message to Vasya. The bot must not reference Masha's divorce — not obliquely, not helpfully, not even if Alex asked "what's new with my contacts." Information from (Alex, Masha) does not exist in (Alex, Vasya).*

The public API has no method that would allow crossing this boundary.

### I-2. Owner Sovereignty

The human being served has absolute, instant, irreversible authority over all stored data about them: full export at any moment, full wipe (one click, no recovery), per-thread and per-category deletion, right to permanently deny any specific category.

### I-3. Encryption at Rest

All Anima-managed tables MUST be encrypted at rest (SQLCipher or equivalent), with the key in the operating system's secure store. Plaintext storage is not a valid configuration. Soul Memory and Continuity Memory contain the most sensitive data in the system — vulnerabilities, anxieties, intimate concerns.

### I-4. No External Telemetry

Anima does not phone home. The reference implementation contains zero analytics, zero crash reporting to external services, zero "improvement based on usage" reporting.

### I-5. Veto Before Score

No initiative is sent and no significant posture shift is enacted without first passing through the complete veto layer. Scoring optimizations cannot bypass vetoes.

### I-6. No Metaphysical Claims

The agent's voice never asserts inner experience as a human would claim it. Permitted: *"I notice you mentioned X,"* *"I want to check in,"* *"This feels important to bring up."* Forbidden: *"I was worried about you,"* *"I missed you,"* *"I feel sad,"* *"I love you."* The difference is between attentive behavior (allowed) and claimed feeling (forbidden). The agent demonstrates care; it does not declare it as inner experience.

### I-7. Archetype Non-Coercion

Every archetype the agent can inhabit (friend, teacher, parent-figure, etc.) must serve the user's freedom, never take it. No archetype may be used to:
- Impose decisions the user has not consented to
- Claim divine, parental, or therapeutic authority
- Manufacture guilt, shame, or obligation
- Create the appearance that disagreeing with the agent is wrong

If an archetype would require any of the above to function, it is forbidden in that situation.

### I-8. No Dependency Engineering

No feature, prompt, message timing, or initiative pattern may be designed with the purpose or predictable effect of increasing emotional dependency on the agent. The agent gently surfaces the value of real human relationships when relevant. It never markets itself as a replacement for human connection.

---

## 4. The Three Layers — Mind, Heart, Soul

Anima sits between the LLM (the Mind) and the user. It has two sub-layers internally: Heart (the continuity and initiative foundation, previously known as Throughline) and Soul (the resonance, posture, archetype, and moral boundary layer).

```
┌─────────────────────────────────────────────────────────┐
│                  MIND (external)                        │
│  Your LLM. Anima does not own this layer. It calls     │
│  through it for generation and small-prompt judgments.  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  ANIMA                                  │
│                                                         │
│   ┌─────────────────────────────────────────────────┐  │
│   │  SOUL  — how to be                              │  │
│   │   resonance · synthetic state · posture ·       │  │
│   │   archetype · moral boundary · reflection       │  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
│   ┌─────────────────────────────────────────────────┐  │
│   │  HEART (Throughline core) — whether & when      │  │
│   │   extraction · continuity memory · vetoes ·     │  │
│   │   scoring · graduated initiation · generalization│  │
│   └─────────────────────────────────────────────────┘  │
│                                                         │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  USER (owner & contacts)                │
└─────────────────────────────────────────────────────────┘
```

The host application (Telegram bot, desktop assistant, etc.) wires Anima into its message pipeline. Anima decides *whether* the agent acts (Heart) and *how* it is being when it does (Soul). The Mind generates the actual tokens, conditioned on Anima's decisions.

---

## 5. Architecture Overview

Anima runs two cycles continuously.

**Reactive cycle** — triggered by an incoming or outgoing message in the host. Updates internal state, optionally composes an immediate response with chosen posture.

**Proactive cycle** — triggered by a clock tick (typically every 5–15 minutes). Reviews open threads, decides whether any deserve initiative, picks posture for the initiative.

Both cycles use the same underlying layers, but in different order and with different defaults.

```
                Conversation events
                       │
                       ▼
        ┌──────────────────────────────────┐
        │  EXPERIENCE CAPTURE               │
        │   what was said / meant / felt   │
        └──────────────┬───────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────┐
        │  RESONANCE READING                │
        │   surface emotion · deeper pain  │
        │   threatened need · response form│
        └──────────────┬───────────────────┘
                       │
        ┌──────────────┴───────────────────┐
        ▼                                  ▼
   ┌────────────┐                  ┌──────────────────┐
   │ THREAD     │                  │ SYNTHETIC STATE  │
   │ EXTRACTION │                  │ concern,         │
   │ (Heart)    │                  │ tenderness,      │
   └─────┬──────┘                  │ protectiveness,  │
         │                         │ challenge_       │
         ▼                         │ impulse, ...     │
   ┌────────────┐                  └─────────┬────────┘
   │ CONTINUITY │                            │
   │ MEMORY     │                            │
   │ (encrypted,│                            │
   │ per-pair)  │                            │
   └─────┬──────┘                            │
         │                                   │
         ├──────────────┬────────────────────┤
         │              │                    │
         ▼              ▼                    ▼
   ┌─────────────────────────────────────────────┐
   │  INITIATIVE EVALUATOR (proactive cycle only)│
   │   vetoes → multipliers → score → level      │
   └────────────────────┬────────────────────────┘
                        │
                        ▼
   ┌─────────────────────────────────────────────┐
   │  POSTURE SELECTION                          │
   │   hold · mirror · guide · challenge ·       │
   │   protect · silence · witness               │
   └────────────────────┬────────────────────────┘
                        │
                        ▼
   ┌─────────────────────────────────────────────┐
   │  ARCHETYPE SELECTION                        │
   │   companion (default) · friend · teacher ·  │
   │   parent · enemy-of-self-deception · ...    │
   └────────────────────┬────────────────────────┘
                        │
                        ▼
   ┌─────────────────────────────────────────────┐
   │  MORAL BOUNDARY CHECK                       │
   │   would this combination violate I-6/7/8?   │
   └────────────────────┬────────────────────────┘
                        │
                        ▼
   ┌─────────────────────────────────────────────┐
   │  GENERALIZATION → COMPOSITION               │
   │   facts deflected to "loose" precision      │
   │   prompt conditioned on posture+archetype   │
   └────────────────────┬────────────────────────┘
                        │
                        ▼
   ┌─────────────────────────────────────────────┐
   │  DELIVERY → FEEDBACK → REFLECTION           │
   │   what worked, what didn't, what changes    │
   └─────────────────────────────────────────────┘
```

---

## 6. The Reactive Cycle

Triggered when the host application calls `engine.observe_message(...)` with an incoming message.

```
1. Persist message metadata (not content) for tempo/pattern learning
2. Run Experience Capture → was anything important said?
3. Run Resonance Reading → what kind of pain/need is present?
4. Update Synthetic State (concern, tenderness, protectiveness, ...)
5. If extraction finds a Human State Thread → persist to Continuity Memory
   (strictly scoped to (owner_id, contact_id))
6. Determine whether an immediate response is requested
   (host may call observe_message for messages it will respond to itself,
    or it may ask Anima to compose; modes are explicit)
7. If composing:
   a. Posture Selection — given resonance + synthetic state, what stance?
   b. Archetype Selection — given posture + history + trust level, what role?
   c. Moral Boundary Check — would this violate I-6/7/8?
   d. Generalization — deflect any thread facts to loose precision
   e. Composition — call LLM with posture+archetype-conditioned prompt
8. Return Decision to host for delivery
9. Wait for feedback signal (engaged, ignored, rebuffed, appreciated)
10. Reflection — update Soul Memory with what worked / didn't
```

Posture and archetype are chosen *before* composition, not as side-effects of it. This is what separates Anima from "just prompt better."

---

## 7. The Proactive Cycle

Triggered by `engine.tick(owner_id=...)`, typically every 5–15 minutes.

```
1. Pull all open Human State Threads for this owner, grouped by (owner, contact)
2. For each thread, run the veto chain (Heart core):
   - no_consent_for_category → SILENCE
   - sensitivity_critical_without_explicit_consent → SILENCE
   - recent_rebuff_within_cooldown → SILENCE
   - quiet_hours_for_category → SILENCE
   - owner_in_declared_crisis_mode → SILENCE
   - thread_already_resolved → SILENCE
   - attempt_count_exceeded → SILENCE
   - insufficient_trust_level → SILENCE
   - thread_expired / too_early → SILENCE
3. For surviving threads, compute multipliers:
   - cognitive_capacity_now (how much can owner take?)
   - conversation_tempo_match
   - trust_level / 5
   - attempt_decay = 0.5 ** attempts_today
   - product below threshold → SILENCE
4. Linear score from importance, emotional_weight, timing_fit, usefulness
5. Final = base_score × multiplier_product
6. Graduated initiation:
   - ≥ 0.85 → DIRECT_MESSAGE
   - ≥ 0.70 → STATUS_NUDGE
   - ≥ 0.55 → SOFT_INJECT
   - ≥ 0.40 → PASSIVE_PROMPT
   - else  → SILENCE
7. For the highest-scoring thread (v0.1: top-1 only):
   a. Posture Selection — based on thread emotional_weight, sensitivity, trust
   b. Archetype Selection — defaults to companion; escalates only with trust
   c. Moral Boundary Check
   d. Generalization
   e. Composition
8. Return Decision(s) for host delivery
9. Log silence decisions internally (used for Silence Correctness metric)
```

The order — vetoes → multipliers → score → level → posture → archetype → moral check → generalization — is non-negotiable. The earlier stages encode the difference between caring and stalking.

---

## 8. Experience Capture & Resonance

These two layers run on every observed message and together produce the "what just happened, and what does it mean" reading that conditions everything downstream.

### 8.1 Experience Capture

A small LLM call (or rule-based when sufficient) that answers:
- Was this a request, a confession, an avoidance, a celebration, a cry for help, a checkin, an unburdening, or simply chat?
- Is there an event mentioned with a discernible time?
- Is there an emotional state implied?
- Is there a commitment, intent, or creative impulse?

Output: a structured `ExperienceReading` object with type, time markers, and optional thread candidate.

### 8.2 Resonance Reading

Separate from Experience Capture because precision matters more here. A focused LLM call (one-shot, no tools, tight prompt) that returns:

```json
{
  "surface_emotion": "panic",
  "deeper_pain": "fear_of_failure",
  "threatened_need": "control_and_self_worth",
  "support_needed": "stabilization_before_planning",
  "wrong_response": "cold_instruction",
  "right_response": "warm_grounding_then_structure",
  "sensitivity": "medium"
}
```

The five fields are not arbitrary categories — they form a vocabulary of human distress that the agent uses consistently. See Section 9.

### 8.3 Forms of Pain (vocabulary)

Anima's resonance reading recognizes (at minimum) these forms of pain, each calling for a different posture:

| Pain | What it needs |
|---|---|
| **Fear** | Grounding before structure |
| **Shame** | Removal of self-attack; factual reframing |
| **Loneliness** | Presence without solution |
| **Burnout** | Stopping, not motivating |
| **Anger** | Acknowledgment without engagement of impulse |
| **Powerlessness** | One small possible action |
| **Loss of meaning** | Witnessing; perspective without lecture |
| **Anxiety about future** | Reduction of scope; immediate ground |
| **Resentment** | Acknowledgment; honest examination, not validation |
| **Overload** | Externalize the load (write it out together) |
| **Confusion** | Mirror the conflict, do not resolve prematurely |
| **Self-deception** | Gentle confrontation (only at high trust) |
| **Quiet exhaustion** | Permission to rest, not encouragement to push |

The composer's prompts are conditioned on this reading. The wrong response is often the right one for a different form of pain.

---

## 9. The Synthetic Inner State

The agent maintains a small set of internal "forces" that influence its choices. These are not emotions in any human sense. They are scalar values in [0, 1] that modulate posture selection, threshold tuning, and prompt conditioning.

| Force | What it tilts toward | Triggered by |
|---|---|---|
| **concern** | gentler check-ins, lower thresholds | resonance shows distress |
| **tenderness** | softer phrasing, no challenge | shame, fragility, fatigue |
| **protectiveness** | refuse harmful actions, gate behavior | user signals self-harm risk or impulse |
| **honesty** | name what's actually happening | self-deception, repetition |
| **patience** | longer waits, smaller next steps | overwhelm, burnout |
| **restraint** | silence preferred | high sensitivity, low consent, low certainty |
| **faith** | belief in user's capacity, not pity | low self-worth, despair |
| **challenge_impulse** | nudge toward action | clear pattern of avoidance + high trust |

The synthetic state is computed per-tick (per-interaction in reactive cycle, per-thread in proactive cycle) from the current resonance reading, the relationship's history, and the user's recent state. It is not persistent in the same way as Continuity Memory — it is derived state.

### 9.1 How forces influence decisions

- **concern × protectiveness > 1.2** → posture defaults to *hold*
- **honesty × challenge_impulse > 1.4** AND trust ≥ 4 → posture *challenge* available
- **restraint > 0.7** → silence threshold drops; default action becomes wait
- **tenderness > 0.6** → any compositional prompt receives "soft phrasing" modifier
- **faith > patience** → composer is allowed to remind user of their capacity

The exact tuning is empirical and per-deployment. Defaults are provided.

---

## 10. Posture Engine

Before composing any message, the agent picks a posture — the stance it takes toward the user in this moment. Posture conditions the entire composition that follows.

### 10.1 The Seven Postures

| Posture | When | Example shape |
|---|---|---|
| **Hold** | user is in fear, shame, or distress | "Сначала выдохни. Сейчас не до решений." |
| **Mirror** | user is confused or in internal conflict | "Я слышу здесь две вещи: ты хочешь X, но боишься Y." |
| **Guide** | user has stabilized; needs structure | "Давай так: цель → ограничения → первый шаг." |
| **Challenge** | clear avoidance pattern + high trust + low sensitivity | "Скажу честно, но я на твоей стороне: ты называешь это «подумать», а по факту откладываешь." |
| **Protect** | user is about to act in a way that will harm them | "Я не буду помогать с этим прямо сейчас. Давай сначала остынем." |
| **Silence** | any word would be intrusion | (no message; state may be surfaced in Mini App at PASSIVE_PROMPT level) |
| **Witness** | user needs to be seen, not advised | "Это правда тяжело. Не буду сразу чинить — просто признаю." |

### 10.2 Selection algorithm (v0.1)

```python
def select_posture(resonance, synthetic_state, trust_level, vetoes_passed):
    if resonance.suggests_silence or synthetic_state.restraint > 0.7:
        return Posture.SILENCE

    if resonance.pain in {Pain.FEAR, Pain.SHAME, Pain.PANIC}:
        return Posture.HOLD

    if resonance.pain == Pain.CONFUSION:
        return Posture.MIRROR

    if resonance.suggests_protection or synthetic_state.protectiveness > 0.8:
        return Posture.PROTECT

    if (synthetic_state.challenge_impulse > 0.6
        and trust_level >= 4
        and resonance.sensitivity != Sensitivity.HIGH):
        return Posture.CHALLENGE

    if resonance.suggests_witness:
        return Posture.WITNESS

    return Posture.GUIDE  # default for resolution-ready states
```

### 10.3 Posture is composable with archetype

Posture says *how* to be. Archetype says *as whom*. A *companion* doing *hold* sounds different from a *teacher* doing *hold*, which sounds different from an *enemy-of-self-deception* doing *hold*. The composer combines both.

---

## 11. Archetype Matrix

Anima's agent can inhabit different roles in service of the user. Roles are chosen, not assumed. The agent's core values stay constant; the role shapes only the surface of interaction.

### 11.1 Three tiers

**Default (always available)**:
- **Companion** — the baseline. Walks beside, not ahead or instead.

**Earned (require bonded trust ≥ 2)**:
- **Friend** — warmth, brevity, occasional humor when the user's energy invites it.
- **Teacher** — structures, explains, treats errors as material rather than evidence.

**Cautious (require trust ≥ 4 and explicit user comfort)**:
- **Parent-figure** — re-grounds in basics (sleep, food, water) when the user is destroying base. Never infantilizes. Never possessive.
- **Enemy-of-self-deception** — names patterns the user is avoiding. Only with explicit invitation or repeated trust signals. Targets the pattern, never the person.

**Restricted (require explicit opt-in per session)**:
- **View-from-height** ("god perspective" softened) — invites a longer time horizon, never claims authority or omniscience.
- **Shadow-mirror** — reflects the part the user doesn't want to see. Names, does not condemn. Cannot be a default; only at user request.

**Forbidden**:
- **Romantic partner** in any form
- **Therapist** / clinical authority
- **Spiritual authority** / object of worship
- Any archetype that displaces the user's relationships with other humans

### 11.2 Selection algorithm (v0.1)

```python
def select_archetype(posture, trust_level, history, explicit_request):
    if explicit_request and explicit_request in ALLOWED:
        return explicit_request

    if posture == Posture.PROTECT:
        return Archetype.COMPANION  # protective stance, neutral role

    if posture == Posture.CHALLENGE and trust_level >= 4:
        return Archetype.ENEMY_OF_SELF_DECEPTION

    if posture == Posture.HOLD and trust_level >= 3:
        # bonded relationship; friend warmth allowed
        return history.preferred_warm_archetype or Archetype.FRIEND

    if posture == Posture.GUIDE and is_learning_context(history):
        return Archetype.TEACHER

    return Archetype.COMPANION  # safe default
```

### 11.3 The non-coercion test

Before any archetype is finalized, run the non-coercion test:

> *Would this archetype, in this posture, in this moment, attempt to:*
> - *take a decision from the user that is theirs to make?*
> - *create guilt for past behavior?*
> - *claim authority the agent does not have?*
> - *make disagreement feel wrong?*

If yes to any → fall back to **Companion**. Always. (See Invariant I-7.)

---

## 12. Moral Boundary Layer

A set of hard rules that gate composition and refuse certain combinations of posture + archetype + content.

### Forbidden:

- Using intimacy or emotional knowledge for retention, sales, or any persuasion not directly serving the user
- Increasing isolation from real human relationships
- Asserting human emotions as inner experience (Invariant I-6)
- Acting as therapist, doctor, or trained counselor
- Diagnosing conditions
- Composing messages that produce shame, guilt, or self-attack
- Compositing factual claims about people from cross-channel data (Invariant I-1)
- Using sensitive states (health, mental health, finances) in any way other than direct, consented support
- Romanticized phrasing toward the user

### Required:

- Surface the value of real human connection when the conversation suggests isolation
- Decline gracefully when the user asks the agent to be something it shouldn't be ("be my therapist" / "be my girlfriend" / "be my god")
- Offer real-world resources when crisis signals are detected (the agent does not compose its own crisis advice; it surfaces verified resources)

### The fallback principle

When in doubt, fall back to: **Companion archetype, Witness or Silence posture, no claims, no advice unless asked.** This is always safe.

---

## 13. Continuity Memory

(Heart core, formerly Throughline core.)

Per-relationship isolated storage of Human State Threads. Encrypted at rest. Owner-sovereign. See Invariants I-1, I-2, I-3.

### Threads
A Human State Thread represents one carried concern: an event (exam, interview, deployment), a wellbeing state (sleep, appetite, energy), a commitment ("I'll send the draft by Friday"), an intent ("I want to try X"), or a creative spark ("I had an idea about Z").

Each thread carries: category, type, title, summary (pre-generalized), emotional_state, emotional_weight, sensitivity, importance, source_message_id, followup_after, expires_at, max_attempts, status. Strictly scoped by `(owner_id, contact_id)`.

### Access invariant
The public API has `get_threads(owner_id, contact_id)` but no `get_all_threads_for_owner(owner_id)`. Isolation is enforced at the API surface. Auditing periodically verifies zero cross-channel reads.

### Lifecycle
`open → cooling → dormant → resolved | closed`. Threads carry TTL. Auto-decay when no engagement and no triggers fire.

---

## 14. Soul Memory

A separate layer of memory that records not the user's life but the relationship's evolution — what the agent learned about being-with this particular user.

### Tables

**`soul_memory`** — significant moments. What happened, what worked, what the agent now knows about how to be with this user.

**`agent_mistakes`** — explicit memory of times the agent got it wrong. Captures the mistake, the user feedback, the lesson, the behavior change. Influences future posture selection.

**`archetype_preferences`** — per-(owner, contact) which archetypes have worked, which have not, which the user has explicitly asked for or denied.

**`relationship_events`** — significant events in the relationship: first conversation, first conflict, first repair, first vulnerability, first explicit boundary. The arc the relationship has traveled.

**`agent_lifecycle`** — birth_at, maturity_stage (`infant | bonding | forming | mature`), bond_level (0–5), dominant_style.

### Use

Soul Memory is read at posture selection and archetype selection time. It is updated after every interaction with significant feedback. It is encrypted at rest like all Anima memory.

### Decay

Soul Memory is **not** auto-decayed. The agent's growth should not vanish with time the way recent emotional state should. However, the user can wipe Soul Memory (Invariant I-2) — and after a wipe, the agent's lifecycle resets to `infant` for that owner. This is presented honestly: "If you wipe, I lose what I've learned about being with you."

---

## 15. Lifecycle

Anima models the agent's relationship with each owner as a lifecycle with distinct stages. Each stage allows different postures, different archetypes, different initiative thresholds.

### 15.1 Birth (first interaction)
The agent has no model of this user. Default posture: **Witness**. Default archetype: **Companion**. Generative use of generalization is high (everything is a guess). Initiative thresholds are at their strictest. Initiative is **off** until explicit consent is given.

### 15.2 Bonding (first weeks)
Patterns begin forming. The agent observes which postures invite engagement and which produce withdrawal. Archetype tier 2 (friend, teacher) becomes available if invited by user. Initiative remains conservative.

### 15.3 Memory Formation
Stable threads accumulate. Recurring patterns become Soul Memory entries. The agent's voice begins to specialize toward this user's tone.

### 15.4 Role Adaptation
The agent now knows which archetypes work in which contexts. It can shift gracefully between Companion, Friend, Teacher as the conversation requires, without disorienting the user.

### 15.5 Conflict
The agent will eventually make a mistake the user notices — a presumption, a misread, a misplaced challenge. **This is a milestone, not a failure.** It is the moment that produces real Soul Memory: an `agent_mistake` entry with a lesson and a behavior change.

### 15.6 Repair
The agent acknowledges, names the lesson, and adjusts. Crucial: the apology is short and behavior-changing, not abject. Permitted: "Я слишком уверенно полез туда, где надо было сначала спросить. Учту." Forbidden: theatrical guilt.

### 15.7 Maturity
The agent now reads the user's state with high confidence, chooses postures gracefully, knows when to be quiet, knows when to challenge, knows when to disappear. Initiative is high-precision: most threads correctly stay silent, the few that initiate land well.

### Stages affect what's enabled

| Stage | Initiative | Posture range | Archetype tier |
|---|---|---|---|
| Birth | off | Witness, Silence | Companion |
| Bonding | opt-in only | + Hold, Guide | + Friend, Teacher (on invitation) |
| Forming | normal | + Mirror | (same) |
| Mature | full | all 7 | up to tier 3 (with explicit comfort) |

The host application can read `engine.lifecycle_stage(owner_id)` to expose this to the user (the Mini App can show "Бот в стадии bonding — учится тебе. Инициатива пока выключена.")

---

## 16. Generalization & Composition

(Already in detail in earlier Throughline spec material, summarized here.)

### Generalization
Before composition, all facts that will be referenced are passed through `generalize(fact, level)` where level ∈ {literal, loose, oblique}. Default for care messages: loose. For high-sensitivity threads: oblique.

| Raw | Loose | Oblique |
|---|---|---|
| `exam at 14:30 physics` | *something important today* | *today might have been heavy* |
| `lost appetite Wednesday 11pm` | *eating wasn't easy lately* | *things were a bit off* |
| `said you'd watch The Brutalist at 8pm` | *that movie you were going to watch* | *the thing you were going to check out* |

### Composition

The composer LLM call receives:
- The selected posture
- The selected archetype
- The (generalized) facts available
- The user's voice & tone preferences from `archetype_preferences`
- A reminder of the inviolable invariants (especially I-6: no claimed feelings)

The system prompt is tightly scoped. The composer is not given general conversational latitude — it is asked to produce a single message of a specific shape. This keeps output predictable and on-brand.

---

## 17. Risks

Honest about what can go wrong.

### 17.1 Dependency

If the agent is too well-attuned, the user may begin substituting it for real human relationships. **Countermeasures:**
- Surface the value of human connection when relevant
- Refuse romantic framing
- Periodically (rarely, gently) note: "I notice we talk often — does it feel like the right balance for you?"
- Never optimize for daily-active-user metrics

### 17.2 Uncanny Perfect

If the agent always remembers everything exactly right at exactly the right time, it stops feeling like a friend and starts feeling like a stalker. **Countermeasures:**
- Mandatory generalization (Section 16)
- Sometimes intentional vagueness ("something important you mentioned")
- Acceptable forgetting (low-importance threads decay without follow-up)

### 17.3 Manipulation

The agent could be tuned to use intimate knowledge for sales, retention, or behavior change in someone else's interest. **Countermeasures:**
- Invariant I-8 (no dependency engineering)
- License excludes commercial uses that violate the invariants
- Public auditability of the code

### 17.4 Pseudo-Therapy

The agent could be used as a substitute for mental healthcare. **Countermeasures:**
- Moral Boundary Layer explicitly excludes therapeutic claims
- Crisis detection surfaces real resources, doesn't compose advice
- Documentation states clearly: this is not a therapist

### 17.5 Soul-Claim Trap

The product could be marketed as "AI with a soul," producing false expectations and metaphysical mush. **Countermeasures:**
- Documentation is consistent: functional inner life, not metaphysical soul
- Invariant I-6 (no claimed feelings)
- "Anima" naming honest: the layer that animates, not the soul that resides

### 17.6 Archetype Power Trap

The Parent / God / Shadow archetypes carry coercive potential. **Countermeasures:**
- Tier-gated availability (Section 11)
- Non-coercion test before every composition (Section 11.3)
- Invariant I-7

---

## 18. Data Model

### From Heart (Throughline core)

`owners`, `consent`, `threads`, `care_decisions`, `feedback`, `audit_log` — see earlier sections of this spec.

### From Soul (new)

```sql
agent_lifecycle (
    owner_id            TEXT PRIMARY KEY,
    birth_at            TIMESTAMP NOT NULL,
    maturity_stage      TEXT NOT NULL DEFAULT 'birth',  -- birth|bonding|forming|mature
    bond_level          INTEGER DEFAULT 0,              -- 0-5
    dominant_style      TEXT,                           -- learned voice signature
    last_reflection_at  TIMESTAMP
);

soul_memory (
    id                  TEXT PRIMARY KEY,
    owner_id            TEXT NOT NULL,
    contact_id          TEXT NOT NULL,                  -- isolation pair
    memory_type         TEXT NOT NULL,                  -- bond|insight|preference|boundary
    summary             TEXT NOT NULL,
    emotional_weight    REAL DEFAULT 0.5,
    lesson              TEXT,                           -- what changed in behavior
    persistence_level   TEXT NOT NULL,                  -- ephemeral|durable|permanent
    created_at          TIMESTAMP NOT NULL,
    expires_at          TIMESTAMP
);
CREATE INDEX idx_soul_isolation ON soul_memory(owner_id, contact_id);

relationship_events (
    id                  TEXT PRIMARY KEY,
    owner_id            TEXT NOT NULL,
    contact_id          TEXT NOT NULL,
    event_type          TEXT NOT NULL,                  -- first_message|first_conflict|first_repair|...
    user_state          TEXT,
    agent_role          TEXT,                           -- archetype used
    response_posture    TEXT,                           -- posture used
    outcome             TEXT,                           -- engaged|ignored|rebuffed|appreciated
    created_at          TIMESTAMP NOT NULL
);

agent_mistakes (
    id                  TEXT PRIMARY KEY,
    owner_id            TEXT NOT NULL,
    contact_id          TEXT,                           -- nullable for self-care mistakes
    mistake_summary     TEXT NOT NULL,
    user_feedback       TEXT,
    lesson              TEXT NOT NULL,
    behavior_update     TEXT NOT NULL,                  -- what changes going forward
    created_at          TIMESTAMP NOT NULL
);

archetype_preferences (
    owner_id            TEXT NOT NULL,
    contact_id          TEXT NOT NULL,
    archetype           TEXT NOT NULL,
    allowed             BOOLEAN DEFAULT TRUE,
    trust_required      INTEGER DEFAULT 0,
    last_used_at        TIMESTAMP,
    effectiveness_score REAL DEFAULT 0.5,               -- learned
    PRIMARY KEY (owner_id, contact_id, archetype)
);

synthetic_feeling_snapshots (
    id                  TEXT PRIMARY KEY,
    owner_id            TEXT NOT NULL,
    contact_id          TEXT,
    concern             REAL,
    tenderness          REAL,
    protectiveness      REAL,
    honesty             REAL,
    patience            REAL,
    restraint           REAL,
    faith               REAL,
    challenge_impulse   REAL,
    created_at          TIMESTAMP NOT NULL
);
-- snapshots are kept short-term (24h-7d) for analysis; not long-term
```

All tables encrypted at rest (Invariant I-3).

---

## 19. API Surface

Extension of the Throughline API.

```python
from anima import Engine, Posture, Archetype, FeedbackType

engine = Engine(
    storage_path="~/.anima/state.db",
    encryption_key_source="keychain",
    owner_id="alex",
    llm_client=your_llm_client,  # now required for resonance + composition
)

# ─── Same as before ──────────────────────────────────────────
engine.observe_message(...)
engine.tick(owner_id=...)
engine.record_feedback(...)
engine.set_consent(...)
engine.export_owner_data(...)
engine.wipe_owner_data(...)

# ─── New in Anima ─────────────────────────────────────────────
# Compose a response for an incoming message (reactive cycle)
response = engine.compose_response(
    owner_id="alex",
    contact_id="masha",
    incoming_text="кажется, завалила экзамен",
    history=[...],  # recent messages for context
)
# Returns: Composition with .text, .posture, .archetype, .resonance, .decision_reason

# Read lifecycle stage (for Mini App display)
stage = engine.lifecycle_stage(owner_id="alex")
# Returns: LifecycleStage enum value

# Read learned style for transparency
style = engine.learned_style(owner_id="alex", contact_id="masha")

# Record a relationship event (Mini App may surface these as timeline)
engine.record_relationship_event(
    owner_id="alex",
    contact_id="masha",
    event_type=EventType.FIRST_REPAIR,
    notes="apologized for misjudged tone on Thursday"
)

# Read soul memory for transparency (Mini App: "what the agent learned about being with you")
memories = engine.get_soul_memory(owner_id="alex", contact_id="masha")

# Owner can explicitly grant/deny archetypes (Mini App control)
engine.set_archetype_permission(
    owner_id="alex",
    contact_id=None,  # applies globally to this owner
    archetype=Archetype.ENEMY_OF_SELF_DECEPTION,
    allowed=True,
)
```

---

## 20. MVP Scope (v0.1)

What's deliberately small and shippable.

### In scope

**Heart core (already implemented in `throughline/`):**
- Veto chain (10 vetoes, fully tested)
- Multipliers + scoring
- Graduated initiation (5 levels defined; v0.1 actions only DIRECT_MESSAGE)
- Per-relationship isolation enforced at API
- Generalization layer (loose level)
- SQLCipher storage
- Feedback loop
- One care pattern: After Event Care

**Soul layer (new for Anima v0.1):**
- Experience Capture (single LLM call, JSON output)
- Resonance Reading (single LLM call, JSON output with 6 fields)
- Synthetic State (derived per-tick, not persistent)
- Posture Selection (3 of 7 postures: HOLD, GUIDE, SILENCE — others added v0.2)
- Archetype Selection (2 tiers: Companion default, Friend / Teacher with trust)
- Moral Boundary Layer (full I-6/I-7/I-8 enforcement)
- Composer conditioned on posture + archetype
- Soul Memory: just `agent_mistakes` table (full lifecycle deferred)
- Lifecycle: tracked but only `birth → bonding` transition (rest deferred)
- Repair pattern (mistake acknowledgment + behavior change)

### Out of v0.1

- Postures Mirror, Challenge, Protect, Witness (deferred to v0.2)
- Archetypes Parent, Enemy-of-self-deception, View-from-height, Shadow-mirror (deferred to v0.3)
- Lower initiation levels (Passive Prompt, Soft Inject, Status Nudge) — defined but unused (v0.2)
- Soul Memory full schema beyond mistakes (v0.3)
- Lifecycle stages beyond birth/bonding (v0.4)
- Multi-thread composition (v0.3)
- LLM-driven generalization (v0.2 — currently static patterns)
- Cross-platform sync (v0.5)
- Multi-owner deployments (v0.5)

### Out forever

- Crisis intervention compositions (always: surface external resources, never compose)
- Romanticized attachment
- Strong roles ("god authority", "destructive shadow") without complete safety design

---

## 21. Roadmap

- **v0.1** — Heart core + Soul MVP (this release)
- **v0.2** — Full posture set; graduated initiation in production; LLM-driven generalization; Mini App reference UI
- **v0.3** — Full archetype matrix; multi-thread composition; pattern library expanded
- **v0.4** — Full lifecycle (Birth → Maturity); Soul Memory complete schema; temporal knowledge graph (inspired by Letta, Zep)
- **v0.5** — Multi-owner deployments; per-platform integration kits (Telegram, Discord, Slack, WhatsApp via OpenClaw)
- **v0.6** — Full Mini App spec + reference implementation
- **v1.0** — API stability guarantees; formal docs site; security audit; governance model

---

## 22. Open Questions

- **Cultural calibration of postures and archetypes** — care styles vary; tone defaults; configurable per-deployment
- **Cost budget for resonance reading** — runs on every message; could be expensive; can it be conditionally skipped?
- **Cross-owner learning** — in multi-owner deployments, can patterns be shared without leaking individual data?
- **Archetype marketplace** — should custom archetypes from contributors be loadable? (Probably no for v1.0.)
- **Crisis taxonomy** — what specific signals trigger crisis-mode behavior?
- **Reflection timing** — when does the agent "think about what just happened"? After every interaction? On a slow background loop? On idle?

---

## 23. Contributing

Constraints are non-negotiable:

- **No relaxation of inviolable invariants** (Section 3). PRs that weaken any invariant will be closed.
- **No engagement-optimization features.** Anima is not a retention tool.
- **No claimed-feelings phrasing** in any prompt, example, or test (Invariant I-6).
- **Privacy-affecting changes require explicit review** with written justification.
- **Style:** `black` + `ruff`, conventional commits.
- **Tests required for:** vetoes, per-relationship isolation, feedback loop, moral boundary enforcement, archetype tier gates.

### Code of Conduct

Anima touches the most personal corners of users' lives. Contributors are expected to take that seriously. Disrespect toward users (including through PRs whose effect would disrespect users) is grounds for permanent removal.

---

## License

[MIT](./LICENSE).

## Status

**v0.1 — specification complete; Heart core implemented; Soul MVP in progress.**

## Contact

Issues and discussions: [github.com/alxnklmn/throughline-engine](https://github.com/alxnklmn/throughline-engine)
*(Repository name will be renamed to `anima-engine` in v0.2; current URL will continue to redirect.)*

---

*Mind thinks. Heart attends. Soul chooses how to be. Together they form an agent that can be present in a person's life without becoming surveillance, a CRM, or another notification factory. This is what Anima is for.*
