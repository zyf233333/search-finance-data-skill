from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.connectors import FredConnector, KennethFrenchConnector, SecEdgarConnector
from scripts.connectors.http import HttpClient


pytestmark = pytest.mark.integration
RUN_INTEGRATION = os.getenv("RUN_INTEGRATION") == "1"


@pytest.mark.skipif(not RUN_INTEGRATION, reason="Set RUN_INTEGRATION=1 to contact public providers.")
def test_fred_real_preview_and_download(tmp_path: Path):
    client = HttpClient(min_interval_seconds=0.2, retries=1, timeout_seconds=30)
    connector = FredConnector(http_client=client)
    assert connector.preview("fred.series.GDP", {"limit": 1}).success
    assert connector.download("fred.series.GDP", {}, str(tmp_path / "fred_gdp.csv")).success


@pytest.mark.skipif(not RUN_INTEGRATION, reason="Set RUN_INTEGRATION=1 to contact public providers.")
def test_french_real_preview_and_download(tmp_path: Path):
    connector = KennethFrenchConnector(http_client=HttpClient(min_interval_seconds=0.2, retries=1, timeout_seconds=30))
    assert connector.preview("kenneth_french.ff3_monthly", {"limit": 1}).success
    assert connector.download("kenneth_french.ff3_monthly", {}, str(tmp_path / "ff3.zip")).success


@pytest.mark.skipif(not RUN_INTEGRATION, reason="Set RUN_INTEGRATION=1 to contact public providers.")
def test_sec_real_preview_and_download(tmp_path: Path):
    connector = SecEdgarConnector(http_client=HttpClient(min_interval_seconds=0.2, retries=1, timeout_seconds=30))
    assert connector.preview("sec.company_tickers", {"limit": 1}).success
    assert connector.download("sec.company_tickers", {}, str(tmp_path / "sec_tickers.json")).success
