# Domain Map

Backend domain modules live in `app/modules/`.

## Domains
- `identity` -> authentication, authorization, roles
- `teachers` -> teacher profiles and teacher workflows
- `lessons` -> lesson entities and lifecycle
- `booking` -> reservation and booking rules
- `scheduling` -> availability, timeslots, timetables
- `billing` -> payments and financial state
- `notifications` -> system notifications
- `admin` -> administrative actions
- `audit` -> operational/audit logs

## Boundary Rule
- Keep business logic inside its domain module.
- Do not move logic across domains without explicit reason and risk review.
