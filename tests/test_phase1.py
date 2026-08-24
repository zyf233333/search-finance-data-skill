from __future__ import annotations

import json

from scripts.connectors.base import DatasetConnector
from scripts.contracts import ConnectorResult, ErrorInfo, ResearchDataSpec, VariableSpec
from scripts.logging_utils import JsonlLogger
from scripts.registry import DatasetRegistry, VariableRegistry
from scripts.state import StateStore


ROOT = __file__.replace("\\tests\\test_phase1.py", "")


def test_research_data_spec_round_trips(tmp_path):
    spec = ResearchDataSpec(
        research_question="Does ESG affect stock crash risk?",
        market="China A-share",
        period_start=2012,
        period_end=2024,
        frequency="annual",
        unit="firm-year",
        variables=[VariableSpec("ESG", role="independent", confidence=0.8)],
    )
    path = tmp_path / "state.json"
    StateStore(path).save(spec)
    loaded = StateStore(path).load()
    assert loaded["spec"]["research_question"].startswith("Does ESG")
    assert loaded["spec"]["variables"][0]["confidence"] == 0.8


def test_registries_load_and_filter():
    variables = VariableRegistry(f"{ROOT}/knowledge/variables.json")
    datasets = DatasetRegistry(f"{ROOT}/knowledge/datasets.json")
    assert variables.get("firm_size")["measurement"] == "ln_total_assets"
    assert datasets.search(access_type="public")[0]["dataset_id"].startswith("kenneth_french")


def test_connector_result_has_structured_error():
    result = ConnectorResult.fail(
        "check_access", ErrorInfo("AUTH_REQUIRED", "Authentication is required.", recoverable=True, next_action="user_login")
    )
    payload = result.to_dict()
    assert payload["success"] is False
    assert payload["error"]["code"] == "AUTH_REQUIRED"
    assert payload["error"]["next_action"] == "user_login"


def test_connector_protocol_is_explicit():
    required = {"discover", "describe", "check_access", "schema", "preview", "download", "validate", "cite"}
    assert required.issubset(set(DatasetConnector.__abstractmethods__))


def test_structured_jsonl_logging(tmp_path):
    path = tmp_path / "events.jsonl"
    JsonlLogger(path).event("schema_checked", dataset_id="fred.series")
    event = json.loads(path.read_text(encoding="utf-8").strip())
    assert event["event"] == "schema_checked"
    assert event["dataset_id"] == "fred.series"
