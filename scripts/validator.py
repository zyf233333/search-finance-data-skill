"""Deterministic, provider-agnostic checks for downloaded public data."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any


def validate_csv(path: str | Path, *, required_fields: list[str] | None = None) -> dict[str, Any]:
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        missing_fields = sorted(set(required_fields or []) - set(fields))
        rows = list(reader)
    missing_values = {field: sum(not (row.get(field) or "").strip() for row in rows) for field in fields}
    return {
        "valid": bool(rows) and not missing_fields,
        "file_type": "csv",
        "row_count": len(rows),
        "fields": fields,
        "missing_required_fields": missing_fields,
        "missing_values": missing_values,
    }


def validate_json(path: str | Path, *, required_fields: list[str] | None = None) -> dict[str, Any]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    records = payload if isinstance(payload, list) else list(payload.values()) if isinstance(payload, dict) else []
    fields = sorted({key for record in records if isinstance(record, dict) for key in record})
    missing_fields = sorted(set(required_fields or []) - set(fields))
    return {
        "valid": bool(records) and not missing_fields,
        "file_type": "json",
        "row_count": len(records),
        "fields": fields,
        "missing_required_fields": missing_fields,
    }


def validate_financial_csv(
    path: str | Path,
    *,
    date_field: str,
    key_fields: list[str] | None = None,
    numeric_fields: list[str] | None = None,
    expected_frequency: str | None = None,
) -> dict[str, Any]:
    """Run deterministic checks useful for research data without guessing bias away."""
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        rows = list(reader)
    key_fields = key_fields or []
    numeric_fields = numeric_fields or []
    parsed_dates: list[date] = []
    invalid_dates = 0
    for row in rows:
        try:
            parsed_dates.append(_parse_date(row.get(date_field, "")))
        except ValueError:
            invalid_dates += 1
    duplicate_count = 0
    if key_fields:
        keys = [tuple((row.get(field) or "").strip() for field in key_fields) for row in rows]
        duplicate_count = sum(count - 1 for count in Counter(keys).values() if count > 1)
    numeric_errors = {field: 0 for field in numeric_fields}
    for row in rows:
        for field in numeric_fields:
            try:
                float((row.get(field) or "").strip())
            except (TypeError, ValueError):
                numeric_errors[field] += 1
    inferred_frequency = infer_frequency(parsed_dates)
    warnings = ["look_ahead_bias: requires manual confirmation of observation and information dates"]
    if key_fields:
        warnings.append("survivorship_bias: requires manual confirmation that delisted entities are represented")
    if expected_frequency and inferred_frequency not in {expected_frequency, "unknown", "insufficient_data"}:
        warnings.append(f"frequency_mismatch: expected {expected_frequency}, inferred {inferred_frequency}")
    return {
        "valid": bool(rows) and date_field in fields and invalid_dates == 0 and duplicate_count == 0 and not any(numeric_errors.values()),
        "file_type": "csv",
        "row_count": len(rows),
        "fields": fields,
        "date_field": date_field,
        "invalid_dates": invalid_dates,
        "duplicate_key_rows": duplicate_count,
        "numeric_errors": numeric_errors,
        "coverage": {"start": min(parsed_dates).isoformat() if parsed_dates else None, "end": max(parsed_dates).isoformat() if parsed_dates else None},
        "inferred_frequency": inferred_frequency,
        "expected_frequency": expected_frequency,
        "warnings": warnings,
    }


def infer_frequency(values: list[date]) -> str:
    if len(values) < 2:
        return "insufficient_data"
    ordered = sorted(set(values))
    gaps = [(right - left).days for left, right in zip(ordered, ordered[1:])]
    median_gap = sorted(gaps)[len(gaps) // 2]
    if median_gap <= 2:
        return "daily"
    if 27 <= median_gap <= 32:
        return "monthly"
    if 80 <= median_gap <= 100:
        return "quarterly"
    if 350 <= median_gap <= 380:
        return "annual"
    return "irregular"


def _parse_date(value: str) -> date:
    normalized = (value or "").strip()
    for parser in (lambda text: datetime.fromisoformat(text).date(), lambda text: datetime.strptime(text, "%Y%m%d").date(), lambda text: datetime.strptime(text, "%Y-%m").date()):
        try:
            return parser(normalized)
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")
