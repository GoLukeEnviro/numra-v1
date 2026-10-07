import importlib.util
import io
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
