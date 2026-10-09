import json
from pathlib import Path
from typing import Any

from agentrestore.hashing import hash_args, hash_content
from agentrestore.idempotent import IdempotencyAdapter, InterceptOutcome
from agentrestore.store import SqliteJournalStore
from agentrestore.types import EffectEntry, EffectKind, EffectStatus


def _entry(
    tool: str,
    args: Any,
    status: EffectStatus = EffectStatus.SUCCESS,
    result: Any = "r",
    fp: str = "f",
) -> EffectEntry:
    return EffectEntry(
        checkpoint_id="c1",
        tool_name=tool,
        args_hash=hash_args(args),
        effect_kind=EffectKind.FILE,
        effect_fingerprint=fp,
        status=status,
        result_ref=hash_content(json.dumps(result)),
        result_json=json.dumps(result),
    )


def test_execute_when_no_prior(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    r = IdempotencyAdapter(store, "c1").intercept("write", {"path": "x"})
    assert r.outcome is InterceptOutcome.EXECUTE


def test_replay(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    store.add_effect(_entry("write", {"path": "x"}, result={"ok": True}))
    r = IdempotencyAdapter(store, "c1").intercept("write", {"path": "x"})
    assert r.outcome is InterceptOutcome.REPLAY
    assert r.result == {"ok": True}


def test_ambiguous_non_success(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    store.add_effect(_entry("write", {"path": "x"}, status=EffectStatus.FAILED))
    r = IdempotencyAdapter(store, "c1").intercept("write", {"path": "x"})
    assert r.outcome is InterceptOutcome.AMBIGUOUS


def test_ambiguous_non_deterministic(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    store.add_effect(_entry("write", {"path": "x"}, result="r1", fp="f1"))
    store.add_effect(_entry("write", {"path": "x"}, result="r2", fp="f2"))
    r = IdempotencyAdapter(store, "c1").intercept("write", {"path": "x"})
    assert r.outcome is InterceptOutcome.AMBIGUOUS


def test_different_args_is_execute(tmp_path: Path) -> None:
    store = SqliteJournalStore(tmp_path / "j.db")
    store.add_effect(_entry("write", {"path": "x"}))
    r = IdempotencyAdapter(store, "c1").intercept("write", {"path": "y"})
    assert r.outcome is InterceptOutcome.EXECUTE
