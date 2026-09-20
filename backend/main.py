from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(title="InternRadar API", version="0.2.0")

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
    exc_str = str(exc)
    if "Failed to resolve" in exc_str or "Name or service not known" in exc_str:
        detail += " | [IMPORTANT]: Supabase domain not resolving. If on Supabase free tier, your project is likely PAUSED due to inactivity. Please open https://supabase.com/dashboard and click 'Restore' or verify SUPABASE_URL in .env."
    response = getattr(exc, "response", None)
    if response is not None:
        snippet = response.text[:200].replace("\n", " ")
        detail += f" | Status: {response.status_code} | Response: {snippet}"
        if response.status_code >= 520:
            detail += " | Supabase origin appears down or blocked. Check project status and URL."
    return detail


# ── AI Helper (Groq Primary with Gemini Fallback) ─────────────────

def _call_groq(prompt: str, system_prompt: str = "") -> str:
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        raise ValueError("GROQ_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json",
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    models_to_try = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
    last_err = None
    for model in models_to_try:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages},
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"].get("content", "")
                if content:
                    return content.strip()
            last_err = f"Status {resp.status_code}: {resp.text[:150]}"
        except Exception as exc:
            last_err = str(exc)

    raise RuntimeError(f"Groq API call failed across models: {last_err}")


def _call_gemini(prompt: str) -> str:
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    last_err = None
    for model in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            resp = requests.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=25,
            )
            if resp.status_code == 200:
                result = resp.json()
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
            last_err = f"Status {resp.status_code}: {resp.text[:150]}"
        except Exception as exc:
            last_err = str(exc)

    raise RuntimeError(f"Gemini API call failed: {last_err}")


def _call_ai(prompt: str, system_prompt: str = "") -> str:
    """Tries Groq first (lightning fast), falls back to Gemini."""
    if os.getenv("GROQ_API_KEY", "").strip():
        try:
            return _call_groq(prompt, system_prompt)
        except Exception as exc:
            logger.warning("Groq AI failed, falling back to Gemini: %s", exc)

    if os.getenv("GEMINI_API_KEY", "").strip():
        return _call_gemini(f"{system_prompt}\n\n{prompt}" if system_prompt else prompt)

    raise HTTPException(status_code=500, detail="Neither GROQ_API_KEY nor GEMINI_API_KEY is configured")


# ── Health & Internships Endpoints ────────────────────────────────

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

    params: dict[str, str] = {
        "select": "id,title,company,location,link,source,keyword,posted_date,scraped_date",
        "limit": str(limit),
        "offset": str(offset),
    }

    if source_in:
        sources = [s.strip() for s in source_in.split(",") if s.strip()]
        if sources:
            params["source"] = f"in.({','.join(sources)})"
    elif source:
        params["source"] = f"eq.{source.strip()}"

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

    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Accept": "application/json",
        "Prefer": "count=exact",
    }

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

    # Parse total count from Content-Range header (e.g. 0-19/450)
    total_count = 0
    content_range = response.headers.get("Content-Range", "")
    if "/" in content_range:
        try:
            total_count = int(content_range.split("/")[-1])
        except (ValueError, IndexError):
            total_count = 0

    try:
        data = response.json()
    except ValueError as exc:
        snippet = response.text[:200].replace("\n", " ")
        raise HTTPException(
            status_code=502,
            detail=f"Supabase returned non-JSON response: {snippet}",
        ) from exc

    items = data if isinstance(data, list) else []
    if total_count == 0 and items:
        total_count = len(items)

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
            params={"select": "source", "limit": "2000"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("Failed to fetch dynamic sources: %s", exc)
        data = []

    items = data if isinstance(data, list) else []
    db_sources = set(item.get("source", "") for item in items if item.get("source"))
    all_sources = sorted(list(db_sources.union({"LinkedIn", "Internshala", "BDJobs", "RemoteOK", "Arbeitnow"})))
    return {"sources": all_sources}


@app.get("/internships/stats")
def get_stats() -> dict[str, object]:
    base_url, service_role_key = _get_supabase_config()

    try:
        response = requests.get(
            f"{base_url}/rest/v1/internships",
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Prefer": "count=exact",
            },
            params={"select": "source", "limit": "2000"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {exc}") from exc

    items = data if isinstance(data, list) else []
    source_counts: dict[str, int] = {}
    for item in items:
        src = item.get("source") or "Unknown"
        source_counts[src] = source_counts.get(src, 0) + 1

    content_range = response.headers.get("Content-Range", "")
    total = len(items)
    if "/" in content_range:
        try:
            total = int(content_range.split("/")[-1])
        except (ValueError, IndexError):
            pass

    return {
        "total": total,
        "by_source": source_counts,
    }


# ── Saved Jobs & Kanban Endpoints ─────────────────────────────────

@app.get("/saved-jobs")
def get_saved_jobs(user_id: str = Query(...)) -> dict:
    """Get all saved jobs for a user, including internship details, status, and notes."""
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


@app.post("/saved-jobs")
def create_saved_job(payload: dict) -> dict:
    """Save an internship to the user's personal profile / Kanban."""
    user_id = payload.get("user_id")
    internship_id = payload.get("internship_id")
    status = payload.get("status", "Saved")

    if not user_id or not internship_id:
        raise HTTPException(status_code=400, detail="'user_id' and 'internship_id' are required")

    base_url, key = _get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }

    try:
        resp = requests.post(
            f"{base_url}/rest/v1/saved_jobs",
            headers=headers,
            json={"user_id": user_id, "internship_id": internship_id, "status": status},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save job: {exc}") from exc

    return {"success": True, "saved_job": data[0] if isinstance(data, list) and data else {}}


@app.delete("/saved-jobs")
def delete_saved_job_by_query(
    user_id: str = Query(...),
    internship_id: str = Query(...),
) -> dict:
    """Delete a saved job using user_id and internship_id."""
    base_url, key = _get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    try:
        resp = requests.delete(
            f"{base_url}/rest/v1/saved_jobs",
            headers=headers,
            params={"user_id": f"eq.{user_id}", "internship_id": f"eq.{internship_id}"},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete saved job: {exc}") from exc
    return {"success": True}


@app.delete("/saved-jobs/{job_id}")
def delete_saved_job_by_id(job_id: str) -> dict:
    """Delete a saved job using its record id."""
    base_url, key = _get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    try:
        resp = requests.delete(
            f"{base_url}/rest/v1/saved_jobs",
            headers=headers,
            params={"id": f"eq.{job_id}"},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete saved job: {exc}") from exc
    return {"success": True}


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


# ── Phase 3: Analytics ───────────────────────────────────────────

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
        data = resp.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=f"Analytics query failed: {exc}") from exc

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

    top_locations = dict(sorted(by_location.items(), key=lambda x: x[1], reverse=True)[:10])
    top_keywords = dict(sorted(by_keyword.items(), key=lambda x: x[1], reverse=True)[:10])

    return {
        "total": len(items),
        "by_source": by_source,
        "by_location": top_locations,
        "by_keyword": top_keywords,
        "by_date": dict(sorted(by_date.items())),
    }


# ── Groq / Gemini AI Endpoints ───────────────────────────────────

@app.post("/analyze-resume-match")
def analyze_resume_match(payload: dict) -> dict:
    """Analyze fit between applicant resume and internship posting using fast Groq AI."""
    resume_text = payload.get("resume_text", "").strip()
    title = payload.get("title", "Internship")
    company = payload.get("company", "Company")
    description = payload.get("description", "")

    if not resume_text:
        return {
            "success": True,
            "match_score": 50,
            "matching_skills": ["General Background"],
            "missing_skills": ["Resume not provided"],
            "recommendation": "Paste your full resume in the Profile & CV tab to get precise match score and tailored advice!",
        }

    prompt = f"""You are an elite technical career advisor.
Evaluate how well the applicant's resume matches this opportunity.

POSITION: {title}
COMPANY: {company}
JOB DETAILS: {description[:800]}

APPLICANT RESUME:
{resume_text[:2500]}

Return STRICTLY a valid JSON object matching this schema, with no markdown, backticks, or extra text:
{{
  "match_score": <number between 20 and 98 representing qualification fit percentage>,
  "matching_skills": [<array of 3-5 key skills found in both resume and role>],
  "missing_skills": [<array of 2-4 important skills needed for this role that are missing or weak in resume>],
  "recommendation": "<2 concise sentences on what the applicant should highlight or brush up on when applying>"
}}"""

    system_prompt = "You are a JSON-only response engine. Return exclusively valid raw JSON without code blocks or conversational text."
    raw_response = _call_ai(prompt, system_prompt)

    try:
        # Clean any backticks or markdown if present
        clean_json = re.sub(r"^```(json)?", "", raw_response.strip(), flags=re.IGNORECASE)
        clean_json = re.sub(r"```$", "", clean_json.strip()).strip()
        result = json.loads(clean_json)
    except Exception:
        # Fallback structured response
        result = {
            "match_score": 75,
            "matching_skills": ["Technical Foundation", "Relevant Coursework"],
            "missing_skills": ["Specific frameworks mentioned in job post"],
            "recommendation": raw_response[:200] if raw_response else "Highlight your most impactful project on your resume before applying.",
        }

    return {"success": True, **result}


@app.post("/generate-outreach-message")
def generate_outreach_message(payload: dict) -> dict:
    """Generate a high-converting, concise LinkedIn connection note / recruiter DM."""
    title = payload.get("title", "Internship")
    company = payload.get("company", "Company")
    user_name = payload.get("user_name", "Applicant")
    resume_text = payload.get("resume_text", "")

    prompt = f"""Write a high-converting, polite, and punchy 3-4 sentence LinkedIn outreach message from an applicant to a hiring manager/recruiter at {company} regarding the {title} position.

Applicant Name: {user_name}
Background summary: {resume_text[:1000] if resume_text else 'Computer Science / Engineering student'}

RULES:
- Length: 50-75 words max (must fit in LinkedIn 300-char connection request or short InMail)
- Sound genuine, ambitious, and respectful. No generic boilerplate phrases like "I hope this message finds you well"
- Highlight 1 concrete technical skill or project match
- Output ONLY the message text."""

    message = _call_ai(prompt, "You write concise, polite, professional LinkedIn outreach messages.")
    return {"success": True, "outreach_message": message}


@app.post("/generate-cover-letter")
def generate_cover_letter(payload: dict) -> dict:
    """Generate a tailored cover letter using AI with resume-aware personalization."""
    title = payload.get("title", "")
    company = payload.get("company", "")
    location = payload.get("location", "")
    user_name = payload.get("user_name", "Applicant")
    user_skills = payload.get("user_skills", "")

    resume_section = (
        f"=== APPLICANT RESUME ===\n{user_skills}\n=== END RESUME ==="
        if user_skills and len(user_skills.strip()) > 50
        else f"Applicant Background: {user_skills or 'Computer Science / Engineering student'}"
    )

    prompt = f"""You are an expert career coach who writes cover letters that actually get interviews.
Write a concise, compelling cover letter for the following position. Make it sound like a real human wrote it.

Position: {title}
Company: {company}
Location: {location}
Applicant Name: {user_name}
{resume_section}

RULES:
- Length: 200-280 words (concise and impactful)
- Start with "Dear {company} Hiring Team,"
- End with "Sincerely,\n{user_name}"
- Reference 2 specific achievements or skills from the resume that fit this position
- Avoid cliché AI words: "delve", "testament", "passion", "landscape", "tapestry", "synergy", "leverage", "foster"
- Output ONLY the letter text without markdown backticks or extra comments."""

    letter_text = _call_ai(prompt, "You are a professional career coach writing tailored cover letters.")
    return {"cover_letter": letter_text}


# ── Email Alerts via Resend ──────────────────────────────────────

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
        logger.error("Resend API error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Email sending failed: {exc}") from exc

    return {"success": True, "message": f"Email sent to {to_email}"}