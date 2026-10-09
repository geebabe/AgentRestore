"""DriftProbe protocol (Phase 2 seam)."""

from __future__ import annotations

from typing import Protocol

from .types import DriftFinding


class DriftProbe(Protocol):
    """Inspects an external system (DB/API) for drift.

    Phase 2. Not implemented in the MVP; retained as the extension seam so the
    scanner can later incorporate database and HTTP state alongside filesystem
    state without changing its interface.
    """

    name: str

    def probe(self) -> DriftFinding: ...
