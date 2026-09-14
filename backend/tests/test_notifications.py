"""
Tests for in-app notification history + push device registration
(routers/notifications.py) against the real (test) MySQL database: the
order-state-machine triggers (routers/orders.py, app/order_events.py) that
actually populate `notification`, reading/marking them via the API, and
push-token register/unregister.

Run from the backend/ directory with: pytest (conftest.py points this at a
dedicated toogood_test database, reloaded fresh from
backend/db/projectwork_en_v2.sql before the session starts).
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app).__enter__()

VALID_LICENSE_FILE = {"license_file": ("lic.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")}


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _new_customer(email: str, username: str) -> str:
    r = client.post(
        "/auth/register/customer",
        json={"email": email, "username": username, "password": "Password123", "password_confirm": "Password123"},
    )
    assert r.status_code == 201, r.text
    login = client.post("/auth/login", json={"email": email, "password": "Password123"})
    return login.json()["access_token"]


def _admin_token() -> str:
    r = client.post("/auth/login", json={"email": "admin@example.com", "password": "Password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _new_approved_vendor_with_box(
    email: str, username: str, *, max_boxes: int = 5, price: float = 4.99
) -> tuple[str, str, str]:
    """Registers a vendor, approves their shop, and adds one box. Returns
    (vendor_token, shop_id, box_id)."""
    token = _new_customer(email, username)
    up = client.post(
        "/users/me/upgrade-to-vendor",
        headers=_auth_headers(token),
        data={"phone": "+39 333 1230000", "shop_address": "Via Test 1, Pisa"},
        files=VALID_LICENSE_FILE,
    )
    assert up.status_code == 200, up.text

    shop_id = client.get("/shops/me", headers=_auth_headers(token)).json()["id"]

    admin_token = _admin_token()
    approve = client.patch(
        f"/admin/shops/{shop_id}/license-status", json={"status": "approved"}, headers=_auth_headers(admin_token)
    )
    assert approve.status_code == 200, approve.text

    box = client.post(
        "/shops/me/boxes",
        json={
            "name": "Box Test",
            "price": price,
            "description": "Box di prova",
            "category": "Varie",
            "allergens": "Nessuno",
            "max_boxes": max_boxes,
            "pickup_window_start": "18:00",
            "pickup_window_end": "19:00",
            "expire_at": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
        },
        headers=_auth_headers(token),
    )
    assert box.status_code == 201, box.text
    return token, shop_id, box.json()["id"]


# ---------------------------------------------------------------------------
# Order state machine triggers -> notification history
# ---------------------------------------------------------------------------

def test_new_order_notifies_the_vendor():
    vendor_token, shop_id, box_id = _new_approved_vendor_with_box("vendor.notif1@example.com", "Vendor Notif One")
    customer_token = _new_customer("customer.notif1@example.com", "Customer Notif One")

    before = client.get("/notifications", headers=_auth_headers(vendor_token)).json()
    assert before == []

    client.post(
        f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 1}, headers=_auth_headers(customer_token)
    )
    order = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token)).json()

    after = client.get("/notifications", headers=_auth_headers(vendor_token)).json()
    assert len(after) == 1
    assert after[0]["is_read"] is False
    assert f"#{order['id']}" in after[0]["text"]
    assert "Nuovo ordine" in after[0]["text"]


def test_order_lifecycle_notifies_the_customer_with_the_right_types():
    vendor_token, shop_id, box_id = _new_approved_vendor_with_box("vendor.notif2@example.com", "Vendor Notif Two")
    customer_token = _new_customer("customer.notif2@example.com", "Customer Notif Two")

    client.post(
        f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 1}, headers=_auth_headers(customer_token)
    )
    order = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token)).json()

    # Still pendingPayment: no notification of its own yet for the customer.
    assert client.get("/notifications", headers=_auth_headers(customer_token)).json() == []

    client.post(f"/orders/{order['id']}/pay", headers=_auth_headers(customer_token))
    client.patch(
        f"/shops/me/orders/{order['id']}", json={"state": "readyForPickup"}, headers=_auth_headers(vendor_token)
    )
    client.patch(f"/shops/me/orders/{order['id']}", json={"state": "pickedUp"}, headers=_auth_headers(vendor_token))

    notifications = client.get("/notifications", headers=_auth_headers(customer_token)).json()
    types = [n["type"] for n in notifications]
    # Newest first (Repository.list_notifications orders by date desc).
    assert types == ["reviewRequest", "pickupReminder", "orderConfirmed"]
    assert all(n["is_read"] is False for n in notifications)


def test_mark_notification_read_and_read_all():
    vendor_token, shop_id, box_id = _new_approved_vendor_with_box("vendor.notif3@example.com", "Vendor Notif Three")
    customer_token = _new_customer("customer.notif3@example.com", "Customer Notif Three")
    client.post(
        f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 1}, headers=_auth_headers(customer_token)
    )
    order = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token)).json()
    client.post(f"/orders/{order['id']}/pay", headers=_auth_headers(customer_token))
    client.patch(
        f"/shops/me/orders/{order['id']}", json={"state": "readyForPickup"}, headers=_auth_headers(vendor_token)
    )

    notifications = client.get("/notifications", headers=_auth_headers(customer_token)).json()
    assert len(notifications) == 2

    mark_one = client.post(
        f"/notifications/{notifications[0]['id']}/read", headers=_auth_headers(customer_token)
    )
    assert mark_one.status_code == 200, mark_one.text
    assert mark_one.json()["is_read"] is True

    after_one = client.get("/notifications", headers=_auth_headers(customer_token)).json()
    read_flags = {n["id"]: n["is_read"] for n in after_one}
    assert read_flags[notifications[0]["id"]] is True
    assert read_flags[notifications[1]["id"]] is False

    read_all = client.post("/notifications/read-all", headers=_auth_headers(customer_token))
    assert read_all.status_code == 204

    after_all = client.get("/notifications", headers=_auth_headers(customer_token)).json()
    assert all(n["is_read"] for n in after_all)


def test_cannot_mark_someone_elses_notification_read():
    vendor_token, shop_id, box_id = _new_approved_vendor_with_box("vendor.notif4@example.com", "Vendor Notif Four")
    customer_a = _new_customer("customer.notif4a@example.com", "Customer Notif Four A")
    customer_b = _new_customer("customer.notif4b@example.com", "Customer Notif Four B")

    client.post(f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 1}, headers=_auth_headers(customer_a))
    order = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_a)).json()
    client.post(f"/orders/{order['id']}/pay", headers=_auth_headers(customer_a))

    mine = client.get("/notifications", headers=_auth_headers(customer_a)).json()
    assert len(mine) == 1

    hijack = client.post(f"/notifications/{mine[0]['id']}/read", headers=_auth_headers(customer_b))
    assert hijack.status_code == 404

    # customer_b's own read-all never touches customer_a's notification.
    client.post("/notifications/read-all", headers=_auth_headers(customer_b))
    still_unread = client.get("/notifications", headers=_auth_headers(customer_a)).json()
    assert still_unread[0]["is_read"] is False


# ---------------------------------------------------------------------------
# Push device registration
# ---------------------------------------------------------------------------

def test_register_and_unregister_push_token():
    customer_token = _new_customer("customer.notif5@example.com", "Customer Notif Five")

    register = client.post(
        "/users/me/push-tokens",
        json={"token": "fcm-token-abc123", "platform": "android"},
        headers=_auth_headers(customer_token),
    )
    assert register.status_code == 204, register.text

    # Re-registering the same token (e.g. app relaunch) is idempotent, not
    # an error — and moving it to a different account is allowed too (the
    # token belongs to whichever account is currently signed in on that
    # device, see Repository.register_push_token).
    other_customer_token = _new_customer("customer.notif5b@example.com", "Customer Notif Five B")
    re_register = client.post(
        "/users/me/push-tokens",
        json={"token": "fcm-token-abc123", "platform": "android"},
        headers=_auth_headers(other_customer_token),
    )
    assert re_register.status_code == 204, re_register.text

    unregister = client.delete(
        "/users/me/push-tokens/fcm-token-abc123", headers=_auth_headers(customer_token)
    )
    assert unregister.status_code == 204

    # Unregistering an unknown/already-removed token is still a clean 204,
    # not an error.
    unregister_again = client.delete(
        "/users/me/push-tokens/fcm-token-abc123", headers=_auth_headers(customer_token)
    )
    assert unregister_again.status_code == 204


def test_push_token_requires_valid_platform():
    customer_token = _new_customer("customer.notif6@example.com", "Customer Notif Six")
    bad = client.post(
        "/users/me/push-tokens",
        json={"token": "fcm-token-xyz", "platform": "windows-phone"},
        headers=_auth_headers(customer_token),
    )
    assert bad.status_code == 422
