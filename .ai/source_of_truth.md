# Source Of Truth And Precedence

## Rule Priority
1. `AGENTS.md` in repository root is the primary source of truth.
2. `.ai/*` files are concise guidance and must not override `AGENTS.md`.
3. If conflict exists, follow `AGENTS.md`.

## High-Impact Limits From `AGENTS.md`
- Default change size: max 5 modified files, max 1 new file (unless explicitly approved).
- Dependency changes are forbidden without explicit approval.
- Database/infrastructure changes require explicit approval.
- Use permission flags when applicable:
  - `ALLOW_BACKEND_CHANGES`
  - `ALLOW_DATABASE_CHANGES`
  - `ALLOW_INFRASTRUCTURE_CHANGES`
  - `ALLOW_DEPENDENCY_CHANGES`

## Execution Expectations
- Start with read-only analysis for non-trivial tasks.
- Use minimal, local, reversible changes.
- Report changed files, commands, checks, and residual risk.
