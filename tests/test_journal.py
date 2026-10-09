from pathlib import Path

from agentrestore.journal import Journal, diff_trees
from agentrestore.store import SqliteJournalStore
from agentrestore.types import EffectKind


def test_diff_trees_created_modified_deleted() -> None:
    before = {"a": "1", "b": "2", "c": "3"}
    after = {"a": "1", "b": "9", "d": "4"}
    by_path = {r.path: r for r in diff_trees(before, after)}
    assert set(by_path) == {"b", "c", "d"}
    assert by_path["b"].hash_before == "2" and by_path["b"].hash_after == "9"
    assert by_path["c"].hash_before == "3" and by_path["c"].hash_after is None
    assert by_path["d"].hash_before is None and by_path["d"].hash_after == "4"


def test_diff_trees_no_change_is_empty() -> None:
    assert diff_trees({"a": "1"}, {"a": "1"}) == []


def test_record_persists_and_computes_hashes(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    j = Journal(store, "c1")
    entry = j.record(tool_name="write", args={"path": "x"}, result="done")
    assert entry.id is not None
    assert entry.effect_kind is EffectKind.UNKNOWN  # no refs
    assert entry.result_json == '"done"'
    got = store.get_effects("c1")
    assert len(got) == 1
    assert got[0].args_hash == entry.args_hash


def test_record_file_change(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    j = Journal(store, "c1")
    entry = j.record_file_change("some/path", tool_name="file")
    assert entry.effect_kind is EffectKind.FILE
    assert len(entry.file_refs) == 1
    assert entry.file_refs[0].path == "some/path"
