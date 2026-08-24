from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from scripts.connectors.fred import FredConnector
from scripts.connectors.http import HttpClient, HttpResponse
from scripts.connectors.kenneth_french import KennethFrenchConnector
from scripts.connectors.sec_edgar import SecEdgarConnector


class StubHttpClient:
    def __init__(self, body: bytes, url: str = "https://provider.test/data") -> None:
        self.body = body
        self.url = url
        self.calls: list[str] = []

    def get(self, url: str) -> HttpResponse:
        self.calls.append(url)
        return HttpResponse(self.body, self.url, "application/octet-stream")


def french_archive() -> bytes:
    contents = "Fama/French Factors\n\n, Mkt-RF, SMB, HML, RF\n192607, 2.96, -2.30, -2.87, 0.22\n192608, 2.64, -1.40, 4.19, 0.25\n\n Annual Factors\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("F-F_Research_Data_Factors.csv", contents)
    return buffer.getvalue()


def test_fred_preview_download_validate_and_evidence(tmp_path: Path):
    data = b"observation_date,GDP\n2024-01-01,27000.0\n2024-04-01,27500.0\n"
    connector = FredConnector(http_client=StubHttpClient(data))
    preview = connector.preview("fred.series.GDP", {"limit": 1})
    assert preview.success and preview.data[0]["GDP"] == "27000.0"

    output = tmp_path / "fred_gdp.csv"
    download = connector.download("fred.series.GDP", {}, str(output))
    assert download.success
    assert output.exists()
    assert Path(download.data["evidence_path"]).exists()
    assert "fred.series.GDP" in (tmp_path / "data_sources.md").read_text(encoding="utf-8")
    assert connector.validate("fred.series.GDP", str(output)).data["row_count"] == 2


def test_sec_preview_download_and_schema(tmp_path: Path):
    data = json.dumps({"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}).encode()
    connector = SecEdgarConnector(http_client=StubHttpClient(data))
    assert connector.schema("sec.company_tickers").data["fields"] == ["cik_str", "ticker", "title"]
    assert connector.preview("sec.company_tickers", {"limit": 1}).data[0]["ticker"] == "AAPL"
    output = tmp_path / "tickers.json"
    assert connector.download("sec.company_tickers", {}, str(output)).success
    assert connector.validate("sec.company_tickers", str(output)).data["row_count"] == 1


def test_kenneth_french_preview_download_and_validate(tmp_path: Path):
    connector = KennethFrenchConnector(http_client=StubHttpClient(french_archive()))
    preview = connector.preview("kenneth_french.ff3_monthly", {"limit": 1})
    assert preview.success and preview.data[0]["Mkt-RF"] == "2.96"
    output = tmp_path / "ff3.zip"
    assert connector.download("kenneth_french.ff3_monthly", {}, str(output)).success
    assert connector.validate("kenneth_french.ff3_monthly", str(output)).data["row_count"] == 2


def test_http_client_reuses_cached_response(tmp_path: Path, monkeypatch):
    calls = []

    class Response:
        headers = type("Headers", (), {"get_content_type": lambda self: "text/plain"})()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return b"cached"

        def geturl(self):
            return "https://provider.test/final"

    def fake_open(*_args, **_kwargs):
        calls.append(True)
        return Response()

    monkeypatch.setattr("scripts.connectors.http.urlopen", fake_open)
    client = HttpClient(cache_dir=tmp_path, min_interval_seconds=0)
    first = client.get("https://provider.test/resource")
    second = client.get("https://provider.test/resource")
    assert first.body == second.body == b"cached"
    assert second.from_cache is True
    assert len(calls) == 1
