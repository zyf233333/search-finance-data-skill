from __future__ import annotations

import json
from pathlib import Path

from scripts.connectors.fred import FredConnector
from scripts.connectors.http import HttpResponse
from scripts.contracts import ResearchDataSpec, VariableSpec
from scripts.identifiers import left_join_rows, normalize_identifier
from scripts.panel import build_research_panel
from scripts.validator import validate_financial_csv
from scripts.workflow import FreeResearchParser, FreeResearchWorkflow


class StubHttpClient:
    def __init__(self, body: bytes):
        self.body = body

    def get(self, url: str) -> HttpResponse:
        return HttpResponse(self.body, url, "text/csv")


def test_financial_validator_reports_quality_and_bias_limits(tmp_path: Path):
    path = tmp_path / "prices.csv"
    path.write_text("date,permno,ret\n2024-01-01,10001,0.1\n2024-01-02,10001,0.2\n", encoding="utf-8")
    result = validate_financial_csv(path, date_field="date", key_fields=["permno", "date"], numeric_fields=["ret"], expected_frequency="daily")
    assert result["valid"] is True
    assert result["inferred_frequency"] == "daily"
    assert any("look_ahead_bias" in warning for warning in result["warnings"])


def test_identifier_normalization_and_join_report():
    assert normalize_identifier("  aapl ", "ticker") == "AAPL"
    assert normalize_identifier("320193", "cik") == "0000320193"
    rows, report = left_join_rows([{"ticker": "AAPL", "ret": "0.1"}], [{"ticker": "AAPL", "sector": "tech"}], keys=["ticker"])
    assert rows[0]["sector"] == "tech"
    assert report.matched_left_rows == 1 and report.unmatched_left_rows == 0


def test_research_panel_writes_merge_report(tmp_path: Path):
    result = build_research_panel(
        [{"date": "2024-01-01", "ret": "0.1"}],
        [([{"date": "2024-01-01", "gdp": "100"}], ["date"])],
        output_path=tmp_path / "panel.csv",
        report_path=tmp_path / "merge_report.json",
    )
    assert result["row_count"] == 1
    assert "gdp" in (tmp_path / "panel.csv").read_text(encoding="utf-8-sig")
    assert json.loads((tmp_path / "merge_report.json").read_text(encoding="utf-8"))["joins"][0]["matched_left_rows"] == 1


def test_free_workflow_runs_from_question_to_evidence(tmp_path: Path):
    fred = FredConnector(http_client=StubHttpClient(b"observation_date,GDP\n2024-01-01,27000\n2024-04-01,27500\n"))
    workflow = FreeResearchWorkflow(tmp_path / "run", connectors={"fred": fred})
    result = workflow.run("Download the US GDP series from FRED", preview_limit=1)
    assert result["success"] is True
    assert result["status"] == "verified"
    assert result["panel"]["row_count"] == 2
    assert Path(result["evidence"]["provenance"]).exists()
    state = json.loads((tmp_path / "run" / "workflow_state.json").read_text(encoding="utf-8"))
    assert state["spec"]["status"] == "verified"


def test_free_parser_maps_common_fred_series():
    spec = FreeResearchParser().parse("Get monthly CPI inflation from FRED")
    assert spec.variables[0].concept == "fred_cpi"
    assert spec.variables[0].raw_variables == ["CPIAUCSL"]


def test_free_workflow_explains_unsupported_request(tmp_path: Path):
    result = FreeResearchWorkflow(tmp_path / "run").run("Find a proprietary private database for an obscure variable")
    assert result["success"] is False
    assert "UNSUPPORTED_RESEARCH_REQUEST" in result["error"]
