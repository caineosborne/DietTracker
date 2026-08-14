# DietTracker

Personal Streamlit tracker for calories in, calories out, and weight. Free-text meal notes are converted into structured calorie estimates using the OpenAI API.

## Setup

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
2. Choose a local password hash (the password itself is never saved):

```bash
uv run python scripts/generate_password_hash.py
```

Copy the result into `APP_PASSWORD_HASH` in `.env`, then set `APP_USERNAME` and a long random `APP_SESSION_SECRET`.

Keep the password hash single-quoted in `.env`, because Docker Compose otherwise treats its `$` separators as variable references:

```text
APP_PASSWORD_HASH='scrypt$...'
```
3. Start the local database:

```bash
docker compose up -d
```

4. Install dependencies:

```bash
uv sync
```

5. Import the existing JSON history once:

```bash
uv run python scripts/import_json_data.py
```

6. Run the app:

```bash
uv run streamlit run app.py
```

## Local Postgres

The app uses the local Postgres service defined in `compose.yaml`. Docker keeps the database data in a named volume, so it remains available after restarting Docker. Your JSON files in `data/` are retained as an unchanged backup/import source.

To stop the local database without deleting its data:

```bash
docker compose stop
```

## Use

- Default model: `gpt-5.4-mini`
- Enter a natural-language meal, review the estimate, and save it.
- Add daily active calories and weight in Daily Details.
- The 200-calorie small-snacks allowance is added automatically each day and can be deleted when it was not needed.
- Current data is stored in local Postgres. For Railway, its `DATABASE_URL` will replace the local value automatically.
- The live database stores timestamps as UTC instants. Use the **Time zone** selector in the app sidebar to choose the timezone used for entry, display, and day boundaries; the choice is saved in the database. `APP_TIMEZONE` is only the initial fallback (currently `Asia/Ho_Chi_Minh`).
- The app requires a username and password. A successful sign-in is remembered in that browser for 30 days; use **Log out** in the sidebar to end it sooner.

## Railway sign-in settings

Before deploying the login branch, add these Railway variables to the DietTracker service:

- `APP_USERNAME` — your chosen username.
- `APP_PASSWORD_HASH` — the output from `scripts/generate_password_hash.py`.
- `APP_SESSION_SECRET` — a long, random value used to encrypt the browser sign-in cookie.

Do not put your plaintext password in Railway or Git. Changing `APP_SESSION_SECRET` signs out every browser immediately.

## Backups

Railway's built-in database backups require its Pro plan. For this personal app, create a portable local JSON backup instead:

```bash
uv run python scripts/export_postgres_backup.py
```

The backup is saved under `backups/`, which is private and ignored by Git. To back up the Railway database, first open a Railway Postgres tunnel, then run the same command in a second terminal with its local `DATABASE_URL`.

To restore a backup, point the database connection at the target database and run:

```bash
uv run python scripts/restore_postgres_backup.py backups/diettracker-YYYY-MM-DDTHHMMSSZ.json --replace
```

`--replace` deliberately replaces the current tracker data, so use it only when you intend to recover from a backup.
