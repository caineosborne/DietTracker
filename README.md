# DietTracker

DietTracker is now a React single-page application backed by a stateless FastAPI service. The frontend is built for Vercel; the API and PostgreSQL connection run on Railway.

```text
DietTracker/
├── frontend/   React + TypeScript + Vite static site
├── backend/    FastAPI, domain logic, PostgreSQL stores, tests and scripts
└── compose.yaml  local PostgreSQL only
```

## Run locally

Start PostgreSQL:

```bash
docker compose up -d
```

Start the API:

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn diettracker.api:app --reload
```

In another terminal, start React:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:5173`.

## Deploy

### Railway API

1. Create a service from this repository with **Root Directory** set to `backend`.
2. Link the existing Railway PostgreSQL service so `DATABASE_URL` is available.
3. Add `OPENAI_API_KEY`, `APP_USERNAME`, `APP_PASSWORD_HASH`, `APP_SESSION_SECRET`, `FRONTEND_URL`, and `COOKIE_SECURE=true`.
4. Deploy. The checked-in command runs `uvicorn diettracker.api:app --workers 1`.
5. Keep the Railway service always online; the frontend connects to the authenticated API directly on startup.

### Vercel frontend

1. Import the same repository with **Root Directory** set to `frontend`.
2. Add `VITE_API_URL=https://your-api.up.railway.app`.
3. Deploy with the Vite preset. The output is a static `dist` site.
4. Put the resulting Vercel HTTPS origin in Railway's `FRONTEND_URL` and redeploy the API.

The React app checks the user's session as soon as it opens, without a separate health-check request. It does not poll or keep a persistent connection open. Meal creates carry a stable request ID, daily activity and weight use upserts, and deletes are retry-safe.

See [backend/README.md](backend/README.md) for API variables, password setup, backups and tests.

For production and local backup instructions, see [BACKUP_GUIDE.md](BACKUP_GUIDE.md).
