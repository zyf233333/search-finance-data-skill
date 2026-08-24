"""Safe adapters for institutionally licensed exports from WRDS, CSMAR, and RESSET."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

from ..access import AccessResolver, AccessState
from ..contracts import ConnectorResult, ErrorInfo
from ..evidence import write_download_evidence
from ..logging_utils import JsonlLogger
from ..validator import validate_csv, validate_json
from .base import DatasetConnector


PROVIDERS = {
    "WRDS": {
        "documentation_url": "https://wrds-www.wharton.upenn.edu/pages/support/accessing-wrds/",
        "datasets": {
            "wrds.compustat.funda": {"name": "Compustat Fundamentals Annual", "table": "funda", "fields": ["gvkey", "datadate", "at", "ni"], "identifiers": ["gvkey", "datadate"], "frequency": "annual"},
            "wrds.crsp.msf": {"name": "CRSP Monthly Stock File", "table": "msf", "fields": ["permno", "date", "ret", "prc", "shrout"], "identifiers": ["permno", "date"], "frequency": "monthly"},
        },
    },
    "CSMAR": {
        "documentation_url": "https://www.gtarsc.com/",
        "datasets": {
            "csmar.stock_monthly": {"name": "China A-Share Monthly Stock Data", "table": "stock_monthly", "fields": ["Stkcd", "Trdmnt", "Mretwd"], "identifiers": ["Stkcd", "Trdmnt"], "frequency": "monthly"},
            "csmar.financial_statement": {"name": "China Listed Company Financial Statements", "table": "financial_statement", "fields": ["Stkcd", "Accper", "A001000000"], "identifiers": ["Stkcd", "Accper"], "frequency": "quarterly"},
        },
    },
    "RESSET": {
        "documentation_url": "https://www.resset.com/",
        "datasets": {
            "resset.stock_daily": {"name": "RESSET Stock Daily Data", "table": "stock_daily", "fields": ["Stkcd", "Trddt", "Dretwd"], "identifiers": ["Stkcd", "Trddt"], "frequency": "daily"},
            "resset.financial": {"name": "RESSET Listed Company Financial Data", "table": "financial", "fields": ["Stkcd", "Accper", "A001000000"], "identifiers": ["Stkcd", "Accper"], "frequency": "quarterly"},
        },
    },
}


ERRORS = {
    "AUTH_REQUIRED": "Complete the provider's legal login or configure a session marker.",
    "SESSION_EXPIRED": "Refresh the provider session through its normal login flow.",
    "MFA_REQUIRED": "Complete the provider MFA challenge in the normal user session.",
    "NO_SUBSCRIPTION": "Confirm that the institution has an active subscription.",
}


class InstitutionalDatasetConnector(DatasetConnector):
    provider = ""

    def __init__(self, *, access_resolver: AccessResolver | None = None, logger: JsonlLogger | None = None) -> None:
        self.access = access_resolver or AccessResolver()
        self.logger = logger
        self.config = PROVIDERS[self.provider]

    def discover(self, query: str) -> ConnectorResult:
        query_lower = query.lower()
        matches = [{"dataset_id": dataset_id, **metadata} for dataset_id, metadata in self.config["datasets"].items() if not query_lower or query_lower in dataset_id.lower() or query_lower in metadata["name"].lower()]
        return ConnectorResult.ok("discover", matches)

    def describe(self, dataset_id: str) -> ConnectorResult:
        metadata = self.config["datasets"].get(dataset_id)
        if metadata is None:
            return self._dataset_error("describe", dataset_id)
        return ConnectorResult.ok("describe", {"dataset_id": dataset_id, "provider": self.provider, "access_type": "institutional", **metadata})

    def check_access(self, dataset_id: str) -> ConnectorResult:
        if dataset_id not in self.config["datasets"]:
            return self._dataset_error("check_access", dataset_id)
        state = self.access.resolve(self.provider)
        if self.logger:
            self.logger.event("access_checked", provider=self.provider, dataset_id=dataset_id, access_type=state.access_type, authenticated=state.authenticated, next_action=state.next_action)
        if state.authenticated and state.session_valid:
            return ConnectorResult.ok("check_access", state.to_dict())
        code = {"user_login": "AUTH_REQUIRED", "refresh_session": "SESSION_EXPIRED", "complete_mfa": "MFA_REQUIRED", "contact_library": "NO_SUBSCRIPTION", "repair_session_marker": "SESSION_EXPIRED"}.get(state.next_action, "AUTH_REQUIRED")
        return ConnectorResult.fail("check_access", ErrorInfo(code, ERRORS.get(code, "Institutional access is not ready."), recoverable=True, next_action=state.next_action), access_state=state.to_dict())

    def schema(self, dataset_id: str) -> ConnectorResult:
        metadata = self.config["datasets"].get(dataset_id)
        if metadata is None:
            return self._dataset_error("schema", dataset_id)
        return ConnectorResult.ok("schema", {"dataset_id": dataset_id, "provider": self.provider, "fields": metadata["fields"], "identifiers": metadata["identifiers"], "frequency": metadata["frequency"]})

    def preview(self, dataset_id: str, params: dict[str, Any] | None = None) -> ConnectorResult:
        access_result = self.check_access(dataset_id)
        if not access_result.success:
            return ConnectorResult.fail("preview", access_result.error, access_state=access_result.metadata["access_state"])
        source = self._source_path(params)
        if source is None:
            return ConnectorResult.fail("preview", ErrorInfo("PREVIEW_NOT_CONFIGURED", "Provide a user-exported file through params['source_file']; remote SQL/browser execution is not enabled by default.", recoverable=True, next_action="provide_authorized_export"))
        try:
            rows = self._preview_file(source, int((params or {}).get("limit", 20)))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return ConnectorResult.fail("preview", ErrorInfo("EXPORT_INVALID", f"Authorized export cannot be previewed: {exc}", recoverable=True))
        return ConnectorResult.ok("preview", rows, source_type="authorized_local_export", source_file=str(source))

    def download(self, dataset_id: str, params: dict[str, Any], output_path: str) -> ConnectorResult:
        access_result = self.check_access(dataset_id)
        if not access_result.success:
            return ConnectorResult.fail("download", access_result.error, access_state=access_result.metadata["access_state"])
        source = self._source_path(params)
        if source is None:
            return ConnectorResult.fail("download", ErrorInfo("DOWNLOAD_NOT_CONFIGURED", "Remote institutional download is intentionally not enabled without a provider-specific authorized adapter. Supply params['source_file'] from a permitted export.", recoverable=True, next_action="provide_authorized_export"))
        if not source.exists() or not source.is_file():
            return ConnectorResult.fail("download", ErrorInfo("EXPORT_NOT_FOUND", f"Authorized export does not exist: {source}", recoverable=True, next_action="check_export_path"))
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)
        validation = self._validate_file(dataset_id, output)
        if not validation["valid"]:
            return ConnectorResult.fail("download", ErrorInfo("VALIDATION_FAILED", "Authorized export failed the declared schema checks."), validation=validation)
        evidence = write_download_evidence(output_file=output, provider=self.provider, dataset=dataset_id, source_url=f"local-authorized-export://{source.name}", documentation_url=self.config["documentation_url"], validation={**validation, "access_type": "institutional", "source_file": source.name})
        if self.logger:
            self.logger.event("institutional_export_copied", provider=self.provider, dataset_id=dataset_id, output_path=str(output), access_type="institutional")
        return ConnectorResult.ok("download", {"output_path": str(output), "access_state": access_result.data, **evidence})

    def validate(self, dataset_id: str, file_path: str) -> ConnectorResult:
        if dataset_id not in self.config["datasets"]:
            return self._dataset_error("validate", dataset_id)
        validation = self._validate_file(dataset_id, Path(file_path))
        return ConnectorResult.ok("validate", validation) if validation["valid"] else ConnectorResult.fail("validate", ErrorInfo("VALIDATION_FAILED", "Institutional export is invalid."), validation=validation)

    def cite(self, dataset_id: str) -> ConnectorResult:
        metadata = self.config["datasets"].get(dataset_id)
        if metadata is None:
            return self._dataset_error("cite", dataset_id)
        return ConnectorResult.ok("cite", {"dataset_id": dataset_id, "provider": self.provider, "citation": f"{self.provider}, {metadata['name']}. Accessed through an authorised institutional subscription."})

    def _source_path(self, params: dict[str, Any] | None) -> Path | None:
        value = (params or {}).get("source_file")
        return Path(value) if value else None

    def _preview_file(self, path: Path, limit: int) -> list[dict[str, Any]]:
        if path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload if isinstance(payload, list) else list(payload.values()) if isinstance(payload, dict) else []
            return records[:limit]
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))[:limit]

    def _validate_file(self, dataset_id: str, path: Path) -> dict[str, Any]:
        required = self.config["datasets"][dataset_id]["fields"]
        return validate_json(path, required_fields=required) if path.suffix.lower() == ".json" else validate_csv(path, required_fields=required)

    def _dataset_error(self, operation: str, dataset_id: str) -> ConnectorResult:
        return ConnectorResult.fail(operation, ErrorInfo("DATASET_NOT_FOUND", f"Unknown {self.provider} dataset: {dataset_id}", recoverable=True, next_action="discover"))


class WrdsConnector(InstitutionalDatasetConnector):
    provider = "WRDS"


class CsmarConnector(InstitutionalDatasetConnector):
    provider = "CSMAR"


class RessetConnector(InstitutionalDatasetConnector):
    provider = "RESSET"
