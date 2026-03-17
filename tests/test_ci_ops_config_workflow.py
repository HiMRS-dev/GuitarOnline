from __future__ import annotations

from pathlib import Path


def test_ci_ops_config_job_uses_shared_validation_script() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "ops-config:" in workflow
    assert "Validate ops config bundle (shared script)" in workflow
    assert "shell: pwsh" in workflow
    assert "run: ./scripts/validate_ops_configs.ps1" in workflow


def test_workflows_with_js_actions_opt_in_to_node24() -> None:
    workflow_paths = [
        ".github/workflows/backup-restore-verify.yml",
        ".github/workflows/backup-schedule-retention.yml",
        ".github/workflows/ci.yml",
        ".github/workflows/deploy.yml",
        ".github/workflows/elevated-account-audit.yml",
        ".github/workflows/load-sanity.yml",
        ".github/workflows/restore-rehearsal.yml",
        ".github/workflows/rollback-drill.yml",
        ".github/workflows/secret-rotation-dry-run.yml",
        ".github/workflows/synthetic-ops-check.yml",
        ".github/workflows/synthetic-ops-retention.yml",
    ]

    for workflow_path in workflow_paths:
        workflow = Path(workflow_path).read_text(encoding="utf-8")
        assert 'FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"' in workflow, workflow_path
