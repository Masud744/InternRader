from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from backend.http_utils import build_session, fetch_html
from backend.models import Internship

logger = logging.getLogger(__name__)


def _safe_text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _slugify(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


def _safe_attr(node: Any, attr_name: str) -> str:
    if not node:
        return ""
    value = node.get(attr_name)
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _dedupe(items: Iterable[Internship]) -> list[Internship]:
    unique: dict[str, Internship] = {}
    for item in items:
        key = item.normalized_link() or item.link
        if key and key not in unique:
            unique[key] = item
    return list(unique.values())


def scrape_linkedin(search_terms: list[str], max_results_per_term: int) -> list[Internship]:
    session = build_session()
    results: list[Internship] = []
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    for term in search_terms:
        html = fetch_html(session, url, params={"keywords": term, "start": "0"})
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("li")
        for card in cards[:max_results_per_term]:
            link_tag = card.select_one("a.base-card__full-link")
            if not link_tag:
                continue

            title = _safe_text(card.select_one("h3.base-search-card__title"))
            company = _safe_text(card.select_one("h4.base-search-card__subtitle"))
            location = _safe_text(card.select_one("span.job-search-card__location"))
            posted_date = ""
            time_tag = card.select_one("time")
            if time_tag:
                posted_date = _safe_attr(time_tag, "datetime") or _safe_text(time_tag)
            link = _safe_attr(link_tag, "href").strip()

            if not title or not link:
                continue

            results.append(
                Internship(
                    title=title,
                    company=company or "Unknown",
                    location=location or "Unknown",
                    link=link,
                    source="LinkedIn",
                    posted_date=posted_date,
                )
            )

    return _dedupe(results)


def scrape_indeed(search_terms: list[str], max_results_per_term: int) -> list[Internship]:
    session = build_session()
    results: list[Internship] = []
    base_url = "https://www.indeed.com/jobs"

    for term in search_terms:
        html = fetch_html(
            session,
            base_url,
            params={"q": f"{term} internship", "sort": "date"},
        )
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("div.job_seen_beacon")
        for card in cards[:max_results_per_term]:
            link_tag = card.select_one("a.jcs-JobTitle")
            if not link_tag:
                continue

            link = urljoin("https://www.indeed.com", _safe_attr(link_tag, "href"))
            title = _safe_text(link_tag)
            company = _safe_text(card.select_one("span[data-testid='company-name']"))
            location = _safe_text(card.select_one("div[data-testid='text-location']"))
            posted_date = _safe_text(card.select_one("span.date"))
            description = _safe_text(card.select_one("div.job-snippet"))

            if not title or not link:
                continue

            results.append(
                Internship(
                    title=title,
                    company=company or "Unknown",
                    location=location or "Unknown",
                    link=link,
                    source="Indeed",
                    posted_date=posted_date,
                    description=description,
                )
            )

    return _dedupe(results)


def scrape_internshala(
    search_terms: list[str], max_results_per_term: int
) -> list[Internship]:
    session = build_session()
    results: list[Internship] = []

    for term in search_terms:
        slug = _slugify(term)
        url = f"https://internshala.com/internships/keywords-{quote_plus(slug)}/"
        html = fetch_html(session, url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("div.individual_internship")
        for card in cards[:max_results_per_term]:
            link_tag = card.select_one("a.job-title-href")
            if not link_tag:
                continue

            title = _safe_text(card.select_one("h3.job-internship-name"))
            company = _safe_text(card.select_one("p.company-name"))
            locations = [
                _safe_text(node)
                for node in card.select("div.row-1-item.locations a, div.row-1-item.locations span")
                if _safe_text(node)
            ]
            location = ", ".join(dict.fromkeys(locations))
            posted_date = _safe_text(card.select_one("div.status-success"))
            link = urljoin("https://internshala.com", _safe_attr(link_tag, "href"))
            description = _safe_text(card.select_one("div.internship_other_details_container"))

            if not title or not link:
                continue

            results.append(
                Internship(
                    title=title,
                    company=company or "Unknown",
                    location=location or "Remote/Not listed",
                    link=link,
                    source="Internshala",
                    posted_date=posted_date,
                    description=description,
                )
            )

    return _dedupe(results)


def scrape_bdjobs(search_terms: list[str], max_results_per_term: int) -> list[Internship]:
    session = build_session()
    results: list[Internship] = []

    for term in search_terms:
        html = fetch_html(
            session,
            "https://jobs.bdjobs.com/jobsearch.asp",
            params={"txtKeyword": term},
        )
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("div.norm-jobs-wrapper, div.sout-jobs-wrapper, div.job-item")
        for card in cards[:max_results_per_term]:
            link_tag = card.select_one("a")
            if not link_tag:
                continue

            title = _safe_text(link_tag)
            company = _safe_text(card.select_one("h4, .comp-name, .cname"))
            location = _safe_text(card.select_one(".locon, .location, .jloc"))
            posted_date = _safe_text(card.select_one(".deadline, .date, .post-date"))
            link = urljoin("https://jobs.bdjobs.com/", _safe_attr(link_tag, "href"))

            if not title or not link:
                continue

            results.append(
                Internship(
                    title=title,
                    company=company or "Unknown",
                    location=location or "Bangladesh",
                    link=link,
                    source="BDJobs",
                    posted_date=posted_date,
                )
            )

    return _dedupe(results)


def scrape_all_sources(
    search_terms: list[str], max_results_per_source: int = 30
) -> list[Internship]:
    source_functions = [
        scrape_linkedin,
        scrape_indeed,
        scrape_internshala,
        scrape_bdjobs,
    ]

    all_items: list[Internship] = []
    for scrape_function in source_functions:
        source_name = scrape_function.__name__.replace("scrape_", "").title()
        try:
            items = scrape_function(search_terms, max_results_per_source)
            logger.info("%s returned %s postings", source_name, len(items))
            if items:
                logger.info("  Sample: %s", items[0].title[:50] if items else "None")
            all_items.extend(items)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("%s failed: %s", source_name, exc)

    deduped = _dedupe(all_items)
    logger.info("Total unique postings across sources: %s", len(deduped))
    return deduped
