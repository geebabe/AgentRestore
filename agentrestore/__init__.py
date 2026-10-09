"""AgentRestore: drift-aware resume middleware for agent frameworks."""

from .core import AgentRestore, AsyncAgentRestore, get_active
from .idempotent import IdempotencyAdapter, InterceptOutcome, InterceptResult
from .reconcile import DeterministicSummarizer, ReconciliationEngine, Summarizer
from .scanner import DriftScanner
from .store import JournalStore, SqliteJournalStore
from .types import (
    ApiRef,
    DbRef,
    DriftAlert,
    DriftFinding,
    DriftReport,
    DriftState,
    EffectEntry,
    EffectKind,
    EffectStatus,
    FileRef,
)

__version__ = "0.1.0"

__all__ = [
    "AgentRestore",
    "AsyncAgentRestore",
    "ApiRef",
    "DbRef",
    "DeterministicSummarizer",
    "DriftAlert",
    "DriftFinding",
    "DriftReport",
    "DriftScanner",
    "DriftState",
    "EffectEntry",
    "EffectKind",
    "EffectStatus",
    "FileRef",
    "IdempotencyAdapter",
    "InterceptOutcome",
    "InterceptResult",
    "JournalStore",
    "ReconciliationEngine",
    "SqliteJournalStore",
    "Summarizer",
    "get_active",
]
