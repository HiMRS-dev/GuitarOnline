from __future__ import annotations

import pytest
from fastapi import Request, Response

import app.main as main_module
from app.core.metrics import build_metrics_response, instrument_http_request


def _make_request(path: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "server": ("testserver", 80),
        "query_string": b"",
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_http_metrics_instrumentation_tracks_status_and_path() -> None:
    async def _no_content(_: Request) -> Response:
        return Response(status_code=204)

    request = _make_request("/health")
    await instrument_http_request(request, _no_content)

    payload = build_metrics_response().body.decode("utf-8")
    assert "guitaronline_http_requests_total" in payload
    assert 'path="/health"' in payload
    assert 'status_code="204"' in payload


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus_payload() -> None:
    response = await main_module.metrics_endpoint(_make_request("/metrics"))
    payload = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "guitaronline_http_requests_total" in payload
