"""Environment Drift Scanner: detect divergence between journal and reality."""

from __future__ import annotations

import os
from collections.abc import Iterable

from .hashing import hash_file, hash_tree
from .store import JournalStore
from .types import DriftFinding, DriftReport, DriftState


class DriftScanner:
    """Probes the environment to see whether it matches the journaled effects."""

    def __init__(self, store: JournalStore) -> None:
        self.store = store

    def scan(
        self,
        checkpoint_id: str,
        watch_paths: Iterable[str] | None = None,
    ) -> DriftReport:
        """Scan filesystem state against the journal for a checkpoint.

        Classification is relative to the *latest* journaled ``hash_after`` per
        path (a deleted file has ``hash_after is None``). If ``watch_paths`` is
        given, any current file not present in the journal is reported as NEW.
        """
        # Last journaled write wins per path.
        expected: dict[str, str | None] = {}
        for ref in self.store.get_file_refs(checkpoint_id):
            expected[ref.path] = ref.hash_after

        findings: list[DriftFinding] = []
        for path, exp in expected.items():
            findings.append(self._classify(path, exp))

        if watch_paths is not None:
            for path, actual in hash_tree(watch_paths).items():
                if path not in expected:
                    findings.append(
                        DriftFinding(path=path, state=DriftState.NEW, actual=actual)
                    )

        return DriftReport(checkpoint_id=checkpoint_id, findings=findings)

    @staticmethod
    def _classify(path: str, expected: str | None) -> DriftFinding:
        exists = os.path.isfile(path)
        if expected is None:
            if not exists:
                return DriftFinding(
                    path=path,
                    state=DriftState.MATCHED,
                    expected=None,
                    actual=None,
                    detail="expected absent",
                )
            return DriftFinding(
                path=path,
                state=DriftState.CHANGED,
                expected=None,
                actual=hash_file(path),
                detail="unexpectedly present",
            )
        if not exists:
            return DriftFinding(path=path, state=DriftState.MISSING, expected=expected)
        actual = hash_file(path)
        if actual == expected:
            return DriftFinding(
                path=path, state=DriftState.MATCHED, expected=expected, actual=actual
            )
        return DriftFinding(
            path=path, state=DriftState.CHANGED, expected=expected, actual=actual
        )
