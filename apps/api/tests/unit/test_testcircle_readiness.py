import importlib.util
import io
import sys
import urllib.error
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parents[4] / "scripts" / "check_testcircle_readiness.py"
_SPEC = importlib.util.spec_from_file_location("check_testcircle_readiness", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
response_is_healthy = _MODULE.response_is_healthy
fetch_json = _MODULE.fetch_json


def test_readiness_requires_healthy_payload_even_on_http_200() -> None:
    assert not response_is_healthy(
        "readiness", 200, {"status": "unhealthy", "database": "unhealthy"}
    )
    assert response_is_healthy("readiness", 200, {"status": "healthy"})
    assert response_is_healthy("liveness", 200, {"status": "live"})


def test_fetch_json_returns_body_of_http_503(monkeypatch: pytest.MonkeyPatch) -> None:
    body = b'{"status": "unhealthy", "database": "unhealthy"}'

    def _urlopen(url: str, timeout: float) -> object:
        raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, io.BytesIO(body))  # type: ignore[arg-type]

    monkeypatch.setattr(_MODULE.urllib.request, "urlopen", _urlopen)
    status_code, parsed = fetch_json("http://x/v1/health/ready", 1.0)
    assert status_code == 503
    assert parsed == {"status": "unhealthy", "database": "unhealthy"}
    assert not response_is_healthy("readiness", status_code, parsed)


def _http_error(url: str, code: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(body))  # type: ignore[arg-type]


def test_fetch_json_keeps_status_code_for_non_json_error_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _urlopen(url: str, timeout: float) -> object:
        raise _http_error(url, 502, b"<html>Bad Gateway</html>")

    monkeypatch.setattr(_MODULE.urllib.request, "urlopen", _urlopen)
    status_code, parsed = fetch_json("http://x/v1/health/ready", 1.0)
    assert status_code == 502
    assert parsed is None
    assert not response_is_healthy("readiness", status_code, parsed)


def test_fetch_json_returns_status_and_body_for_http_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Response(io.BytesIO):
        status = 200

        def __enter__(self) -> "_Response":
            return self

    monkeypatch.setattr(
        _MODULE.urllib.request,
        "urlopen",
        lambda url, timeout: _Response(b'{"status": "healthy"}'),
    )
    assert fetch_json("http://x/v1/health/ready", 1.0) == (200, {"status": "healthy"})


def test_main_exits_nonzero_when_readiness_returns_503(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    backup = tmp_path / "backup.dump"
    backup.write_bytes(b"x")

    def _fetch(url: str, timeout_seconds: float) -> tuple[int, object]:
        if url.endswith("/live"):
            return 200, {"status": "live"}
        return 503, {"status": "unhealthy", "database": "unhealthy"}

    monkeypatch.setattr(_MODULE, "fetch_json", _fetch)
    monkeypatch.setattr(sys, "argv", ["check", "--base-url", "http://x", "--backup", str(backup)])
    assert _MODULE.main() != 0
