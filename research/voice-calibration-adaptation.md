# Voice calibration & anti-AI-tells — adaptation note

**Source materials**

- [humanizer skill](https://github.com/blader/humanizer) by blader — MIT-licensed
  Claude Code / OpenCode skill. v2.5.1 at adaptation time.
- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) —
  CC-BY-SA 4.0, maintained by WikiProject AI Cleanup. The humanizer skill
  cites this as its primary reference; we cite it directly here too.

The humanizer skill was written for editorial tooling — one-shot rewriting
of essay/article-shaped text. Anima is a different surface: live chat,
1–3 sentence agent replies, latency- and cost-sensitive. This document
records what was adapted, what was dropped, and why — both for license
attribution and so future contributors can see the engineering reasoning
rather than re-derive it.

---

## What was adapted

### A. Voice calibration → ``throughline/voice.py``

The humanizer skill's "Voice Calibration (Optional)" section describes a
small, well-shaped algorithm: read a sample of the user's own writing,
extract sentence-rhythm / word-choice / punctuation / verbal-tic patterns,
match in subsequent output. This is exactly the algorithm Anima needs to
populate the previously-empty ``agent_lifecycle.dominant_style`` field.

``throughline/voice.py::calibrate_voice`` implements this as a single
JSON-mode LLM call against a tight system prompt. Key adaptations:

- **Output format**: humanizer's calibration is conversational (the agent
  reads samples, internalises them, produces rewritten text). Ours is
  structured — JSON returning a 3–6-line "voice signature" string that
  ``composer.compose()`` folds into its system prompt via the existing
  ``learned_style`` parameter. The signature lives in the database; the
  agent does not need to re-read samples each compose.
- **No content storage**: Anima never stores raw message content. The
  Engine method ``calibrate_voice(samples)`` takes the samples as inputs,
  produces a signature, persists only the signature (which describes
  patterns, not message contents).
- **Privacy hardening**: the prompt explicitly forbids quoting individual
  messages. It describes patterns, not contents. Combined with the
  per-relationship isolation rule (the host pulls samples from a single
  channel; the engine has no cross-channel read), this keeps the
  signature within a single (owner, contact) pair's scope.
- **Hard cap on signature length**: 800 chars max — the signature is
  appended to every composer prompt; unbounded growth would balloon
  token cost.

### B. Anti-AI-tells subset → ``composer._BASELINE_STYLE_DONTS``

The humanizer skill catalogues 28 pattern categories. We pulled the
**nine categories most likely to leak into a 1–3 sentence chat reply**
and made them composer baseline constraints. They appear in every
composer prompt under "style (sound human, not generated)", separate
from the moral-layer HARD constraints so they tune voice without
escalating safety severity.

Selected categories:

| # | Pattern | Why kept |
|---|---|---|
| 1 | Signposting / meta-announcements | "давай разберём", "let's break this down" — common in chat |
| 2 | Sycophancy ("great question!", "отличный вопрос!") | First-line tell in many AI replies |
| 3 | Rule-of-three forcing | LLMs pad lists; even one extra item breaks tone |
| 4 | Hyphenated-pair overuse | Stacked "cross-functional, data-driven, real-time…" |
| 5 | Em-dash overuse | The single most recognisable stylistic tell |
| 6 | Generic positive closers ("everything will work out!") | Particularly damaging in care contexts — already partial in moral.py for BURNOUT/SHAME |
| 7 | Inflated significance ("testament", "pivotal moment", "landscape") | Leaks even into short responses |
| 8 | Copula avoidance ("serves as", "stands as", "boasts") | LLMs default to elaborate verbs over "is/has" |
| 9 | Vague attributions ("experts say", "studies show") | Subtle but degrades trust |

---

## What was deliberately not adapted

The remaining 19 categories address either:

- **Wikipedia/essay-shaped output** (challenges-and-future-prospects
  sections, outline-like vertical lists with bolded inline headers, false
  ranges across multi-paragraph arcs, knowledge-cutoff disclaimers,
  notability/media-coverage emphasis) — Anima composer's hard length cap
  (1–3 sentences, max_tokens=220) makes these structurally impossible.
- **Persuasive-essay tropes** (persuasive authority — "the real question
  is…", elegant variation / synonym cycling) — these need a longer text
  to manifest.
- **Output-format issues** (curly quotation marks, title case in
  headings, fragmented headers, emojis decorating bullet items) — the
  composer prompt already forbids markdown / bullets / signoffs, which
  preempts these.
- **The "final anti-AI audit pass"** described in humanizer's process
  (draft → audit → final). For a 1–3 sentence message the cost of an
  additional LLM call doubles latency for marginal gain; the post-
  composition pass we already have (``moral.audit_output``) catches the
  invariant-level violations, which is the load-bearing audit.

---

## Where the lines are drawn

`composer._BASELINE_STYLE_DONTS` exists separately from
`moral._baseline_constraints()` to keep two concerns distinct:

- **Moral baseline** (I-6 / I-8 / forbidden roles / romantic phrasing /
  generalization preference) — these are **safety invariants**. The
  post-composition audit (`moral.audit_output`) actively scans the
  produced text for them. A retry is triggered if any fires, and a safe
  fallback ships if retry fails.
- **Style baseline** (this document's subject) — these are **voice
  quality** constraints. They go into the composer prompt but are not
  post-audited. They are not safety. A small style leak does not block
  delivery; a moral violation does.

This separation is deliberate. It lets us iterate aggressively on voice
quality without raising the severity of moral enforcement, and vice
versa.

---

## License & attribution

- humanizer skill: MIT (Copyright © contributors). The MIT license
  permits adaptation with attribution; this document and the in-code
  comments at `throughline/composer.py::_BASELINE_STYLE_DONTS` and
  `throughline/voice.py` provide it.
- Wikipedia AI Cleanup guide: CC-BY-SA 4.0. We cite directly rather than
  reproducing prose.

If you contribute additional patterns from either source, follow the same
attribution convention (in-code comment + an entry in the "What was
adapted" or "What was deliberately not adapted" table above).
