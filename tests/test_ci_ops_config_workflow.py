from __future__ import annotations

from pathlib import Path


def test_ci_ops_config_job_uses_shared_validation_script() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "ops-config:" in workflow
    assert "Validate ops config bundle (shared script)" in workflow
    assert "shell: pwsh" in workflow
    assert "run: ./scripts/validate_ops_configs.ps1" in workflow

