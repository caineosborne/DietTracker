# Meal Tracker

Local Streamlit meal tracker that turns free-text meal notes into structured calorie estimates using the OpenAI API.

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

## Notes

- Default model: `gpt-5.4-mini`
- Primary flow: enter natural-language meal text, estimate, then save
- Manual editing is available as a fallback when the parsed time or calories need correction
- Data is stored locally in `data/meals.json`
