import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).parents[4] / "scripts" / "check_testcircle_readiness.py"
_SPEC = importlib.util.spec_from_file_location("check_testcircle_readiness", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
response_is_healthy = _MODULE.response_is_healthy


def test_readiness_requires_healthy_payload_even_on_http_200() -> None:
    assert not response_is_healthy(
        "readiness", 200, {"status": "unhealthy", "database": "unhealthy"}
    )
    assert response_is_healthy("readiness", 200, {"status": "healthy"})
    assert response_is_healthy("liveness", 200, {"status": "live"})
