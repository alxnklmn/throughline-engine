"""
Storage layer for Anima — SQLCipher only.

Invariant I-3 (SPEC.md §3) makes encryption at rest non-negotiable:

> *Care/Soul data contains the user's emotional patterns, vulnerabilities,
> anxieties, personal questions. All tables managed by Anima MUST be
> encrypted at rest (SQLCipher or equivalent), key held in OS-secure
> storage. Plaintext storage is not a valid configuration.*

This module exposes a single backend: ``SqlcipherStorage``. There is
deliberately no plain-sqlite fallback — any "for testing" workaround is
exactly the door an attacker would push on. Tests use SQLCipher too, with
a deterministic key from a fixture.

Public API:

    storage = open_storage(
        path="~/.anima/state.db",
        key_source="env:ANIMA_DB_KEY",
    )
    storage.init_schema()
    storage.set_consent(...)
    ...
    storage.close()

The ``key_source`` argument resolves the encryption key:

- ``"env:VAR_NAME"`` — read from environment variable
- ``"keychain:service"`` — read from OS keychain (macOS/Linux Secret Service)
- ``"file:/path/to/key"`` — read from a file (mode 0600 enforced)
- a callable returning ``bytes`` — fully custom

Returned key MUST be at least 32 bytes (256-bit). Shorter keys raise
``WeakKeyError`` to prevent foot-guns.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Union

# SQLCipher is imported LAZILY in _load_sqlcipher() — that way importing
# throughline.storage at module load works on developer machines without
# libsqlcipher installed (so the Heart core type/veto/scoring code can be
# tested in isolation). The error is raised when an actual encrypted DB is
# opened, with full install instructions — not at import time.
#
# Two backends supported, tried in this order:
#   1. sqlcipher3-binary — recommended (precompiled wheel, no gcc needed)
#   2. pysqlcipher3 — legacy fallback (source-only, requires libsqlcipher-dev
#      + gcc at install time; last PyPI release was 2018 and it does not
#      build on Python 3.12). Kept for backwards compatibility with existing
#      installs.
# Both expose the same DB-API 2.0 interface so the rest of this module is
# backend-agnostic.
_sqlcipher = None


def _load_sqlcipher():
    """Import SQLCipher backend on first use. Raises with install hints if missing.

    Tries sqlcipher3-binary first (no compilation needed), falls back to
    pysqlcipher3. Either provides the same DB-API 2.0 surface that this
    module uses.
    """
    global _sqlcipher
    if _sqlcipher is not None:
        return _sqlcipher
    # 1. Try the modern, precompiled sqlcipher3 wheel.
    try:
        from sqlcipher3 import dbapi2 as sqlcipher  # type: ignore[import-untyped]
        _sqlcipher = sqlcipher
        return sqlcipher
    except ImportError:
        pass
    # 2. Fall back to legacy pysqlcipher3.
    try:
        from pysqlcipher3 import dbapi2 as sqlcipher  # type: ignore[import-untyped]
        _sqlcipher = sqlcipher
        return sqlcipher
    except ImportError as exc:
        raise ImportError(
            "Anima requires SQLCipher at runtime (Invariant I-3, SPEC.md §3). "
            "Install ONE of:\n"
            "  pip install sqlcipher3-binary  # recommended — precompiled wheel\n"
            "  pip install pysqlcipher3       # legacy — needs libsqlcipher-dev + gcc\n"
            "On macOS, the binary wheel works out of the box; if you must use "
            "pysqlcipher3, `brew install sqlcipher` first.\n"
            "On Debian/Ubuntu, sqlcipher3-binary needs no system deps; "
            "pysqlcipher3 needs `apt install libsqlcipher-dev`.\n"
            "Plaintext SQLite is NOT a valid Anima configuration."
        ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────────────

class StorageError(Exception):
    """Base for all storage-layer errors."""


class WeakKeyError(StorageError):
    """Raised when the encryption key is too short to be safe."""


class KeySourceError(StorageError):
    """Raised when the key_source cannot be resolved."""


class IsolationViolation(StorageError):
    """Raised if a query attempts to cross channel boundaries (I-1)."""


# ─────────────────────────────────────────────────────────────────────────────
# Key resolution
# ─────────────────────────────────────────────────────────────────────────────

KeySource = Union[str, Callable[[], bytes]]

_MIN_KEY_BYTES = 32  # 256 bits


def resolve_key(source: KeySource) -> bytes:
    """Turn a ``key_source`` (string scheme or callable) into raw key bytes.

    Raises ``KeySourceError`` if the source cannot be resolved,
    ``WeakKeyError`` if the resolved key is shorter than 32 bytes.
    """
    if callable(source):
        try:
            key = source()
        except Exception as exc:  # noqa: BLE001 — user-provided callable
            raise KeySourceError(f"key callable raised: {exc!r}") from exc
        if not isinstance(key, (bytes, bytearray)):
            raise KeySourceError(
                f"key callable must return bytes, got {type(key).__name__}"
            )
        key = bytes(key)
    elif isinstance(source, str):
        scheme, _, rest = source.partition(":")
        if not rest:
            raise KeySourceError(
                f"key_source string must be 'scheme:value', got {source!r}"
            )
        if scheme == "env":
            value = os.environ.get(rest)
            if not value:
                raise KeySourceError(f"env var {rest!r} not set or empty")
            key = value.encode("utf-8")
        elif scheme == "file":
            path = Path(rest).expanduser()
            if not path.exists():
                raise KeySourceError(f"key file {path} does not exist")
            st = path.stat()
            # Enforce 0600 / 0400 on the key file. Group/other readable is unsafe.
            if st.st_mode & (stat.S_IRGRP | stat.S_IROTH | stat.S_IWGRP | stat.S_IWOTH):
                raise KeySourceError(
                    f"key file {path} has unsafe permissions "
                    f"(must be readable only by owner; chmod 600)"
                )
            key = path.read_bytes().strip()
        elif scheme == "keychain":
            # Optional dependency: keyring. We don't import at module load
            # because it pulls in dbus on Linux which is overkill for many deps.
            try:
                import keyring  # type: ignore[import-untyped]
            except ImportError as exc:
                raise KeySourceError(
                    "keychain key_source requires the optional `keyring` "
                    "dependency: pip install keyring"
                ) from exc
            value = keyring.get_password("anima", rest)
            if not value:
                raise KeySourceError(
                    f"keychain entry anima/{rest} not found"
                )
            key = value.encode("utf-8")
        else:
            raise KeySourceError(
                f"unknown key_source scheme {scheme!r} "
                "(expected env: / file: / keychain: or a callable)"
            )
    else:
        raise KeySourceError(
            f"key_source must be str or callable, got {type(source).__name__}"
        )

    if len(key) < _MIN_KEY_BYTES:
        raise WeakKeyError(
            f"encryption key is {len(key)} bytes; minimum is {_MIN_KEY_BYTES} "
            "(256 bits). Generate one with: python -c "
            "'import secrets; print(secrets.token_hex(32))'"
        )
    return key


# ─────────────────────────────────────────────────────────────────────────────
# Schema (Heart + Soul, mirrors SPEC.md §8 + §18)
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA_STATEMENTS = [
    # Schema version table — first to allow future migrations
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    # ── Heart core ──────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS owners (
        id               TEXT PRIMARY KEY,
        created_at       TIMESTAMP NOT NULL,
        proactivity_mode TEXT NOT NULL DEFAULT 'silent',
        care_level       INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS consent (
        owner_id          TEXT NOT NULL,
        contact_id        TEXT,                       -- NULL = self-directed care
        category          TEXT NOT NULL,
        level             TEXT NOT NULL,              -- denied|task|event|wellbeing|full
        quiet_hours_start INTEGER,
        quiet_hours_end   INTEGER,
        updated_at        TIMESTAMP NOT NULL,
        PRIMARY KEY (owner_id, contact_id, category)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS threads (
        id                  TEXT PRIMARY KEY,
        owner_id            TEXT NOT NULL,
        contact_id          TEXT NOT NULL,            -- isolation pair component
        category            TEXT NOT NULL,
        type                TEXT NOT NULL,
        title               TEXT NOT NULL,
        summary             TEXT NOT NULL,
        emotional_state     TEXT,
        emotional_weight    REAL DEFAULT 0.5,
        sensitivity         TEXT NOT NULL DEFAULT 'medium',
        importance          REAL DEFAULT 0.5,
        source_message_id   TEXT,
        followup_after      TIMESTAMP,
        expires_at          TIMESTAMP NOT NULL,
        max_attempts        INTEGER DEFAULT 1,
        attempts_count      INTEGER DEFAULT 0,
        last_attempt_at     TIMESTAMP,
        status              TEXT NOT NULL DEFAULT 'open',
        created_at          TIMESTAMP NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_threads_isolation ON threads(owner_id, contact_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_threads_followup ON threads(status, followup_after)",
    """
    CREATE TABLE IF NOT EXISTS care_decisions (
        id                  TEXT PRIMARY KEY,
        thread_id           TEXT NOT NULL,
        care_score          REAL NOT NULL,
        initiation_level    TEXT NOT NULL,
        decision_reason     TEXT,
        veto_triggered      TEXT,
        posture             TEXT,
        archetype           TEXT,
        composed_message    TEXT,
        delivered_at        TIMESTAMP,
        created_at          TIMESTAMP NOT NULL,
        FOREIGN KEY (thread_id) REFERENCES threads(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feedback (
        id            TEXT PRIMARY KEY,
        decision_id   TEXT NOT NULL,
        feedback_type TEXT NOT NULL,
        raw_signal    TEXT,
        created_at    TIMESTAMP NOT NULL,
        FOREIGN KEY (decision_id) REFERENCES care_decisions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id         TEXT PRIMARY KEY,
        owner_id   TEXT NOT NULL,
        contact_id TEXT,
        action     TEXT NOT NULL,
        detail     TEXT,
        created_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS observed_messages (
        id           TEXT PRIMARY KEY,
        owner_id     TEXT NOT NULL,
        contact_id   TEXT NOT NULL,
        direction    TEXT NOT NULL,
        timestamp    TIMESTAMP NOT NULL,
        char_count   INTEGER,                          -- metadata only
        sentiment    TEXT
        -- intentionally NO content column: only metadata for tempo learning
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_observed_pair_time ON observed_messages(owner_id, contact_id, timestamp)",
    # ── Soul layer ──────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS agent_lifecycle (
        owner_id           TEXT PRIMARY KEY,
        birth_at           TIMESTAMP NOT NULL,
        maturity_stage     TEXT NOT NULL DEFAULT 'birth',
        bond_level         INTEGER DEFAULT 0,
        dominant_style     TEXT,
        last_reflection_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS soul_memory (
        id                TEXT PRIMARY KEY,
        owner_id          TEXT NOT NULL,
        contact_id        TEXT NOT NULL,
        memory_type       TEXT NOT NULL,
        summary           TEXT NOT NULL,
        emotional_weight  REAL DEFAULT 0.5,
        lesson            TEXT,
        persistence_level TEXT NOT NULL DEFAULT 'durable',
        created_at        TIMESTAMP NOT NULL,
        expires_at        TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_soul_isolation ON soul_memory(owner_id, contact_id)",
    """
    CREATE TABLE IF NOT EXISTS relationship_events (
        id               TEXT PRIMARY KEY,
        owner_id         TEXT NOT NULL,
        contact_id       TEXT NOT NULL,
        event_type       TEXT NOT NULL,
        user_state       TEXT,
        agent_role       TEXT,
        response_posture TEXT,
        outcome          TEXT,
        notes            TEXT,
        created_at       TIMESTAMP NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_rel_events_pair ON relationship_events(owner_id, contact_id, created_at)",
    """
    CREATE TABLE IF NOT EXISTS agent_mistakes (
        id              TEXT PRIMARY KEY,
        owner_id        TEXT NOT NULL,
        contact_id      TEXT,
        mistake_summary TEXT NOT NULL,
        user_feedback   TEXT,
        lesson          TEXT NOT NULL,
        behavior_update TEXT NOT NULL,
        created_at      TIMESTAMP NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_mistakes_owner ON agent_mistakes(owner_id, created_at)",
    """
    CREATE TABLE IF NOT EXISTS archetype_preferences (
        owner_id            TEXT NOT NULL,
        contact_id          TEXT NOT NULL,
        archetype           TEXT NOT NULL,
        allowed             INTEGER NOT NULL DEFAULT 1,
        trust_required      INTEGER NOT NULL DEFAULT 0,
        last_used_at        TIMESTAMP,
        effectiveness_score REAL NOT NULL DEFAULT 0.5,
        PRIMARY KEY (owner_id, contact_id, archetype)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS synthetic_feeling_snapshots (
        id                TEXT PRIMARY KEY,
        owner_id          TEXT NOT NULL,
        contact_id        TEXT,
        concern           REAL,
        tenderness        REAL,
        protectiveness    REAL,
        honesty           REAL,
        patience          REAL,
        restraint         REAL,
        faith             REAL,
        challenge_impulse REAL,
        created_at        TIMESTAMP NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_synth_owner_time ON synthetic_feeling_snapshots(owner_id, created_at)",
]

_CURRENT_SCHEMA_VERSION = "1"


# ─────────────────────────────────────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────────────────────────────────────

class SqlcipherStorage:
    """SQLCipher-backed storage. Single mandatory backend.

    Per Invariant I-3, this is the only valid Anima storage. There is no
    plain-sqlite fallback by design — the absence of a backdoor IS the
    security property.

    Args:
        path: Filesystem path to the database file.
        key_source: How to resolve the encryption key. See module docstring.
        kdf_iter: SQLCipher KDF iteration count. SQLCipher 4 default is
            256000; we expose it for tests that want faster setup.
    """

    def __init__(
        self,
        path: Union[str, Path],
        key_source: KeySource,
        *,
        kdf_iter: int = 256000,
    ) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._key = resolve_key(key_source)
        self._kdf_iter = kdf_iter
        self._conn = self._open()
        # Restrict file perms — even though file is encrypted, leaking the
        # ciphertext to other local users is worse than not.
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            # On some FS (network mounts) chmod may fail; not fatal but log.
            pass

    # ── connection management ───────────────────────────────────────────────

    def _open(self):
        sqlcipher = _load_sqlcipher()
        conn = sqlcipher.connect(str(self.path), isolation_level=None)
        conn.row_factory = sqlcipher.Row
        cur = conn.cursor()
        # Set the key. SQLCipher requires PRAGMA key BEFORE any other operation.
        # We pass the key as a hex blob if it looks like hex, else as a passphrase.
        # Passphrase route lets the KDF iterate; hex route is direct-set.
        key_str = self._key.decode("utf-8", errors="replace")
        if all(c in "0123456789abcdefABCDEF" for c in key_str) and len(key_str) == 64:
            cur.execute(f"PRAGMA key = \"x'{key_str}'\"")
        else:
            # Treat as passphrase. Escape any single-quotes in the key.
            safe = key_str.replace("'", "''")
            cur.execute(f"PRAGMA key = '{safe}'")
        cur.execute(f"PRAGMA kdf_iter = {self._kdf_iter}")
        cur.execute("PRAGMA cipher_page_size = 4096")
        cur.execute("PRAGMA cipher_memory_security = ON")
        # Validate by reading one byte of header. If the key is wrong this
        # raises with a "file is not a database" message.
        try:
            cur.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except sqlcipher.DatabaseError as exc:
            raise StorageError(
                f"failed to open encrypted database at {self.path} — "
                "key likely incorrect"
            ) from exc
        return conn

    @property
    def _sqlcipher_module(self):
        """Loaded pysqlcipher3 module — for callers needing Row / exceptions."""
        return _load_sqlcipher()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> "SqlcipherStorage":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── schema ──────────────────────────────────────────────────────────────

    def init_schema(self) -> None:
        """Idempotently create all tables and indices."""
        cur = self._conn.cursor()
        for stmt in _SCHEMA_STATEMENTS:
            cur.execute(stmt)
        cur.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
            (_CURRENT_SCHEMA_VERSION,),
        )

    def schema_version(self) -> Optional[str]:
        sqlcipher = _load_sqlcipher()
        cur = self._conn.cursor()
        try:
            row = cur.execute(
                "SELECT value FROM schema_meta WHERE key = 'version'"
            ).fetchone()
            return row["value"] if row else None
        except sqlcipher.OperationalError:
            return None

    # ── isolation guard helpers (Invariant I-1) ─────────────────────────────

    @staticmethod
    def _require_pair(owner_id: str, contact_id: Optional[str]) -> None:
        """Reject queries that look like cross-channel reads.

        Most read paths require BOTH owner_id and contact_id. ``None`` for
        contact_id is allowed ONLY for explicitly self-directed paths.
        Callers that legitimately need self-care must pass an explicit
        sentinel (the same owner_id) rather than None.
        """
        if not owner_id:
            raise IsolationViolation("owner_id is required for every query")
        if contact_id is not None and contact_id == "":
            raise IsolationViolation(
                "contact_id must be a non-empty string or None (self-care)"
            )

    # ── raw access (for tests + advanced callers) ───────────────────────────

    def execute(self, sql: str, params: tuple = ()):
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql: str, seq: list):
        cur = self._conn.cursor()
        cur.executemany(sql, seq)
        return cur


# ─────────────────────────────────────────────────────────────────────────────
# Convenience top-level
# ─────────────────────────────────────────────────────────────────────────────

def open_storage(
    path: Union[str, Path],
    key_source: KeySource,
    *,
    kdf_iter: int = 256000,
) -> SqlcipherStorage:
    """Open and initialize an encrypted Anima database in one call."""
    storage = SqlcipherStorage(path, key_source, kdf_iter=kdf_iter)
    storage.init_schema()
    return storage
