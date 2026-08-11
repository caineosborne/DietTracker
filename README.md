# DietTracker

Personal Streamlit tracker for calories in, calories out, and weight. Free-text meal notes are converted into structured calorie estimates using the OpenAI API.

## Setup

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
2. Start the local database:

```bash
docker compose up -d
```

3. Install dependencies:

```bash
uv sync
```

4. Import the existing JSON history once:

```bash
uv run python scripts/import_json_data.py
```

5. Run the app:

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
