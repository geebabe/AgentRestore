"""Framework tool wrappers.

These are framework-agnostic: they read the active :class:`AgentRestore`
context (via :func:`agentrestore.core.get_active`) and journal filesystem
changes around the wrapped callable. Real framework adapters (LangGraph,
PydanticAI, OpenAI Agents SDK, MCP) build on these primitives.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from typing import Any, TypeVar, overload

from ..core import get_active
from ..journal import diff_trees

F = TypeVar("F", bound=Callable[..., Any])


def _paths(active: Any, watch_paths: Iterable[str] | None) -> list[str]:
    return list(watch_paths) if watch_paths is not None else list(active.watch_paths)


@overload
def wrap_tool(
    func: F,
    *,
    watch_paths: Iterable[str] | None = None,
    tool_name: str | None = None,
) -> F: ...


@overload
def wrap_tool(
    func: None = None,
    *,
    watch_paths: Iterable[str] | None = None,
    tool_name: str | None = None,
) -> Callable[[F], F]: ...


def wrap_tool(
    func: F | None = None,
    *,
    watch_paths: Iterable[str] | None = None,
    tool_name: str | None = None,
) -> F | Callable[[F], F]:
    """Decorate a synchronous tool so its file changes are journaled.

    When no AgentRestore context is active, the function runs unchanged.
    """

    def decorator(fn: F) -> F:
        name = tool_name or str(getattr(fn, "__name__", "tool"))

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            active = get_active()
            if active is None:
                return fn(*args, **kwargs)
            paths = _paths(active, watch_paths)
            before = active.journal.snapshot(paths) if paths else {}
            result = fn(*args, **kwargs)
            if paths:
                after = active.journal.snapshot(paths)
                refs = diff_trees(before, after)
                if refs:
                    active.journal.record(
                        tool_name=name,
                        args={"args": args, "kwargs": kwargs},
                        file_refs=refs,
                        result=result,
                    )
            return result

        return wrapper  # type: ignore[return-value]

    if func is None:
        return decorator
    return decorator(func)


@overload
def awrap_tool(
    func: F,
    *,
    watch_paths: Iterable[str] | None = None,
    tool_name: str | None = None,
) -> F: ...


@overload
def awrap_tool(
    func: None = None,
    *,
    watch_paths: Iterable[str] | None = None,
    tool_name: str | None = None,
) -> Callable[[F], F]: ...


def awrap_tool(
    func: F | None = None,
    *,
    watch_paths: Iterable[str] | None = None,
    tool_name: str | None = None,
) -> F | Callable[[F], F]:
    """Async equivalent of :func:`wrap_tool`."""

    def decorator(fn: F) -> F:
        name = tool_name or str(getattr(fn, "__name__", "tool"))

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            active = get_active()
            if active is None:
                return await fn(*args, **kwargs)
            paths = _paths(active, watch_paths)
            before = active.journal.snapshot(paths) if paths else {}
            result = await fn(*args, **kwargs)
            if paths:
                after = active.journal.snapshot(paths)
                refs = diff_trees(before, after)
                if refs:
                    active.journal.record(
                        tool_name=name,
                        args={"args": args, "kwargs": kwargs},
                        file_refs=refs,
                        result=result,
                    )
            return result

        return wrapper  # type: ignore[return-value]

    if func is None:
        return decorator
    return decorator(func)


__all__ = ["wrap_tool", "awrap_tool"]
