from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

import app.workers.outbox_notifications_worker as worker_module


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
async def test_run_cycle_uses_config_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _DummySession()
    captured: dict[str, object] = {}

    monkeypatch.setattr(worker_module, "SessionLocal", lambda: _DummySessionContext(session))
    monkeypatch.setattr(worker_module, "AuditRepository", lambda db: ("audit", db))
    monkeypatch.setattr(worker_module, "NotificationsRepository", lambda db: ("notifications", db))
    monkeypatch.setattr(worker_module, "BillingRepository", lambda db: ("billing", db))

    class _FakeNotificationsOutboxWorker:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            captured.update(kwargs)

        async def run_once(self) -> dict[str, int]:
            return {"requeued": 1, "processed": 2, "failed": 0, "dispatched": 3}

    monkeypatch.setattr(worker_module, "NotificationsOutboxWorker", _FakeNotificationsOutboxWorker)

    config = worker_module.OutboxNotificationsWorkerConfig(
        log_level=logging.INFO,
        mode="once",
        poll_seconds=9,
        batch_size=33,
        max_retries=7,
        base_backoff_seconds=45,
        max_backoff_seconds=600,
    )
    result = await worker_module.run_cycle(config)

    assert result == {"requeued": 1, "processed": 2, "failed": 0, "dispatched": 3}
    assert session.committed is True
    assert captured["audit_repository"] == ("audit", session)
    assert captured["notifications_repository"] == ("notifications", session)
    assert captured["billing_repository"] == ("billing", session)
    assert captured["batch_size"] == 33
    assert captured["max_retries"] == 7
    assert captured["base_backoff_seconds"] == 45
    assert captured["max_backoff_seconds"] == 600


def test_load_worker_config_reads_new_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_LOG_LEVEL", "debug")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_MODE", "poll")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_POLL_SECONDS", "21")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_BATCH_SIZE", "55")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_MAX_RETRIES", "8")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_BASE_BACKOFF_SECONDS", "40")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_MAX_BACKOFF_SECONDS", "400")

    config = worker_module.load_worker_config()

    assert config.log_level == logging.DEBUG
    assert config.mode == "loop"
    assert config.poll_seconds == 21
    assert config.batch_size == 55
    assert config.max_retries == 8
    assert config.base_backoff_seconds == 40
    assert config.max_backoff_seconds == 400


def test_load_worker_config_supports_legacy_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTBOX_WORKER_LOG_LEVEL", "warning")
    monkeypatch.setenv("OUTBOX_WORKER_MODE", "loop")
    monkeypatch.setenv("OUTBOX_WORKER_POLL_SECONDS", "16")
    monkeypatch.setenv("OUTBOX_WORKER_BATCH_SIZE", "66")
    monkeypatch.setenv("OUTBOX_WORKER_MAX_RETRIES", "9")
    monkeypatch.setenv("OUTBOX_WORKER_BASE_BACKOFF_SECONDS", "50")
    monkeypatch.setenv("OUTBOX_WORKER_MAX_BACKOFF_SECONDS", "500")

    config = worker_module.load_worker_config()

    assert config.log_level == logging.WARNING
    assert config.mode == "loop"
    assert config.poll_seconds == 16
    assert config.batch_size == 66
    assert config.max_retries == 9
    assert config.base_backoff_seconds == 50
    assert config.max_backoff_seconds == 500


def test_load_worker_config_falls_back_to_defaults_for_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_LOG_LEVEL", "invalid")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_MODE", "invalid")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_POLL_SECONDS", "0")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_BATCH_SIZE", "NaN")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_MAX_RETRIES", "-2")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_BASE_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("NOTIFICATIONS_OUTBOX_WORKER_MAX_BACKOFF_SECONDS", "oops")

    config = worker_module.load_worker_config()

    assert config.log_level == logging.INFO
    assert config.mode == worker_module.DEFAULT_MODE
    assert config.poll_seconds == worker_module.DEFAULT_POLL_SECONDS
    assert config.batch_size == worker_module.DEFAULT_BATCH_SIZE
    assert config.max_retries == worker_module.DEFAULT_MAX_RETRIES
    assert config.base_backoff_seconds == worker_module.DEFAULT_BASE_BACKOFF_SECONDS
    assert config.max_backoff_seconds == worker_module.DEFAULT_MAX_BACKOFF_SECONDS
