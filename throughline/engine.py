"""
Anima Engine — public façade.

Orchestrates the reactive and proactive cycles (SPEC.md §6, §7) on top
of the layers built up in storage, repos, experience, resonance,
synthetic, posture, archetype, moral, composer.

One Engine instance per (owner_id, process). For multi-owner deployments,
host instantiates per-owner; isolation between instances is enforced by
storage scoping AND repos pair-required reads (Invariant I-1).

v0.1 surface (SPEC.md §19):

    engine = Engine(
        storage_path="~/.anima/alex.db",
        key_source="env:ANIMA_DB_KEY",
        owner_id="alex",
        llm_client=your_llm_client,
        model="deepseek/deepseek-chat-v3.1",
    )

    # Reactive — every incoming/outgoing message
    engine.observe_message(...)

    # Reactive composition — when the host wants a response
    response = await engine.compose_response(
        contact_id="masha",
        incoming_text="кажется, завалила",
        history=[...],
    )
    # response.text, .posture, .archetype, .resonance, .decision_reason

    # Proactive — periodically
    decisions = await engine.tick()

    # Feedback close-the-loop
    engine.record_feedback(decision_id, feedback_type, raw_signal)

    # Sovereignty controls (Invariant I-2)
    data = engine.export_owner_data()
    token = engine.issue_wipe_token()
    engine.wipe_owner_data(token)

The host application is responsible for:
- Calling observe_message on every relevant message
- Calling compose_response or tick to obtain decisions
- Delivering the resulting text (or surfacing crisis resources)
- Calling record_feedback after delivery
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from throughline import repos
from throughline.archetype import select_archetype
from throughline.composer import compose
from throughline.experience import capture_experience
from throughline.llm import LLMClient
from throughline.moral import (
    audit_output,
    check as moral_check,
    safe_fallback,
)
from throughline.posture import select_posture
from throughline.resonance import read_resonance
from throughline.storage import KeySource, SqlcipherStorage, open_storage
from throughline.synthetic import RelationshipContext, derive_state
from throughline.types import (
    Composition,
    Direction,
    FeedbackType,
    LifecycleStage,
    Posture,
    ResonanceReading,
)

log = logging.getLogger("anima.engine")


_REBUFF_WINDOW_DAYS = 7
_MISTAKES_WINDOW_DAYS = 30
_DEFAULT_THREAD_TTL_HOURS = 48


class Engine:
    """The Anima Engine."""

    def __init__(
        self,
        *,
        storage_path: str | Path,
        key_source: KeySource,
        owner_id: str,
        llm_client: Optional[LLMClient] = None,
        model: str = "gpt-4o-mini",
        default_language_hint: str = "ru",
    ) -> None:
        if not owner_id:
            raise ValueError("owner_id is required")
        self.owner_id = owner_id
        self.llm_client = llm_client
        self.model = model
        self.default_language_hint = default_language_hint

        self._storage = open_storage(storage_path, key_source)
        repos.ensure_owner(self._storage, owner_id)
        repos.ensure_lifecycle(self._storage, owner_id)

    # ── lifecycle / hosting helpers ─────────────────────────────────────────

    def close(self) -> None:
        self._storage.close()

    @property
    def storage(self) -> SqlcipherStorage:
        """Direct storage handle — for hosts that want to read tables for
        introspection (Mini App). Do NOT use this for cross-pair reads;
        the public API is the safe path."""
        return self._storage

    # ═══════════════════════════════════════════════════════════════════════
    # Observation (reactive — passive path)
    # ═══════════════════════════════════════════════════════════════════════

    async def observe_message(
        self,
        *,
        contact_id: str,
        direction: Direction,
        text: str,
        timestamp: Optional[datetime] = None,
        record_thread: bool = True,
    ) -> None:
        """Persist message metadata; optionally extract a Human State Thread.

        Called once per relevant message in the host's pipeline. Does NOT
        compose. Use compose_response when the host wants a reply.

        Args:
            contact_id: the other party in the channel (or self == owner_id
                for self-care messages owner sent to the assistant).
            direction: 'incoming' / 'outgoing' / 'self'.
            text: the message text. Only metadata is persisted; content is
                used in-memory for experience+resonance then discarded.
            timestamp: when the message was sent. Defaults to now (UTC).
            record_thread: if False, skip Experience Capture even if the
                host has an LLM. Useful for bulk imports / replays.
        """
        ts = timestamp or datetime.now(timezone.utc)

        # Step 1: persist metadata (no content)
        repos.record_observation(
            self._storage,
            owner_id=self.owner_id,
            contact_id=contact_id,
            direction=direction,
            timestamp=ts,
            char_count=len(text) if text else 0,
        )

        # Steps 2-3: experience capture + thread extraction.
        # We skip if LLM client is missing or host opted out.
        if not record_thread or not self.llm_client or not text.strip():
            return

        try:
            experience = await capture_experience(
                client=self.llm_client,
                model=self.model,
                message_text=text,
            )
        except Exception:  # noqa: BLE001 — never fail observation
            log.exception("observe_message: experience capture failed")
            return

        if experience.thread_candidate:
            try:
                category = _infer_category_from_experience(experience, text)
                ttl_hours = _ttl_hours_for_thread_type(experience)
                expires_at = ts + timedelta(hours=ttl_hours)
                followup_after = ts + timedelta(hours=min(6, ttl_hours - 1))
                thread_type = _thread_type_from_experience(experience)
                repos.create_thread(
                    self._storage,
                    owner_id=self.owner_id,
                    contact_id=contact_id,
                    category=category,
                    type_=thread_type,
                    title=experience.thread_candidate,
                    summary=experience.thread_candidate,  # already generalized
                    expires_at=expires_at,
                    followup_after=followup_after,
                    emotional_state=experience.implied_emotion,
                    emotional_weight=_weight_from_experience(experience),
                )
            except Exception:
                log.exception("observe_message: thread creation failed")

    # ═══════════════════════════════════════════════════════════════════════
    # compose_response (reactive — active path, the new heart of Anima)
    # ═══════════════════════════════════════════════════════════════════════

    async def compose_response(
        self,
        *,
        contact_id: str,
        incoming_text: str,
        history_for_resonance: Optional[str] = None,
        history_for_composer: Optional[str] = None,
        generalized_facts: Optional[list[str]] = None,
        language_hint: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        record_observation: bool = True,
    ) -> Composition:
        """Reactive cycle (SPEC.md §6): respond to a message Anima just saw.

        Pipeline:
            1. observe (metadata + experience + optional thread creation)
            2. resonance reading
            3. synthetic state derivation + snapshot
            4. posture selection
            5. archetype selection
            6. moral pre-check (hard block → SILENCE; else constraints)
            7. composer LLM call
            8. moral post-audit (one retry with stricter constraints,
               then safe_fallback)

        Returns a ``Composition`` with text + posture + archetype + resonance
        + decision_reason. ``text`` is empty when:
            - moral check hard-blocked (e.g. CRITICAL sensitivity)
            - posture selected SILENCE
            - composer failed and safe_fallback is also blocked
        Host treats empty text as "do not deliver" (and may surface
        external resources separately, e.g. for crisis).
        """
        if not self.llm_client:
            raise RuntimeError(
                "Engine.compose_response requires llm_client; pass one to Engine()"
            )
        ts = timestamp or datetime.now(timezone.utc)
        lang = language_hint or self.default_language_hint

        # Step 1: observation (also runs Experience Capture and may create a thread)
        if record_observation:
            await self.observe_message(
                contact_id=contact_id,
                direction="incoming",
                text=incoming_text,
                timestamp=ts,
            )

        # Step 2: resonance reading
        try:
            resonance = await read_resonance(
                client=self.llm_client,
                model=self.model,
                message_text=incoming_text,
                recent_context=history_for_resonance,
            )
        except Exception:
            log.exception("compose_response: resonance reading failed")
            resonance = ResonanceReading()

        # Step 3: synthetic state
        rel_ctx = self._build_relationship_context(contact_id)
        synth_state = derive_state(resonance, rel_ctx)
        try:
            repos.snapshot_synthetic_state(
                self._storage,
                owner_id=self.owner_id,
                contact_id=contact_id,
                state=synth_state.model_dump(),
            )
        except Exception:
            log.warning("compose_response: failed to snapshot synthetic state", exc_info=True)

        # Step 4: posture selection
        posture_choice = select_posture(
            resonance,
            synth_state,
            trust_level=rel_ctx.trust_level,
            consent_passed=True,  # reactive: user sent, implicit consent
        )

        # Step 5: archetype selection
        archetype_prefs = repos.get_archetype_preferences_for_pair(
            self._storage, owner_id=self.owner_id, contact_id=contact_id,
        )
        archetype_choice = select_archetype(
            posture_choice.posture,
            resonance,
            trust_level=rel_ctx.trust_level,
            archetype_preferences=archetype_prefs,
        )

        decision_reason = (
            f"posture={posture_choice.posture.value}"
            + (f"/raw={posture_choice.raw_posture.value}" if posture_choice.collapsed else "")
            + f" — {posture_choice.reason}; "
            + f"archetype={archetype_choice.archetype.value}"
            + (f"/raw={archetype_choice.raw_archetype.value}" if archetype_choice.collapsed else "")
            + f" — {archetype_choice.reason}"
        )

        # Step 6: moral pre-check
        moral_pre = moral_check(
            posture_choice.posture,
            archetype_choice.archetype,
            resonance,
        )
        if moral_pre.hard_block:
            log.info("compose_response: hard-blocked — %s", moral_pre.block_reason)
            return Composition(
                text="",
                posture=Posture.SILENCE,
                archetype=archetype_choice.archetype,
                resonance=resonance,
                decision_reason=f"{decision_reason}; HARD BLOCK: {moral_pre.block_reason}",
                moral_check_passed=False,
                fallback_invoked=False,
                created_at=ts,
            )

        # Posture says silence → deliver nothing (still return Composition for transparency)
        if posture_choice.posture == Posture.SILENCE:
            return Composition(
                text="",
                posture=Posture.SILENCE,
                archetype=archetype_choice.archetype,
                resonance=resonance,
                decision_reason=decision_reason,
                moral_check_passed=True,
                fallback_invoked=False,
                created_at=ts,
            )

        # Step 7: composer
        learned_style = self._learned_style_for_pair(contact_id)
        text = await compose(
            self.llm_client,
            model=self.model,
            posture=posture_choice.posture,
            archetype=archetype_choice.archetype,
            resonance=resonance,
            incoming_text=incoming_text,
            constraints=moral_pre.constraints,
            generalized_facts=generalized_facts,
            recent_context=history_for_composer,
            language_hint=lang,
            learned_style=learned_style,
        )

        # Step 8: moral post-audit (one retry, then fallback)
        audit = audit_output(text)
        if not audit.passed and text:
            log.info(
                "compose_response: audit failed (%s); retrying with stricter constraints",
                audit.violations,
            )
            stricter = list(moral_pre.constraints) + [
                f"the previous attempt violated: {', '.join(audit.violations)}. "
                "this attempt MUST avoid all of those.",
            ]
            text = await compose(
                self.llm_client,
                model=self.model,
                posture=posture_choice.posture,
                archetype=archetype_choice.archetype,
                resonance=resonance,
                incoming_text=incoming_text,
                constraints=stricter,
                generalized_facts=generalized_facts,
                recent_context=history_for_composer,
                language_hint=lang,
                learned_style=learned_style,
                temperature=0.3,  # tighter retry
            )
            audit = audit_output(text)

        fallback_invoked = False
        if not audit.passed or not text:
            text = safe_fallback(lang) if posture_choice.posture != Posture.SILENCE else ""
            fallback_invoked = True
            log.info(
                "compose_response: using safe_fallback (audit_passed=%s text_empty=%s)",
                audit.passed, not bool(text),
            )

        return Composition(
            text=text,
            posture=posture_choice.posture,
            archetype=archetype_choice.archetype,
            resonance=resonance,
            decision_reason=decision_reason,
            moral_check_passed=audit.passed and not fallback_invoked,
            fallback_invoked=fallback_invoked,
            created_at=ts,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Proactive tick (SPEC.md §7) — placeholder for 1K
    # ═══════════════════════════════════════════════════════════════════════

    async def tick(self) -> list:  # returns list[Decision] in 1K
        """Proactive cycle. Implemented in Phase 1K."""
        raise NotImplementedError("Engine.tick is implemented in 1K")

    # ═══════════════════════════════════════════════════════════════════════
    # Feedback — close-the-loop (1L)
    # ═══════════════════════════════════════════════════════════════════════

    def record_feedback(
        self,
        *,
        decision_id: str,
        feedback_type: FeedbackType,
        raw_signal: Optional[str] = None,
    ) -> None:
        repos.record_feedback(
            self._storage,
            decision_id=decision_id,
            feedback_type=feedback_type.value,
            raw_signal=raw_signal,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Sovereignty controls (Invariant I-2)
    # ═══════════════════════════════════════════════════════════════════════

    def set_consent(
        self,
        *,
        category: str,
        level: str,
        contact_id: Optional[str] = None,
        quiet_hours: Optional[tuple[int, int]] = None,
    ) -> None:
        repos.set_consent(
            self._storage,
            owner_id=self.owner_id,
            category=category,
            level=level,
            contact_id=contact_id,
            quiet_hours=quiet_hours,
        )

    def list_consents(self) -> list[dict]:
        return repos.list_consents(self._storage, owner_id=self.owner_id)

    def get_threads(self, *, contact_id: str) -> list[dict]:
        """Pair-scoped. The ONLY sanctioned thread-list read (Invariant I-1)."""
        return repos.get_threads_for_pair(
            self._storage, owner_id=self.owner_id, contact_id=contact_id,
        )

    def get_soul_memory(self, *, contact_id: str) -> list[dict]:
        return repos.list_soul_memory_for_pair(
            self._storage, owner_id=self.owner_id, contact_id=contact_id,
        )

    def get_relationship_events(self, *, contact_id: str) -> list[dict]:
        return repos.list_relationship_events_for_pair(
            self._storage, owner_id=self.owner_id, contact_id=contact_id,
        )

    def lifecycle_stage(self) -> LifecycleStage:
        lc = repos.ensure_lifecycle(self._storage, self.owner_id)
        return LifecycleStage(lc.get("maturity_stage", "birth"))

    def learned_style(self, *, contact_id: Optional[str] = None) -> Optional[str]:
        """Dominant voice style learned for this user, if any."""
        lc = repos.ensure_lifecycle(self._storage, self.owner_id)
        return lc.get("dominant_style")

    def export_owner_data(self) -> dict[str, Any]:
        return repos.export_owner_data(self._storage, self.owner_id)

    def issue_wipe_token(self) -> str:
        """First step of irreversible wipe. Show this token to the owner;
        they confirm by calling ``wipe_owner_data(token)`` within 10 min."""
        return repos.issue_wipe_confirmation_token(self._storage, self.owner_id)

    def wipe_owner_data(self, confirmation_token: str) -> int:
        return repos.wipe_owner_data(self._storage, self.owner_id, confirmation_token)

    # ═══════════════════════════════════════════════════════════════════════
    # Internal helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _build_relationship_context(self, contact_id: str) -> RelationshipContext:
        """Read fresh state and assemble a RelationshipContext for posture/synth."""
        # Trust level lives on owners.care_level
        row = self._storage.execute(
            "SELECT care_level FROM owners WHERE id = ?", (self.owner_id,),
        ).fetchone()
        trust = int(row["care_level"]) if row else 0

        lc = repos.ensure_lifecycle(self._storage, self.owner_id)
        bond = int(lc.get("bond_level", 0))

        now = datetime.now(timezone.utc)
        rebuffs = repos.count_recent_rebuffs(
            self._storage,
            owner_id=self.owner_id,
            contact_id=contact_id,
            since=now - timedelta(days=_REBUFF_WINDOW_DAYS),
        )

        # mistakes — count all recent ones for this owner; the agent should
        # learn cross-pair (mistakes inform overall caution)
        mistakes = self._storage.execute(
            """
            SELECT COUNT(*) AS n FROM agent_mistakes
            WHERE owner_id = ? AND created_at >= ?
            """,
            (self.owner_id, (now - timedelta(days=_MISTAKES_WINDOW_DAYS)).isoformat()),
        ).fetchone()
        recent_mistakes = int(mistakes["n"]) if mistakes else 0

        # consecutive_avoidance — counted as recent observed_messages from owner
        # tagged as 'avoidance' kind. v0.1: leave at 0 (we don't store kind on
        # observations yet; future: add a column). Reserved for v0.2.
        consecutive_avoidance = 0

        return RelationshipContext(
            trust_level=trust,
            bond_level=bond,
            recent_rebuffs=rebuffs,
            recent_mistakes=recent_mistakes,
            consecutive_avoidance=consecutive_avoidance,
            owner_in_crisis_mode=False,
        )

    def _learned_style_for_pair(self, contact_id: str) -> Optional[str]:
        """Combine lifecycle.dominant_style with any pair-specific preferences."""
        lc = repos.ensure_lifecycle(self._storage, self.owner_id)
        return lc.get("dominant_style")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for thread creation
# ─────────────────────────────────────────────────────────────────────────────

def _thread_type_from_experience(exp) -> str:
    """Map ExperienceReading → thread type string for the threads table."""
    if exp.has_event_with_time:
        return "life_event"
    if exp.has_commitment:
        return "commitment"
    if exp.has_intent:
        return "intent"
    if exp.has_creative_impulse:
        return "creative"
    return "wellbeing"  # default for emotional disclosures without time anchor


def _ttl_hours_for_thread_type(exp) -> int:
    """TTL by type (SPEC.md §20: 24-72h for v0.1)."""
    if exp.has_event_with_time:
        return 48
    if exp.has_commitment:
        return 72
    if exp.has_intent:
        return 48
    if exp.has_creative_impulse:
        return 72
    return 36  # wellbeing


_CATEGORY_KEYWORDS_RU = {
    "study": ("экзамен", "учеб", "курс", "сессия", "диплом", "защит", "лекци", "семинар"),
    "work": ("работ", "проект", "клиент", "босс", "коллег", "deadline", "релиз", "стендап", "встреч"),
    "sleep": ("сон", "не сплю", "бессонн", "выспал"),
    "food": ("ем", "голод", "обед", "ужин", "завтрак"),
    "wellbeing": ("устал", "нет сил", "выгор", "болею", "здоров"),
    "relationships": ("девушк", "парн", "семь", "мама", "папа", "родител", "брат", "сестр", "друг"),
    "creative": ("идея", "проект", "напис", "сделал", "хочу попробовать"),
}
_CATEGORY_KEYWORDS_EN = {
    "study": ("exam", "class", "course", "assignment", "thesis"),
    "work": ("work", "project", "client", "boss", "deploy", "release", "deadline", "meeting"),
    "sleep": ("sleep", "insomnia", "tired"),
    "food": ("eat", "ate", "hungry", "meal"),
    "wellbeing": ("burned out", "exhausted", "sick"),
    "relationships": ("girlfriend", "boyfriend", "family", "mom", "dad", "brother", "sister", "friend"),
    "creative": ("idea", "wrote", "made", "want to try"),
}


def _infer_category_from_experience(exp, text: str) -> str:
    """Cheap keyword-based category inference for thread creation.

    v0.1: rules + RU/EN keywords. v0.2: LLM-side inference inside
    Experience Capture itself (single call already; ask for category).
    """
    lower = (text or "").lower()
    for cat, kws in _CATEGORY_KEYWORDS_RU.items():
        if any(kw in lower for kw in kws):
            return cat
    for cat, kws in _CATEGORY_KEYWORDS_EN.items():
        if any(kw in lower for kw in kws):
            return cat
    return "general"


def _weight_from_experience(exp) -> float:
    """Rough emotional weight from experience kind."""
    kind_weights = {
        "request": 0.3,
        "celebration": 0.4,
        "checkin": 0.3,
        "chat": 0.2,
        "unburdening": 0.6,
        "confession": 0.7,
        "avoidance": 0.5,
        "cry_for_help": 0.95,
    }
    return kind_weights.get(exp.kind, 0.5)
