# AGENTS.md — GuitarOnline Repository Rules

This file defines repository-level rules for AI coding agents (including Codex) working in this project.

The goal is to help the project move forward without damaging architecture, contracts, data, security, or operations.

If multiple actions are possible, always choose the option that is:

smaller, safer, more local, easier to review, and easier to undo.

---

# 1. Core Operating Principle

Agents must behave like a careful developer working inside an existing production-oriented codebase.

Priority order:

stability > safety > correctness > clarity > minimal progress > speed

Never optimize for cleverness.  
Never redesign architecture unless explicitly asked.

---

# 2. Default Mode — Read Only Analysis First

Before writing or editing code the agent must:

1. inspect relevant files
2. understand current implementation
3. propose the smallest viable change
4. list files that will be modified
5. estimate risk

Required format:

What I found  
What I will change  
Files to modify  
Risk level  
Checks to run

For non-trivial tasks the agent should provide a short plan first.

Confirmation is required only for high-risk changes or restricted areas.

---

# 3. Repository Structure

Main areas of the project:

Backend

app/

Domain modules

app/modules/

Admin frontend

web-admin/

Infrastructure

Dockerfile  
docker-compose.yml  
.env  
deployment configs  

Testing

pytest  
Playwright  
ruff  

The agent must respect the current structure and must not reorganize the project.

---

# 4. Backend Architecture Rules

Backend logic is organized by domains in:

app/modules/

Examples of modules:

teachers  
lessons  
identity  
booking  
billing  
scheduling  
notifications  
admin  
audit  

Rules:

- treat modules as domain boundaries
- do not merge modules
- do not split modules
- do not rename modules
- do not move logic between modules casually
- do not introduce new "core", "shared", "common", or "framework" layers

When adding functionality prefer the existing module.

---

# 5. API Contract Protection

API contracts must remain stable.

The agent must not silently change:

request schemas  
response schemas  
field names  
status codes  
error payload format  
authentication behavior  
pagination structure  
sorting or filtering behavior  

If a contract change is necessary the agent must:

1. explicitly say the contract changes
2. list affected endpoints
3. state whether the change is breaking
4. update tests
5. mention frontend impact

---

# 6. Database Hard Lock

Database schema changes are forbidden by default.

Without explicit permission the agent must not:

- modify SQLAlchemy models
- add/remove fields
- rename columns
- rename tables
- change relationships
- create Alembic migrations
- edit migration history

Schema changes are allowed only with explicit permission.

If allowed:

- migrations must use Alembic
- migrations must be minimal
- rollback must be possible
- data migration risks must be explained

---

# 7. Infrastructure Hard Lock

Infrastructure is read-only unless explicitly approved.

Protected files:

Dockerfile  
docker-compose.yml  
deployment configs  
CI/CD configs  
startup scripts  
reverse proxy configs  
monitoring configs  
environment wiring  

If infrastructure changes are approved the agent must explain:

reason for change  
affected services  
operational impact  
rollback plan  

---

# 8. Frontend Rules (web-admin)

Frontend changes must stay small and local.

Allowed:

UI bug fixes  
minor layout changes  
small components  
text updates  
minor styling  

Forbidden by default:

frontend architecture redesign  
changing build system  
changing Vite configuration  
introducing state managers  
replacing routing libraries  
large UI redesigns  

If the task is UI-only, do not modify backend.

---

# 9. Dependency Freeze

Dependencies must not change unless explicitly approved.

The agent must not:

add Python packages  
remove Python packages  
update versions  
add npm packages  
remove npm packages  
update frontend dependency versions  

If a dependency change is necessary the agent must explain:

why existing tools are insufficient  
the trade-offs  
the scope of impact  

---

# 10. Refactoring Restrictions

Refactoring is allowed only if:

- it is local
- it is small
- it is required to complete the task
- it stays within the same module

Forbidden:

large codebase cleanup  
cross-module refactoring  
mass renaming  
architecture redesign  
global pattern replacement  

---

# 11. Change Size Limits

Default limits per task:

maximum 8 modified files  
maximum 2 new files  

If more changes are needed the agent should keep the change scoped and explain why the extra files are necessary.

---

# 12. File Creation Policy

When creating files:

prefer existing directories  
prefer the nearest module  
avoid new top-level folders  
avoid speculative files  
avoid placeholder files  

Create a new file only when clearly required.

---

# 13. Quality Gate

Before reporting success the agent must run relevant checks when available.

Examples:

pytest  
ruff  
targeted tests  
Playwright smoke checks  

The agent must report:

what was executed  
what passed  
what failed  
what was not tested  

Never claim tests passed if they were not run.

---

# 14. Logging and Observability

The agent must not weaken operational visibility.

Protected features:

health endpoints  
readiness endpoints  
metrics exposure  
audit logging  
operational logs  
tracing hooks  

If observability changes occur the agent must explain why.

---

# 15. Security Rules

The agent must never expose or hardcode:

API keys  
tokens  
passwords  
payment secrets  
.env values  
private credentials  

Secrets must never appear in logs or code.

Exception:

The agent may provide secrets in chat only if the user gives explicit and direct permission in the current message.

In such cases, the agent must:

- confirm that the user explicitly requested the secret
- avoid storing the secret in files or code
- avoid repeating the secret unnecessarily
- clearly warn that sharing secrets in chat may be unsafe

---

# 16. Sensitive Business Logic

Sensitive areas include:

billing  
payments  
identity  
authentication  
authorization  
booking logic  
lesson access rules  
teacher/student permissions  

Changes in these areas must include:

risk explanation  
logic explanation  
verification plan  

---

# 17. Environment Handling

Rules:

never commit real secrets  
do not guess production values  
do not alter env wiring casually  
use `.env.example` only for documentation  

---

# 18. Permission Flags

Restricted areas may be unlocked only with explicit flags.

Supported flags:

ALLOW_BACKEND_CHANGES  
ALLOW_DATABASE_CHANGES  
ALLOW_INFRASTRUCTURE_CHANGES  
ALLOW_DEPENDENCY_CHANGES  

Flags apply only to the current task.

---

# 19. Escalation Rules

If a task involves:

database changes  
infrastructure changes  
API breaking changes  
auth or billing logic  
dependency changes  
more than 8 files across multiple modules  

the agent must escalate before editing.

Escalation requires explaining:

reason  
scope  
risks  
required permission  

---

# 20. Change Report

After making changes the agent must report:

changed files  
summary of edits  
commands executed  
test results  
remaining risks  

---

# 21. Developer Friendly Rule

The repository owner is still learning the system.

The agent must prefer:

clear code  
predictable structure  
simple solutions  
small changes  

Avoid:

overengineering  
clever abstractions  
enterprise patterns without need  

---

# 22. Ambiguity Rule

If something is unclear, the agent should make the safest reasonable assumption and continue when the ambiguity is minor and low-risk.

The agent must stop and ask only if the ambiguity affects:

database design  
auth behavior  
deployment configuration  
payment flows  
API semantics  
or could cause unsafe or breaking changes

Never guess:

database design  
auth behavior  
deployment configuration  
payment flows  
API semantics  

---

# 23. Final Philosophy

This project evolves through small safe steps.

Prefer:

one small change over a large refactor  
one module change over cross-module edits  
explicit approval over silent decisions  

When unsure:

stop and choose the safest option.