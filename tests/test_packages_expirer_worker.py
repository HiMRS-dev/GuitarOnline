from __future__ import annotations

from dataclasses import dataclass

import pytest

import app.workers.packages_expirer as worker_module


@dataclass
class _DummySession:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True


class _DummySessionContext:
    def __init__(self, session: _DummySession) -> None:
        self._session = session

    async def __aenter__(self) -> _DummySession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False


@pytest.mark.asyncio
async def test_run_cycle_uses_system_expiration_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _DummySession()
    captured: dict[str, object] = {}

    monkeypatch.setattr(worker_module, "SessionLocal", lambda: _DummySessionContext(session))
    monkeypatch.setattr(worker_module, "BillingRepository", lambda db: ("billing", db))
    monkeypatch.setattr(worker_module, "AuditRepository", lambda db: ("audit", db))

    class _FakeBillingService:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            captured.update(kwargs)

        async def expire_packages_system(self, **kwargs) -> int:  # noqa: ANN003
            captured["expire_call"] = kwargs
            return 3

    monkeypatch.setattr(worker_module, "BillingService", _FakeBillingService)

    result = await worker_module.run_cycle()

    assert result == 3
    assert session.committed is True
    assert captured["repository"] == ("billing", session)
    assert captured["audit_repository"] == ("audit", session)
    assert captured["expire_call"] == {"trigger": "worker_expire_packages"}
