"""Research-ready panel output with deterministic merge diagnostics."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .identifiers import JoinReport, left_join_rows


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv_rows(path: str | Path, rows: list[dict[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = _field_order(rows)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_research_panel(
    base_rows: list[dict[str, Any]],
    additions: list[tuple[list[dict[str, Any]], list[str]]],
    *,
    output_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    rows = list(base_rows)
    reports: list[JoinReport] = []
    for right_rows, keys in additions:
        rows, report = left_join_rows(rows, right_rows, keys=keys)
        reports.append(report)
    write_csv_rows(output_path, rows)
    report_payload = {"row_count": len(rows), "output_path": str(output_path), "joins": [report.to_dict() for report in reports]}
    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_payload


def _field_order(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    return fields
