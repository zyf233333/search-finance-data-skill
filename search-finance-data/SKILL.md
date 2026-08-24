---
name: search-finance-data
description: Find and download free, public finance data for an empirical research question, with preview, validation, provenance, and a research-ready panel. Use for FRED, Kenneth French, or SEC EDGAR data; do not use for institutional databases or paid sources.
---

# Search Finance Data

Use this skill when the user asks to locate, download, validate, or prepare a free public finance dataset for research.

## Scope

The backend is the full repository containing the `knowledge/`, `schemas/`, and
`scripts/` directories. When this skill is cloned, run commands from that
repository root; the bundled wrapper locates the root automatically.

Supported public paths:

- FRED Graph CSV series, such as GDP and CPI.
- Kenneth R. French Data Library monthly Fama/French factors.
- SEC EDGAR company ticker/CIK reference data.

Institutional databases (WRDS, CSMAR, RESSET), paid databases, credentials, cookies, and private exports are outside this skill's scope.

## Execution

For a concrete request, run the bundled deterministic wrapper:

```powershell
python "search-finance-data/scripts/run_search_finance_data.py" "<research question>" --output "<output directory>"
```

The wrapper executes the repository workflow, which performs:

`parse → resolve public dataset → describe/schema → access check → preview → download → validate → research_panel → Evidence Package`.

Use a new output directory for each run. If the request is unsupported, explain the supported public alternatives instead of inventing a data source. Do not silently substitute an institutional or paid source.

## User-Facing Result

Report the selected provider and dataset, preview/validation status, row count, coverage and warnings. Link the generated `processed/research_panel.csv`, `evidence/data_sources.md`, `evidence/provenance.json`, and `workflow_result.json`. Mention that look-ahead or survivorship-bias warnings require researcher review.

## Compliance

Only use official public endpoints. Never request, store, print, or infer passwords, API keys, cookies, or institutional session data. Keep generated data, caches, logs, and evidence in the selected run directory.
