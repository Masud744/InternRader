# InternRadar Development Plan

## Project Overview
Automated internship aggregation and notification system that scrapes job portals, filters by keywords, stores in Supabase, and sends daily email digests.

---

## Architecture

### Backend (`/backend/`)
- **main.py** - FastAPI REST API
  - Endpoints: `/health`, `/internships` (with filtering), `/internships/sources`, `/internships/stats`
  - CORS enabled for frontend access
  
- **sources.py** - Web scrapers
  - LinkedIn, Indeed, Internshala, BDJobs
  - BeautifulSoup HTML parsing
  - Deduplication and error handling
  
- **models.py** - Data structures
  - `Internship` dataclass with normalization
  
- **keyword_filter.py** - Filtering logic
  
- **supabase_client.py** - Database layer
  - REST API integration
  - Duplicate handling via `on_conflict`
  
- **notifier.py** - Email notifications
  
- **http.py** - HTTP utilities

### Frontend (`/frontend/`)
- `index.html` - Dashboard UI
- `app.js` - Client logic (API, pagination, bookmarks, CSV export)
- `styles.css` - Styling
- `supabase.js` - Auth integration

---

## Current Features
- [x] Multi-source scraping (LinkedIn, Indeed, Internshala, BDJobs)
- [x] Keyword-based filtering
- [x] Supabase persistence
- [x] Daily email digest
- [x] FastAPI REST endpoints
- [x] Frontend dashboard with filtering
- [x] GitHub Actions automation
- [x] Bookmark functionality
- [x] Analytics tab

---

## Setup & Configuration

### Environment Variables (`.env`)
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=
EMAIL_TO=
JOB_KEYWORDS=ai,machine learning,deep learning,robotics,iot,embedded,python,backend,full stack,api,cloud,devops,cybersecurity,data science
SEARCH_TERMS=
MAX_RESULTS_PER_SOURCE=30
SEND_EMPTY_DIGEST=true
DRY_RUN=false
```

### Installation
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### Running
```bash
# Scraper
python main.py

# API (dev)
uvicorn backend.main:app --reload

# Frontend
cd frontend && python -m http.server 5500
```

---

## Development Roadmap

### Phase 1: Core Enhancements
- [ ] Add retry logic with exponential backoff for scrapers
- [ ] Implement user-agent rotation
- [ ] Add proxy support for anti-bot mitigation
- [ ] Improve error handling and logging

### Phase 2: Frontend Improvements
- [ ] User authentication/registration
- [ ] Personalized recommendations based on saved keywords
- [ ] Job alert subscription
- [ ] Dark mode toggle

### Phase 3: Notifications
- [ ] Telegram bot notifications
- [ ] WhatsApp notifications
- [ ] Webhook support for custom integrations

### Phase 4: Analytics & Intelligence
- [ ] Dashboard charts (jobs by source, trends over time)
- [ ] Resume matching with AI
- [ ] Salary estimation
- [ ] Application tracking

### Phase 5: Scalability
- [ ] Docker containerization
- [ ] Redis caching for API responses
- [ ] Background job queue (Celery/RQ)
- [ ] Rate limiting per source

---

## Testing Strategy
- Unit tests for scraper parsing functions
- Integration tests for Supabase client
- API endpoint tests
- Frontend component tests

---

## Known Issues & Considerations
- LinkedIn may block scraper requests (needs rotating proxies)
- Indeed/Internshala HTML selectors may change frequently
- Supabase REST API has 1000 row limit per request
- Email digest sends to all recipients (no personalization)