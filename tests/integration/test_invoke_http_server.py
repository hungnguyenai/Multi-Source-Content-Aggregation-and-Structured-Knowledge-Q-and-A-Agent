"""CMN-C1-128 -- HTTP-level regression test for the /invoke server-envelope adapter.

Exercises the actual FastAPI endpoint (src/api/server.py), not just
PreProcessNode directly or agent.invoke() bypassing the HTTP layer -- neither
of those catches a future break in the JSON-envelope construction between
InvokeRequest and PreProcessNode's envelope parser.
"""
from fastapi.testclient import TestClient

from framework.schemas.agent_status import AgentStatus
from src.api.server import app

client = TestClient(app)

_VALID_SOURCE_CONFIGS = [{"source_type": "web", "source_uri": "https://example.com/a", "metadata": {}}]


def test_invoke_http_with_source_configs_succeeds():
    """Full HTTP round trip (InvokeRequest -> envelope -> PreProcessNode) reaches SUCCESS."""
    resp = client.post("/invoke", json={"input": "What is X?", "source_configs": _VALID_SOURCE_CONFIGS})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") in (AgentStatus.SUCCESS, AgentStatus.SUCCESS.value)


def test_invoke_http_without_source_configs_errors():
    """Omitting source_configs must reach PreProcessNode's deny path, not silently vanish."""
    resp = client.post("/invoke", json={"input": "What is X?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") in (AgentStatus.ERROR, AgentStatus.ERROR.value)
