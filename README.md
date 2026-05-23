# InternRadar

Automated internship aggregation and notification system.

InternRadar scrapes internship/job postings from multiple sources, filters them by keywords, stores new records in Supabase, and sends a daily email digest. The workflow can run on a schedule via GitHub Actions.

## Implemented Features

- Multi-source scraping (LinkedIn, Indeed, Internshala, BDJobs)
- Structured extraction: title, company, location, link, source, posted date
- Keyword-based filtering (IoT, Robotics, Embedded, AI, ML, Backend, FastAPI, React, etc.)
- Supabase persistence with duplicate avoidance
- Daily digest email with newly inserted internships
- GitHub Actions scheduled automation
- Optional FastAPI endpoint to query stored internships

## Project Structure

- `backend/` - All backend code (FastAPI, scraper, filter, database, email)
- `frontend/` - HTML/CSS/JS dashboard
- `.github/workflows/` - Daily scheduler
- `config.py` - Configuration settings
- `main.py` - Main entry point for running the scraper

## 1) Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.10+ is supported. The project uses Supabase REST API via `requests`, so no Supabase SDK build toolchain is required.

Copy environment template:

```bash
copy .env.example .env
```

Fill all needed values in `.env`.

## 2) Create Database Tables in Supabase

Run SQL from `database/schema.sql` in the Supabase SQL editor.

## 3) Local Run

```bash
python main.py
```

## 4) Configure GitHub Actions Secrets

Add these repository secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`
- `JOB_KEYWORDS`
- `SEARCH_TERMS`
- `MAX_RESULTS_PER_SOURCE`
- `SEND_EMPTY_DIGEST`

Workflow file: `.github/workflows/daily_internradar.yml`

## Run Backend API

```bash
uvicorn backend.main:app --reload
```

## Run Frontend

```bash
cd frontend
python -m http.server 5500
```

Endpoints:

- `GET /health`
- `GET /internships?limit=50&keyword=ai&source=LinkedIn`

## Optional Frontend (HTML, CSS, JS)

The frontend is implemented with plain HTML, CSS, and JavaScript.

Open `frontend/index.html` directly in your browser, or serve it locally:

```bash
cd frontend
python -m http.server 5500
```

Then visit:

- `http://127.0.0.1:5500`

The dashboard fetches internship data from the FastAPI backend endpoint.

## Recommended Next Steps

1. Configure `.env` and run `python main.py` locally to verify scraping, filtering, and insert flow.
2. Start the API (`uvicorn api.main:app --reload`) and verify `GET /internships` returns rows.
3. Open `frontend/index.html` and confirm dashboard loading and filtering.
4. Add GitHub repository secrets and run the workflow manually once before relying on schedule.
5. Add source-level tests for parser selectors and keyword filter behavior.

## Important Notes

- Some job portals can change HTML frequently or apply anti-bot protections. Scraper selectors may need periodic updates.
- Always comply with website terms of service and robots policies.
- For production-grade reliability, consider official APIs where available and add retries/proxy/captcha-safe strategies.

## Future Improvements

- User login system
- Personalized recommendations
- Telegram/WhatsApp notification channels
- Dashboard analytics
- Resume matching and AI-based recommendations
