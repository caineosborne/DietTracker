# DietTracker

Personal Streamlit tracker for calories in, calories out, and weight. Free-text meal notes are converted into structured calorie estimates using the OpenAI API.

## Setup

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
2. Install dependencies:

```bash
uv sync
```

3. Run the app:

```bash
uv run streamlit run app.py
```

## Use

- Default model: `gpt-5.4-mini`
- Enter a natural-language meal, review the estimate, and save it.
- Add daily active calories and weight in Daily Details.
- The 200-calorie small-snacks allowance is added automatically each day and can be deleted when it was not needed.
- Current data is stored locally under `data/`; it will move to Postgres as part of the hosting work.
