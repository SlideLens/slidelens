"""SMTP email delivery with Jinja2 templates."""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
from uuid import UUID

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict, SecretStr

from app.config import Settings

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates" / "email"


class OutboxMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    to: str
    subject: str
    html: str


class EmailService:
    """Sends report-ready mail; uses outbox when SMTP is unset (MVP: no verify mail)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.outbox: list[OutboxMessage] = []

    @property
    def smtp_enabled(self) -> bool:
        return bool(self._settings.smtp_host)

    async def send_report_ready(
        self,
        to: str,
        review_id: UUID,
        score: int,
        *,
        report_url: str | None = None,
    ) -> None:
        base = self._settings.public_app_url.rstrip("/")
        url = report_url or f"{base}/reviews/{review_id}"
        html = self._env.get_template("report_ready.html").render(
            report_url=url,
            score=score,
            review_id=str(review_id),
            app_name=self._settings.app_name,
        )
        await self._send(to=to, subject=f"Разбор готов — Скор {score}", html=html)

    async def _send(self, *, to: str, subject: str, html: str) -> None:
        if not self.smtp_enabled:
            self.outbox.append(OutboxMessage(to=to, subject=subject, html=html))
            return

        message = EmailMessage()
        message["From"] = self._settings.smtp_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content("Откройте HTML-версию письма.")
        message.add_alternative(html, subtype="html")

        password = self._settings.smtp_password
        await aiosmtplib.send(
            message,
            hostname=self._settings.smtp_host,
            port=self._settings.smtp_port,
            username=self._settings.smtp_user or None,
            password=_secret(password) if password else None,
            start_tls=True,
        )


def _secret(value: SecretStr | None) -> str | None:
    return value.get_secret_value() if value is not None else None
