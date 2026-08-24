"""SEC EDGAR public company-ticker reference connector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..contracts import ConnectorResult, ErrorInfo
from ..validator import validate_json
from .public import PublicDatasetConnector


class SecEdgarConnector(PublicDatasetConnector):
    provider = "U.S. Securities and Exchange Commission"
    documentation_url = "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
    ticker_url = "https://www.sec.gov/files/company_tickers.json"
    dataset_id = "sec.company_tickers"

    def discover(self, query: str) -> ConnectorResult:
        normalized = query.upper()
        if normalized in {"TICKER", "TICKERS", "COMPANY", "COMPANIES", "SEC"}:
            return ConnectorResult.ok("discover", [{"dataset_id": self.dataset_id, "description": "SEC company ticker/CIK reference"}])
        return ConnectorResult.ok("discover", [])

    def describe(self, dataset_id: str) -> ConnectorResult:
        if dataset_id != self.dataset_id:
            return ConnectorResult.fail("describe", ErrorInfo("DATASET_NOT_FOUND", f"Unknown SEC dataset: {dataset_id}", recoverable=True))
        return ConnectorResult.ok("describe", {"dataset_id": dataset_id, "provider": self.provider, "dataset_name": "EDGAR Company Ticker Reference", "documentation_url": self.documentation_url, "access_type": "public", "frequency": "periodic"})

    def schema(self, dataset_id: str) -> ConnectorResult:
        if dataset_id != self.dataset_id:
            return ConnectorResult.fail("schema", ErrorInfo("DATASET_NOT_FOUND", f"Unknown SEC dataset: {dataset_id}", recoverable=True))
        return ConnectorResult.ok("schema", {"dataset_id": dataset_id, "fields": ["cik_str", "ticker", "title"]})

    def preview(self, dataset_id: str, params: dict[str, Any] | None = None) -> ConnectorResult:
        if dataset_id != self.dataset_id:
            return ConnectorResult.fail("preview", ErrorInfo("DATASET_NOT_FOUND", f"Unknown SEC dataset: {dataset_id}", recoverable=True))
        result = self._download_bytes("preview", self.ticker_url)
        if not result.success:
            return result
        records = list(json.loads(result.data.decode("utf-8")).values())
        return ConnectorResult.ok("preview", records[: int((params or {}).get("limit", 20))], source_url=result.metadata["source_url"])

    def download(self, dataset_id: str, params: dict[str, Any], output_path: str) -> ConnectorResult:
        if dataset_id != self.dataset_id:
            return ConnectorResult.fail("download", ErrorInfo("DATASET_NOT_FOUND", f"Unknown SEC dataset: {dataset_id}", recoverable=True))
        result = self._download_bytes("download", self.ticker_url)
        if not result.success:
            return result
        temp = Path(output_path).with_suffix(Path(output_path).suffix + ".tmp")
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(result.data)
        validation = validate_json(temp, required_fields=["cik_str", "ticker", "title"])
        temp.unlink()
        if not validation["valid"]:
            return ConnectorResult.fail("download", ErrorInfo("VALIDATION_FAILED", "SEC response failed JSON validation."), validation=validation)
        return self._write_download(dataset_id=dataset_id, output_path=output_path, content=result.data, source_url=result.metadata["source_url"], validation=validation)

    def validate(self, dataset_id: str, file_path: str) -> ConnectorResult:
        validation = validate_json(file_path, required_fields=["cik_str", "ticker", "title"])
        return ConnectorResult.ok("validate", validation) if validation["valid"] else ConnectorResult.fail("validate", ErrorInfo("VALIDATION_FAILED", "SEC JSON is invalid."), validation=validation)

    def cite(self, dataset_id: str) -> ConnectorResult:
        return ConnectorResult.ok("cite", {"dataset_id": dataset_id, "citation": "U.S. Securities and Exchange Commission, EDGAR company tickers."})
