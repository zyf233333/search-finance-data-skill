"""Public FRED graph CSV connector (no API key required for this endpoint)."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ..contracts import ConnectorResult, ErrorInfo
from ..validator import validate_csv
from .public import PublicDatasetConnector


class FredConnector(PublicDatasetConnector):
    provider = "Federal Reserve Bank of St. Louis"
    documentation_url = "https://fred.stlouisfed.org/docs/api/fred/"
    base_url = "https://fred.stlouisfed.org/graph/fredgraph.csv"

    def _series_id(self, dataset_id: str, params: dict[str, Any] | None = None) -> str:
        if params and params.get("series_id"):
            return str(params["series_id"])
        return dataset_id.removeprefix("fred.series.")

    def _url(self, series_id: str) -> str:
        return f"{self.base_url}?{urlencode({'id': series_id})}"

    def discover(self, query: str) -> ConnectorResult:
        return ConnectorResult.ok("discover", [{"dataset_id": f"fred.series.{query.upper()}", "series_id": query.upper()}])

    def describe(self, dataset_id: str) -> ConnectorResult:
        series_id = self._series_id(dataset_id)
        return ConnectorResult.ok("describe", {"dataset_id": dataset_id, "series_id": series_id, "provider": self.provider, "dataset_name": f"FRED Series {series_id}", "documentation_url": self.documentation_url, "access_type": "public"})

    def schema(self, dataset_id: str) -> ConnectorResult:
        series_id = self._series_id(dataset_id)
        return ConnectorResult.ok("schema", {"dataset_id": dataset_id, "fields": ["observation_date", series_id]})

    def preview(self, dataset_id: str, params: dict[str, Any] | None = None) -> ConnectorResult:
        series_id = self._series_id(dataset_id, params)
        result = self._download_bytes("preview", self._url(series_id))
        if not result.success:
            return result
        rows = list(csv.DictReader(io.StringIO(result.data.decode("utf-8-sig"))))
        limit = int((params or {}).get("limit", 20))
        return ConnectorResult.ok("preview", rows[:limit], source_url=result.metadata["source_url"], fields=["observation_date", series_id])

    def download(self, dataset_id: str, params: dict[str, Any], output_path: str) -> ConnectorResult:
        series_id = self._series_id(dataset_id, params)
        result = self._download_bytes("download", self._url(series_id))
        if not result.success:
            return result
        temp = Path(output_path).with_suffix(Path(output_path).suffix + ".tmp")
        temp.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(result.data)
        validation = validate_csv(temp, required_fields=["observation_date", series_id])
        temp.unlink()
        if not validation["valid"]:
            return ConnectorResult.fail("download", ErrorInfo("VALIDATION_FAILED", "FRED response failed CSV validation."), validation=validation)
        return self._write_download(dataset_id=dataset_id, output_path=output_path, content=result.data, source_url=result.metadata["source_url"], validation=validation)

    def validate(self, dataset_id: str, file_path: str) -> ConnectorResult:
        series_id = self._series_id(dataset_id)
        validation = validate_csv(file_path, required_fields=["observation_date", series_id])
        return ConnectorResult.ok("validate", validation) if validation["valid"] else ConnectorResult.fail("validate", ErrorInfo("VALIDATION_FAILED", "FRED CSV is invalid."), validation=validation)

    def cite(self, dataset_id: str) -> ConnectorResult:
        return ConnectorResult.ok("cite", {"dataset_id": dataset_id, "citation": "Federal Reserve Bank of St. Louis, FRED."})
