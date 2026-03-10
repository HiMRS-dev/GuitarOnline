from scripts.secret_guard import scan_text


def test_allowlists_env_identifier_in_secret_name_context() -> None:
    findings = scan_text(
        "workflow.yml",
        'echo "::error::Missing required repository secret: PROD_ENV_FILE_B64"\n',
    )

    assert findings == []


def test_still_flags_real_secret_assignment() -> None:
    findings = scan_text("settings.py", "password: Qx9mN2vL7sH3pK5t\n")  # secret-scan: allow

    assert len(findings) == 1
    assert findings[0].rule == "generic_secret_assignment"


def test_does_not_allowlist_env_identifier_without_context() -> None:
    findings = scan_text("settings.py", "password=PROD_ENV_FILE_B64\n")  # secret-scan: allow

    assert len(findings) == 1
    assert findings[0].rule == "generic_secret_assignment"


def test_allowlists_shared_credential_placeholder() -> None:
    findings = scan_text("notes.txt", "local password = shared_credential_12345\n")

    assert findings == []
