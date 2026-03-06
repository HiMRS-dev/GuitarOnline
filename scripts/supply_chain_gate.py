#!/usr/bin/env python3
"""Run supply-chain security checks and emit machine-readable artifacts."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / ".tmp" / "security"
DEFAULT_PIP_AUDIT_IGNORE_FILE = REPO_ROOT / "ops" / "security" / "pip_audit_ignore.txt"
DEFAULT_WEB_ADMIN_DIR = REPO_ROOT / "web-admin"


def _print_cmd(command: list[str], *, cwd: Path | None = None) -> None:
    rendered = " ".join(shlex.quote(part) for part in command)
    if cwd is not None:
        print(f"$ (cd {cwd} && {rendered})")
    else:
        print(f"$ {rendered}")


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    _print_cmd(command, cwd=cwd)
    return subprocess.run(  # noqa: S603
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=False,
        text=True,
        capture_output=capture_output,
    )


def _read_pip_audit_ignore_ids(path: Path) -> list[str]:
    if not path.exists():
        raise RuntimeError(f"pip-audit ignore file not found: {path}")
    ignore_ids: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        normalized = raw_line.split("#", 1)[0].strip()
        if normalized:
            ignore_ids.append(normalized)
    return ignore_ids


def _run_pip_audit(*, output_file: Path, ignore_ids: list[str]) -> None:
    command = [
        "pip-audit",
        "--skip-editable",
        "--format",
        "json",
        "--output",
        str(output_file),
    ]
    for vuln_id in ignore_ids:
        command.extend(["--ignore-vuln", vuln_id])
    result = _run(command)
    if result.returncode != 0:
        raise RuntimeError(f"pip-audit failed with exit code {result.returncode}")


def _run_backend_sbom(*, output_file: Path) -> None:
    command = [
        "cyclonedx-py",
        "environment",
        "--output-format",
        "JSON",
        "--output-file",
        str(output_file),
    ]
    result = _run(command)
    if result.returncode != 0:
        raise RuntimeError(f"cyclonedx-py failed with exit code {result.returncode}")


def _run_npm_audit(
    *,
    web_admin_dir: Path,
    output_file: Path,
    audit_level: str,
) -> None:
    if shutil.which("npm") is None:
        raise RuntimeError(
            "npm is not available in PATH; install Node.js/npm or run with --skip-npm",
        )
    if not web_admin_dir.exists():
        raise RuntimeError(f"web-admin directory not found: {web_admin_dir}")

    lockfile = web_admin_dir / "package-lock.json"
    lockfile_preexisting = lockfile.exists()

    try:
        if not lockfile_preexisting:
            lock_result = _run(
                [
                    "npm",
                    "install",
                    "--package-lock-only",
                    "--ignore-scripts",
                    "--no-audit",
                    "--no-fund",
                ],
                cwd=web_admin_dir,
            )
            if lock_result.returncode != 0:
                raise RuntimeError(
                    "npm install --package-lock-only failed before npm audit",
                )

        result = _run(
            [
                "npm",
                "audit",
                "--omit=dev",
                f"--audit-level={audit_level}",
                "--json",
            ],
            cwd=web_admin_dir,
            capture_output=True,
        )

        output_file.write_text(result.stdout, encoding="utf-8")
        if result.returncode != 0:
            if result.stderr.strip():
                print(result.stderr.strip(), file=sys.stderr)
            raise RuntimeError(f"npm audit failed with exit code {result.returncode}")

        try:
            json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("npm audit returned non-JSON output") from exc
    finally:
        if not lockfile_preexisting and lockfile.exists():
            lockfile.unlink()


def _write_summary(
    *,
    output_file: Path,
    pip_audit_report: Path,
    backend_sbom_report: Path,
    npm_audit_report: Path | None,
    pip_audit_ignore_ids: list[str],
) -> None:
    summary: dict[str, object] = {
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "pip_audit_report": str(pip_audit_report),
        "backend_sbom_report": str(backend_sbom_report),
        "pip_audit_ignore_ids": pip_audit_ignore_ids,
    }
    if npm_audit_report is None:
        summary["npm_audit_report"] = None
    else:
        summary["npm_audit_report"] = str(npm_audit_report)
    output_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Python/npm supply-chain checks and write JSON artifacts.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--pip-audit-ignore-file",
        default=str(DEFAULT_PIP_AUDIT_IGNORE_FILE),
    )
    parser.add_argument("--web-admin-dir", default=str(DEFAULT_WEB_ADMIN_DIR))
    parser.add_argument("--npm-audit-level", default="high")
    parser.add_argument("--skip-npm", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pip_audit_ignore_ids = _read_pip_audit_ignore_ids(Path(args.pip_audit_ignore_file))
    pip_audit_report = output_dir / "pip_audit.json"
    backend_sbom_report = output_dir / "backend_sbom_cyclonedx.json"
    npm_audit_report = output_dir / "npm_audit.json"
    summary_report = output_dir / "summary.json"

    _run_pip_audit(output_file=pip_audit_report, ignore_ids=pip_audit_ignore_ids)
    _run_backend_sbom(output_file=backend_sbom_report)

    if args.skip_npm:
        resolved_npm_report: Path | None = None
    else:
        _run_npm_audit(
            web_admin_dir=Path(args.web_admin_dir),
            output_file=npm_audit_report,
            audit_level=args.npm_audit_level,
        )
        resolved_npm_report = npm_audit_report

    _write_summary(
        output_file=summary_report,
        pip_audit_report=pip_audit_report,
        backend_sbom_report=backend_sbom_report,
        npm_audit_report=resolved_npm_report,
        pip_audit_ignore_ids=pip_audit_ignore_ids,
    )

    print("Supply-chain gate completed.")
    print(f"  pip_audit_report={pip_audit_report}")
    print(f"  backend_sbom_report={backend_sbom_report}")
    if resolved_npm_report is None:
        print("  npm_audit_report=skipped")
    else:
        print(f"  npm_audit_report={resolved_npm_report}")
    print(f"  summary_report={summary_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
