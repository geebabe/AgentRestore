"""Semantic Reconciliation Engine: turn drift into an observation for the model."""

from __future__ import annotations

from typing import Protocol

from .types import DriftReport, DriftState

_STATE_LABEL = {
    DriftState.MATCHED: "MATCHED",
    DriftState.CHANGED: "CHANGED",
    DriftState.MISSING: "MISSING",
    DriftState.NEW: "NEW",
}


class Summarizer(Protocol):
    """Phase-2 seam: converts a :class:`DriftReport` into a model observation.

    The MVP uses :class:`DeterministicSummarizer`; a future LLM-backed
    summarizer can implement this protocol and be swapped in.
    """

    def __call__(self, report: DriftReport) -> str | None: ...


class DeterministicSummarizer:
    """Deterministic, LLM-free drift summary (no model call in Phase 1)."""

    def __call__(self, report: DriftReport) -> str | None:
        if not report.has_drift:
            return None
        lines = ["[environment_changed] External drift detected since the last checkpoint:"]
        for finding in report.findings:
            if finding.state is DriftState.MATCHED:
                continue
            parts = [f"- {finding.path}: {_STATE_LABEL[finding.state]}"]
            if finding.expected is not None:
                parts.append(f"(expected {finding.expected})")
            if finding.actual is not None:
                parts.append(f"(actual {finding.actual})")
            if finding.detail:
                parts.append(f"[{finding.detail}]")
            lines.append(" ".join(parts))
        lines.append(
            "The prior plan or filesystem assumptions may be stale. Re-check before acting."
        )
        return "\n".join(lines)


class ReconciliationEngine:
    """Produces a synthetic observation from a drift report."""

    def __init__(self, summarizer: Summarizer | None = None) -> None:
        self.summarizer: Summarizer = summarizer or DeterministicSummarizer()

    def reconcile(self, report: DriftReport) -> str | None:
        """Return an observation string, or ``None`` when there is nothing to say."""
        return self.summarizer(report)
