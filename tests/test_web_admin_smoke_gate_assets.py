from __future__ import annotations

import json
from pathlib import Path


def test_web_admin_package_declares_smoke_e2e_script() -> None:
    package_json = json.loads(Path("web-admin/package.json").read_text(encoding="utf-8"))
    scripts = package_json.get("scripts", {})
    dev_dependencies = package_json.get("devDependencies", {})

    assert scripts.get("test:smoke:e2e") == "playwright test --config=playwright.config.ts"
    assert "@playwright/test" in dev_dependencies


def test_ci_workflow_runs_web_admin_smoke_e2e() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "web-admin:" in workflow
    assert "Install Playwright browser (Chromium)" in workflow
    assert "npx playwright install --with-deps chromium" in workflow
    assert "Run frontend smoke e2e" in workflow
    assert "npm run test:smoke:e2e" in workflow


def test_deploy_workflow_gates_on_web_admin_smoke_e2e() -> None:
    workflow = Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")

    assert "Run web-admin smoke e2e gate" in workflow
    assert "Build web-admin bundle" in workflow
    assert "npx playwright install --with-deps chromium" in workflow
    assert "npm run test:smoke:e2e" in workflow
