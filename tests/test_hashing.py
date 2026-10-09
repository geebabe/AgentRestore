from pathlib import Path

from agentrestore.hashing import (
    canonicalize,
    hash_args,
    hash_bytes,
    hash_content,
    hash_file,
    hash_tree,
    make_effect_fingerprint,
)
from agentrestore.types import FileRef


def test_hash_bytes_deterministic() -> None:
    assert hash_bytes(b"abc") == hash_bytes(b"abc")
    assert hash_bytes(b"abc") != hash_bytes(b"abd")


def test_hash_content_matches_bytes() -> None:
    assert hash_content("abc") == hash_bytes(b"abc")


def test_hash_file(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("hello")
    assert hash_file(str(p)) == hash_content("hello")


def test_canonicalize_is_order_independent() -> None:
    assert canonicalize({"a": 1, "b": 2}) == canonicalize({"b": 2, "a": 1})


def test_hash_args_order_independent() -> None:
    assert hash_args({"a": 1, "b": 2}) == hash_args({"b": 2, "a": 1})
    assert hash_args({"a": 1}) != hash_args({"a": 2})


def test_make_effect_fingerprint_deterministic() -> None:
    ref1 = FileRef(path="x", hash_before="a", hash_after="b")
    ref2 = FileRef(path="x", hash_before="a", hash_after="b")
    assert make_effect_fingerprint([ref1]) == make_effect_fingerprint([ref2])
    ref3 = FileRef(path="x", hash_before="a", hash_after="c")
    assert make_effect_fingerprint([ref1]) != make_effect_fingerprint([ref3])


def test_hash_tree_walks_recursively(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_text("1")
    (tmp_path / "sub" / "b.txt").write_text("2")
    tree = hash_tree([str(tmp_path)])
    assert len(tree) == 2
    assert all(v for v in tree.values())
