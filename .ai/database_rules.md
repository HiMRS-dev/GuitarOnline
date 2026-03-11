# Database Rules

Database schema is hard-locked by default.

## Forbidden Without Explicit Permission
- Modify SQLAlchemy models
- Add/remove fields
- Rename columns/tables
- Change relationships
- Create or edit migration history

## If Database Change Is Explicitly Approved
- Use Alembic with a new minimal migration.
- Keep rollback possible.
- Explain data migration and operational risk.
- Never edit existing migration history.
