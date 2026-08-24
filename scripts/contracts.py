"""Typed, serialisable contracts shared by planners and connectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

Status = Literal["unresolved", "resolved", "verified", "failed"]
AccessType = Literal["public", "api_key", "institutional", "account", "browser_session"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class VariableSpec:
    concept: str
    role: str = "control"
    measurement: str | None = None
    raw_variables: list[str] = field(default_factory=list)
    status: Status = "unresolved"
    confidence: float | None = None
    notes: str | None = None


@dataclass
class ResearchDataSpec:
    research_question: str
    market: str | None = None
    period_start: int | None = None
    period_end: int | None = None
    frequency: str | None = None
    unit: str | None = None
    variables: list[VariableSpec] = field(default_factory=list)
    spec_id: str = field(default_factory=lambda: f"rds_{uuid4().hex[:12]}")
    status: Status = "unresolved"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorInfo:
    code: str
    message: str
    recoverable: bool = False
    next_action: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectorResult:
    success: bool
    operation: str
    data: Any = None
    error: ErrorInfo | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if self.error is not None:
            value["error"] = self.error.to_dict()
        return value

    @classmethod
    def ok(cls, operation: str, data: Any = None, **metadata: Any) -> "ConnectorResult":
        return cls(True, operation, data=data, metadata=metadata)

    @classmethod
    def fail(cls, operation: str, error: ErrorInfo, **metadata: Any) -> "ConnectorResult":
        return cls(False, operation, error=error, metadata=metadata)


@dataclass
class ProvenanceRecord:
    variable_id: str
    concept: str
    source: str
    dataset: str
    raw_fields: list[str] = field(default_factory=list)
    formula: str | None = None
    frequency: str | None = None
    downloaded_at: str | None = None
    documentation_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
