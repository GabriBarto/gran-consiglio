"""
Smoke tests covering the main flows end-to-end against the in-memory fake
DB: customer registration -> email verification -> login -> refresh, and
vendor registration with a license upload -> upgrade-to-vendor for an
existing customer.

Run from the backend/ directory with: pytest
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.database import db
from app.main import app

# NOTE: TestClient must be used as a context manager (or __enter__()'d) for
# Starlette to fire the app's lifespan/startup hook — otherwise
# seed_fake_data() never runs and the seeded demo accounts silently don't
# exist. Doesn't affect the tests below (they don't touch seeded users) but
# any future test relying on them needs this.
client = TestClient(app).__enter__()


def _register_customer(email="new.customer@example.com", username="Nuovo Cliente"):
    return client.post(
        "/auth/register/customer",
        json={
            "email": email,
            "username": username,
            "password": "Password123",
            "password_confirm": "Password123",
        },
    )


def test_register_login_and_refresh_flow():
    resp = _register_customer()
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "customer"
    assert body["email_verified"] is False

    # Duplicate email/username is rejected.
    dup = _register_customer()
    assert dup.status_code == 409

    # Verify email via the OTP that was "sent" (captured straight from the
    # in-memory store, since there's no real mailbox in tests).
    user = db.get_by_email("new.customer@example.com")
    otp = db.pending_verifications[user.id]["otp"]
    verify = client.post("/auth/verify-email", json={"email": user.email, "otp": otp})
    assert verify.status_code == 200, verify.text

    login = client.post("/auth/login", json={"email": user.email, "password": "Password123"})
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    me = client.get("/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == user.email

    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text

    # The rotated (old) refresh token can no longer be reused.
    reused = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401


def test_register_vendor_with_license_upload():
    resp = client.post(
        "/auth/register/vendor",
        data={
            "email": "nuovo.venditore@example.com",
            "username": "Nuovo Venditore",
            "password": "Password123",
            "password_confirm": "Password123",
            "phone": "+39 333 0000000",
            "shop_address": "Via Test 1, Roma",
        },
        files={"license_file": ("licenza.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "vendor"
    assert body["license"]["status"] == "pending_review"


def test_forgot_and_reset_password():
    _register_customer(email="reset.me@example.com", username="Reset Me")
    user = db.get_by_email("reset.me@example.com")

    forgot = client.post("/auth/forgot-password", json={"email": user.email})
    assert forgot.status_code == 200

    token = None
    for u_id, pending in db.pending_resets.items():
        if u_id == user.id:
            token = pending["jti"]
    assert token is not None  # a reset was actually recorded

    # Recover the real JWT rather than just its jti, by re-issuing one and
    # overwriting the bookkeeping (keeps the test independent from log
    # capture / email transport).
    from app import security

    jwt_token = security.create_password_reset_token(user.id)
    db.pending_resets[user.id] = {"jti": security.decode_token(jwt_token, expected_purpose="password_reset")["jti"]}

    reset = client.post(
        "/auth/reset-password",
        json={"token": jwt_token, "new_password": "NewPassword123", "new_password_confirm": "NewPassword123"},
    )
    assert reset.status_code == 200, reset.text

    login_old = client.post("/auth/login", json={"email": user.email, "password": "Password123"})
    assert login_old.status_code == 401

    login_new = client.post("/auth/login", json={"email": user.email, "password": "NewPassword123"})
    assert login_new.status_code == 200


def test_upgrade_customer_to_vendor():
    _register_customer(email="upgrade.me@example.com", username="Upgrade Me")
    login = client.post("/auth/login", json={"email": "upgrade.me@example.com", "password": "Password123"})
    token = login.json()["access_token"]

    upgrade = client.post(
        "/users/me/upgrade-to-vendor",
        headers={"Authorization": f"Bearer {token}"},
        data={"phone": "+39 333 1111111", "shop_address": "Via Upgrade 9, Milano"},
        files={"license_file": ("licenza.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )
    assert upgrade.status_code == 200, upgrade.text
    assert upgrade.json()["role"] == "vendor"


def test_seeded_demo_accounts_are_present_and_can_log_in():
    # Guards against the lifespan/seed_fake_data() gotcha noted above: if
    # TestClient ever stops being entered as a context manager, this is the
    # test that would catch it.
    for email in (
        "cliente.demo@example.com",
        "vivaio.rossi@example.com",
        "ortofrutta.bianchi@example.com",
    ):
        resp = client.post("/auth/login", json={"email": email, "password": "Password123"})
        assert resp.status_code == 200, f"{email}: {resp.text}"
