# Backend Rules

## Modularity
- Backend logic must stay in domain modules (`app/modules/*`).
- Prefer existing patterns inside each module.
- Keep API routers thin; avoid placing business logic there.

## Forbidden By Default
- Merge modules
- Split modules
- Rename modules
- Move logic across modules casually
- Introduce new `core/shared/common/framework` layers

## Sensitive Backend Areas
- `identity`
- `billing`
- `booking`
- `scheduling`

Changes in these areas require explicit risk explanation and verification plan.
