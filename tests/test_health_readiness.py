from __future__ import annotations

import pytest
from fastapi import HTTPException

import app.main as main_module


@pytest.mark.asyncio
async def test_readiness_check_returns_ready_when_database_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _ready() -> bool:
        return True

    monkeypatch.setattr(main_module, "_is_database_ready", _ready)

    response = await main_module.readiness_check()

    assert response["status"] == "ready"
    assert response["database"] == "ok"
    assert "timestamp" in response


@pytest.mark.asyncio
async def test_readiness_check_returns_503_when_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _not_ready() -> bool:
        return False

    monkeypatch.setattr(main_module, "_is_database_ready", _not_ready)

    with pytest.raises(HTTPException) as exc:
        await main_module.readiness_check()
    assert exc.value.status_code == 503
