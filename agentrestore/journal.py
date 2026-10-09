"""Tool Effect Journal: record the physical side effects of tool calls."""

from __future__ import annotations

import os
import time
from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any

from .hashing import canonicalize, hash_args, hash_content, hash_tree, make_effect_fingerprint
from .store import JournalStore
from .types import (
    ApiRef,
    DbRef,
    EffectEntry,
    EffectKind,
    EffectStatus,
    FileRef,
)


def _size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def diff_trees(before: Mapping[str, str], after: Mapping[str, str]) -> list[FileRef]:
    """Compare two path->hash snapshots and produce a FileRef per changed file.

    - created: ``hash_before`` is ``None``
    - modified: both hashes set
    - deleted: ``hash_after`` is ``None``
    """
    refs: list[FileRef] = []
    for path in sorted(set(before) | set(after)):
        b = before.get(path)
        a = after.get(path)
        if b == a:
            continue
        refs.append(FileRef(path=path, hash_before=b, hash_after=a, size=_size(path)))
    return refs


def _kind_of(
    files: tuple[FileRef, ...],
    dbs: tuple[DbRef, ...],
    apis: tuple[ApiRef, ...],
) -> EffectKind:
    if files:
        return EffectKind.FILE
    if dbs:
        return EffectKind.DB
    if apis:
        return EffectKind.API
    return EffectKind.UNKNOWN


def _encode_result(result: Any) -> tuple[str | None, str | None]:
    if result is None:
        return None, None
    json_str = canonicalize(result)
    return hash_content(json_str), json_str


class Journal:
    """Records tool side effects into a :class:`JournalStore` for a checkpoint."""

    def __init__(self, store: JournalStore, checkpoint_id: str) -> None:
        self.store = store
        self.checkpoint_id = checkpoint_id

    def snapshot(self, paths: Iterable[str]) -> dict[str, str]:
        """Hash the current contents of ``paths`` into a path->hash map."""
        return hash_tree(paths)

    def record(
        self,
        *,
        tool_name: str,
        args: Any = None,
        file_refs: Iterable[FileRef] = (),
        db_refs: Iterable[DbRef] = (),
        api_refs: Iterable[ApiRef] = (),
        status: EffectStatus = EffectStatus.SUCCESS,
        result: Any = None,
    ) -> EffectEntry:
        """Build, persist, and return an :class:`EffectEntry`."""
        files = tuple(file_refs)
        dbs = tuple(db_refs)
        apis = tuple(api_refs)
        result_ref, result_json = _encode_result(result)
        entry = EffectEntry(
            checkpoint_id=self.checkpoint_id,
            tool_name=tool_name,
            args_hash=hash_args(args),
            effect_kind=_kind_of(files, dbs, apis),
            effect_fingerprint=make_effect_fingerprint(files, dbs, apis),
            status=status,
            file_refs=files,
            db_refs=dbs,
            api_refs=apis,
            result_ref=result_ref,
            result_json=result_json,
            ts=time.time(),
        )
        return replace(entry, id=self.store.add_effect(entry))

    def record_file_change(
        self,
        path: str,
        *,
        hash_before: str | None = None,
        hash_after: str | None = None,
        tool_name: str = "file",
        args: Any = None,
        result: Any = None,
        status: EffectStatus = EffectStatus.SUCCESS,
    ) -> EffectEntry:
        """Record a single file's change as a file effect."""
        ref = FileRef(
            path=path,
            hash_before=hash_before,
            hash_after=hash_after if hash_after is not None else None,
            size=_size(path),
        )
        return self.record(
            tool_name=tool_name,
            args=args,
            file_refs=(ref,),
            status=status,
            result=result,
        )
