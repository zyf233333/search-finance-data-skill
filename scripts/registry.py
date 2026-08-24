"""Versioned JSON-backed registries for variables and datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RegistryError(ValueError):
    """Raised when a registry is malformed or an item cannot be found."""


class JsonRegistry:
    def __init__(self, path: str | Path, item_key: str, id_field: str = "id") -> None:
        self.path = Path(path)
        self.item_key = item_key
        self.id_field = id_field
        self._document: dict[str, Any] | None = None

    @property
    def document(self) -> dict[str, Any]:
        if self._document is None:
            try:
                self._document = json.loads(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise RegistryError(f"Registry file not found: {self.path}") from exc
            except json.JSONDecodeError as exc:
                raise RegistryError(f"Invalid registry JSON: {self.path}") from exc
            if not isinstance(self._document, dict) or not isinstance(self._document.get(self.item_key), list):
                raise RegistryError(f"Registry must contain a list named '{self.item_key}'")
        return self._document

    def all(self) -> list[dict[str, Any]]:
        return list(self.document[self.item_key])

    def get(self, item_id: str) -> dict[str, Any]:
        for item in self.all():
            if item.get(self.id_field) == item_id:
                return dict(item)
        raise RegistryError(f"Unknown {self.item_key[:-1]} id: {item_id}")

    def search(self, **criteria: Any) -> list[dict[str, Any]]:
        return [item for item in self.all() if all(item.get(k) == v for k, v in criteria.items())]


class VariableRegistry(JsonRegistry):
    def __init__(self, path: str | Path) -> None:
        super().__init__(path, "variables", "variable_id")


class DatasetRegistry(JsonRegistry):
    def __init__(self, path: str | Path) -> None:
        super().__init__(path, "datasets", "dataset_id")
