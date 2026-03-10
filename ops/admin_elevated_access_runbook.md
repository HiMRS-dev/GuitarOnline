# Admin Elevated Access Runbook

This runbook defines the controlled invite/approve flow for privileged roles (`teacher`, `admin`)
and the evidence required for auditability.

## 1) Scope

- Public self-registration must remain limited to `student`.
- Elevated roles are created only through admin-protected provisioning endpoint:
  - `POST /api/v1/admin/users/provision`
- Teacher enablement is a two-step flow:
  1. Provision account in `pending` profile state.
  2. Approve explicitly from admin panel/API.

## 2) Invite (Provision) Flow

1. Authenticate as `admin`.
2. Call provision endpoint for `teacher` or `admin`.

Teacher example:

```bash
curl -X POST "${BASE_URL}/api/v1/admin/users/provision" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "teacher.invite@example.com",
    "password": "StrongPass123!",
    "timezone": "UTC",
    "role": "teacher",
    "teacher_profile": {
      "display_name": "Invited Teacher",
      "bio": "Session invite flow",
      "experience_years": 5
    }
  }'
```

Expected result:
- HTTP `201`.
- Teacher profile is created with `status=pending` and `verified=false`.
- Audit event emitted: `admin.user.provision`.

## 3) Approve / Disable Flow

Approve teacher profile:

```bash
curl -X POST "${BASE_URL}/api/v1/admin/teachers/${TEACHER_USER_ID}/verify" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

Disable teacher profile and account:

```bash
curl -X POST "${BASE_URL}/api/v1/admin/teachers/${TEACHER_USER_ID}/disable" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

Expected audit trail:
- `admin.teacher.verify` for approval.
- `admin.teacher.disable` for disable action.

## 4) Elevated Account Audit Report

Generate point-in-time report (local stack):

```bash
docker compose -f docker-compose.prod.yml exec -T app \
  python scripts/elevated_account_audit.py --output-dir ops/reports/elevated-account-audit
```

Generate and store report from target host (recommended):
- Run workflow: `.github/workflows/elevated-account-audit.yml`
- Manual dispatch input:
  - `confirm=AUDIT`
- Output artifact:
  - `elevated-account-audit-report-<run_id>`
  - includes JSON report, Markdown report, and remote execution log.

## 5) Audit Acceptance Criteria

- Every privileged account in report has one of:
  - `provision_source=admin.user.provision`, or
  - `provision_source=legacy_or_unknown` with reviewed remediation owner.
- Every teacher in active use is either:
  - `teacher_status=verified`, or
  - explicitly tracked as `pending`/`disabled`.
- Latest report artifact link is recorded in `CONTEXT_CHECKPOINT.md`.

