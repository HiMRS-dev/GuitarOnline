from __future__ import annotations

from pathlib import Path


def test_elevated_account_audit_workflow_references_remote_runner_and_artifact() -> None:
    workflow = Path(".github/workflows/elevated-account-audit.yml").read_text(encoding="utf-8")
    assert "name: elevated-account-audit" in workflow
    assert "scripts/run_elevated_account_audit_remote.sh" in workflow
    assert "elevated-account-audit-report-${{ github.run_id }}" in workflow


def test_elevated_access_runbook_maps_provision_and_approval_endpoints() -> None:
    runbook = Path("ops/admin_elevated_access_runbook.md").read_text(encoding="utf-8")
    assert "POST /api/v1/admin/users/provision" in runbook
    assert "/api/v1/admin/teachers/${TEACHER_USER_ID}/verify" in runbook
    assert "/api/v1/admin/teachers/${TEACHER_USER_ID}/disable" in runbook


def test_elevated_account_audit_script_emits_expected_report_markers() -> None:
    script = Path("scripts/elevated_account_audit.py").read_text(encoding="utf-8")
    assert "elevated_account_audit_json=" in script
    assert "elevated_account_audit_markdown=" in script
    assert "elevated_account_audit_status=success" in script
