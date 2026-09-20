from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from backend.models import Internship

logger = logging.getLogger(__name__)


class DailyEmailNotifier:
    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        sender: str = "",
        recipients: list[str] | None = None,
        resend_api_key: str = "",
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender = sender or "InternRadar <onboarding@resend.dev>"
        self.recipients = recipients or []
        self.resend_api_key = resend_api_key or os.getenv("RESEND_API_KEY", "").strip()
        self.use_tls = use_tls

    @staticmethod
    def _build_text_body(
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

    @staticmethod
    def _build_html_body(
        new_items: list[Internship], total_filtered: int, total_scraped: int
    ) -> str:
        now = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

        cards_html = ""
        for item in new_items[:30]:
            cards_html += f"""
            <div style="background:#0f294d; border:1px solid #1e3a5f; border-radius:8px; padding:16px; margin-bottom:14px;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="background:#3b82f6; color:#ffffff; font-size:11px; font-weight:700; padding:3px 8px; border-radius:4px; text-transform:uppercase;">{item.source}</span>
                <span style="color:#94a3b8; font-size:12px;">{item.posted_date or 'Recent'}</span>
              </div>
              <h3 style="margin:0 0 4px 0; color:#f8fafc; font-size:16px; font-weight:600;">{item.title}</h3>
              <p style="margin:0 0 8px 0; color:#60a5fa; font-size:13px; font-weight:500;">{item.company} &bull; <span style="color:#cbd5e1;">{item.location}</span></p>
              {f'<p style="margin:0 0 12px 0; color:#94a3b8; font-size:12px;">Tag: {item.keyword}</p>' if item.keyword else ''}
              <a href="{item.normalized_link()}" target="_blank" style="display:inline-block; background:#3b82f6; color:#ffffff; text-decoration:none; padding:7px 14px; border-radius:5px; font-size:12px; font-weight:600;">Apply / View Details &rarr;</a>
            </div>
            """

        if not new_items:
            cards_html = """
            <div style="text-align:center; padding:30px; background:#0f294d; border-radius:8px; color:#94a3b8;">
              <p style="font-size:15px; margin:0;">No new postings matched your filters today. We'll check again on the next run!</p>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="margin:0; padding:20px; background:#071326; font-family:'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#f8fafc;">
          <div style="max-width:620px; margin:0 auto; background:#0b1d3a; border:1px solid #1e3a5f; border-radius:10px; padding:24px; box-shadow:0 10px 25px rgba(0,0,0,0.5);">
            
            <div style="border-bottom:1px solid #1e3a5f; padding-bottom:16px; margin-bottom:20px;">
              <span style="font-size:11px; letter-spacing:1px; color:#3b82f6; font-weight:700; text-transform:uppercase;">INTERNRADAR INTELLIGENCE</span>
              <h1 style="margin:6px 0 4px 0; color:#f8fafc; font-size:22px;">Daily Internship Digest</h1>
              <p style="margin:0; color:#94a3b8; font-size:13px;">Generated on {now}</p>
            </div>

            <div style="display:flex; gap:10px; margin-bottom:24px;">
              <div style="flex:1; background:#071326; border:1px solid #1e3a5f; border-radius:6px; padding:10px; text-align:center;">
                <div style="font-size:11px; color:#94a3b8;">TOTAL SCRAPED</div>
                <div style="font-size:18px; font-weight:700; color:#60a5fa;">{total_scraped}</div>
              </div>
              <div style="flex:1; background:#071326; border:1px solid #1e3a5f; border-radius:6px; padding:10px; text-align:center;">
                <div style="font-size:11px; color:#94a3b8;">KEYWORD MATCH</div>
                <div style="font-size:18px; font-weight:700; color:#34d399;">{total_filtered}</div>
              </div>
              <div style="flex:1; background:#071326; border:1px solid #1e3a5f; border-radius:6px; padding:10px; text-align:center;">
                <div style="font-size:11px; color:#94a3b8;">NEW OPPORTUNITIES</div>
                <div style="font-size:18px; font-weight:700; color:#fbbf24;">{len(new_items)}</div>
              </div>
            </div>

            <div style="margin-bottom:20px;">
              <h2 style="font-size:15px; text-transform:uppercase; letter-spacing:0.5px; color:#94a3b8; margin-bottom:12px;">Curated Matches For You:</h2>
              {cards_html}
            </div>

            <div style="border-top:1px solid #1e3a5f; padding-top:16px; text-align:center; color:#64748b; font-size:12px;">
              <p style="margin:0 0 6px 0;">InternRadar — Automated Global Career Node</p>
              <p style="margin:0;"><a href="https://internrader.netlify.app" style="color:#3b82f6; text-decoration:none;">Open Web Dashboard</a></p>
            </div>

          </div>
        </body>
        </html>
        """
        return html

    def send_digest(
        self, new_items: list[Internship], total_filtered: int, total_scraped: int
    ) -> None:
        if not self.recipients:
            logger.warning("No email recipients configured, skipping digest")
            return

        subject = f"InternRadar Daily Digest ({len(new_items)} new opportunities)"
        text_body = self._build_text_body(new_items, total_filtered, total_scraped)
        html_body = self._build_html_body(new_items, total_filtered, total_scraped)

        # 1. Try Resend API first if key is present
        if self.resend_api_key:
            try:
                logger.info("Sending digest email via Resend API to %s", self.recipients)
                resp = requests.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": self.sender,
                        "to": self.recipients,
                        "subject": subject,
                        "html": html_body,
                        "text": text_body,
                    },
                    timeout=20,
                )
                if resp.status_code in (200, 201):
                    logger.info("Digest successfully sent via Resend API!")
                    return
                logger.warning("Resend returned error %s: %s", resp.status_code, resp.text)
            except Exception as exc:
                logger.warning("Resend API delivery failed: %s", exc)

        # 2. Fallback to standard SMTP
        if self.smtp_host and self.username and self.password:
            try:
                logger.info("Sending digest email via SMTP (%s:%s)", self.smtp_host, self.smtp_port)
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self.sender
                msg["To"] = ", ".join(self.recipients)

                msg.attach(MIMEText(text_body, "plain"))
                msg.attach(MIMEText(html_body, "html"))

                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    if self.use_tls:
                        server.starttls()
                    server.login(self.username, self.password)
                    server.sendmail(self.sender, self.recipients, msg.as_string())
                logger.info("Digest successfully sent via SMTP!")
                return
            except Exception as exc:
                logger.warning("SMTP delivery failed: %s", exc)

        logger.warning("Neither Resend nor SMTP could successfully send the digest email.")
