"""Run the repository's free public-data workflow from the installed skill."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def find_repository(start: Path) -> Path:
    """Find the repository root from this script's installed location."""
    for candidate in (start, *start.parents):
        if (
            (candidate / "scripts" / "workflow.py").is_file()
            and (candidate / "knowledge" / "datasets.json").is_file()
        ):
            return candidate
    raise RuntimeError(
        "Could not find the skill repository root. Run this command from a clone "
        "of the full search-finance-data-skill repository."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Search and download free public finance data.")
    parser.add_argument("question")
    parser.add_argument("--output", help="Run output directory; defaults to the repository's .local folder.")
    parser.add_argument("--preview-limit", type=int, default=5)
    args = parser.parse_args()
    repository = find_repository(Path(__file__).resolve().parent)
    output = Path(args.output) if args.output else repository / ".local" / f"search-{datetime.now():%Y%m%d-%H%M%S}"
    command = [
        sys.executable,
        "-B",
        "-m",
        "scripts.workflow",
        args.question,
        "--output",
        str(output),
        "--preview-limit",
        str(args.preview_limit),
    ]
    completed = subprocess.run(command, cwd=repository, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
