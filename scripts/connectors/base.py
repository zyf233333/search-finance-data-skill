"""Common connector protocol for public and institutional data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..contracts import ConnectorResult, ErrorInfo


class DatasetConnector(ABC):
    """Provider adapter boundary; methods always return ConnectorResult."""

    def _not_implemented(self, operation: str) -> ConnectorResult:
        return ConnectorResult.fail(
            operation,
            ErrorInfo("NOT_IMPLEMENTED", f"{operation} is not implemented by this connector.", recoverable=False),
        )

    @abstractmethod
    def discover(self, query: str) -> ConnectorResult:
        raise NotImplementedError

    @abstractmethod
    def describe(self, dataset_id: str) -> ConnectorResult:
        raise NotImplementedError

    @abstractmethod
    def check_access(self, dataset_id: str) -> ConnectorResult:
        raise NotImplementedError

    @abstractmethod
    def schema(self, dataset_id: str) -> ConnectorResult:
        raise NotImplementedError

    @abstractmethod
    def preview(self, dataset_id: str, params: dict[str, Any] | None = None) -> ConnectorResult:
        raise NotImplementedError

    @abstractmethod
    def download(self, dataset_id: str, params: dict[str, Any], output_path: str) -> ConnectorResult:
        raise NotImplementedError

    @abstractmethod
    def validate(self, dataset_id: str, file_path: str) -> ConnectorResult:
        raise NotImplementedError

    @abstractmethod
    def cite(self, dataset_id: str) -> ConnectorResult:
        raise NotImplementedError
