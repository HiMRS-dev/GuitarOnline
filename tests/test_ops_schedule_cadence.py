from __future__ import annotations

from pathlib import Path


def test_restore_rehearsal_runs_daily_for_streak_tracking() -> None:
    workflow = Path(".github/workflows/restore-rehearsal.yml").read_text(encoding="utf-8")

    assert 'name: restore-rehearsal' in workflow
    assert 'cron: "20 3 * * *"' in workflow
    assert 'cron: "20 3 * * 1"' not in workflow


def test_synthetic_ops_retention_remains_daily() -> None:
    workflow = Path(".github/workflows/synthetic-ops-retention.yml").read_text(
        encoding="utf-8"
    )

    assert 'name: synthetic-ops-retention' in workflow
    assert 'cron: "45 3 * * *"' in workflow


def test_synthetic_ops_check_remains_hourly() -> None:
    workflow = Path(".github/workflows/synthetic-ops-check.yml").read_text(
        encoding="utf-8"
    )

    assert 'name: synthetic-ops-check' in workflow
    assert 'cron: "15 * * * *"' in workflow
