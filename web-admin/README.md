# web-admin

React + TypeScript admin UI scaffold powered by Vite.

## Local Run

1. Install dependencies:
   - `npm install`
2. Optional env for local API target (`web-admin/.env`):
   - `VITE_API_BASE_URL=/api/v1`
   - `VITE_DEV_API_TARGET=http://localhost:8000`
3. Start dev server:
   - `npm run dev`

By default admin UI uses relative API base `"/api/v1"` and Vite dev proxy
for `"/api/*"` requests to `VITE_DEV_API_TARGET` (fallback: `http://localhost:8000`).

Use absolute `VITE_API_BASE_URL` only when you intentionally need a different backend.
Public app base path is configured with `VITE_BASE_PATH` (`/` for local dev, `/admin/`
for reverse-proxy deployment).

## Auth Storage Strategy

- v1 (current): access/refresh tokens are stored in `localStorage` for rapid bootstrap.
- v2 (planned): migrate token storage to backend-issued httpOnly cookies and keep frontend
  token-free to reduce XSS exposure.
