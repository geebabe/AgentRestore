"""Persistence for the effect journal and drift reports."""

from __future__ import annotations

import json
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .types import (
    ApiRef,
    DbRef,
    DriftReport,
    EffectEntry,
    EffectKind,
    EffectStatus,
    FileRef,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS effect_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    args_hash TEXT NOT NULL,
    effect_kind TEXT NOT NULL,
    effect_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    result_ref TEXT,
    result_json TEXT,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_effect_checkpoint ON effect_entries(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_effect_lookup
    ON effect_entries(checkpoint_id, tool_name, args_hash);

CREATE TABLE IF NOT EXISTS file_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    effect_id INTEGER NOT NULL REFERENCES effect_entries(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    hash_before TEXT,
    hash_after TEXT,
    size INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_file_effect ON file_refs(effect_id);

CREATE TABLE IF NOT EXISTS db_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    effect_id INTEGER NOT NULL REFERENCES effect_entries(id) ON DELETE CASCADE,
    backend TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    before_hash TEXT,
    after_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_db_effect ON db_refs(effect_id);

CREATE TABLE IF NOT EXISTS api_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    effect_id INTEGER NOT NULL REFERENCES effect_entries(id) ON DELETE CASCADE,
    method TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_hash TEXT,
    response_hash TEXT,
    idempotency_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_api_effect ON api_refs(effect_id);

CREATE TABLE IF NOT EXISTS drift_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_id TEXT NOT NULL,
    ts REAL NOT NULL,
    summary_json TEXT NOT NULL,
    injected_observation TEXT
);
CREATE INDEX IF NOT EXISTS idx_drift_checkpoint ON drift_reports(checkpoint_id);
"""


class JournalStore(ABC):
    """Storage backend for the effect journal and drift reports."""

    @abstractmethod
    def add_effect(self, entry: EffectEntry) -> int:
        """Persist an effect entry and its refs; return its assigned id."""

    @abstractmethod
    def get_effects(self, checkpoint_id: str) -> list[EffectEntry]:
        """Return all effect entries for a checkpoint, in insertion order."""

    @abstractmethod
    def get_file_refs(self, checkpoint_id: str) -> list[FileRef]:
        """Return all file refs for a checkpoint, in insertion order."""

    @abstractmethod
    def record_drift(self, report: DriftReport, observation: str | None = None) -> int:
        """Persist a drift report; return its assigned id."""

    @abstractmethod
    def close(self) -> None:
        """Close the underlying connection."""


class SqliteJournalStore(JournalStore):
    """SQLite-backed journal store (WAL mode)."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- writes -----------------------------------------------------------
    def add_effect(self, entry: EffectEntry) -> int:
        cur = self._conn.execute(
            "INSERT INTO effect_entries "
            "(checkpoint_id, tool_name, args_hash, effect_kind, effect_fingerprint, "
            " status, result_ref, result_json, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.checkpoint_id,
                entry.tool_name,
                entry.args_hash,
                entry.effect_kind.value,
                entry.effect_fingerprint,
                entry.status.value,
                entry.result_ref,
                entry.result_json,
                entry.ts,
            ),
        )
        effect_id = int(cur.lastrowid) if cur.lastrowid is not None else 0
        for fref in entry.file_refs:
            self._conn.execute(
                "INSERT INTO file_refs (effect_id, path, hash_before, hash_after, size) "
                "VALUES (?, ?, ?, ?, ?)",
                (effect_id, fref.path, fref.hash_before, fref.hash_after, fref.size),
            )
        for dref in entry.db_refs:
            self._conn.execute(
                "INSERT INTO db_refs (effect_id, backend, entity, entity_id, "
                "before_hash, after_hash) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    effect_id,
                    dref.backend,
                    dref.entity,
                    dref.entity_id,
                    dref.before_hash,
                    dref.after_hash,
                ),
            )
        for aref in entry.api_refs:
            self._conn.execute(
                "INSERT INTO api_refs (effect_id, method, endpoint, request_hash, "
                "response_hash, idempotency_key) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    effect_id,
                    aref.method,
                    aref.endpoint,
                    aref.request_hash,
                    aref.response_hash,
                    aref.idempotency_key,
                ),
            )
        self._conn.commit()
        return effect_id

    def record_drift(self, report: DriftReport, observation: str | None = None) -> int:
        summary = json.dumps([asdict(f) for f in report.findings])
        cur = self._conn.execute(
            "INSERT INTO drift_reports (checkpoint_id, ts, summary_json, injected_observation) "
            "VALUES (?, ?, ?, ?)",
            (report.checkpoint_id, time.time(), summary, observation),
        )
        self._conn.commit()
        return int(cur.lastrowid) if cur.lastrowid is not None else 0

    # -- reads ------------------------------------------------------------
    def get_effects(self, checkpoint_id: str) -> list[EffectEntry]:
        rows = self._conn.execute(
            "SELECT * FROM effect_entries WHERE checkpoint_id = ? ORDER BY id",
            (checkpoint_id,),
        ).fetchall()
        out: list[EffectEntry] = []
        for row in rows:
            out.append(
                EffectEntry(
                    id=row["id"],
                    checkpoint_id=row["checkpoint_id"],
                    tool_name=row["tool_name"],
                    args_hash=row["args_hash"],
                    effect_kind=EffectKind(row["effect_kind"]),
                    effect_fingerprint=row["effect_fingerprint"],
                    status=EffectStatus(row["status"]),
                    file_refs=tuple(self._file_refs(row["id"])),
                    db_refs=tuple(self._db_refs(row["id"])),
                    api_refs=tuple(self._api_refs(row["id"])),
                    result_ref=row["result_ref"],
                    result_json=row["result_json"],
                    ts=row["ts"],
                )
            )
        return out

    def get_file_refs(self, checkpoint_id: str) -> list[FileRef]:
        rows = self._conn.execute(
            "SELECT fr.* FROM file_refs fr "
            "JOIN effect_entries e ON fr.effect_id = e.id "
            "WHERE e.checkpoint_id = ? ORDER BY fr.id",
            (checkpoint_id,),
        ).fetchall()
        return [self._row_to_file_ref(r) for r in rows]

    # -- helpers ----------------------------------------------------------
    def _file_refs(self, effect_id: int) -> list[FileRef]:
        rows = self._conn.execute(
            "SELECT * FROM file_refs WHERE effect_id = ? ORDER BY id", (effect_id,)
        ).fetchall()
        return [self._row_to_file_ref(r) for r in rows]

    def _db_refs(self, effect_id: int) -> list[DbRef]:
        rows = self._conn.execute(
            "SELECT * FROM db_refs WHERE effect_id = ? ORDER BY id", (effect_id,)
        ).fetchall()
        return [
            DbRef(
                backend=r["backend"],
                entity=r["entity"],
                entity_id=r["entity_id"],
                before_hash=r["before_hash"],
                after_hash=r["after_hash"],
            )
            for r in rows
        ]

    def _api_refs(self, effect_id: int) -> list[ApiRef]:
        rows = self._conn.execute(
            "SELECT * FROM api_refs WHERE effect_id = ? ORDER BY id", (effect_id,)
        ).fetchall()
        return [
            ApiRef(
                method=r["method"],
                endpoint=r["endpoint"],
                request_hash=r["request_hash"],
                response_hash=r["response_hash"],
                idempotency_key=r["idempotency_key"],
            )
            for r in rows
        ]

    @staticmethod
    def _row_to_file_ref(row: Any) -> FileRef:
        return FileRef(
            path=row["path"],
            hash_before=row["hash_before"],
            hash_after=row["hash_after"],
            size=row["size"],
        )

    def close(self) -> None:
        self._conn.close()
