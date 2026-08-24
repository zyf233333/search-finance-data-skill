"""Reusable mechanics for permitted public-data connector downloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import ConnectorResult, ErrorInfo
from ..evidence import write_download_evidence
from ..logging_utils import JsonlLogger
from .base import DatasetConnector
from .http import HttpClient, HttpClientError


class PublicDatasetConnector(DatasetConnector):
    provider = ""
    documentation_url = ""

    def __init__(self, *, http_client: HttpClient | None = None, logger: JsonlLogger | None = None) -> None:
        self.http = http_client or HttpClient()
        self.logger = logger

    def check_access(self, dataset_id: str) -> ConnectorResult:
        return ConnectorResult.ok("check_access", {"dataset_id": dataset_id, "access_type": "public", "authenticated": False})

    def _download_bytes(self, operation: str, url: str) -> ConnectorResult:
        try:
            response = self.http.get(url)
        except HttpClientError as exc:
            return ConnectorResult.fail(
                operation,
                ErrorInfo("NETWORK_ERROR", str(exc), recoverable=True, next_action="retry"),
                source_url=url,
            )
        return ConnectorResult.ok(operation, response.body, source_url=response.url, from_cache=response.from_cache)

    def _write_download(
        self,
        *,
        dataset_id: str,
        output_path: str,
        content: bytes,
        source_url: str,
        validation: dict[str, Any],
    ) -> ConnectorResult:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        evidence = write_download_evidence(
            output_file=output,
            provider=self.provider,
            dataset=dataset_id,
            source_url=source_url,
            documentation_url=self.documentation_url,
            validation=validation,
        )
        if self.logger:
            self.logger.event("download_complete", provider=self.provider, dataset_id=dataset_id, output_path=str(output))
        return ConnectorResult.ok("download", {"output_path": str(output), **evidence})
