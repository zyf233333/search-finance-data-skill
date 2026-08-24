"""Durable workflow state for resumable research-data tasks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import ResearchDataSpec, utc_now


class StateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, spec: ResearchDataSpec, *, events: list[dict[str, Any]] | None = None) -> None:
        payload = {"spec": spec.to_dict(), "events": events or [], "saved_at": utc_now()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))
