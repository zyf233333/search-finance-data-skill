"""Deterministic identifier normalization and join diagnostics."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable


def normalize_identifier(value: Any, identifier_type: str) -> str:
    text = "" if value is None else str(value).strip()
    kind = identifier_type.lower()
    if kind in {"ticker", "cusip", "isin"}:
        return re.sub(r"\s+", "", text).upper()
    if kind == "cik":
        digits = re.sub(r"\D", "", text)
        return digits.zfill(10) if digits else ""
    if kind in {"permno", "permco", "gvkey"}:
        digits = re.sub(r"\D", "", text)
        return digits.zfill(6) if digits else ""
    return text


@dataclass
class JoinReport:
    left_rows: int
    right_rows: int
    matched_left_rows: int
    unmatched_left_rows: int
    duplicate_right_keys: int
    key_fields: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_rows(rows: Iterable[dict[str, Any]], *, field: str, identifier_type: str) -> list[dict[str, Any]]:
    return [{**row, field: normalize_identifier(row.get(field), identifier_type)} for row in rows]


def left_join_rows(left: list[dict[str, Any]], right: list[dict[str, Any]], *, keys: list[str], suffix: str = "_right") -> tuple[list[dict[str, Any]], JoinReport]:
    right_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in right:
        right_groups[tuple(row.get(key) for key in keys)].append(row)
    duplicate_right_keys = sum(len(group) - 1 for group in right_groups.values() if len(group) > 1)
    result: list[dict[str, Any]] = []
    matched = 0
    for left_row in left:
        key = tuple(left_row.get(field) for field in keys)
        matches = right_groups.get(key, [])
        if matches:
            matched += 1
            right_row = matches[0]
            merged = dict(left_row)
            for field, value in right_row.items():
                if field in keys:
                    continue
                target = field if field not in merged else f"{field}{suffix}"
                merged[target] = value
        else:
            merged = dict(left_row)
        result.append(merged)
    report = JoinReport(len(left), len(right), matched, len(left) - matched, duplicate_right_keys, list(keys))
    return result, report
