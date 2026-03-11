# API Contract Rules

API contracts must remain stable.

## Do Not Silently Change
- Request schemas
- Response schemas
- Field names
- Status codes
- Error payload format
- Authentication behavior
- Pagination/sorting/filtering behavior

## If Contract Change Is Required
1. Explicitly describe the change.
2. List affected endpoints.
3. Mark breaking vs non-breaking.
4. Update tests.
5. Mention frontend impact.
