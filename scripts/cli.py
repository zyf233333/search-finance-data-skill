"""Command-line entry point for safe public-data inspection and download."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .connectors import CsmarConnector, FredConnector, KennethFrenchConnector, RessetConnector, SecEdgarConnector, WrdsConnector
from .connectors.http import HttpClient
from .logging_utils import JsonlLogger


def _connector(provider: str, cache_dir: Path, log_path: Path):
    client = HttpClient(cache_dir=cache_dir)
    logger = JsonlLogger(log_path)
    return {"fred": FredConnector(http_client=client, logger=logger), "french": KennethFrenchConnector(http_client=client, logger=logger), "sec": SecEdgarConnector(http_client=client, logger=logger), "wrds": WrdsConnector(logger=logger), "csmar": CsmarConnector(logger=logger), "resset": RessetConnector(logger=logger)}[provider]


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or download permitted public financial datasets.")
    parser.add_argument("provider", choices=["fred", "french", "sec", "wrds", "csmar", "resset"])
    parser.add_argument("operation", choices=["discover", "describe", "schema", "preview", "download", "validate", "cite"])
    parser.add_argument("dataset_id")
    parser.add_argument("--series-id", help="FRED series identifier, e.g. GDP")
    parser.add_argument("--output", help="Target file for download or validation")
    parser.add_argument("--cache-dir", default=".local/cache")
    parser.add_argument("--log-path", default=".local/logs/events.jsonl")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--source-file", help="Path to an export the user obtained through an authorised institutional session")
    args = parser.parse_args()

    connector = _connector(args.provider, Path(args.cache_dir), Path(args.log_path))
    params = {"limit": args.limit}
    if args.series_id:
        params["series_id"] = args.series_id
    if args.source_file:
        params["source_file"] = args.source_file
    if args.operation == "discover":
        result = connector.discover(args.dataset_id)
    elif args.operation in {"describe", "schema", "cite"}:
        result = getattr(connector, args.operation)(args.dataset_id)
    elif args.operation == "preview":
        result = connector.preview(args.dataset_id, params)
    elif args.operation == "download":
        if not args.output:
            parser.error("--output is required for download")
        result = connector.download(args.dataset_id, params, args.output)
    else:
        if not args.output:
            parser.error("--output is required for validate")
        result = connector.validate(args.dataset_id, args.output)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
