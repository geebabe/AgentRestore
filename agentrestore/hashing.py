"""BLAKE3 hashing and canonicalization helpers."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from typing import Any

from blake3 import blake3

from .types import ApiRef, DbRef, FileRef

_CHUNK = 1024 * 1024


def hash_bytes(data: bytes) -> str:
    """BLAKE3 hex digest of raw bytes."""
    return blake3(data).hexdigest()


def hash_content(text: str) -> str:
    """BLAKE3 hex digest of a UTF-8 string."""
    return hash_bytes(text.encode("utf-8"))


def hash_file(path: str) -> str:
    """BLAKE3 hex digest of a file's contents, streamed."""
    hasher = blake3()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonicalize(obj: Any) -> str:
    """Stable, order-independent JSON serialization of any JSON-ish object."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=repr)


def hash_args(args: Any) -> str:
    """Deterministic hash of tool arguments (order-independent for dicts)."""
    return hash_content(canonicalize(args))


def _file_ref_dict(ref: FileRef) -> dict[str, Any]:
    return {
        "path": ref.path,
        "before": ref.hash_before,
        "after": ref.hash_after,
        "size": ref.size,
    }


def _db_ref_dict(ref: DbRef) -> dict[str, Any]:
    return {
        "backend": ref.backend,
        "entity": ref.entity,
        "entity_id": ref.entity_id,
        "before": ref.before_hash,
        "after": ref.after_hash,
    }


def _api_ref_dict(ref: ApiRef) -> dict[str, Any]:
    return {
        "method": ref.method,
        "endpoint": ref.endpoint,
        "request": ref.request_hash,
        "response": ref.response_hash,
        "idempotency_key": ref.idempotency_key,
    }


def make_effect_fingerprint(
    file_refs: Iterable[FileRef] = (),
    db_refs: Iterable[DbRef] = (),
    api_refs: Iterable[ApiRef] = (),
) -> str:
    """Deterministic fingerprint of a tool call's physical side effects.

    Identical effects produce identical fingerprints regardless of the arguments
    that produced them, which is what lets the idempotency adapter distinguish a
    true replay from a subtly different re-execution.
    """
    payload = {
        "files": [_file_ref_dict(r) for r in file_refs],
        "db": [_db_ref_dict(r) for r in db_refs],
        "api": [_api_ref_dict(r) for r in api_refs],
    }
    return hash_content(canonicalize(payload))


def hash_tree(paths: Iterable[str]) -> dict[str, str]:
    """Recursively hash all files under the given paths.

    Returns a mapping of normalized path -> BLAKE3 hex digest. Skips ``.git``
    directories and files that cannot be read.
    """
    result: dict[str, str] = {}
    for root in paths:
        if os.path.isfile(root):
            try:
                result[os.path.normpath(root)] = hash_file(root)
            except OSError:
                continue
            continue
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d != ".git")
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                try:
                    result[os.path.normpath(full)] = hash_file(full)
                except OSError:
                    continue
    return result
