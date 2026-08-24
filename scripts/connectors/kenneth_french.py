"""Kenneth French Data Library connector for the monthly FF3 archive."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from typing import Any

from ..contracts import ConnectorResult, ErrorInfo
from .public import PublicDatasetConnector


class KennethFrenchConnector(PublicDatasetConnector):
    provider = "Kenneth R. French Data Library"
    documentation_url = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
    dataset_id = "kenneth_french.ff3_monthly"
    archive_url = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"

    def discover(self, query: str) -> ConnectorResult:
        if any(token in query.lower() for token in ("fama", "french", "factor", "ff3")):
            return ConnectorResult.ok("discover", [{"dataset_id": self.dataset_id, "description": "Fama/French 3 Factors, monthly and annual"}])
        return ConnectorResult.ok("discover", [])

    def describe(self, dataset_id: str) -> ConnectorResult:
        if dataset_id != self.dataset_id:
            return ConnectorResult.fail("describe", ErrorInfo("DATASET_NOT_FOUND", f"Unknown French dataset: {dataset_id}", recoverable=True))
        return ConnectorResult.ok("describe", {"dataset_id": dataset_id, "provider": self.provider, "dataset_name": "Fama/French 3 Factors", "documentation_url": self.documentation_url, "access_type": "public", "frequency": "monthly"})

    def schema(self, dataset_id: str) -> ConnectorResult:
        if dataset_id != self.dataset_id:
            return ConnectorResult.fail("schema", ErrorInfo("DATASET_NOT_FOUND", f"Unknown French dataset: {dataset_id}", recoverable=True))
        return ConnectorResult.ok("schema", {"dataset_id": dataset_id, "fields": ["date", "Mkt-RF", "SMB", "HML", "RF"]})

    def _monthly_rows(self, archive: bytes) -> list[dict[str, str]]:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            csv_name = next(name for name in bundle.namelist() if name.lower().endswith(".csv"))
            text = bundle.read(csv_name).decode("latin-1")
        lines = text.splitlines()
        header_index = next(index for index, line in enumerate(lines) if "Mkt-RF" in line and "SMB" in line and "HML" in line)
        block = []
        for line in lines[header_index:]:
            if not line.strip():
                break
            block.append(line)
        reader = csv.DictReader(block, skipinitialspace=True)
        return [{key.strip(): value.strip() for key, value in row.items() if key is not None} for row in reader if row.get(reader.fieldnames[0] or "", "").strip().isdigit()]

    def preview(self, dataset_id: str, params: dict[str, Any] | None = None) -> ConnectorResult:
        if dataset_id != self.dataset_id:
            return ConnectorResult.fail("preview", ErrorInfo("DATASET_NOT_FOUND", f"Unknown French dataset: {dataset_id}", recoverable=True))
        result = self._download_bytes("preview", self.archive_url)
        if not result.success:
            return result
        rows = self._monthly_rows(result.data)
        return ConnectorResult.ok("preview", rows[: int((params or {}).get("limit", 20))], source_url=result.metadata["source_url"])

    def download(self, dataset_id: str, params: dict[str, Any], output_path: str) -> ConnectorResult:
        if dataset_id != self.dataset_id:
            return ConnectorResult.fail("download", ErrorInfo("DATASET_NOT_FOUND", f"Unknown French dataset: {dataset_id}", recoverable=True))
        result = self._download_bytes("download", self.archive_url)
        if not result.success:
            return result
        rows = self._monthly_rows(result.data)
        validation = {"valid": bool(rows), "file_type": "zip", "row_count": len(rows), "fields": ["date", "Mkt-RF", "SMB", "HML", "RF"]}
        if not validation["valid"]:
            return ConnectorResult.fail("download", ErrorInfo("VALIDATION_FAILED", "French archive has no monthly observations."), validation=validation)
        return self._write_download(dataset_id=dataset_id, output_path=output_path, content=result.data, source_url=result.metadata["source_url"], validation=validation)

    def validate(self, dataset_id: str, file_path: str) -> ConnectorResult:
        rows = self._monthly_rows(Path(file_path).read_bytes())
        validation = {"valid": bool(rows), "file_type": "zip", "row_count": len(rows), "fields": ["date", "Mkt-RF", "SMB", "HML", "RF"]}
        return ConnectorResult.ok("validate", validation) if validation["valid"] else ConnectorResult.fail("validate", ErrorInfo("VALIDATION_FAILED", "French archive is invalid."), validation=validation)

    def cite(self, dataset_id: str) -> ConnectorResult:
        return ConnectorResult.ok("cite", {"dataset_id": dataset_id, "citation": "Kenneth R. French Data Library, Fama/French Research Data Factors."})
