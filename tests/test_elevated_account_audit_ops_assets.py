from __future__ import annotations

from pathlib import Path


def test_elevated_account_audit_workflow_references_remote_runner_and_artifact() -> None:
    workflow = Path(".github/workflows/elevated-account-audit.yml").read_text(encoding="utf-8")
    assert "name: elevated-account-audit" in workflow
    assert "scripts/run_elevated_account_audit_remote.sh" in workflow
    assert "elevated-account-audit-report-${{ github.run_id }}" in workflow


def test_elevated_access_runbook_maps_role_change_and_disable_endpoints() -> None:
    runbook = Path("ops/admin_elevated_access_runbook.md").read_text(encoding="utf-8")
    assert "POST /api/v1/admin/users/${USER_ID}/role" in runbook
    assert "users/provision" not in runbook
    assert "/api/v1/admin/teachers/${TEACHER_USER_ID}/verify" not in runbook
    assert "/api/v1/admin/teachers/${TEACHER_USER_ID}/disable" in runbook


def test_elevated_account_audit_script_emits_expected_report_markers() -> None:
    script = Path("scripts/elevated_account_audit.py").read_text(encoding="utf-8")
    assert "elevated_account_audit_json=" in script
    assert "elevated_account_audit_markdown=" in script
    assert "elevated_account_audit_status=success" in script


def test_deploy_smoke_check_uses_role_reassignment_flow() -> None:
    script = Path("scripts/deploy_smoke_check.py").read_text(encoding="utf-8")
    assert "/api/v1/admin/users/" in script
    assert "/role" in script
    assert "users/provision" not in script


def test_deploy_smoke_check_supports_fixed_smoke_pool_in_test_env() -> None:
    script = Path("scripts/deploy_smoke_check.py").read_text(encoding="utf-8")
    assert 'os.getenv("APP_ENV", "").strip().lower() == "test"' in script
    assert 'TEST_SMOKE_ADMIN_EMAIL' in script
    assert 'TEST_SMOKE_STUDENT_EMAIL' in script
    assert 'TEST_SMOKE_STUDENT_TWO_EMAIL' in script
    assert 'Smoke: fixed test-contour identities' in script
    assert '"/api/v1/identity/auth/register"' in script


def test_test_contour_deploy_smoke_remote_runner_uses_reset_and_stdin_scripts() -> None:
    script = Path("scripts/run_deploy_smoke_remote.sh").read_text(encoding="utf-8")
    assert "test contour only" in script
    assert 'docker-compose.test.yml' in script
    assert 'DEPLOY_SMOKE_AUTO_START_TEST_STACK' in script
    assert 'scripts/reset_test_smoke_pool.py' in script
    assert 'python - < scripts/reset_test_smoke_pool.py' in script
    assert 'python - < scripts/deploy_smoke_check.py' in script
    assert 'starting app service' in script


def test_deploy_workflow_supports_manual_test_smoke_operation() -> None:
    workflow = Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")
    assert "operation:" in workflow
    assert "- deploy_live" in workflow
    assert "- test_smoke_only" in workflow
    assert "Type DEPLOY for live deploy or TEST_SMOKE for test smoke" in workflow
    assert "github.event.inputs.operation == 'deploy_live'" in workflow
    assert "github.event.inputs.operation == 'test_smoke_only'" in workflow
    assert "scripts/run_deploy_smoke_remote.sh" in workflow
    assert "test-deploy-smoke-" in workflow
