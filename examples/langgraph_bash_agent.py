"""Runnable demo of AgentRestore's drift detection.

Run:  python examples/langgraph_bash_agent.py

This simulates a LangGraph-style agent loop that writes files with a bash-like
tool, then pauses (human review / crash), during which the outside world edits
one of the files. On resume, AgentRestore raises DriftAlert before the agent can
act on stale state.

Real LangGraph integration is the same pattern: decorate the graph's tools with
``@wrap_tool`` and wrap the node body with ``AgentRestore(...)``. No framework
import is required for the demo itself.
"""

from __future__ import annotations

import os
import tempfile

from agentrestore import AgentRestore, DriftAlert
from agentrestore.wrappers.langgraph import wrap_tool

CHECKPOINT_ID = "task_42"


@wrap_tool
def write_file(path: str, content: str) -> str:
    """Simulate a bash tool that writes a file on disk."""
    with open(path, "w") as fh:
        fh.write(content)
    return f"wrote {len(content)} bytes to {path}"


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="agentrestore-demo-")
    workspace = os.path.join(tmp, "workspace")
    os.makedirs(workspace)
    db = os.path.join(tmp, "journal.db")

    # 1) First run: the agent writes files inside the watched directory.
    with AgentRestore(checkpoint_id=CHECKPOINT_ID, watch_paths=[workspace], store=db):
        print(write_file(os.path.join(workspace, "draft.md"), "# Draft\n"))
        print(write_file(os.path.join(workspace, "notes.txt"), "hello\n"))

    # 2) Pause (human-in-the-loop review / crash). The world moves underneath.
    with open(os.path.join(workspace, "draft.md"), "w") as fh:
        fh.write("# Draft (edited by a human during review)\n")

    # 3) Resume: drift is detected before the agent acts on stale state.
    try:
        with AgentRestore(checkpoint_id=CHECKPOINT_ID, watch_paths=[workspace], store=db):
            print("resumed cleanly (no drift)")  # unreachable in this demo
    except DriftAlert as e:
        print("\nDriftAlert raised:\n")
        for finding in e.report.findings:
            print(f"  {finding.state.value:8} {finding.path}")
            if finding.expected:
                print(f"      expected {finding.expected[:16]}…")
            if finding.actual:
                print(f"      actual   {finding.actual[:16]}…")

    # 4) Show the synthetic observation the model would see on resume.
    ar = AgentRestore(checkpoint_id=CHECKPOINT_ID, watch_paths=[workspace], store=db)
    observation = ar.reconcile(ar.scan())
    print("\nSynthetic observation for the model:\n")
    print(observation)


if __name__ == "__main__":
    main()
