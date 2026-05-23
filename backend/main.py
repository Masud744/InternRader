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