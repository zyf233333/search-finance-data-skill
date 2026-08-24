# Repository Guidelines

## Project Structure & Module Organization

This repository is currently a documentation-first design scaffold for the Empirical Finance Data Skill. Product requirements, architecture, and acceptance criteria live under `需求分析/`:

- `empirical_finance_data_skill_PRD.txt` — user goals and MVP scope.
- `empirical_finance_data_skill_technical_design.txt` — architecture, schemas, connectors, and data-flow design.
- `开发进度.txt` — completion checklist and verification baseline.

As implementation begins, follow the planned layout: `knowledge/` for registries, `schemas/` for JSON Schema, `scripts/` for Python orchestration and connectors, `templates/` for evidence outputs, `examples/` for end-to-end cases, and `tests/` for automated checks. Keep generated data out of source control (for example, use `raw/`, `processed/`, and `evidence/` in a separate run directory).

## Build, Test, and Development Commands

No build system or executable code is present yet. When Python modules are added, run commands from the repository root, for example:

```powershell
python -m pytest
python -m pytest tests/test_fred.py -q
python -m <module> --help
```

Document new setup or lint commands here and in the project README. Prefer offline fixtures; live database downloads should be explicit integration checks.

## Coding Style & Naming Conventions

Use Python 3 with four-space indentation, type hints, and deterministic functions. Format and lint with the chosen tooling (for example, `ruff format` and `ruff check`). Use `snake_case` for files, functions, variables, and registry identifiers; use `PascalCase` for classes. Connectors should implement the shared protocol (`discover`, `describe`, `check_access`, `schema`, `preview`, `download`, `validate`, `cite`) and return structured results.

## Testing Guidelines

Use `pytest`, naming files `test_*.py` and tests `test_<behavior>`. Cover schema validation, registry resolution, access/error states, preview-before-download behavior, financial-data validation, provenance, and identifier joins. Verify successful results and explainable failures; do not require credentials or paid databases by default.

## Commit & Pull Request Guidelines

There is no Git history in the current scaffold, so no repository-specific convention is established. Use short imperative commit subjects (for example, `Add FRED connector schema`) and keep each commit focused. Pull requests should explain the user-visible or architectural change, link the relevant requirement, include tests or fixture evidence, and call out licensing, authentication, or data-quality implications. Include sample output or screenshots when changing generated evidence formats.

## Security & Data-Access Rules

Never commit API keys, passwords, session cookies, or downloaded restricted data. Respect provider terms, institutional access controls, rate limits, and download restrictions. Store credentials only through approved local mechanisms and make access failures explicit (`AUTH_REQUIRED`, `LICENSE_RESTRICTED`, etc.).
