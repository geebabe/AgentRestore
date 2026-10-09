# AGENTS.md — coding guide for AgentRestore

This file is for coding agents (and humans) working in this repo. Read it first.

## What we're building

AgentRestore: drift-aware resume middleware for agent frameworks. See:
- `docs/SPEC.md` — the **source of truth** for what to build and how. Follow it exactly.
- `docs/research.md` — why, and the competitive landscape.
- `docs/note.txt` — the original pitch.

## Hard rules

1. **The spec wins.** If `docs/SPEC.md` and anything else disagree, follow the spec and flag the conflict.
2. Core modules (`hashing`, `journal`, `store`, `scanner`, `reconcile`, `idempotent`, `types`, `probes`)
   must **never import an agent framework**. Only `wrappers/*` may.
3. Use **`checkpoint_id`** as the universal partition key. Never introduce `thread_id`/`session_id` in core code.
4. Hashes are **BLAKE3 hex (64 chars)**. Never identify content by size alone.
5. Drift must raise **`DriftAlert`** (a dedicated exception), never a bare `RuntimeError`.
6. Keep `DriftReport` a plain, dependency-free dataclass; it must survive `dataclasses.asdict`.
7. `blake3` is a runtime dependency; stdlib `sqlite3` (WAL mode) for storage; no ORM.

## Style

- Python 3.11+ syntax (`X | None`, dataclasses, `frozen=True` where sensible).
- Sync-first for MVP; add an async mirror only where the spec calls for it (`AsyncAgentRestore`).
- Type hints on all public APIs; `ruff` + `mypy` must pass.
- Tests in `tests/`, one file per module, `pytest` + `pytest-asyncio`.

## MVP checklist (Phase 1 only)

Build in this order, verifying each module's tests before moving on:

1. `types.py` — enums + dataclasses (Section 4.4 of the spec).
2. `hashing.py` — BLAKE3 file/content hashing + arg canonicalization.
3. `store.py` — `JournalStore` ABC + `SqliteJournalStore` (WAL, schema from Section 4.1–4.3).
4. `journal.py` — `EffectEntry` recording + `watch_paths` before/after hashing.
5. `scanner.py` — filesystem drift scan → `DriftReport` (matched/changed/missing/new).
6. `reconcile.py` — deterministic `DriftReport` → observation string (no LLM).
7. `idempotent.py` — replay-by-fingerprint for `file` effects.
8. `core.py` — `AgentRestore` / `AsyncAgentRestore` context managers + `DriftAlert`.
9. `wrappers/langgraph.py` — `wrap_tool` decorator (Phase 1 framework adapter).
10. `examples/langgraph_bash_agent.py` — runnable demo.

Do **not** build Phase 2 items (MCP proxy, DB/API probes, PydanticAI/OpenAI adapters, LLM summarizer)
unless explicitly asked. Stub the `DriftProbe` protocol in `probes.py` but don't implement DB/HTTP yet.

## Definition of done (MVP)

All 7 acceptance criteria in `docs/SPEC.md` §7 pass; `pytest`, `ruff`, `mypy` clean.
