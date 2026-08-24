"""Small standard-library HTTP client with retry, cache, and rate limiting."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HttpClientError(RuntimeError):
    """Raised after a recoverable HTTP failure has exhausted retries."""


@dataclass(frozen=True)
class HttpResponse:
    body: bytes
    url: str
    content_type: str | None
    from_cache: bool = False


class HttpClient:
    """Fetch public data without retaining credentials or request secrets."""

    def __init__(
        self,
        *,
        cache_dir: str | Path | None = None,
        user_agent: str = "EmpiricalFinanceDataSkill/0.1",
        retries: int = 2,
        min_interval_seconds: float = 0.2,
        timeout_seconds: float = 30,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.user_agent = user_agent
        self.retries = retries
        self.min_interval_seconds = min_interval_seconds
        self.timeout_seconds = timeout_seconds
        self._last_request_at = 0.0

    def get(self, url: str, *, headers: Mapping[str, str] | None = None, use_cache: bool = True) -> HttpResponse:
        cache_path = self._cache_path(url)
        if use_cache and cache_path is not None and cache_path.exists():
            metadata = json.loads(cache_path.with_suffix(".json").read_text(encoding="utf-8"))
            return HttpResponse(cache_path.read_bytes(), metadata["url"], metadata.get("content_type"), from_cache=True)

        request_headers = {"User-Agent": self.user_agent, "Accept": "*/*"}
        if headers:
            request_headers.update(headers)
        request = Request(url, headers=request_headers)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self._wait_for_rate_limit()
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 -- URLs are provider constants.
                    body = response.read()
                    result = HttpResponse(body, response.geturl(), response.headers.get_content_type())
                    if cache_path is not None:
                        self._write_cache(cache_path, result)
                    return result
            except (HTTPError, URLError, TimeoutError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.4 * (2**attempt))
        detail = f"{type(last_error).__name__}: {last_error}" if last_error is not None else "unknown network error"
        raise HttpClientError(f"Request failed after {self.retries + 1} attempts: {url} ({detail})") from last_error

    def _wait_for_rate_limit(self) -> None:
        wait = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _cache_path(self, url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / digest

    def _write_cache(self, path: Path, response: HttpResponse) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.body)
        path.with_suffix(".json").write_text(
            json.dumps({"url": response.url, "content_type": response.content_type}, indent=2), encoding="utf-8"
        )
