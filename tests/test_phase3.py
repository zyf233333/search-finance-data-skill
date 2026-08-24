from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.access import AccessResolver
from scripts.connectors.institutional import CsmarConnector, RessetConnector, WrdsConnector
from scripts.contracts import ProvenanceRecord, ResearchDataSpec, VariableSpec
from scripts.evidence_package import build_evidence_package


def marker(path: Path, **payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_access_resolver_distinguishes_required_states(tmp_path: Path):
    missing = AccessResolver({}).resolve("WRDS")
    assert missing.authenticated is False and missing.next_action == "user_login"

    expired = AccessResolver({"WRDS_SESSION_FILE": str(marker(tmp_path / "expired.json", status="expired"))}).resolve("WRDS")
    assert expired.next_action == "refresh_session"
    assert expired.to_dict()["details"]["marker_valid"] is True

    mfa = AccessResolver({"CSMAR_SESSION_FILE": str(marker(tmp_path / "mfa.json", status="mfa_required"))}).resolve("CSMAR")
    assert mfa.next_action == "complete_mfa"

    no_subscription = AccessResolver({"RESSET_SESSION_FILE": str(marker(tmp_path / "none.json", status="no_subscription"))}).resolve("RESSET")
    assert no_subscription.subscription == "none"

    api_key = AccessResolver({"FRED_API_KEY": "must-not-be-returned"}).resolve_api_key("FRED", "FRED_API_KEY")
    assert api_key.authenticated is True
    assert "must-not-be-returned" not in json.dumps(api_key.to_dict())


def test_connector_returns_auth_required_without_session():
    result = WrdsConnector(access_resolver=AccessResolver({})).check_access("wrds.compustat.funda")
    assert result.success is False
    assert result.error.code == "AUTH_REQUIRED"
    assert result.error.next_action == "user_login"
    assert result.metadata["access_state"]["provider"] == "WRDS"


def test_authorized_export_preview_download_and_validate(tmp_path: Path):
    session_path = marker(tmp_path / "wrds-session.json", status="authenticated")
    export = tmp_path / "funda.csv"
    with export.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["gvkey", "datadate", "at", "ni"])
        writer.writeheader()
        writer.writerow({"gvkey": "001234", "datadate": "2024-12-31", "at": "100", "ni": "10"})
    connector = WrdsConnector(access_resolver=AccessResolver({"WRDS_SESSION_FILE": str(session_path)}))
    preview = connector.preview("wrds.compustat.funda", {"source_file": str(export), "limit": 1})
    assert preview.success and preview.data[0]["gvkey"] == "001234"
    output = tmp_path / "raw" / "funda.csv"
    downloaded = connector.download("wrds.compustat.funda", {"source_file": str(export)}, str(output))
    assert downloaded.success
    assert Path(downloaded.data["evidence_path"]).exists()
    assert connector.validate("wrds.compustat.funda", str(output)).data["row_count"] == 1


def test_institutional_connectors_have_provider_catalogs():
    assert CsmarConnector().discover("stock").data
    assert RessetConnector().discover("financial").data
    assert WrdsConnector().schema("wrds.crsp.msf").data["identifiers"] == ["permno", "date"]


def test_evidence_package_separates_facts_and_redacts_secrets(tmp_path: Path):
    spec = ResearchDataSpec(
        research_question="Does firm size predict returns?",
        frequency="annual",
        variables=[VariableSpec("firm_size", role="control", measurement="ln_total_assets", raw_variables=["at"], status="resolved")],
    )
    paths = build_evidence_package(
        tmp_path / "evidence",
        spec,
        provenance=[ProvenanceRecord("firm_size", "firm_size", "WRDS", "wrds.compustat.funda", ["at"], "ln(at)", "annual", documentation_url="https://wrds-www.wharton.upenn.edu/")],
        data_sources=[{"dataset": "wrds.compustat.funda", "provider": "WRDS", "access_type": "institutional", "documentation_url": "https://wrds-www.wharton.upenn.edu/"}],
        citations=[{"key": "wrds_compustat", "author": "WRDS", "title": "Compustat Fundamentals", "year": "2024"}],
        facts=["The raw field at is total assets in the selected export."],
        suggested_wording=["Firm size is measured as the natural logarithm of total assets."],
        access_log=[{"event": "access_checked", "provider": "WRDS", "api_key": "do-not-write", "status": "authenticated"}],
    )
    assert set(paths) == {"provenance", "variable_dictionary", "data_sources", "citations", "methodology_notes", "access_log"}
    assert "do-not-write" not in Path(paths["access_log"]).read_text(encoding="utf-8")
    notes = Path(paths["methodology_notes"]).read_text(encoding="utf-8")
    assert "## FACT" in notes and "## SUGGESTED WORDING" in notes
    provenance = json.loads(Path(paths["provenance"]).read_text(encoding="utf-8"))
    assert provenance["records"][0]["dataset"] == "wrds.compustat.funda"
    with Path(paths["variable_dictionary"]).open(encoding="utf-8-sig", newline="") as stream:
        assert next(csv.DictReader(stream))["variable_id"] == "firm_size"
