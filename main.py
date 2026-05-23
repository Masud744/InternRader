from __future__ import annotations

import logging
import importlib.util
import sys
from pathlib import Path

from config import load_settings
from backend.supabase_client import InternshipRepository
from backend.keyword_filter import filter_internships
from backend.sources import scrape_all_sources

PROJECT_ROOT = Path(__file__).resolve().parent
EMAIL_MODULE_DIR = PROJECT_ROOT / "backend"


def _load_email_notifier_class():
    notifier_path = EMAIL_MODULE_DIR / "notifier.py"
    module_name = "internradar_email_notifier"
    spec = importlib.util.spec_from_file_location(module_name, notifier_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load email notifier module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DailyEmailNotifier


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def run_pipeline() -> int:
    configure_logging()
    logger = logging.getLogger("internradar")
    settings = load_settings()

    logger.info("Starting InternRadar daily run")
    scraped_items = scrape_all_sources(
        search_terms=settings.search_terms,
        max_results_per_source=settings.max_results_per_source,
    )
    logger.info("Scraped %s total postings", len(scraped_items))

    filtered_items = filter_internships(scraped_items, settings.keywords)
    logger.info("Filtered down to %s postings by keywords", len(filtered_items))

    new_items = filtered_items
    if settings.dry_run:
        logger.info("DRY_RUN enabled, skipping database insert")
    elif settings.supabase_url and settings.supabase_service_role_key:
        try:
            repository = InternshipRepository(
                supabase_url=settings.supabase_url,
                supabase_service_role_key=settings.supabase_service_role_key,
            )
            new_items = repository.insert_new(filtered_items)
            logger.info("Inserted %s new postings into Supabase", len(new_items))
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Database persistence skipped: %s", exc)
            new_items = filtered_items
    else:
        logger.warning(
            "Supabase is not configured, skipping persistence for this run"
        )

    if settings.smtp_host and settings.email_from and settings.email_to:
        notifier_class = _load_email_notifier_class()
        notifier = notifier_class(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            sender=settings.email_from,
            recipients=settings.email_to,
        )
        if new_items or settings.send_empty_digest:
            notifier.send_digest(
                new_items,
                total_filtered=len(filtered_items),
                total_scraped=len(scraped_items),
            )
            logger.info("Daily digest email sent to %s", ", ".join(settings.email_to))
        else:
            logger.info("No new postings found, digest skipped")
    else:
        logger.warning("SMTP settings are incomplete, skipping email notification")

    logger.info("InternRadar daily run finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_pipeline())
