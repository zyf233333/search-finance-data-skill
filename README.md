# Empirical Finance Data Skill

Phase 2 supports permission-compliant public downloads from Kenneth French Data Library, FRED's graph CSV endpoint, and SEC EDGAR's company ticker reference. The implementation uses only the Python standard library.

Run the offline suite from the repository root:

```powershell
python -m pytest -q
```

Run live checks only when intentionally validating external providers:

```powershell
$env:RUN_INTEGRATION='1'
python -m pytest -m integration -q
```

Preview a public FRED series before downloading it:

```powershell
python -m scripts.cli fred preview fred.series.GDP --series-id GDP
python -m scripts.cli fred download fred.series.GDP --series-id GDP --output .local/raw/fred_gdp.csv
```

Each download produces a SHA-256 evidence JSON record and updates `.local/raw/data_sources.md`. Credentials, restricted downloads, generated datasets, caches, and logs must remain outside version control.

Phase 3 adds WRDS, CSMAR, and RESSET access-state handling and safe ingestion of a user-exported file from an authorised session. Configure only a non-secret session marker such as `WRDS_SESSION_FILE` containing `{"status":"authenticated"}`; never place passwords, cookies, or keys in the marker. Remote institutional automation remains disabled unless a provider-specific adapter is reviewed and enabled.

The Evidence Package generator writes `provenance.json`, `variable_dictionary.csv`, `data_sources.md`, `citations.bib`, `methodology_notes.md`, and a redacted `access_log.json`:

```python
from scripts.evidence_package import build_evidence_package
paths = build_evidence_package("evidence", spec, provenance=records, facts=["..."], suggested_wording=["..."])
```

Phase 4 provides the free end-to-end workflow. It parses the three benchmark request types, resolves only public datasets, probes access/schema, previews before download, validates the result, writes `processed/research_panel.csv` and `processed/merge_report.json`, and persists `workflow_state.json`:

```powershell
python -m scripts.workflow "Download the US GDP series from FRED" --output .local/run
python -m scripts.workflow "Download monthly Fama-French three factors" --output .local/run
python -m scripts.workflow "Download the SEC company ticker and CIK reference" --output .local/run
```

The workflow flags look-ahead and survivorship-bias questions for human review; it does not claim to infer those risks automatically.

## Share or install the skill

This repository contains both the runtime backend and the Codex skill definition
under `search-finance-data/`. To share it, publish the repository as a public
GitHub repository and send its URL. Keep `.local/`, generated data, credentials,
cookies, API keys, and other private exports out of the repository.

After cloning, run commands from the repository root. The skill wrapper uses
relative discovery, so it works from any clone location:

```powershell
python "search-finance-data/scripts/run_search_finance_data.py" "<research question>" --output ".local/run"
```
