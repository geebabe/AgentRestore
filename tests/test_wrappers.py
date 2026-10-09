from pathlib import Path

import pytest

from agentrestore import AgentRestore, DriftAlert
from agentrestore.wrappers.langgraph import wrap_tool


def test_wrap_tool_journals_file_changes(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = tmp_path / "j.db"

    @wrap_tool
    def write(path: str, content: str) -> str:
        with open(path, "w") as fh:
            fh.write(content)
        return f"wrote {len(content)}"

    with AgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db)):
        assert write(str(ws / "a.txt"), "hello") == "wrote 5"

    (ws / "a.txt").write_text("changed")
    with pytest.raises(DriftAlert):
        with AgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db)):
            pass


def test_wrap_tool_noop_without_context() -> None:
    @wrap_tool
    def identity(x: int) -> int:
        return x

    assert identity(1) == 1


def test_wrap_tool_with_explicit_watch_paths(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = tmp_path / "j.db"

    @wrap_tool(watch_paths=[str(ws)])
    def write(path: str, content: str) -> None:
        with open(path, "w") as fh:
            fh.write(content)

    with AgentRestore(checkpoint_id="c1", store=str(db)):
        write(str(ws / "a.txt"), "hello")

    (ws / "a.txt").write_text("changed")
    with pytest.raises(DriftAlert):
        with AgentRestore(checkpoint_id="c1", watch_paths=[str(ws)], store=str(db)):
            pass
