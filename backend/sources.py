from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from backend.http_utils import build_session, fetch_html
from backend.models import Internship

logger = logging.getLogger(__name__)


def _safe_text(node: Any) -> str:
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

            title = _safe_text(card.select_one("h3.base-search-card__title")) or _safe_text(link_tag)
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
                    location=location or "Remote/Global",
                    link=link,
                    source="LinkedIn",
                    posted_date=posted_date,
                )
            )

    return _dedupe(results)


def scrape_internshala(search_terms: list[str], max_results_per_term: int) -> list[Internship]:
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

            title = _safe_text(card.select_one("h3.job-internship-name")) or _safe_text(link_tag)
            company = _safe_text(card.select_one("p.company-name"))
            locations = [
                _safe_text(node)
                for node in card.select("div.row-1-item.locations a, div.row-1-item.locations span")
                if _safe_text(node)
            ]
            location = ", ".join(dict.fromkeys(locations)) or "Remote"
            posted_date = _safe_text(card.select_one("div.status-success"))
            link = urljoin("https://internshala.com", _safe_attr(link_tag, "href"))
            description = _safe_text(card.select_one("div.internship_other_details_container"))

            if not title or not link:
                continue

            results.append(
                Internship(
                    title=title,
                    company=company or "Unknown",
                    location=location,
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
    gateway_url = "https://gateway.bdjobs.com/recruitment-account-test/api/JobSearch/GetJobSearch"

    for term in search_terms:
        try:
            resp = session.get(gateway_url, params={"txtKeyword": term}, timeout=15)
            if resp.status_code == 200:
                payload = resp.json()
                items = payload.get("data") if isinstance(payload, dict) else []
                if isinstance(items, list):
                    for item in items[:max_results_per_term]:
                        job_id = item.get("Jobid")
                        title = item.get("jobTitle")
                        company = item.get("companyName")
                        location = item.get("location") or "Bangladesh"
                        posted_date = item.get("publishDate") or item.get("deadline") or ""
                        raw_desc = item.get("jobDescription") or item.get("jobContext") or ""
                        desc_text = re.sub(r"<[^>]+>", " ", str(raw_desc)).strip()

                        if not job_id or not title:
                            continue

                        link = f"https://jobs.bdjobs.com/jobdetails.asp?id={job_id}"
                        results.append(
                            Internship(
                                title=str(title).strip(),
                                company=str(company or "Unknown").strip(),
                                location=str(location).strip(),
                                link=link,
                                source="BDJobs",
                                posted_date=str(posted_date)[:10] if posted_date else "",
                                description=desc_text[:500],
                            )
                        )
                    continue
        except Exception as exc:
            logger.warning("BDJobs Gateway API request failed: %s", exc)

    return _dedupe(results)


def scrape_remoteok(search_terms: list[str], max_results_per_term: int) -> list[Internship]:
    session = build_session()
    results: list[Internship] = []
    tags = ["internship", "junior", "student"]

    for tag in tags:
        try:
            url = f"https://remoteok.com/api?tag={tag}"
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                continue

            data = resp.json()
            if not isinstance(data, list):
                continue

            # First item in RemoteOK API is legal notice
            jobs = [j for j in data if isinstance(j, dict) and j.get("id")]

            for job in jobs[:max_results_per_term]:
                title = job.get("position", "")
                company = job.get("company", "Unknown")
                location = job.get("location") or "Worldwide / Remote"
                link = job.get("url") or job.get("apply_url") or ""
                posted_date = str(job.get("date", ""))[:10]
                description = re.sub(r"<[^>]+>", " ", str(job.get("description", ""))).strip()[:500]

                if not title or not link:
                    continue

                results.append(
                    Internship(
                        title=title,
                        company=company,
                        location=location,
                        link=link,
                        source="RemoteOK",
                        posted_date=posted_date,
                        description=description,
                    )
                )
        except Exception as exc:
            logger.warning("RemoteOK fetch failed for tag %s: %s", tag, exc)

    return _dedupe(results)


def scrape_arbeitnow(search_terms: list[str], max_results_per_term: int) -> list[Internship]:
    session = build_session()
    results: list[Internship] = []

    try:
        url = "https://www.arbeitnow.com/api/job-board-api"
        resp = session.get(url, timeout=15)
        if resp.status_code == 200:
            payload = resp.json()
            jobs = payload.get("data", [])
            for job in jobs:
                title = job.get("title", "")
                company = job.get("company_name", "Unknown")
                location = job.get("location", "Remote")
                link = job.get("url", "")
                tags = [t.lower() for t in job.get("tags", [])]
                is_intern = any(k in title.lower() or k in tags for k in ["intern", "internship", "trainee", "working student", "junior"])
                
                # Check if it matches search terms or is an internship
                matches_term = any(
                    term.lower() in title.lower() or any(term.lower() in t for t in tags)
                    for term in search_terms
                )

                if (is_intern or matches_term) and title and link:
                    raw_desc = job.get("description", "")
                    desc_text = re.sub(r"<[^>]+>", " ", str(raw_desc)).strip()[:500]
                    results.append(
                        Internship(
                            title=title,
                            company=company,
                            location=location,
                            link=link,
                            source="Arbeitnow",
                            posted_date="",
                            description=desc_text,
                        )
                    )
                if len(results) >= max_results_per_term:
                    break
    except Exception as exc:
        logger.warning("Arbeitnow API fetch failed: %s", exc)

    return _dedupe(results)


def scrape_indeed(search_terms: list[str], max_results_per_term: int) -> list[Internship]:
    session = build_session()
    results: list[Internship] = []
    base_url = "https://www.indeed.com/jobs"

    for term in search_terms:
        try:
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
        except Exception as exc:
            logger.warning("Indeed scrape failed: %s", exc)

    return _dedupe(results)


def scrape_all_sources(
    search_terms: list[str], max_results_per_source: int = 30
) -> list[Internship]:
    source_functions = [
        scrape_linkedin,
        scrape_internshala,
        scrape_bdjobs,
        scrape_remoteok,
        scrape_arbeitnow,
        scrape_indeed,
    ]

    all_items: list[Internship] = []
    for scrape_function in source_functions:
        source_name = scrape_function.__name__.replace("scrape_", "").title()
        try:
            items = scrape_function(search_terms, max_results_per_source)
            logger.info("%s returned %s postings", source_name, len(items))
            if items:
                logger.info("  Sample: %s at %s", items[0].title[:40], items[0].company[:30])
            all_items.extend(items)
        except Exception as exc:
            logger.warning("%s failed: %s", source_name, exc)

    deduped = _dedupe(all_items)
    logger.info("Total unique postings across sources: %s", len(deduped))
    return deduped
