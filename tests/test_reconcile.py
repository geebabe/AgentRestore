from agentrestore.reconcile import DeterministicSummarizer, ReconciliationEngine
from agentrestore.types import DriftFinding, DriftReport, DriftState


def test_no_drift_returns_none() -> None:
    report = DriftReport(checkpoint_id="c1", findings=[])
    assert DeterministicSummarizer()(report) is None


def test_drift_summary_lists_changed_and_skips_matched() -> None:
    report = DriftReport(
        checkpoint_id="c1",
        findings=[
            DriftFinding(path="a", state=DriftState.CHANGED, expected="e", actual="x"),
            DriftFinding(path="b", state=DriftState.MATCHED, expected="y", actual="y"),
        ],
    )
    text = ReconciliationEngine().reconcile(report)
    assert text is not None
    assert "CHANGED" in text
    assert "MATCHED" not in text
    assert "a" in text


def test_reconcile_engine_default_summarizer() -> None:
    report = DriftReport(checkpoint_id="c1", findings=[])
    assert ReconciliationEngine().reconcile(report) is None
