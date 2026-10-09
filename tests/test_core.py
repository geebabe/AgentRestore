from pathlib import Path

import pytest

from agentrestore import AgentRestore, AsyncAgentRestore, DriftAlert


def _write(p: Path, s: str) -> None:
    p.write_text(s)


def test_context_manager_journals_and_clean_resume(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = tmp_path / "j.db"
    with AgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db)):
        _write(ws / "a.txt", "hello")
    # Resuming with no external change raises nothing.
    with AgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db)):
        pass


def test_drift_alert_on_external_change(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = tmp_path / "j.db"
    with AgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db)):
        _write(ws / "a.txt", "hello")
    _write(ws / "a.txt", "changed externally")
    with pytest.raises(DriftAlert) as exc:
        with AgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db)):
            pass
    report = exc.value.report
    assert report.has_drift
    assert any(f.state.value == "changed" for f in report.findings)


def test_explicit_journal_file_change(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = tmp_path / "j.db"
    p = ws / "a.txt"
    with AgentRestore(checkpoint_id="c1", store=str(db)) as ar:
        _write(p, "hello")
        ar.journal_file_change(str(p))
    _write(p, "changed")
    with pytest.raises(DriftAlert):
        with AgentRestore(checkpoint_id="c1", store=str(db)):
            pass


def test_scan_and_reconcile_standalone(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = tmp_path / "j.db"
    with AgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db)):
        _write(ws / "a.txt", "hello")
    _write(ws / "a.txt", "changed")
    ar = AgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db))
    report = ar.scan()
    assert report.has_drift
    observation = ar.reconcile(report)
    assert observation is not None
    assert "CHANGED" in observation


async def test_async_context_manager(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = tmp_path / "j.db"
    async with AsyncAgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db)):
        _write(ws / "a.txt", "hello")
    _write(ws / "a.txt", "changed")
    with pytest.raises(DriftAlert):
        async with AsyncAgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db)):
            pass
