# Admin Elevated Access Runbook

This runbook defines the controlled role reassignment flow for privileged roles
(`teacher`, `admin`) and the evidence required for auditability.

## 1) Scope

- Public self-registration must remain limited to `student`.
- Elevated roles are assigned only to existing accounts through admin-protected role change endpoint:
  - `POST /api/v1/admin/users/${USER_ID}/role`
- Assigning `teacher` immediately creates or reactivates the teacher profile in active state.

## 2) Role Reassignment Flow

1. User completes public registration and is created as `student`.
2. Authenticate as `admin`.
3. Call role change endpoint for `teacher` or `admin`.

Teacher example:

```bash
curl -X POST "${BASE_URL}/api/v1/admin/users/${USER_ID}/role" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "teacher"
  }'
```

Expected result:
- HTTP `200`.
- Existing account receives role `teacher`.
- Teacher profile is created if missing and ends up with `status=active`.
- Audit event emitted: `admin.user.role.change`.

## 3) Disable Flow

Disable teacher profile and account:

```bash
curl -X POST "${BASE_URL}/api/v1/admin/teachers/${TEACHER_USER_ID}/disable" \
  -H "Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
```

Expected audit trail:
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
  - `access_source=admin.user.role.change`, or
  - `access_source=legacy_or_unknown` with reviewed remediation owner.
- Every teacher in active use has `teacher_status=active`.
- Latest report artifact link is recorded in `CONTEXT_CHECKPOINT.md`.
