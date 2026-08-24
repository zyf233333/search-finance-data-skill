"""Create a minimal, reproducible evidence record for public downloads."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_download_evidence(
    *,
    output_file: str | Path,
    provider: str,
    dataset: str,
    source_url: str,
    documentation_url: str,
    validation: dict[str, Any],
) -> dict[str, Any]:
    output = Path(output_file)
    downloaded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    record = {
        "provider": provider,
        "dataset": dataset,
        "source_url": source_url,
        "documentation_url": documentation_url,
        "downloaded_at": downloaded_at,
        "file_name": output.name,
        "sha256": sha256_file(output),
        "validation": validation,
    }
    evidence_path = output.with_name(output.name + ".evidence.json")
    evidence_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    _append_data_source_markdown(output.parent / "data_sources.md", record)
    return {"evidence_path": str(evidence_path), **record}


def _append_data_source_markdown(path: Path, record: dict[str, Any]) -> None:
    """Append a readable companion record; the JSON file remains authoritative."""
    if not path.exists():
        path.write_text("# Data Sources\n\n", encoding="utf-8")
    block = (
        f"## {record['dataset']}\n\n"
        f"- Provider: {record['provider']}\n"
        f"- Downloaded at: {record['downloaded_at']}\n"
        f"- Source URL: {record['source_url']}\n"
        f"- Documentation: {record['documentation_url']}\n"
        f"- File: `{record['file_name']}`\n"
        f"- SHA-256: `{record['sha256']}`\n"
        f"- Validation: {record['validation']['row_count']} rows; valid={record['validation']['valid']}\n\n"
    )
    with path.open("a", encoding="utf-8") as stream:
        stream.write(block)
