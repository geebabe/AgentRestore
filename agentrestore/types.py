"""Shared types and enums for AgentRestore."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EffectKind(StrEnum):
    FILE = "file"
    DB = "db"
    API = "api"
    PROCESS = "process"
    UNKNOWN = "unknown"


class EffectStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


class DriftState(StrEnum):
    MATCHED = "matched"
    CHANGED = "changed"
    MISSING = "missing"
    NEW = "new"


@dataclass(frozen=True)
class FileRef:
    path: str
    hash_before: str | None = None
    hash_after: str | None = None
    size: int = 0


@dataclass(frozen=True)
class DbRef:
    backend: str
    entity: str
    entity_id: str
    before_hash: str | None = None
    after_hash: str | None = None


@dataclass(frozen=True)
class ApiRef:
    method: str
    endpoint: str
    request_hash: str | None = None
    response_hash: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class EffectEntry:
    checkpoint_id: str
    tool_name: str
    args_hash: str
    effect_kind: EffectKind
    effect_fingerprint: str
    status: EffectStatus = EffectStatus.PENDING
    file_refs: tuple[FileRef, ...] = ()
    db_refs: tuple[DbRef, ...] = ()
    api_refs: tuple[ApiRef, ...] = ()
    result_ref: str | None = None
    result_json: str | None = None
    ts: float = 0.0
    id: int | None = None


@dataclass(frozen=True)
class DriftFinding:
    path: str
    state: DriftState
    expected: str | None = None
    actual: str | None = None
    detail: str = ""


@dataclass
class DriftReport:
    checkpoint_id: str
    findings: list[DriftFinding] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return any(f.state is not DriftState.MATCHED for f in self.findings)

    @property
    def drift_count(self) -> int:
        return sum(1 for f in self.findings if f.state is not DriftState.MATCHED)


class DriftAlert(Exception):
    """Raised when environment drift is detected on resume."""

    def __init__(self, report: DriftReport) -> None:
        self.report = report
        super().__init__(self._message())

    def _message(self) -> str:
        return (
            f"Drift detected for checkpoint {self.report.checkpoint_id!r}: "
            f"{self.report.drift_count} finding(s)"
        )


__all__ = [
    "ApiRef",
    "DbRef",
    "DriftAlert",
    "DriftFinding",
    "DriftReport",
    "DriftState",
    "EffectEntry",
    "EffectKind",
    "EffectStatus",
    "FileRef",
]

# Re-export Any for convenience in downstream type hints without extra imports.
__any__ = Any
