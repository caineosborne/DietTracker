# DietTracker Backup and Restore Guide

DietTracker includes a portable JSON backup tool. A backup contains meals, daily activity, weight entries, removed snack-allowance days, and saved application settings such as the timezone.

Backups are written to a private `backups/` directory that Git ignores. Copy important backups somewhere outside this repository as well—for example, encrypted cloud storage.

## Back up the local database

Start the local PostgreSQL service if it is not already running:

```bash
docker compose up -d
```

Then run:

```bash
cd backend
uv sync
uv run python scripts/export_postgres_backup.py
```

If `--output` is omitted, the script creates a timestamped file under `backend/backups/`.

The command prints the output path and the number of records included. Open the JSON file and confirm it contains a recent `exported_at` value and non-empty record counts where expected.

## Back up the production Railway database

The safest approach is an SSH tunnel, which does not require exposing PostgreSQL publicly.

### 1. Install and connect the Railway CLI

If needed on macOS:

```bash
brew install railway
railway login
```

From the repository root, link the CLI to the production Railway project:

```bash
railway link
```

Choose the DietTracker project and production environment.

### 2. Open a database tunnel

In the first terminal, run the following, replacing `Postgres` if your Railway database service has a different name:

```bash
railway connect Postgres --tunnel-only --port 55432
```

Railway prints a PostgreSQL connection URL using `localhost:55432`. Keep this terminal open until the backup finishes.

### 3. Run the backup through the tunnel

In a second terminal:

```bash
cd backend
DATABASE_URL='PASTE_THE_TUNNEL_CONNECTION_URL_HERE' \
  uv run python scripts/export_postgres_backup.py \
  --output "../backups/diettracker-production-$(date -u +%Y-%m-%dT%H%M%SZ).json"
```

The resulting filename looks like `diettracker-production-2026-08-20T013000Z.json`. Keep the connection URL inside single quotes. Do not save it in Git, screenshots, notes, or shell scripts.

When the backup completes, return to the tunnel terminal and press `Ctrl+C`.

## Restore a backup

Restoring is deliberately more difficult because it replaces the current DietTracker records. Take a fresh backup of the destination first.

For a local database:

```bash
cd backend
uv run python scripts/restore_postgres_backup.py \
  ../backups/diettracker-production-YYYY-MM-DDTHHMMSSZ.json \
  --replace
```

For Railway, open the tunnel described above and provide its connection URL only to the restore command:

```bash
cd backend
DATABASE_URL='PASTE_THE_TUNNEL_CONNECTION_URL_HERE' \
  uv run python scripts/restore_postgres_backup.py \
  ../backups/diettracker-production-YYYY-MM-DDTHHMMSSZ.json \
  --replace
```

`--replace` deletes the destination's current DietTracker meals, activity, weights, snack-removal records, and settings before importing the backup. It does not drop the PostgreSQL database or affect schemas belonging to other applications.

## Recommended routine

- Create a production JSON backup weekly and before deployments involving database changes.
- Keep at least three dated copies outside the repository.
- Never commit backup files or database connection URLs.
- Occasionally restore a backup into the local database and confirm that meals, activity, weights, and settings appear correctly. A backup is only proven once it has been restored successfully.

For additional protection, Railway also supports volume snapshots and standard PostgreSQL `pg_dump` backups. The DietTracker JSON format is convenient for inspecting and moving this application's records; a `pg_dump` is the stronger whole-database disaster-recovery option.
