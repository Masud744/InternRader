from __future__ import annotations

from typing import Iterable

import requests

from backend.models import Internship


class InternshipRepository:
    def __init__(
        self,
        supabase_url: str,
        supabase_service_role_key: str,
        table_name: str = "internships",
        timeout: int = 30,
    ) -> None:
        self.base_url = supabase_url.rstrip("/")
        self.api_key = supabase_service_role_key
        self.table_name = table_name
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "apikey": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    @staticmethod
    def _chunks(items: list[Internship], size: int = 100) -> Iterable[list[Internship]]:
        for index in range(0, len(items), size):
            yield items[index : index + size]

    def _insert_chunk(self, items: list[Internship]) -> set[str]:
        payload = [item.as_record() for item in items]
        endpoint = f"{self.base_url}/rest/v1/{self.table_name}"

        try:
            response = self.session.post(
                endpoint,
                params={"on_conflict": "link"},
                headers={"Prefer": "resolution=ignore-duplicates,return=representation"},
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Supabase REST insert failed: {exc}") from exc

        data = response.json()
        if not isinstance(data, list):
            return set()

        inserted_links: set[str] = set()
        for row in data:
            link = str(row.get("link", "")).strip()
            if link:
                inserted_links.add(link)
        return inserted_links

    def insert_new(self, internships: list[Internship]) -> list[Internship]:
        unique: dict[str, Internship] = {}
        for internship in internships:
            key = internship.normalized_link() or internship.link
            if key and key not in unique:
                unique[key] = internship

        deduped_items = list(unique.values())
        if not deduped_items:
            return []

        inserted: list[Internship] = []
        for chunk in self._chunks(deduped_items):
            inserted_links = self._insert_chunk(chunk)
            inserted.extend(
                item for item in chunk if item.normalized_link() in inserted_links
            )
        return inserted
