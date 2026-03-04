from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.shared.exceptions import BusinessRuleException, register_exception_handlers


def _build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/app-error")
    async def app_error() -> dict:
        raise BusinessRuleException("Rule failed", details={"rule": "demo"})

    @app.get("/http-error")
    async def http_error() -> dict:
        raise HTTPException(status_code=403, detail="Forbidden for this role")

    @app.get("/validation/{value}")
    async def validation(value: int) -> dict:
        return {"value": value}

    @app.get("/unhandled")
    async def unhandled() -> dict:
        raise RuntimeError("boom")

    return app


def test_app_exception_uses_unified_error_envelope_with_details() -> None:
    client = TestClient(_build_app())
    response = client.get("/app-error")
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "business_rule_violation",
            "message": "Rule failed",
            "details": {"rule": "demo"},
        },
    }


def test_http_exception_uses_unified_error_envelope_with_details() -> None:
    client = TestClient(_build_app())
    response = client.get("/http-error")
    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "forbidden"
    assert payload["error"]["message"] == "Forbidden for this role"
    assert payload["error"]["details"] == {"detail": "Forbidden for this role"}


def test_validation_exception_uses_unified_error_envelope() -> None:
    client = TestClient(_build_app())
    response = client.get("/validation/not-an-int")
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "Request validation failed"
    assert "errors" in payload["error"]["details"]
    assert isinstance(payload["error"]["details"]["errors"], list)


def test_unhandled_exception_uses_internal_error_shape() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)
    response = client.get("/unhandled")
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "details": None,
        },
    }
