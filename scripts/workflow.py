"""End-to-end workflow for the free public-data path."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .connectors import FredConnector, KennethFrenchConnector, SecEdgarConnector
from .connectors.http import HttpClient
from .contracts import ConnectorResult, ErrorInfo, ProvenanceRecord, ResearchDataSpec, VariableSpec
from .evidence_package import build_evidence_package
from .logging_utils import JsonlLogger
from .panel import build_research_panel
from .registry import DatasetRegistry
from .state import StateStore
from .validator import validate_financial_csv


class WorkflowError(RuntimeError):
    """Raised for a user-correctable workflow planning or data error."""


@dataclass
class DatasetSelection:
    variable_ids: list[str]
    dataset_id: str
    provider_key: str


class FreeResearchParser:
    """Small deterministic parser for the first free-data benchmark tasks."""

    FRED_SERIES = {
        "gdp": ("GDP", "quarterly", "gdp"),
        "gross domestic product": ("GDP", "quarterly", "gdp"),
        "cpi": ("CPIAUCSL", "monthly", "fred_cpi"),
        "inflation": ("CPIAUCSL", "monthly", "fred_cpi"),
        "unemployment": ("UNRATE", "monthly", "fred_unemployment"),
        "unemployment rate": ("UNRATE", "monthly", "fred_unemployment"),
        "federal funds": ("FEDFUNDS", "monthly", "fred_federal_funds_rate"),
        "interest rate": ("FEDFUNDS", "monthly", "fred_federal_funds_rate"),
        "industrial production": ("INDPRO", "monthly", "fred_industrial_production"),
        "treasury 10 year": ("DGS10", "daily", "fred_treasury_10y"),
    }

    def parse(self, question: str) -> ResearchDataSpec:
        text = question.lower()
        if "fama" in text or "french" in text or "ff3" in text or "three factor" in text:
            variables = [
                VariableSpec("ff_mkt", role="independent", measurement="market_excess_return", raw_variables=["Mkt-RF"], status="resolved", confidence=0.98),
                VariableSpec("ff_smb", role="control", measurement="size_factor", raw_variables=["SMB"], status="resolved", confidence=0.98),
                VariableSpec("ff_hml", role="control", measurement="value_factor", raw_variables=["HML"], status="resolved", confidence=0.98),
                VariableSpec("risk_free_rate", role="control", measurement="risk_free_rate", raw_variables=["RF"], status="resolved", confidence=0.98),
            ]
            return ResearchDataSpec(question, market="United States", frequency="monthly", unit="month", variables=variables, status="resolved")
        for phrase, (series_id, frequency, concept) in self.FRED_SERIES.items():
            if phrase in text:
                return ResearchDataSpec(question, market="United States", frequency=frequency, unit="observation", variables=[VariableSpec(concept, role="dependent", measurement=f"fred_series_{series_id.lower()}", raw_variables=[series_id], status="resolved", confidence=0.95)], status="resolved")
        if "sec" in text or "ticker" in text or "company cik" in text or "edgar" in text:
            return ResearchDataSpec(question, market="United States", frequency="periodic", unit="company", variables=[VariableSpec("sec_company_ticker", role="identifier", measurement="ticker_cik_reference", raw_variables=["cik_str", "ticker", "title"], status="resolved", confidence=0.95)], status="resolved")
        raise WorkflowError("UNSUPPORTED_RESEARCH_REQUEST: supported free requests include FRED GDP/CPI/unemployment/interest-rate/industrial-production/Treasury series, Fama-French factors, and SEC company identifiers.")


class FreeDatasetResolver:
    """Resolve only public datasets and reject institutional candidates."""

    def __init__(self, registry: DatasetRegistry) -> None:
        self.registry = registry

    def resolve(self, spec: ResearchDataSpec) -> list[DatasetSelection]:
        selections: dict[str, DatasetSelection] = {}
        for index, variable in enumerate(spec.variables):
            variable_id = _variable_id(variable.concept, index)
            concept = variable.concept.lower()
            if concept == "gdp" or "gdp" in concept or concept.startswith("fred_"):
                dataset_id = f"fred.series.{(variable.raw_variables or ['GDP'])[0].upper()}"
                provider_key = "fred"
            elif concept.startswith("ff_") or concept == "risk_free_rate":
                dataset_id = "kenneth_french.ff3_monthly"
                provider_key = "french"
            elif concept.startswith("sec_") or "ticker" in concept:
                dataset_id = "sec.company_tickers"
                provider_key = "sec"
            else:
                raise WorkflowError(f"UNRESOLVED_VARIABLE: no free public dataset mapping for {variable.concept}.")
            if not dataset_id.startswith("fred.series."):
                metadata = self.registry.get(dataset_id)
                if metadata.get("access_type") != "public":
                    raise WorkflowError(f"NON_PUBLIC_DATASET: {dataset_id} is not public.")
            selection = selections.setdefault(dataset_id, DatasetSelection([], dataset_id, provider_key))
            selection.variable_ids.append(variable_id)
        return list(selections.values())


class FreeResearchWorkflow:
    def __init__(self, output_dir: str | Path, *, connectors: dict[str, Any] | None = None, registry_path: str | Path = "knowledge/datasets.json") -> None:
        self.output_dir = Path(output_dir)
        self.logger = JsonlLogger(self.output_dir / "logs" / "events.jsonl")
        client = HttpClient(cache_dir=self.output_dir / "cache", min_interval_seconds=0.2)
        self.connectors = connectors or {"fred": FredConnector(http_client=client, logger=self.logger), "french": KennethFrenchConnector(http_client=client, logger=self.logger), "sec": SecEdgarConnector(http_client=client, logger=self.logger)}
        self.resolver = FreeDatasetResolver(DatasetRegistry(registry_path))

    def run(self, request: str | ResearchDataSpec, *, preview_limit: int = 5) -> dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            spec = FreeResearchParser().parse(request) if isinstance(request, str) else request
        except WorkflowError as exc:
            question = request if isinstance(request, str) else request.research_question
            spec = ResearchDataSpec(question, status="failed")
            events = [{"stage": "parse", "status": "failed", "error": str(exc)}]
            StateStore(self.output_dir / "workflow_state.json").save(spec, events=events)
            result = {"success": False, "spec_id": spec.spec_id, "status": "failed", "error": str(exc), "events": events}
            (self.output_dir / "workflow_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
        events: list[dict[str, Any]] = [{"stage": "parse", "status": "completed", "spec_id": spec.spec_id}]
        try:
            selections = self.resolver.resolve(spec)
            events.append({"stage": "resolve", "status": "completed", "datasets": [selection.dataset_id for selection in selections]})
            provenance: list[ProvenanceRecord] = []
            data_sources: list[dict[str, Any]] = []
            citations: list[dict[str, str]] = []
            access_log: list[dict[str, Any]] = []
            tabular_sources: list[list[dict[str, Any]]] = []
            for selection in selections:
                connector = self.connectors[selection.provider_key]
                describe = self._require(connector.describe(selection.dataset_id), "describe")
                schema = self._require(connector.schema(selection.dataset_id), "schema")
                access = self._require(connector.check_access(selection.dataset_id), "check_access")
                access_log.append({"event": "access_checked", "provider": describe["provider"] if "provider" in describe else selection.provider_key, "dataset_id": selection.dataset_id, "access_type": "public", "authenticated": access.get("authenticated", False)})
                preview = self._require(connector.preview(selection.dataset_id, {"limit": preview_limit}), "preview")
                raw_path = self.output_dir / "raw" / _output_name(selection.dataset_id)
                download = self._require(connector.download(selection.dataset_id, {}, str(raw_path)), "download")
                validation = self._require(connector.validate(selection.dataset_id, str(raw_path)), "validate")
                if raw_path.suffix.lower() == ".csv":
                    date_field = "observation_date" if "observation_date" in schema.get("fields", []) else "date"
                    financial_checks = validate_financial_csv(raw_path, date_field=date_field, numeric_fields=[field for field in schema.get("fields", []) if field != date_field], expected_frequency=spec.frequency)
                    validation = {**validation, "financial_checks": financial_checks}
                self.logger.event("workflow_dataset_complete", dataset_id=selection.dataset_id, row_count=validation.get("row_count"), preview_rows=len(preview))
                receipt = json.loads(Path(download["evidence_path"]).read_text(encoding="utf-8"))
                data_sources.append({"dataset": selection.dataset_id, "provider": describe.get("provider", "Public provider"), "access_type": "public", "coverage": validation.get("coverage", "See validation record"), "documentation_url": describe.get("documentation_url", receipt.get("documentation_url")), "notes": f"Previewed {len(preview)} rows before download."})
                citations.append({"key": _citation_key(selection.dataset_id), "author": describe.get("provider", "Public provider"), "title": describe.get("dataset_name", selection.dataset_id), "year": receipt.get("downloaded_at", "")[:4], "url": receipt.get("documentation_url", "")})
                extracted_rows = _extract_rows(raw_path)
                if extracted_rows:
                    tabular_sources.append(extracted_rows)
                for variable_id in selection.variable_ids:
                    variable = next(variable for index, variable in enumerate(spec.variables) if _variable_id(variable.concept, index) == variable_id)
                    provenance.append(ProvenanceRecord(variable_id, variable.concept, describe.get("provider", "Public provider"), selection.dataset_id, variable.raw_variables or schema.get("fields", []), variable.measurement, spec.frequency, receipt.get("downloaded_at"), receipt.get("documentation_url")))
                events.append({"stage": selection.dataset_id, "status": "completed", "preview_rows": len(preview), "validation": validation})
            processed = self.output_dir / "processed"
            panel_path = processed / "research_panel.csv"
            additions = []
            if tabular_sources:
                base_fields = set(tabular_sources[0][0]) if tabular_sources[0] else set()
                for right_rows in tabular_sources[1:]:
                    right_fields = set(right_rows[0]) if right_rows else set()
                    candidate = next((field for field in ("date", "observation_date", "ticker", "cik_str", "gvkey", "permno") if field in base_fields and field in right_fields), None)
                    if candidate:
                        additions.append((right_rows, [candidate]))
            merge_report = build_research_panel(tabular_sources[0] if tabular_sources else [], additions, output_path=panel_path, report_path=processed / "merge_report.json")
            evidence_paths = build_evidence_package(self.output_dir / "evidence", spec, provenance=provenance, data_sources=data_sources, citations=citations, facts=[f"{record.dataset} was retrieved from {record.source}." for record in provenance], suggested_wording=[f"The variable {record.variable_id} is sourced from {record.dataset}." for record in provenance], access_log=access_log)
            spec.status = "verified"
            StateStore(self.output_dir / "workflow_state.json").save(spec, events=events)
            result = {"success": True, "spec_id": spec.spec_id, "status": "verified", "datasets": [selection.dataset_id for selection in selections], "panel": merge_report, "evidence": evidence_paths, "events": events}
        except (WorkflowError, KeyError, OSError, ValueError) as exc:
            spec.status = "failed"
            events.append({"stage": "workflow", "status": "failed", "error": str(exc)})
            StateStore(self.output_dir / "workflow_state.json").save(spec, events=events)
            result = {"success": False, "spec_id": spec.spec_id, "status": "failed", "error": str(exc), "events": events}
        (self.output_dir / "workflow_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    @staticmethod
    def _require(result: ConnectorResult, operation: str) -> Any:
        if not result.success:
            message = result.error.message if result.error else f"{operation} failed"
            code = result.error.code if result.error else "OPERATION_FAILED"
            raise WorkflowError(f"{code}: {message}")
        return result.data


def _variable_id(concept: str, index: int) -> str:
    return "_".join("".join(character if character.isalnum() else "_" for character in concept.lower()).split("_")) or f"variable_{index + 1}"


def _output_name(dataset_id: str) -> str:
    if dataset_id.startswith("fred.series."):
        return f"{dataset_id.removeprefix('fred.series.').lower()}.csv"
    if dataset_id.startswith("kenneth_french"):
        return "french_ff3.zip"
    return "sec_company_tickers.json"


def _citation_key(dataset_id: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in dataset_id)


def _extract_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else list(payload.values()) if isinstance(payload, dict) else []
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            name = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
            text = archive.read(name).decode("latin-1")
        lines = text.splitlines()
        header = next(index for index, line in enumerate(lines) if "Mkt-RF" in line and "SMB" in line and "HML" in line)
        rows: list[dict[str, Any]] = []
        block = []
        for line in lines[header:]:
            if not line.strip():
                break
            block.append(line)
        for row in csv.DictReader(block, skipinitialspace=True):
            if row and list(row.values())[0].strip().isdigit():
                normalized = {key.strip(): value.strip() for key, value in row.items() if key is not None}
                if "" in normalized:
                    normalized["date"] = normalized.pop("")
                rows.append(normalized)
        return rows
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the free public-data research workflow.")
    parser.add_argument("question")
    parser.add_argument("--output", default=".local/run")
    parser.add_argument("--preview-limit", type=int, default=5)
    args = parser.parse_args()
    result = FreeResearchWorkflow(args.output).run(args.question, preview_limit=args.preview_limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
