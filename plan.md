# Meal Tracker App Plan

## Goal

Build a simple personal meal tracker that lets me type what I ate in plain English, gets a rough calorie estimate from an LLM, stores the structured result, and shows daily/weekly totals.

The priority is low effort and consistency, not perfect nutrition tracking.

## Core Principle

The app should answer:

> “Am I broadly on track this week?”

Not:

> “Exactly how many calories and macros did I consume?”

## Target Behaviour

Example input:

```text
Small pho bo tai
Bun thit nuong, no spring roll
Half mango
Ice cream
```

Example output:

| Meal | Calories |
|---|---:|
| Small pho bo tai | 450 |
| Bun thit nuong, no spring roll | 650 |
| Half mango | 100 |
| Ice cream | 250 |
| **Total** | **1,450** |

The app should save the original text, the structured estimate, and allow manual edits.

By deafult the entry should be recorded at the current time, but this should also be able to be added retrospectively - both in terms of 'yesterday I had Pho for lunch'

---

# Phase 1 — Local Streamlit App with JSON Storage

## Objective

Build the working app locally with minimum infrastructure.

## Stack

- Streamlit
- Python
- OpenAI API
- Local JSON file storage
- Pydantic for structured output

## Features

### 1. Add Meal Log

Input box:

```text
Small pho bo tai
```

Button:

```text
Estimate
```

LLM returns structured output:

```json
{
  "items": [
    {
      "name": "Small phở bò tái",
      "calories_low": 400,
      "calories_mid": 475,
      "calories_high": 550,
      "protein_level": "medium",
      "confidence": "medium",
      "notes": "Typical small beef pho portion."
    }
  ],
  "total_calories_mid": 475
}

This also needs the time and date consumed  - defaulting to the current time 

```

### 2. Manual Override

Allow editing:

- meal name
- calories
- notes
- date/time

If I type:

```text
Poke bowl, label says 720 calories
```

Then the app should use 720 instead of inventing an estimate.

### 3. Save Log

Save each record to:

```text
data/meals.json
```

Each record should include:

```json
{
  "id": "uuid",
  "timestamp": "2026-06-28T12:35:00+07:00",
  "raw_text": "Small pho bo tai",
  "items": [],
  "total_calories_mid": 475,
  "user_override": null,
  "created_at": "2026-06-28T12:36:00+07:00"
}
```

### 4. Today View

Show:

- meals logged today
- daily total
- target range
- simple status

Status bands:

| Calories | Status |
|---:|---|
| < 1,800 | Low |
| 1,800–2,200 | Good deficit |
| 2,200–2,600 | Maintenance-ish |
| > 2,600 | High day |

### 5. Week View

Show:

- total calories this week
- average per day
- number of heavy meals
- number of fried extras / spring rolls
- number of sweets / ice creams
- rough protein quality: low / medium / good

## Phase 1 File Structure

```text
meal-tracker/
  app.py
  meal_estimator.py
  meal_store.py
  schemas.py
  prompts.py
  data/
    meals.json
  requirements.txt
  .env
  .gitignore
  README.md
  plan.md
```

## Phase 1 Done When

- I can run `streamlit run app.py`
- I can enter meals in free text
- LLM returns structured estimates
- I can edit the estimate before saving
- JSON storage works
- Today and week dashboards work
- No deployment yet




# Phase 2 — Move Storage to Supabase, Still Run Locally

## Objective

Replace local JSON with persistent cloud database storage while keeping the app local.

## Stack

- Streamlit local
- OpenAI API
- Supabase Postgres
- Supabase Python client

## Supabase Table

Table name:

```text
meal_logs
```

Suggested columns:

| Column | Type | Notes |
|---|---|---|
| id | uuid | primary key |
| timestamp | timestamptz | meal time |
| raw_text | text | original user input |
| total_calories_mid | integer | main calorie estimate |
| calories_low | integer | optional total low estimate |
| calories_high | integer | optional total high estimate |
| structured_json | jsonb | full LLM response |
| user_override | integer | optional manual calorie override |
| notes | text | optional |
| created_at | timestamptz | insert time |

For now this is single-user, so no `user_id` is needed.

Optional future column:

```text
user_id uuid
```

## Features

### 1. Replace JSON Writes

Instead of writing to `data/meals.json`, insert into Supabase.

### 2. Replace JSON Reads

Today and week views should query Supabase.

### 3. Keep Export

Add an export button to download all logs as JSON or CSV.

### 4. Keep Local Development

Run locally:

```bash
streamlit run app.py
```

Secrets stored locally in `.env` or `.streamlit/secrets.toml`.

## Environment Variables

```text
OPENAI_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

For personal use, service role key is acceptable locally, but do not expose it in browser code.

## Phase 2 Done When

- Supabase table exists
- App can save meal logs to Supabase
- App can read today/week totals from Supabase
- Local JSON is no longer the main store
- Export still works
- Local app remains fully usable

---

# Phase 3 — Deploy to Streamlit Community Cloud

## Objective

Make the app accessible from phone and laptop without running it locally.

## Stack

- Streamlit Community Cloud
- GitHub repo
- Streamlit secrets
- Supabase database
- OpenAI API

## Deployment Architecture

```text
Phone / Laptop
      ↓
Streamlit Community Cloud
      ↓
OpenAI API
      ↓
Supabase
```

## Steps

### 1. Prepare Repo

Ensure repo has:

```text
app.py
requirements.txt
README.md
```

Do not commit:

```text
.env
.streamlit/secrets.toml
data/meals.json
```

### 2. requirements.txt

Minimum:

```text
streamlit
openai
pydantic
supabase
python-dotenv
pandas
```

### 3. Add Secrets in Streamlit Cloud

Add:

```text
OPENAI_API_KEY="..."
SUPABASE_URL="..."
SUPABASE_SERVICE_ROLE_KEY="..."
```

### 4. Deploy

- Push repo to GitHub
- Open Streamlit Community Cloud
- Select repo
- Select branch
- Select `app.py`
- Deploy

### 5. Test on Phone

Confirm:

- app loads on mobile
- meal entry works
- estimate works
- save works
- weekly dashboard works

## Phase 3 Done When

- App is accessible from phone
- API key is not exposed
- Data persists in Supabase
- I can log food while out
- Dashboard reflects latest Supabase data

---

# Future Improvements

## Optional Phase 4 — Better UX

- Quick buttons for common meals
- Recent meals list
- “Repeat this meal”
- Add weight tracking
- Add Garmin active calorie manual entry
- Weekly trend chart
- Meal tags:
  - soup
  - rice
  - noodles
  - fried
  - sweet
  - high protein
  - low protein

## Optional Phase 5 — Multi-user

Add:

- Supabase Auth
- user_id column
- row-level security
- per-user dashboards

This is not needed for the personal version.

## Optional Phase 6 — React Frontend

Only consider this if the app becomes something I use constantly and want to polish.

Potential production architecture:

```text
React / Next.js
      ↓
Serverless endpoint
      ↓
OpenAI API
      ↓
Supabase
```

Keep:

- Supabase schema
- meal estimation prompt
- structured output schema
- business rules

Replace:

- Streamlit UI

---

# Design Rules

## Do

- Estimate in ranges
- Preserve raw input
- Allow manual override
- Prefer useful over precise
- Make logging take under 15 seconds
- Show weekly trend, not perfection

## Do Not

- Build a full MyFitnessPal clone
- Require ingredient-level logging
- Require exact portion weights
- Overbuild authentication in v1
- Spend more time tracking food than eating well

---

# Initial Meal Estimate Reference

Use this as a starting point for the prompt or internal reference table.

| Meal | Rough Calories |
|---|---:|
| Small phở bò tái | 400–550 |
| Phở bò tái | 500–650 |
| Large phở bò tái | 650–800 |
| Phở gà | 450–650 |
| Bánh mì | 450–650 |
| Cơm gà | 550–750 |
| Bún bò Huế | 500–750 |
| Bún thịt nướng | 650–850 |
| Bún thịt nướng with spring rolls | 800–1050 |
| Mì Quảng | 600–850 |
| Mì Quảng with spring rolls | 800–1050 |
| Gỏi cuốn | 80–120 each |
| Poke bowl | 650–900 |
| Burrito | 800–1100 |
| Half mango | 80–120 |
| Ice cream | 200–350 |
| Americano | 0–20 |
| Soda water | 0 |

---

# Success Criteria

This app is successful if:

- I use it most days
- It keeps me broadly around 1,900–2,200 calories/day
- It helps me spot high-calorie patterns
- It does not make food feel obsessive
- It supports gradual weight loss of roughly 0.5 kg/week
