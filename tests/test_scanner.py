from pathlib import Path

from agentrestore.hashing import hash_content
from agentrestore.scanner import DriftScanner
from agentrestore.store import SqliteJournalStore
from agentrestore.types import DriftState, EffectEntry, EffectKind, FileRef


def _entry(path: str, hash_after: str, i: int = 0) -> EffectEntry:
    return EffectEntry(
        checkpoint_id="c1",
        tool_name="t",
        args_hash=f"a{i}",
        effect_kind=EffectKind.FILE,
        effect_fingerprint=f"f{i}",
        file_refs=(FileRef(path=path, hash_before=None, hash_after=hash_after),),
    )


def test_matched(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    p = ws / "f.txt"
    p.write_text("hello")
    store = SqliteJournalStore(tmp_path / "j.db")
    store.add_effect(_entry(str(p), hash_content("hello")))
    report = DriftScanner(store).scan("c1")
    assert not report.has_drift


def test_changed(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    p = ws / "f.txt"
    p.write_text("hello")
    store = SqliteJournalStore(tmp_path / "j.db")
    store.add_effect(_entry(str(p), hash_content("hello")))
    p.write_text("changed")
    report = DriftScanner(store).scan("c1")
    assert report.has_drift
    assert report.findings[0].state is DriftState.CHANGED


def test_missing(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    p = ws / "f.txt"
    p.write_text("hello")
    store = SqliteJournalStore(tmp_path / "j.db")
    store.add_effect(_entry(str(p), hash_content("hello")))
    p.unlink()
    report = DriftScanner(store).scan("c1")
    assert report.findings[0].state is DriftState.MISSING


def test_new_file_detected_with_watch_paths(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    store = SqliteJournalStore(tmp_path / "j.db")
    (ws / "untracked.txt").write_text("x")
    report = DriftScanner(store).scan("c1", watch_paths=[str(ws)])
    states = {f.state for f in report.findings}
    assert DriftState.NEW in states
