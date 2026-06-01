from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def fetch_html(
    session: requests.Session,
    url: str,
    params: dict[str, str] | None = None,
    timeout: int = 30,
) -> str | None:
    try:
        logger.info(f"Fetching: {url} with params: {params}")
        response = session.get(url, params=params, timeout=timeout)
        logger.info(f"Response status: {response.status_code} for {url}")
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        logger.warning("Request failed for %s: %s", url, exc)
        return None
