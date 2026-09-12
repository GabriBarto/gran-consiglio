"""
Email sending layer.

Falls back to a console "mock" sender (just logs what would be sent) unless
SMTP_HOST is configured, so the API is fully runnable end-to-end without any
real mail provider. To send real email, either:
  - set SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD in .env and keep using
    send_email() as-is (plain smtplib), or
  - swap send_email()'s body for fastapi-mail's FastMail().send_message(...)
    if you'd rather use its templating/attachments support.
Nothing else in the app needs to change either way.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from .config import settings

logger = logging.getLogger("toogood.email")


def send_email(*, to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        # Mock backend: no SMTP configured, just log so the flow is
        # testable end-to-end without a real mail provider.
        logger.info("[MOCK EMAIL] To: %s | Subject: %s\n%s", to, subject, body)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


def send_verification_email(*, to: str, token: str, otp: str) -> None:
    link = f"{settings.frontend_base_url}/verify-email?token={token}"
    send_email(
        to=to,
        subject="Conferma la tua email — Gran Consiglio",
        body=(
            "Benvenuto su Gran Consiglio!\n\n"
            f"Conferma il tuo indirizzo email aprendo questo link:\n{link}\n\n"
            f"In alternativa inserisci questo codice nell'app: {otp}\n\n"
            f"Il link/codice scade tra {settings.email_verification_expire_minutes} minuti."
        ),
    )


def send_password_reset_email(*, to: str, token: str) -> None:
    link = f"{settings.frontend_base_url}/reset-password?token={token}"
    send_email(
        to=to,
        subject="Reimposta la tua password — Gran Consiglio",
        body=(
            "Hai richiesto di reimpostare la password del tuo account.\n\n"
            f"Apri questo link per sceglierne una nuova:\n{link}\n\n"
            "Se non sei stato tu, ignora pure questa email: la tua password "
            "attuale resta valida.\n\n"
            f"Il link scade tra {settings.password_reset_expire_minutes} minuti."
        ),
    )
