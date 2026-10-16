"""
Push notification sending via Firebase Cloud Messaging (the `firebase-admin`
library).

Falls back to a console "mock" sender (just logs what would be sent) unless
a Firebase service account is configured, so the API is fully runnable
end-to-end without a real Firebase project — same pattern as
app/email_utils.py. To send real pushes: download a service account key
from the Firebase console (Project settings -> Service accounts ->
Generate new private key) and set FIREBASE_CREDENTIALS_FILE to its path in
.env. Nothing else in the app needs to change either way — see
app/order_events.py, the only caller.

This only gets a message *to* Firebase — actually receiving it on a device
also needs: a real Firebase project with an Android/iOS app registered in
it, that project's `google-services.json` wired into the Expo app (see
app.json), and a development build (Expo Go does not support remote push
from SDK 53 on Android — see src/utils/pushNotifications.js). None of that
is a backend concern.
"""
from __future__ import annotations

import logging

from .config import settings

logger = logging.getLogger("toogood.push")

_app = None
_init_attempted = False


def _get_app():
    """Lazily initializes the firebase-admin app on first real send, so
    importing this module never requires the `firebase-admin` package to
    even be installed correctly (or a project configured) when no push is
    ever actually attempted — same laziness as the mock-by-default SMTP
    path in email_utils.py."""
    global _app, _init_attempted
    if _init_attempted:
        return _app
    _init_attempted = True

    if not settings.firebase_credentials_file:
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(settings.firebase_credentials_file)
        _app = firebase_admin.initialize_app(cred)
    except Exception:
        logger.exception(
            "Inizializzazione Firebase fallita (FIREBASE_CREDENTIALS_FILE=%s) — le push "
            "restano in modalità mock finché non è risolta.",
            settings.firebase_credentials_file,
        )
        _app = None
    return _app


def send_push(*, token: str, title: str, body: str) -> None:
    """Sends one push to one device token. Best-effort: any failure
    (invalid/expired token, Firebase unreachable, ...) is logged and
    swallowed here — see app/order_events.py, which already treats every
    notification trigger as best-effort so one bad device token never
    blocks an order state transition."""
    app = _get_app()
    if not app:
        logger.info("[MOCK PUSH] To: %s... | %s: %s", token[:16], title, body)
        return

    from firebase_admin import messaging

    message = messaging.Message(
        token=token, notification=messaging.Notification(title=title, body=body)
    )
    messaging.send(message, app=app)
