from pathlib import Path

from agentrestore.store import SqliteJournalStore
from agentrestore.types import (
    DriftFinding,
    DriftReport,
    DriftState,
    EffectEntry,
    EffectKind,
    EffectStatus,
    FileRef,
)


def test_add_and_get_effects_roundtrip(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    entry = EffectEntry(
        checkpoint_id="c1",
        tool_name="write",
        args_hash="ah",
        effect_kind=EffectKind.FILE,
        effect_fingerprint="fp",
        status=EffectStatus.SUCCESS,
        file_refs=(FileRef(path="p", hash_before="b", hash_after="a"),),
        ts=1.0,
    )
    eid = store.add_effect(entry)
    assert eid > 0
    got = store.get_effects("c1")
    assert len(got) == 1
    assert got[0].id == eid
    assert got[0].file_refs == (FileRef(path="p", hash_before="b", hash_after="a"),)


def test_get_effects_scoped_by_checkpoint(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    store.add_effect(
        EffectEntry(
            checkpoint_id="c1", tool_name="t", args_hash="a",
            effect_kind=EffectKind.FILE, effect_fingerprint="f",
        )
    )
    store.add_effect(
        EffectEntry(
            checkpoint_id="c2", tool_name="t", args_hash="a",
            effect_kind=EffectKind.FILE, effect_fingerprint="f",
        )
    )
    assert len(store.get_effects("c1")) == 1
    assert len(store.get_effects("c2")) == 1
    assert store.get_effects("c3") == []


def test_get_file_refs_ordered(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    store.add_effect(
        EffectEntry(
            checkpoint_id="c1", tool_name="t", args_hash="a1",
            effect_kind=EffectKind.FILE, effect_fingerprint="f1",
            file_refs=(FileRef(path="p1", hash_after="x"),),
        )
    )
    store.add_effect(
        EffectEntry(
            checkpoint_id="c1", tool_name="t", args_hash="a2",
            effect_kind=EffectKind.FILE, effect_fingerprint="f2",
            file_refs=(FileRef(path="p2", hash_after="y"),),
        )
    )
    refs = store.get_file_refs("c1")
    assert [r.path for r in refs] == ["p1", "p2"]


def test_record_drift(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    report = DriftReport(
        checkpoint_id="c1",
        findings=[DriftFinding(path="p", state=DriftState.CHANGED, expected="a", actual="b")],
    )
    rid = store.record_drift(report, observation="obs")
    assert rid > 0
