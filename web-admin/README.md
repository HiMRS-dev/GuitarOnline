# web-admin

React + TypeScript admin UI scaffold powered by Vite.

## Local Run

1. Install dependencies:
   - `npm install`
2. Copy env template:
   - `.env.example` -> `.env`
3. Start dev server:
   - `npm run dev`

Default API base URL is provided by `VITE_API_BASE_URL`.

## Auth Storage Strategy

- v1 (current): access/refresh tokens are stored in `localStorage` for rapid bootstrap.
- v2 (planned): migrate token storage to backend-issued httpOnly cookies and keep frontend
  token-free to reduce XSS exposure.
