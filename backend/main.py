from __future__ import annotations

import os
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(title="InternRadar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalize_supabase_url(url: str) -> str:
    cleaned = url.rstrip("/")
    if cleaned.endswith("/rest/v1"):
        cleaned = cleaned[:-8]
    return cleaned


def _get_supabase_config() -> tuple[str, str]:
    url = _normalize_supabase_url(os.getenv("SUPABASE_URL", "").strip())
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not url or not key:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_ANON_KEY is missing",
        )
    return url, key


def _format_supabase_error(prefix: str, exc: requests.RequestException) -> str:
    detail = f"{prefix}: {exc}"
    response = getattr(exc, "response", None)
    if response is not None:
        snippet = response.text[:200].replace("\n", " ")
        detail += f" | Status: {response.status_code} | Response: {snippet}"
        if response.status_code >= 520:
            detail += " | Supabase origin appears down or blocked. Check project status and URL."
    return detail


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/internships")
def list_internships(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    keyword: str | None = None,
    location: str | None = None,
    source: str | None = None,
    source_in: str | None = None,
    sort: str = Query(default="latest", pattern="^(latest|oldest|company_asc|company_desc)$"),
    date_from: str | None = None,
) -> dict[str, object]:
    base_url, service_role_key = _get_supabase_config()
    
    count_params: dict[str, str] = {"select": "id", "limit": "1000"}
    if source_in:
        sources = [s.strip() for s in source_in.split(",") if s.strip()]
        if sources:
            count_params["source"] = f"in.({','.join(sources)})"
    if keyword:
        count_params["keyword"] = f"ilike.*{keyword.lower()}*"
    if location:
        count_params["location"] = f"ilike.*{location.lower()}*"
    if date_from:
        count_params["scraped_date"] = f"gte.{date_from}"
    
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Accept": "application/json",
    }

    try:
        count_response = requests.get(
            f"{base_url}/rest/v1/internships",
            headers=headers,
            params=count_params,
            timeout=30,
        )
        count_response.raise_for_status()
        all_data = count_response.json()
        total_count = len(all_data) if isinstance(all_data, list) else 0
    except requests.RequestException as exc:
        logger.warning(_format_supabase_error("Supabase count query failed", exc))
        total_count = 0
    
    params: dict[str, str] = {
        "select": "id,title,company,location,link,source,keyword,posted_date,scraped_date",
        "limit": str(limit),
        "offset": str(offset),
    }
    
    if source_in:
        sources = [s.strip() for s in source_in.split(",") if s.strip()]
        if sources:
            params["source"] = f"in.({','.join(sources)})"
    
    if keyword:
        params["keyword"] = f"ilike.*{keyword.lower()}*"
    if location:
        params["location"] = f"ilike.*{location.lower()}*"
    if date_from:
        params["scraped_date"] = f"gte.{date_from}"
    
    order_field = "scraped_date"
    if sort == "oldest":
        order_field = "scraped_date"
        order = "asc"
    elif sort == "company_asc":
        order_field = "company"
        order = "asc"
    elif sort == "company_desc":
        order_field = "company"
        order = "desc"
    else:
        order = "desc"
    
    params["order"] = f"{order_field}.{order}"

    try:
        response = requests.get(
            f"{base_url}/rest/v1/internships",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = _format_supabase_error("Supabase REST query failed", exc)
        raise HTTPException(status_code=500, detail=detail) from exc

    try:
        data = response.json()
    except ValueError as exc:
        snippet = response.text[:200].replace("\n", " ")
        raise HTTPException(
            status_code=502,
            detail=f"Supabase returned non-JSON response: {snippet}",
        ) from exc
    items = data if isinstance(data, list) else []
    return {
        "count": len(items),
        "total": total_count,
        "items": items,
        "limit": limit,
        "offset": offset,
        "sort": sort,
    }


@app.get("/internships/sources")
def get_sources() -> dict[str, object]:
    base_url, service_role_key = _get_supabase_config()
    
    try:
        response = requests.get(
            f"{base_url}/rest/v1/internships",
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
            },
            params={
                "select": "source",
                "limit": 1000,
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get sources: {exc}") from exc
    
    data = response.json()
    items = data if isinstance(data, list) else []
    sources = list(set(item.get("source", "") for item in items if item.get("source")))
    return {"sources": sorted(sources)}


@app.get("/internships/stats")
def get_stats() -> dict[str, object]:
    base_url, service_role_key = _get_supabase_config()
    
    try:
        response = requests.get(
            f"{base_url}/rest/v1/internships",
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
            },
            params={
                "select": "source,scraped_date",
                "limit": 1000,
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {exc}") from exc
    
    data = response.json()
    items = data if isinstance(data, list) else []
    
    source_counts: dict[str, int] = {}
    for item in items:
        src = item.get("source") or "Unknown"
        source_counts[src] = source_counts.get(src, 0) + 1
    
    return {
        "total": len(items),
        "by_source": source_counts,
    }


# ── Phase 2: Kanban – saved_jobs status management ──────────────

@app.patch("/saved-jobs/{job_id}/status")
def update_saved_job_status(job_id: str, status: str = Query(...)) -> dict:
    """Update the status of a saved job (Saved, Applied, Interviewing, Accepted, Rejected)."""
    valid_statuses = ["Saved", "Applied", "Interviewing", "Accepted", "Rejected"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    base_url, key = _get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    try:
        resp = requests.patch(
            f"{base_url}/rest/v1/saved_jobs",
            headers=headers,
            params={"id": f"eq.{job_id}"},
            json={"status": status},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {exc}") from exc
    return {"success": True, "status": status}


@app.get("/saved-jobs")
def get_saved_jobs(user_id: str = Query(...)) -> dict:
    """Get all saved jobs for a user, including internship details and status."""
    base_url, key = _get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(
            f"{base_url}/rest/v1/saved_jobs",
            headers=headers,
            params={
                "select": "id,status,created_at,internship_id,internships(id,title,company,location,link,source,keyword,posted_date)",
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch saved jobs: {exc}") from exc
    data = resp.json()
    return {"items": data if isinstance(data, list) else []}


# ── Phase 3: Enhanced Analytics ──────────────────────────────────

@app.get("/analytics")
def get_analytics() -> dict:
    """Get comprehensive analytics data for charts."""
    base_url, key = _get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(
            f"{base_url}/rest/v1/internships",
            headers=headers,
            params={"select": "source,location,keyword,posted_date,scraped_date", "limit": "2000"},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=f"Analytics query failed: {exc}") from exc

    data = resp.json()
    items = data if isinstance(data, list) else []

    by_source: dict[str, int] = {}
    by_location: dict[str, int] = {}
    by_keyword: dict[str, int] = {}
    by_date: dict[str, int] = {}

    for item in items:
        src = item.get("source") or "Unknown"
        by_source[src] = by_source.get(src, 0) + 1

        loc = item.get("location") or "Unknown"
        loc_clean = loc.split(",")[0].strip() if loc else "Unknown"
        by_location[loc_clean] = by_location.get(loc_clean, 0) + 1

        kw = item.get("keyword") or "general"
        by_keyword[kw] = by_keyword.get(kw, 0) + 1

        sd = (item.get("scraped_date") or "")[:10]
        if sd:
            by_date[sd] = by_date.get(sd, 0) + 1

    # Top 10 locations
    top_locations = dict(sorted(by_location.items(), key=lambda x: x[1], reverse=True)[:10])
    # Top 10 keywords
    top_keywords = dict(sorted(by_keyword.items(), key=lambda x: x[1], reverse=True)[:10])

    return {
        "total": len(items),
        "by_source": by_source,
        "by_location": top_locations,
        "by_keyword": top_keywords,
        "by_date": dict(sorted(by_date.items())),
    }


# ── Phase 4: AI Cover Letter Generator ──────────────────────────

@app.post("/generate-cover-letter")
def generate_cover_letter(payload: dict) -> dict:
    """Generate a tailored cover letter using Gemini AI with resume-aware personalization."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")

    title = payload.get("title", "")
    company = payload.get("company", "")
    location = payload.get("location", "")
    user_name = payload.get("user_name", "Applicant")
    user_skills = payload.get("user_skills", "")  # This is now the full resume text

    # Build a smart, resume-aware prompt
    if user_skills and len(user_skills.strip()) > 50:
        # Full resume provided — deep personalization mode
        resume_section = f"""
=== APPLICANT'S FULL RESUME / CV ===
{user_skills}
=== END RESUME ===
"""
        personalization_instructions = """
CRITICAL PERSONALIZATION RULES:
- You MUST read the resume above carefully and extract SPECIFIC projects, skills, coursework, and experiences that are directly relevant to this particular job.
- Reference at least 2-3 specific items from the resume (project names, technologies used, achievements, relevant coursework).
- Connect EACH mentioned experience directly to what this company/role likely needs.
- Do NOT use generic phrases. Every sentence should feel like it was written by a human who knows both the applicant and the company.
- Vary sentence structure. Mix short punchy sentences with longer descriptive ones.
- The tone should sound like a confident peer, not a desperate applicant."""
    else:
        # No resume — lighter personalization
        resume_section = f"\nApplicant Background: {user_skills if user_skills else 'Computer Science / Engineering student'}\n"
        personalization_instructions = """
PERSONALIZATION RULES:
- Write a solid, professional cover letter based on the job title and company.
- Use confident, natural language. Avoid filler and cliché phrases."""

    prompt = f"""You are an expert career coach who writes cover letters that actually get interviews.
Write a cover letter for the following position. Make it sound like a REAL HUMAN wrote it — not an AI.

=== JOB DETAILS ===
Position: {title}
Company: {company}
Location: {location}
Applicant Name: {user_name}
{resume_section}
{personalization_instructions}

FORMATTING & STYLE RULES:
- Length: 200-300 words (concise and impactful, no fluff)
- Start with "Dear {company} Hiring Team," (or a specific team name if inferrable from the role)
- End with "Sincerely,\\n{user_name}"
- Do NOT use placeholder brackets like [Your Name], [University], etc. — use actual info from the resume or leave it out
- Do NOT use these overused AI words: "delve", "testament", "passion", "landscape", "tapestry", "synergy", "leverage", "foster", "beacon", "moreover", "furthermore", "pivotal"
- Write in first person, active voice
- Each paragraph should have a DIFFERENT focus (don't repeat points)
- Paragraph 1: Hook — why this specific role at this specific company excites you (be specific, not generic)
- Paragraph 2: Your strongest relevant experience/project mapped to what the role needs
- Paragraph 3: A second relevant experience or skill + what you'll bring to the team
- Paragraph 4: Brief, confident closing — express enthusiasm for next steps
- No generic sign-offs like "I look forward to the opportunity to discuss my qualifications further"

OUTPUT: Return ONLY the cover letter text, no extra commentary or markdown formatting."""

    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        )
        resp = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        text = result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        logger.error(f"Gemini API error: {exc}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {exc}") from exc

    return {"cover_letter": text}


# ── Phase 6: Email Alerts via Resend ─────────────────────────────

@app.post("/send-alert-email")
def send_alert_email(payload: dict) -> dict:
    """Send an email alert about new matching internships."""
    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    if not resend_key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY is not configured")

    to_email = payload.get("to", "")
    subject = payload.get("subject", "InternRadar — New Internship Matches!")
    html_body = payload.get("html", "")

    if not to_email or not html_body:
        raise HTTPException(status_code=400, detail="'to' and 'html' fields are required")

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": "InternRadar <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            },
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error(f"Resend API error: {exc}")
        raise HTTPException(status_code=500, detail=f"Email sending failed: {exc}") from exc

    return {"success": True, "message": f"Email sent to {to_email}"}