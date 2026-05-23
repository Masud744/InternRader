from __future__ import annotations

import smtplib
from datetime import datetime, timezone

from backend.models import Internship


class DailyEmailNotifier:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        sender: str,
        recipients: list[str],
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender = sender
        self.recipients = recipients
        self.use_tls = use_tls

    @staticmethod
    def _build_body(
        new_items: list[Internship], total_filtered: int, total_scraped: int
    ) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            "InternRadar Daily Internship Digest",
            f"Generated: {now}",
            "",
            f"Total scraped: {total_scraped}",
            f"Keyword-matched: {total_filtered}",
            f"New in database: {len(new_items)}",
            "",
        ]

        if not new_items:
            lines.append("No new internships were found today.")
            return "\n".join(lines)

        lines.append("New opportunities:")
        for index, item in enumerate(new_items, start=1):
            lines.extend(
                [
                    f"{index}. {item.title}",
                    f"   Company: {item.company}",
                    f"   Location: {item.location}",
                    f"   Source: {item.source}",
                    f"   Matched keyword: {item.keyword or 'N/A'}",
                    f"   Posted date: {item.posted_date or 'N/A'}",
                    f"   Link: {item.normalized_link()}",
                    "",
                ]
            )

        return "\n".join(lines).strip()

    def send_digest(
        self, new_items: list[Internship], total_filtered: int, total_scraped: int
    ) -> None:
        subject = f"InternRadar Daily Update ({len(new_items)} new internships)"
        body = self._build_body(new_items, total_filtered, total_scraped)

        message = (
            f"From: {self.sender}\r\n"
            f"To: {', '.join(self.recipients)}\r\n"
            f"Subject: {subject}\r\n"
            "Content-Type: text/plain; charset=UTF-8\r\n"
            "\r\n"
            f"{body}"
        )

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
            if self.use_tls:
                server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            server.sendmail(self.sender, self.recipients, message.encode("utf-8"))
