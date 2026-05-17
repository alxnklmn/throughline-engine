"""
Throughline Engine — public façade.

This is the v0.1 MVP scope (SPEC.md §14):
- After Event Care pattern only
- Direct Message initiation only
- Veto layer enforced
- Short-lived threads (24-72h)
- Feedback loop active
- Per-relationship isolation at storage API

Most internals are stubbed and marked TODO; this file defines the contract
that the rest of the package implements against.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from throughline.types import (
    CategoryConsent,
    Decision,
    Direction,
    FeedbackType,
    Thread,
)


class Engine:
    """The Throughline Engine.

    One instance per owner. For multi-owner deployments, instantiate per-owner
    with strict isolation between instances (see SPEC.md §9, Invariant I-1).

    Args:
        storage_path: Path to the SQLite (SQLCipher) database.
        encryption_key_source: Either "keychain" to pull from OS keychain,
            or a callable returning the key bytes.
        owner_id: The owner this engine serves.
        llm_client: Optional LLM client for generalization and composition.
            If None, the engine operates in "veto-only" mode and produces
            no messages (useful for testing the decision layer).
    """

    def __init__(
        self,
        storage_path: str | Path,
        encryption_key_source: str | callable,
        owner_id: str,
        llm_client: Optional[object] = None,
    ) -> None:
        self.storage_path = Path(storage_path).expanduser()
        self.owner_id = owner_id
        self.llm_client = llm_client
        # TODO(v0.1): initialize SQLCipher storage layer
        # TODO(v0.1): load owner consent
        # TODO(v0.1): wire extractor, veto chain, scorer, generalizer, composer

    # ─────────────────────────────────────────────────────────────────
    # Observation — feed events into the engine
    # ─────────────────────────────────────────────────────────────────

    def observe_message(
        self,
        owner_id: str,
        contact_id: str,
        direction: Direction,
        text: str,
        timestamp: datetime,
        message_id: Optional[str] = None,
    ) -> None:
        """Record a message and potentially extract a thread.

        This is called once per message in the host application's message
        pipeline. The engine decides whether to create a Human State Thread.

        Per-relationship isolation: the (owner_id, contact_id) pair scopes
        all derived threads. No information learned here ever crosses to
        another contact's channel.
        """
        # TODO(v0.1): persist message metadata (not content) for tempo learning
        # TODO(v0.1): run Extraction Layer; if thread detected, persist with
        #             strict (owner_id, contact_id) scoping
        raise NotImplementedError("v0.1 stub")

    # ─────────────────────────────────────────────────────────────────
    # Initiative — poll for decisions
    # ─────────────────────────────────────────────────────────────────

    def tick(self, owner_id: str) -> list[Decision]:
        """Evaluate all open threads for the owner; return decisions.

        Hosts call this on a schedule (every 5-15 minutes is typical).
        Returns a list of Decision objects. SILENCE decisions are usually
        not returned but ARE logged internally for Silence Correctness
        metric computation.

        v0.1: only one DIRECT_MESSAGE decision returned per tick at most
        (multi-thread composition is v0.3+).
        """
        # TODO(v0.1): query open threads for this owner
        # TODO(v0.1): for each thread, run evaluator (vetoes → multipliers → score)
        # TODO(v0.1): pick top-1, compose if direct, return
        raise NotImplementedError("v0.1 stub")

    # ─────────────────────────────────────────────────────────────────
    # Feedback — close the learning loop
    # ─────────────────────────────────────────────────────────────────

    def record_feedback(
        self,
        decision_id: str,
        feedback_type: FeedbackType,
        raw_signal: Optional[str] = None,
    ) -> None:
        """Record owner reaction to a delivered initiative.

        Mandatory call after any user-visible initiative. Without it, the
        engine cannot calibrate and degrades over time. See SPEC.md §12.
        """
        # TODO(v0.1): persist feedback; update thread status; adjust trust
        raise NotImplementedError("v0.1 stub")

    # ─────────────────────────────────────────────────────────────────
    # Owner controls — sovereignty (Invariant I-2)
    # ─────────────────────────────────────────────────────────────────

    def set_consent(
        self,
        owner_id: str,
        category: str,
        level: CategoryConsent,
        contact_id: Optional[str] = None,
        quiet_hours: Optional[tuple[int, int]] = None,
    ) -> None:
        """Grant or modify consent for a category.

        If `contact_id` is None, the consent applies to self-directed care.
        """
        raise NotImplementedError("v0.1 stub")

    def get_threads(
        self,
        owner_id: str,
        contact_id: str,
    ) -> list[Thread]:
        """Return all threads in the (owner_id, contact_id) channel.

        This is the ONLY sanctioned read path. There is intentionally no
        `get_all_threads_for_owner` method — enforcing isolation at the API.
        """
        raise NotImplementedError("v0.1 stub")

    def export_owner_data(self, owner_id: str) -> dict:
        """Full export of all data about the owner. Invariant I-2."""
        raise NotImplementedError("v0.1 stub")

    def wipe_owner_data(
        self,
        owner_id: str,
        confirmation_token: str,
    ) -> None:
        """Irreversible wipe of all data about the owner. Invariant I-2.

        `confirmation_token` must match a token obtained via a separate
        explicit consent call. Two-step to prevent accidents.
        """
        raise NotImplementedError("v0.1 stub")
