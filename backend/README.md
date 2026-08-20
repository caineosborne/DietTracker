# DietTracker API

FastAPI JSON backend for DietTracker. It is designed for a sleeping Railway service: startup does not touch PostgreSQL or OpenAI, `/health` is lightweight, and every database operation uses a short-lived connection.

## Local development

```bash
cp .env.example .env
uv sync
uv run uvicorn diettracker.api:app --reload
```

The API runs at `http://localhost:8000`. Start PostgreSQL from the repository root with `docker compose up -d`.

Generate a password hash with:

```bash
uv run python scripts/generate_password_hash.py
```

Set `APP_USERNAME`, `APP_PASSWORD_HASH`, and a long random `APP_SESSION_SECRET`. Sign-in returns a signed 30-day session token; private endpoints validate it on every request. Passwords are verified against the existing scrypt hash and are never stored.

## Railway

Create a Railway service from this repository and set its root directory to `/backend`. `railway.toml` starts exactly one Uvicorn worker.

Required variables:

- `DATABASE_URL` — supplied by the linked Railway PostgreSQL service.
- `OPENAI_API_KEY`
- `APP_USERNAME`
- `APP_PASSWORD_HASH`
- `APP_SESSION_SECRET`
- `FRONTEND_URLS` — any additional comma-separated HTTPS frontend origins. The production and current preview Vercel origins are already allowed in code.
- `COOKIE_SECURE=true`

Optional variables are `OPENAI_MODEL` and `APP_TIMEZONE`.

After the first successful deployment, enable **Serverless** in the Railway service settings so the service sleeps after inactivity. Keep the healthcheck path as `/health`. Do not add a minimum replica or background worker to this API service.

## Verification

```bash
uv run pytest
```

Tests live in `tests/` and remain version-controlled. They are not imported by the running API.

## Optional Telegram integration

The retained Telegram bot is isolated from the API under `integrations/` and its packages are not installed in production by default. To use it locally:

```bash
uv sync --extra telegram
uv run python -m integrations.telegram_bot
```
