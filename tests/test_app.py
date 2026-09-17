from fastapi.testclient import TestClient

from m365_mcp.app import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        healthz_response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "m365-mcp-server",
        "version": "0.1.0",
    }
    assert healthz_response.status_code == 200
    assert healthz_response.json() == response.json()


def test_mcp_mount_is_present() -> None:
    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)
