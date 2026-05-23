from __future__ import annotations

from backend.models import Internship


def filter_internships(items: list[Internship], keywords: list[str]) -> list[Internship]:
    normalized_keywords = [keyword.strip().lower() for keyword in keywords if keyword.strip()]
    filtered: list[Internship] = []

    for item in items:
        haystack = " ".join(
            [item.title, item.company, item.location, item.description]
        ).lower()
        matched_keyword = next(
            (keyword for keyword in normalized_keywords if keyword in haystack),
            None,
        )
        if matched_keyword:
            item.keyword = matched_keyword
            filtered.append(item)

    return filtered
