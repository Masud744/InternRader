from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PREFIXES = ("utm_", "trk", "ref", "src")


def normalize_link(raw_url: str) -> str:
    if not raw_url:
        return ""

    parsed = urlsplit(raw_url.strip())
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not any(key.lower().startswith(prefix) for prefix in TRACKING_PREFIXES)
    ]
    normalized_query = urlencode(filtered_query)

    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme, parsed.netloc, path, normalized_query, ""))


@dataclass
class Internship:
    title: str
    company: str
    location: str
    link: str
    source: str
    posted_date: str | None = None
    description: str = ""
    keyword: str | None = None
    scraped_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def normalized_link(self) -> str:
        return normalize_link(self.link)

    def as_record(self) -> dict[str, str | None]:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "link": self.normalized_link(),
            "source": self.source,
            "keyword": self.keyword,
            "posted_date": self.posted_date,
            "scraped_date": self.scraped_date,
        }
