# research/

The behavioural research record for Anima. Unlike `tests/` (deterministic
correctness of the layers), this directory holds the instruments and
findings for the question that matters most and is hardest to measure:

> Does the engine actually make an assistant feel *present* without
> turning into surveillance — and does it know when not to speak?

## Contents

| File | What it is |
|---|---|
| `behavioral-eval-protocol.md` | The evaluation instrument: blinded, comparative (Anima ON vs OFF), with concrete scenarios, scoring rubrics, and zero-tolerance invariant probes. Run by a human evaluator. |
| `HEARTENGINE-CRITIQUE.md` | The design-rationale critique that shaped the architecture. Documents the gaps that had to be closed before code (veto-before-score, generalization, graduated initiation, encryption-from-day-one, …). Kept here so the protocol's references resolve and the rationale travels with the engine. |
| `runs/<date>/` | Per-run output: raw transcripts, filled scoring sheet, one-page findings. Accumulates into the engine's behavioural track record over time. |

## Principle

Negative results are committed too. If a build does not beat the
no-engine baseline on blind preference, that finding goes in the record
as plainly as a positive one. The research is only worth keeping if it
can say "this did not work yet."
