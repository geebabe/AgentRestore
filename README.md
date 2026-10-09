# AgentRestore

**Drift-aware resume middleware for agent frameworks.**
Reconcile what changed in the world during a pause or crash, and make it visible to the model.

Long-horizon agents desynchronize when they resume: existing checkpointers save only messages,
ignoring the *physical* side effects of tool calls (files written, DB rows changed, APIs called).
When the external world moves during a human-in-the-loop window or a crash, the agent acts on a
stale snapshot and corrupts its trajectory.

AgentRestore adds the missing layer: a **Tool Effect Journal**, an **Environment Drift Scanner**,
a **Semantic Reconciliation Engine**, and an **Idempotent Resume Adapter** — as a drop-in
middleware for the framework you already use.

## Documentation

- [`docs/SPEC.md`](docs/SPEC.md) — the specification and source of truth.
- [`docs/research.md`](docs/research.md) — research, competitive landscape, and citations.
- [`docs/note.txt`](docs/note.txt) — the original idea pitch.
- [`AGENTS.md`](AGENTS.md) — coding guide.

## Status

**Pre-MVP.** The specification is complete; implementation is next.

## Quickstart (target API — Phase 1)

```python
from agentrestore import AgentRestore, DriftAlert

# First run: journal file changes under ./workspace
with AgentRestore(checkpoint_id="task_42", watch_paths=["./workspace"]) as ar:
    # ... agent runs its bash/file tools here ...

# Resume: detect drift if the world moved during the pause
try:
    with AgentRestore(checkpoint_id="task_42", watch_paths=["./workspace"]):
        ...
except DriftAlert as e:
    for f in e.report.findings:
        print(f.path, f.state, f.expected, f.actual)
```

## Tech stack

Python 3.11+, BLAKE3 hashing, SQLite (WAL), no ORM. Adapters for LangGraph (Phase 1),
PydanticAI / OpenAI Agents SDK / MCP (Phase 2).

## License

TBD.
