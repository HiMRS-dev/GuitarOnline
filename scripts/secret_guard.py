#!/usr/bin/env python3
"""Secret leak scanner used by CI and local pre-commit hooks."""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "backups",
}

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".mp3",
    ".mp4",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}

ALLOWLIST_TERMS = {
    "change-me",
    "replace",
    "example",
    "dummy",
    "sample",
    "test",
    "localhost",
    "your_",
    "your-",
    "token_here",
    "xxxx",
    "demopass123",
}


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    capture_group: int | None = None
    min_entropy: float | None = None


@dataclass(frozen=True)
class Finding:
    path: str
    line_number: int
    rule: str
    line: str
    secret: str


RULES: tuple[Rule, ...] = (
    Rule(
        name="private_key",
        pattern=re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    Rule(
        name="slack_webhook",
        pattern=re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+"),
    ),
    Rule(
        name="aws_access_key_id",
        pattern=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    Rule(
        name="github_pat",
        pattern=re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,255}\b"),
    ),
    Rule(
        name="jwt_token",
        pattern=re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    Rule(
        name="basic_auth_url",
        pattern=re.compile(r"https?://[^/\s:@]{2,}:[^@\s]{8,}@"),
    ),
    Rule(
        name="generic_secret_assignment",
        pattern=re.compile(
            r"(?i)\b(?:api[_-]?key|secret(?:_key)?|token|password|passwd|client[_-]?secret|access[_-]?key|private[_-]?key)\b\s*[:=]\s*['\"]?([A-Za-z0-9][A-Za-z0-9_\-\/+=]{15,})['\"]?"
        ),
        capture_group=1,
        min_entropy=3.6,
    ),
)


def run_git(args: list[str]) -> bytes:
    process = subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return process.stdout


def list_repo_files() -> list[str]:
    output = run_git(["ls-files", "-z"])
    return [item for item in output.decode("utf-8", errors="ignore").split("\0") if item]


def list_staged_files() -> list[str]:
    output = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"])
    return [item for item in output.decode("utf-8", errors="ignore").split("\0") if item]


def read_repo_file(path: str) -> bytes:
    return Path(path).read_bytes()


def read_staged_file(path: str) -> bytes:
    return run_git(["show", f":{path}"])


def is_binary(data: bytes) -> bool:
    sample = data[:8192]
    return b"\x00" in sample


def should_skip_path(path: str) -> bool:
    file_path = Path(path)
    if any(part in SKIP_DIRS for part in file_path.parts):
        return True
    if file_path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def entropy(value: str) -> float:
    if not value:
        return 0.0
    freq: dict[str, int] = {}
    for char in value:
        freq[char] = freq.get(char, 0) + 1
    size = len(value)
    return -sum((count / size) * math.log2(count / size) for count in freq.values())


def looks_allowlisted(line: str, secret: str) -> bool:
    lowered_line = line.lower()
    lowered_secret = secret.lower()

    if "secret-scan: allow" in lowered_line:
        return True

    if any(term in lowered_secret for term in ALLOWLIST_TERMS):
        return True

    if "<" in secret and ">" in secret:
        return True

    return False


def redact(secret: str) -> str:
    if len(secret) <= 8:
        return "***"
    return f"{secret[:4]}***{secret[-4:]}"


def make_snippet(line: str, secret: str) -> str:
    compact = " ".join(line.strip().split())
    redacted = compact.replace(secret, redact(secret), 1)
    if len(redacted) > 180:
        return redacted[:177] + "..."
    return redacted


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[int, str, str]] = set()

    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            for match in rule.pattern.finditer(line):
                secret = match.group(rule.capture_group) if rule.capture_group else match.group(0)
                if not secret:
                    continue

                if rule.min_entropy is not None and entropy(secret) < rule.min_entropy:
                    continue

                if looks_allowlisted(line, secret):
                    continue

                key = (line_number, rule.name, secret)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    Finding(
                        path=path,
                        line_number=line_number,
                        rule=rule.name,
                        line=line,
                        secret=secret,
                    )
                )

    return findings


def scan_mode(mode: str, max_file_bytes: int) -> int:
    if mode == "repo":
        files = list_repo_files()
        reader = read_repo_file
    elif mode == "staged":
        files = list_staged_files()
        reader = read_staged_file
    else:  # pragma: no cover - argparse enforces choices
        raise ValueError(f"Unsupported mode: {mode}")

    if mode == "staged" and not files:
        print("Secret scan passed. No staged files to scan.")
        return 0

    findings: list[Finding] = []
    for path in files:
        if should_skip_path(path):
            continue
        try:
            data = reader(path)
        except FileNotFoundError:
            continue
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        if len(data) > max_file_bytes or is_binary(data):
            continue

        text = data.decode("utf-8", errors="ignore")
        findings.extend(scan_text(path, text))

    if not findings:
        print("Secret scan passed.")
        return 0

    print("Secret scan failed. Potential secrets detected:")
    for finding in findings:
        snippet = make_snippet(finding.line, finding.secret)
        print(f"- {finding.path}:{finding.line_number} [{finding.rule}] {snippet}")
    print("If a match is intentional, add an inline marker: secret-scan: allow")
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan repository text for potential secret leaks.")
    parser.add_argument(
        "--mode",
        choices=("repo", "staged"),
        default="repo",
        help="Scan tracked repository files or staged files.",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=1_500_000,
        help="Skip files larger than this threshold.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return scan_mode(mode=args.mode, max_file_bytes=args.max_file_bytes)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
