"""Idempotent Resume Adapter: intercept replayed tool calls."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .hashing import hash_args
from .store import JournalStore
from .types import EffectStatus


class InterceptOutcome(StrEnum):
    REPLAY = "replay"
    AMBIGUOUS = "ambiguous"
    EXECUTE = "execute"


@dataclass(frozen=True)
class InterceptResult:
    outcome: InterceptOutcome
    result: Any = None
    reason: str = ""


class IdempotencyAdapter:
    """Short-circuits tool calls that would re-execute a known effect."""

    def __init__(self, store: JournalStore, checkpoint_id: str) -> None:
        self.store = store
        self.checkpoint_id = checkpoint_id

    def intercept(self, tool_name: str, args: Any) -> InterceptResult:
        """Decide whether a tool call is a replay, new, or ambiguous.

        Matching is by ``tool_name`` + ``args_hash``. If multiple *different*
        effects share the same args (non-determinism), the call is AMBIGUOUS.
        """
        args_hash = hash_args(args)
        matches = [
            e
            for e in self.store.get_effects(self.checkpoint_id)
            if e.tool_name == tool_name and e.args_hash == args_hash
        ]
        if not matches:
            return InterceptResult(InterceptOutcome.EXECUTE, reason="no prior effect")

        successes = [e for e in matches if e.status is EffectStatus.SUCCESS]
        if successes:
            fingerprints = {e.effect_fingerprint for e in successes}
            if len(fingerprints) > 1:
                return InterceptResult(
                    InterceptOutcome.AMBIGUOUS,
                    reason="non-deterministic prior effects for identical arguments",
                )
            latest = successes[-1]
            if latest.result_json is not None:
                return InterceptResult(
                    InterceptOutcome.REPLAY,
                    result=json.loads(latest.result_json),
                    reason="replayed identical prior effect",
                )
            return InterceptResult(
                InterceptOutcome.AMBIGUOUS,
                reason="prior success has no cached result",
            )

        return InterceptResult(
            InterceptOutcome.AMBIGUOUS,
            reason="prior effect ended in a non-success state",
        )
