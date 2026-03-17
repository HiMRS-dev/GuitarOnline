from __future__ import annotations

from pathlib import Path


def test_ci_ops_config_job_uses_shared_validation_script() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "ops-config:" in workflow
    assert "Validate ops config bundle (shared script)" in workflow
    assert "shell: pwsh" in workflow
    assert "run: ./scripts/validate_ops_configs.ps1" in workflow


def test_workflows_use_node24_ready_action_versions() -> None:
    workflows_root = Path(".github/workflows")
    deprecated_refs = [
        "actions/checkout@v4",
        "actions/setup-node@v4",
        "actions/setup-python@v5",
        "actions/upload-artifact@v4",
        "webfactory/ssh-agent@v0.9.0",
    ]
    required_refs = [
        "actions/checkout@v6",
        "actions/setup-node@v6",
        "actions/setup-python@v6",
        "actions/upload-artifact@v7",
        "webfactory/ssh-agent@v0.10.0",
    ]

    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in workflows_root.glob("*.yml")
    )

    for ref in deprecated_refs:
        assert ref not in workflow_text, ref

    for ref in required_refs:
        assert ref in workflow_text, ref
