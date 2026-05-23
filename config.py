from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

load_dotenv()

DEFAULT_KEYWORDS = [
    "ai",
    "machine learning",
    "deep learning",
    "computer vision",
    "robotics",
    "iot",
    "embedded",
    "firmware",
    "electronics",
    "python",
    "backend",
    "full stack",
    "api",
    "cloud",
    "devops",
    "edge ai",
    "cybersecurity",
    "data science",
]


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name, "")
    if not value.strip():
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    email_from: str
    email_to: list[str]
    keywords: list[str]
    search_terms: list[str]
    max_results_per_source: int
    send_empty_digest: bool
    dry_run: bool


def load_settings() -> Settings:
    keywords = _csv_env("JOB_KEYWORDS", DEFAULT_KEYWORDS)
    search_terms = _csv_env("SEARCH_TERMS", keywords)

    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        smtp_host=os.getenv("SMTP_HOST", "").strip(),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", "").strip(),
        smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
        email_from=os.getenv("EMAIL_FROM", "").strip(),
        email_to=_csv_env("EMAIL_TO", []),
        keywords=keywords,
        search_terms=search_terms,
        max_results_per_source=int(os.getenv("MAX_RESULTS_PER_SOURCE", "30")),
        send_empty_digest=_bool_env("SEND_EMPTY_DIGEST", default=True),
        dry_run=_bool_env("DRY_RUN", default=False),
    )
