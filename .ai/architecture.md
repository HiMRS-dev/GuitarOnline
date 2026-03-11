# GuitarOnline Architecture

GuitarOnline is a modular online education platform built as a modular monolith.

## Tech Stack
- Backend: FastAPI
- ORM: SQLAlchemy
- Migrations: Alembic (`alembic/`)
- Database: PostgreSQL
- Cache/Broker: Redis
- Admin frontend: React + TypeScript + Vite
- Infrastructure: Docker + docker-compose

## Repository Layout
- `app/` -> backend application
- `app/modules/` -> domain modules
- `web-admin/` -> admin UI
- `alembic/` -> database migrations
- `Dockerfile`, `docker-compose.yml` -> infrastructure

## Architectural Rules
- Keep changes small, local, and reversible.
- Respect existing module boundaries.
- Do not reorganize repository structure.
- Do not introduce new architecture layers unless explicitly requested.

## Source Of Truth
If any `.ai/*` note conflicts with repository policy, follow `AGENTS.md`.
