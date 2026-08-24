"""Generate the complete, human-readable Evidence Package for a research task."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .contracts import ProvenanceRecord, ResearchDataSpec, utc_now


SENSITIVE_KEYS = {"password", "passwd", "secret", "token", "api_key", "apikey", "cookie", "session_cookie", "authorization", "credential"}


@dataclass
class EvidencePackage:
    output_dir: Path
    provenance: list[ProvenanceRecord] = field(default_factory=list)
    data_sources: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, str]] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    suggested_wording: list[str] = field(default_factory=list)
    access_log: list[dict[str, Any]] = field(default_factory=list)

    def write(self, spec: ResearchDataSpec) -> dict[str, str]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "provenance": self.output_dir / "provenance.json",
            "variable_dictionary": self.output_dir / "variable_dictionary.csv",
            "data_sources": self.output_dir / "data_sources.md",
            "citations": self.output_dir / "citations.bib",
            "methodology_notes": self.output_dir / "methodology_notes.md",
            "access_log": self.output_dir / "access_log.json",
        }
        self._write_json(paths["provenance"], {"schema_version": "0.1.0", "spec_id": spec.spec_id, "generated_at": utc_now(), "records": [record.to_dict() for record in self.provenance]})
        self._write_variable_dictionary(paths["variable_dictionary"], spec)
        self._write_data_sources(paths["data_sources"])
        self._write_citations(paths["citations"])
        self._write_methodology(paths["methodology_notes"], spec)
        self._write_json(paths["access_log"], {"schema_version": "0.1.0", "generated_at": utc_now(), "events": [_redact(item) for item in self.access_log]})
        return {name: str(path) for name, path in paths.items()}

    def _write_variable_dictionary(self, path: Path, spec: ResearchDataSpec) -> None:
        records_by_id = {record.variable_id: record for record in self.provenance}
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["variable_id", "concept", "role", "measurement", "raw_fields", "formula", "source", "dataset", "frequency", "documentation_url", "status"])
            writer.writeheader()
            for index, variable in enumerate(spec.variables):
                variable_id = _variable_id(variable.concept, index)
                record = records_by_id.get(variable_id)
                writer.writerow({"variable_id": variable_id, "concept": variable.concept, "role": variable.role, "measurement": variable.measurement or "", "raw_fields": ";".join(variable.raw_variables), "formula": record.formula if record else "", "source": record.source if record else "", "dataset": record.dataset if record else "", "frequency": record.frequency if record and record.frequency else (spec.frequency or ""), "documentation_url": record.documentation_url if record else "", "status": variable.status})

    def _write_data_sources(self, path: Path) -> None:
        lines = ["# Data Sources", "", "Generated from the task's source and access records.", ""]
        for item in self.data_sources:
            lines.extend([f"## {item.get('dataset', item.get('dataset_id', 'Unknown dataset'))}", "", f"- Provider: {item.get('provider', 'Unknown')}", f"- Access: {item.get('access_type', 'institutional')}", f"- Coverage: {item.get('coverage', 'Not specified')}", f"- Documentation: {item.get('documentation_url', 'Not specified')}", f"- Notes: {item.get('notes', 'Use only within the provider licence.')}", ""])
        path.write_text("\n".join(lines), encoding="utf-8")

    def _write_citations(self, path: Path) -> None:
        entries = []
        for index, citation in enumerate(self.citations, 1):
            key = citation.get("key") or f"dataset{index}"
            entries.append("@misc{" + key + ",\n" + "\n".join(f"  {field} = {{{value}}}," for field, value in citation.items() if field != "key") + "\n}")
        path.write_text("\n\n".join(entries) + ("\n" if entries else ""), encoding="utf-8")

    def _write_methodology(self, path: Path, spec: ResearchDataSpec) -> None:
        lines = ["# Methodology Notes", "", f"Research question: {spec.research_question}", "", "## FACT", ""]
        lines.extend(f"- {fact}" for fact in self.facts or ["No factual notes were supplied."])
        lines.extend(["", "## SUGGESTED WORDING", ""])
        lines.extend(f"- {word}" for word in self.suggested_wording or ["No suggested wording was supplied."])
        lines.extend(["", "Generated facts and suggested wording are intentionally kept separate.", ""])
        path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(_redact(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _variable_id(concept: str, index: int) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", concept.lower()).strip("_")
    return normalized or f"variable_{index + 1}"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS or any(fragment in key.lower() for fragment in ("password", "secret", "token", "cookie", "credential", "api_key", "authorization")) else _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def build_evidence_package(output_dir: str | Path, spec: ResearchDataSpec, *, provenance: Iterable[ProvenanceRecord] = (), data_sources: Iterable[dict[str, Any]] = (), citations: Iterable[dict[str, str]] = (), facts: Iterable[str] = (), suggested_wording: Iterable[str] = (), access_log: Iterable[dict[str, Any]] = ()) -> dict[str, str]:
    package = EvidencePackage(Path(output_dir), list(provenance), list(data_sources), list(citations), list(facts), list(suggested_wording), list(access_log))
    return package.write(spec)
