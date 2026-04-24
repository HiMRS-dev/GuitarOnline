# ADM-08 Rollout/Cutover Notes (2026-04-25)

## Cutover Decision
- Default admin flow switched to framework-first route:
  - `/admin/platform`
- Legacy admin flow remains available for one release cycle as fallback:
  - `/admin/kpi`
  - `/admin/users`
  - `/admin/teachers`
  - `/admin/calendar`
  - `/admin/audit`
  - `/admin/students`
  - `/admin/packages`

## Implemented Routing Changes
1. Backend login redirect now points admin users to framework-first route:
   - `/portal?auth=login&next=/admin/platform&entry=admin`
2. Frontend defaults now target `/admin/platform`:
   - portal redirect constant updated,
   - web-admin wildcard route for authenticated session updated,
   - login success quick-link updated.
3. Legacy routes were intentionally preserved unchanged for rollback safety.

## Rollback Plan
- If framework screens regress in production:
  1. revert the cutover commit,
  2. restore default next path to `/admin/kpi`,
  3. keep `/admin/platform` available only as opt-in beta route.

## Validation Checklist
- `GET /admin/login` and `/admin/login/` redirect to `/portal?...next=/admin/platform...`.
- Authenticated admin opening `/admin/platform` gets framework shell.
- Legacy paths listed above still open and function.
