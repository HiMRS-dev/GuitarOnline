# Infrastructure Rules

Infrastructure is read-only unless explicitly approved.

## Protected Areas
- `Dockerfile`
- `docker-compose.yml`
- Deployment configs
- CI/CD configs
- Startup scripts
- Reverse proxy and monitoring configs
- Environment wiring

## Approval Requirements
When approved, document:
- reason for change
- affected services
- operational impact
- rollback plan

Never hardcode secrets.
