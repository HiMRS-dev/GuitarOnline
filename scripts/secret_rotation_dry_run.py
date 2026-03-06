#!/usr/bin/env python3
"""Rehearse JWT secret rotation without changing runtime infrastructure."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from jose import JWTError, jwt

from app.core.config import Settings

DEFAULT_ENV_FILE = Path(".env")
DEFAULT_OUTPUT_JSON = Path(".tmp/security/secret_rotation_dry_run_report.json")
DEFAULT_OUTPUT_MD = Path(".tmp/security/secret_rotation_dry_run_report.md")
DEFAULT_SECRET_BYTES = 48


@dataclass(frozen=True)
class EnvParseResult:
    rows: list[tuple[str, str | None]]
    values: dict[str, str]


def _fingerprint(secret_value: str) -> str:
    digest = hashlib.sha256(secret_value.encode("utf-8")).hexdigest()
    return digest[:12]


def _parse_env_file(path: Path) -> EnvParseResult:
    if not path.exists():
        raise RuntimeError(f"Environment file not found: {path}")

    rows: list[tuple[str, str | None]] = []
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            rows.append((raw_line, None))
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        values[key] = value
        rows.append((key, value))
    return EnvParseResult(rows=rows, values=values)


def _write_env_file(path: Path, parsed: EnvParseResult, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    rendered_lines: list[str] = []
    seen_keys: set[str] = set()
    for row_key, row_value in parsed.rows:
        if row_value is None:
            rendered_lines.append(row_key)
            continue
        seen_keys.add(row_key)
        rendered_lines.append(f"{row_key}={values.get(row_key, '')}")

    for key, value in values.items():
        if key not in seen_keys:
            rendered_lines.append(f"{key}={value}")

    path.write_text("\n".join(rendered_lines) + "\n", encoding="utf-8")


def _resolve_rotation_target(
    env_values: dict[str, str],
    requested: Literal["auto", "SECRET_KEY", "JWT_SECRET"],
) -> str:
    if requested != "auto":
        return requested

    jwt_secret = env_values.get("JWT_SECRET", "").strip()
    if jwt_secret:
        return "JWT_SECRET"
    return "SECRET_KEY"


def _validate_settings(env_file: Path) -> str:
    settings = Settings(_env_file=str(env_file))
    return settings.jwt_algorithm


def _run_jwt_probe(*, previous_secret: str, rotated_secret: str, algorithm: str) -> None:
    now_ts = int(time.time())
    payload = {
        "sub": "secret-rotation-dry-run",
        "iat": now_ts,
        "exp": now_ts + 300,
        "scope": "rotation_probe",
    }

    previous_token = jwt.encode(payload, previous_secret, algorithm=algorithm)
    jwt.decode(previous_token, previous_secret, algorithms=[algorithm])

    try:
        jwt.decode(previous_token, rotated_secret, algorithms=[algorithm])
    except JWTError:
        pass
    else:
        raise RuntimeError(
            "Rotation probe failed: token signed with previous key is still valid with rotated key",
        )

    rotated_token = jwt.encode(payload, rotated_secret, algorithm=algorithm)
    jwt.decode(rotated_token, rotated_secret, algorithms=[algorithm])


def _resolve_repo_slug(explicit_repo: str | None) -> str:
    if explicit_repo and explicit_repo.strip():
        return explicit_repo.strip()

    result = subprocess.run(  # noqa: S603
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Failed to detect git remote URL for repository slug resolution")

    remote_url = result.stdout.strip()
    patterns = (
        r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
        r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        matched = re.match(pattern, remote_url)
        if matched:
            return f"{matched.group(1)}/{matched.group(2)}"

    raise RuntimeError(f"Unsupported origin URL format: {remote_url}")


def _run_gh(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _verify_github_secret_access(*, repository: str, secret_name: str) -> None:
    auth_result = _run_gh("auth", "status")
    if auth_result.returncode != 0:
        raise RuntimeError("GitHub CLI auth check failed. Run `gh auth login` before dry-run.")

    list_result = _run_gh("secret", "list", "--repo", repository)
    if list_result.returncode != 0:
        stderr = list_result.stderr.strip()
        raise RuntimeError(
            "Failed to list repository secrets via GitHub CLI. "
            f"repo={repository}, details={stderr or 'n/a'}",
        )

    names: set[str] = set()
    for line in list_result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        names.add(stripped.split()[0])
    if secret_name not in names:
        raise RuntimeError(
            "Required repository secret not found: "
            f"{secret_name} (repo={repository})",
        )


def _write_report_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_report_md(path: Path, payload: dict[str, object]) -> None:
    github_repo = payload.get("github_repo")
    github_secret = payload.get("github_secret_name")
    lines = [
        "# Secret Rotation Dry-Run Report",
        "",
        f"- Generated at (UTC): `{payload['generated_at_utc']}`",
        f"- Source env file: `{payload['source_env_file']}`",
        f"- Rotation target key: `{payload['rotation_target']}`",
        f"- Active key fingerprint (sha256/12): `{payload['active_secret_fingerprint']}`",
        f"- Candidate key fingerprint (sha256/12): `{payload['candidate_secret_fingerprint']}`",
        f"- Candidate key length: `{payload['candidate_secret_length']}`",
        f"- JWT algorithm: `{payload['jwt_algorithm']}`",
        "",
        "## Steps",
        "",
    ]
    for step_name, step_state in payload["steps"].items():
        lines.append(f"- `{step_name}`: `{step_state}`")

    if github_repo is not None and github_secret is not None:
        lines.extend(
            [
                "",
                "## GitHub Secret Check",
                "",
                f"- Repository: `{github_repo}`",
                f"- Required secret: `{github_secret}`",
            ],
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Dry-run does not write to remote hosts, `.env`, or GitHub repository secrets.",
            "- JWT rotation invalidates tokens signed with previous key material.",
        ],
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a non-destructive rehearsal for JWT secret rotation.",
    )
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument(
        "--rotation-target",
        choices=("auto", "SECRET_KEY", "JWT_SECRET"),
        default="auto",
    )
    parser.add_argument("--secret-bytes", type=int, default=DEFAULT_SECRET_BYTES)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--github-secret-name", default="PROD_ENV_FILE_B64")
    parser.add_argument("--skip-github-check", action="store_true")
    parser.add_argument("--keep-candidate-env", action="store_true")
    args = parser.parse_args()

    if args.secret_bytes < 16:
        raise RuntimeError("--secret-bytes must be >= 16")

    source_env_file = Path(args.env_file)
    parsed_env = _parse_env_file(source_env_file)

    rotation_target = _resolve_rotation_target(
        parsed_env.values,
        args.rotation_target,
    )
    current_secret = parsed_env.values.get(rotation_target, "").strip()
    if not current_secret:
        raise RuntimeError(
            f"Cannot rotate empty value for {rotation_target}. Set it in {source_env_file}.",
        )

    candidate_secret = secrets.token_urlsafe(args.secret_bytes)
    rotated_values = dict(parsed_env.values)
    rotated_values[rotation_target] = candidate_secret

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    candidate_env_path = Path(".tmp/security") / f"secret_rotation_candidate_{timestamp}.env"
    _write_env_file(candidate_env_path, parsed_env, rotated_values)

    steps: dict[str, str] = {
        "parse_env": "ok",
        "prepare_candidate_env": "ok",
    }

    jwt_algorithm = _validate_settings(candidate_env_path)
    steps["validate_settings"] = "ok"

    _run_jwt_probe(
        previous_secret=current_secret,
        rotated_secret=candidate_secret,
        algorithm=jwt_algorithm,
    )
    steps["jwt_rotation_probe"] = "ok"

    github_repo: str | None = None
    if args.skip_github_check:
        steps["github_secret_access"] = "skipped"
    else:
        github_repo = _resolve_repo_slug(args.repo)
        _verify_github_secret_access(
            repository=github_repo,
            secret_name=args.github_secret_name,
        )
        steps["github_secret_access"] = "ok"

    report_payload: dict[str, object] = {
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source_env_file": str(source_env_file),
        "rotation_target": rotation_target,
        "active_secret_fingerprint": _fingerprint(current_secret),
        "candidate_secret_fingerprint": _fingerprint(candidate_secret),
        "candidate_secret_length": len(candidate_secret),
        "jwt_algorithm": jwt_algorithm,
        "github_repo": github_repo,
        "github_secret_name": args.github_secret_name if github_repo is not None else None,
        "steps": steps,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    _write_report_json(output_json, report_payload)
    _write_report_md(output_md, report_payload)

    if not args.keep_candidate_env:
        candidate_env_path.unlink(missing_ok=True)
        steps["candidate_env_cleanup"] = "ok"
        _write_report_json(output_json, report_payload)
        _write_report_md(output_md, report_payload)

    print("Secret rotation dry-run completed.")
    print(f"  source_env_file={source_env_file}")
    print(f"  rotation_target={rotation_target}")
    print(f"  active_secret_fingerprint={_fingerprint(current_secret)}")
    print(f"  candidate_secret_fingerprint={_fingerprint(candidate_secret)}")
    print(f"  output_json={output_json}")
    print(f"  output_md={output_md}")
    if github_repo is not None:
        print(f"  github_repo={github_repo}")
        print(f"  github_secret_name={args.github_secret_name}")
    else:
        print("  github_secret_check=skipped")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
