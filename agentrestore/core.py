"""AgentRestore context managers and public orchestration API."""

from __future__ import annotations

import contextvars
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .idempotent import IdempotencyAdapter, InterceptResult
from .journal import Journal, diff_trees
from .reconcile import ReconciliationEngine
from .scanner import DriftScanner
from .store import JournalStore, SqliteJournalStore
from .types import DriftAlert, DriftReport, EffectEntry

_active: contextvars.ContextVar[AgentRestoreBase | None] = contextvars.ContextVar(
    "agentrestore_active", default=None
)


def get_active() -> AgentRestoreBase | None:
    """Return the AgentRestore instance active in the current task context, if any."""
    return _active.get()


class AgentRestoreBase:
    """Shared logic for the sync and async context managers."""

    def __init__(
        self,
        checkpoint_id: str,
        watch_paths: Iterable[str] = (),
        store: JournalStore | str | Path | None = None,
        *,
        reconcile_on_resume: bool = False,
    ) -> None:
        self.checkpoint_id = checkpoint_id
        self.watch_paths = list(watch_paths)
        self._store_arg = store
        self._store: JournalStore | None = None
        self._journal: Journal | None = None
        self._owns_store = not isinstance(store, JournalStore)
        self._before: dict[str, str] = {}
        self._token: contextvars.Token[AgentRestoreBase | None] | None = None
        self.reconcile_on_resume = reconcile_on_resume
        self.last_report: DriftReport | None = None
        self.observation: str | None = None

    # -- lifecycle helpers -------------------------------------------------
    def _make_store(self) -> JournalStore:
        if isinstance(self._store_arg, JournalStore):
            self._owns_store = False
            return self._store_arg
        self._owns_store = True
        path = (
            self._store_arg
            if self._store_arg is not None
            else f"agentrestore-{self.checkpoint_id}.db"
        )
        return SqliteJournalStore(path)

    def _ensure_open(self) -> None:
        if self._store is None:
            self._store = self._make_store()
            self._journal = Journal(self._store, self.checkpoint_id)

    def _scan_and_alert(self) -> None:
        report = DriftScanner(self.store).scan(self.checkpoint_id, self.watch_paths or None)
        self.last_report = report
        if report.has_drift:
            if self.reconcile_on_resume:
                self.observation = ReconciliationEngine().reconcile(report)
            raise DriftAlert(report)

    def _begin(self) -> None:
        self._ensure_open()
        self._scan_and_alert()
        self._before = self.journal.snapshot(self.watch_paths)
        self._token = _active.set(self)

    def _end(self, exc_type: type[BaseException] | None) -> None:
        try:
            if self._token is not None:
                _active.reset(self._token)
                self._token = None
            if exc_type is None and self._journal is not None:
                after = self._journal.snapshot(self.watch_paths)
                refs = diff_trees(self._before, after)
                if refs:
                    self._journal.record(tool_name="__watch__", file_refs=refs)
        finally:
            if self._owns_store and self._store is not None:
                self._store.close()
                self._store = None

    # -- properties --------------------------------------------------------
    @property
    def store(self) -> JournalStore:
        self._ensure_open()
        assert self._store is not None
        return self._store

    @property
    def journal(self) -> Journal:
        self._ensure_open()
        assert self._journal is not None
        return self._journal

    # -- public API --------------------------------------------------------
    def journal_file_change(
        self,
        path: str,
        tool_name: str = "file",
        args: Any = None,
        result: Any = None,
    ) -> EffectEntry:
        """Explicitly journal a single file's change."""
        return self.journal.record_file_change(path, tool_name=tool_name, args=args, result=result)

    def scan(self) -> DriftReport:
        """Scan for drift without raising."""
        return DriftScanner(self.store).scan(self.checkpoint_id, self.watch_paths or None)

    def reconcile(self, report: DriftReport | None = None) -> str | None:
        """Return the synthetic observation for a report (or the latest scan)."""
        rep = report if report is not None else (self.last_report or self.scan())
        return ReconciliationEngine().reconcile(rep)

    def intercept(self, tool_name: str, args: Any) -> InterceptResult:
        """Check whether a tool call should be replayed, executed, or is ambiguous."""
        return IdempotencyAdapter(self.store, self.checkpoint_id).intercept(tool_name, args)

    def close(self) -> None:
        """Close the store if it is open."""
        if self._store is not None:
            self._store.close()
            self._store = None


class AgentRestore(AgentRestoreBase):
    """Synchronous drift-aware resume context manager."""

    def __enter__(self) -> AgentRestore:
        self._begin()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        self._end(exc_type)


class AsyncAgentRestore(AgentRestoreBase):
    """Async drift-aware resume context manager.

    Note: the MVP journal store is synchronous (SQLite); this class mirrors the
    API with async enter/exit for use inside async agent loops.
    """

    async def __aenter__(self) -> AsyncAgentRestore:
        self._begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        self._end(exc_type)
