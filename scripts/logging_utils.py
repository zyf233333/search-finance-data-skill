"""Small structured JSONL logger with no credential persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import utc_now


class JsonlLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def event(self, event: str, **fields: Any) -> None:
        payload = {"timestamp": utc_now(), "event": event, **fields}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
