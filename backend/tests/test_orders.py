"""
Tests for the customer-facing cart -> checkout -> order flow
(routers/cart.py, routers/orders.py) against the real (test) MySQL
database: add/update/remove cart items, checkout into a booked order
(availability re-validated and locked at that point), cancellation
(restocks), the vendor side of marking an order picked up, and RBAC /
ownership isolation on both sides.

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


def _admin_token() -> str:
    r = client.post("/auth/login", json={"email": "admin@example.com", "password": "Password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

def test_cart_add_update_remove():
    _, shop_id, box_id = _new_approved_vendor_with_box("vendor.cart1@example.com", "Vendor Cart One")
    customer_token = _new_customer("customer.cart1@example.com", "Customer Cart One")

    empty = client.get(f"/shops/{shop_id}/cart", headers=_auth_headers(customer_token))
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    add = client.post(
        f"/shops/{shop_id}/cart/items",
        json={"box_id": box_id, "quantity": 2},
        headers=_auth_headers(customer_token),
    )
    assert add.status_code == 201, add.text
    assert add.json()["items"][0]["quantity"] == 2
    assert add.json()["total_price"] == round(4.99 * 2, 2)

    # Adding the same box again accumulates quantity rather than duplicating the line.
    add_again = client.post(
        f"/shops/{shop_id}/cart/items",
        json={"box_id": box_id, "quantity": 1},
        headers=_auth_headers(customer_token),
    )
    assert len(add_again.json()["items"]) == 1
    assert add_again.json()["items"][0]["quantity"] == 3

    update = client.put(
        f"/shops/{shop_id}/cart/items/{box_id}", json={"quantity": 1}, headers=_auth_headers(customer_token)
    )
    assert update.status_code == 200
    assert update.json()["items"][0]["quantity"] == 1

    remove = client.delete(f"/shops/{shop_id}/cart/items/{box_id}", headers=_auth_headers(customer_token))
    assert remove.status_code == 200
    assert remove.json()["items"] == []


def test_cart_requires_shop_to_be_approved():
    token = _new_customer("vendor.cart2@example.com", "Vendor Cart Two")
    up = client.post(
        "/users/me/upgrade-to-vendor",
        headers=_auth_headers(token),
        data={"phone": "+39 333 1230001", "shop_address": "Via Test 2, Pisa"},
        files=VALID_LICENSE_FILE,
    )
    assert up.status_code == 200, up.text
    shop_id = client.get("/shops/me", headers=_auth_headers(token)).json()["id"]  # still pending_review

    customer_token = _new_customer("customer.cart2@example.com", "Customer Cart Two")
    resp = client.get(f"/shops/{shop_id}/cart", headers=_auth_headers(customer_token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

def test_checkout_creates_order_and_updates_availability():
    _, shop_id, box_id = _new_approved_vendor_with_box("vendor.order1@example.com", "Vendor Order One", max_boxes=5)
    customer_token = _new_customer("customer.order1@example.com", "Customer Order One")

    client.post(
        f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 2}, headers=_auth_headers(customer_token)
    )

    checkout = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token))
    assert checkout.status_code == 201, checkout.text
    order = checkout.json()
    assert order["state"] == "booked"
    assert order["total_price"] == round(4.99 * 2, 2)
    assert order["items"][0]["quantity"] == 2
    assert order["pickup_window"] == "18:00-19:00"

    # Cart is emptied (marked completed) after a successful checkout.
    cart_after = client.get(f"/shops/{shop_id}/cart", headers=_auth_headers(customer_token))
    assert cart_after.json()["items"] == []

    # Box availability reflects the sale.
    box_after = client.get(f"/shops/{shop_id}/boxes", headers=_auth_headers(customer_token)).json()
    assert box_after[0]["available"] == 3
    assert box_after[0]["sold_boxes"] == 2

    # It shows up in the customer's own order history and detail view.
    history = client.get("/orders", headers=_auth_headers(customer_token))
    assert history.status_code == 200
    assert len(history.json()) == 1
    detail = client.get(f"/orders/{order['id']}", headers=_auth_headers(customer_token))
    assert detail.status_code == 200


def test_checkout_rejects_when_not_enough_availability():
    _, shop_id, box_id = _new_approved_vendor_with_box("vendor.order2@example.com", "Vendor Order Two", max_boxes=2)
    customer_token = _new_customer("customer.order2@example.com", "Customer Order Two")

    client.post(
        f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 3}, headers=_auth_headers(customer_token)
    )
    checkout = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token))
    assert checkout.status_code == 409

    # Rejected checkout leaves the cart untouched, not partially consumed.
    cart_after = client.get(f"/shops/{shop_id}/cart", headers=_auth_headers(customer_token))
    assert cart_after.json()["items"][0]["quantity"] == 3


def test_checkout_without_a_cart_rejected():
    _, shop_id, _box_id = _new_approved_vendor_with_box("vendor.order3@example.com", "Vendor Order Three")
    customer_token = _new_customer("customer.order3@example.com", "Customer Order Three")

    # Never added anything -> no cart row exists at all yet.
    checkout = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token))
    assert checkout.status_code == 404


def test_checkout_emptied_cart_rejected():
    _, shop_id, box_id = _new_approved_vendor_with_box("vendor.order3b@example.com", "Vendor Order Three B")
    customer_token = _new_customer("customer.order3b@example.com", "Customer Order Three B")

    # A cart row now exists, but ends up with zero items in it.
    client.post(
        f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 1}, headers=_auth_headers(customer_token)
    )
    client.delete(f"/shops/{shop_id}/cart/items/{box_id}", headers=_auth_headers(customer_token))

    checkout = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token))
    assert checkout.status_code == 400


# ---------------------------------------------------------------------------
# Cancellation / pickup
# ---------------------------------------------------------------------------

def test_customer_can_cancel_booked_order_and_stock_is_restored():
    _, shop_id, box_id = _new_approved_vendor_with_box("vendor.order4@example.com", "Vendor Order Four", max_boxes=5)
    customer_token = _new_customer("customer.order4@example.com", "Customer Order Four")

    client.post(
        f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 2}, headers=_auth_headers(customer_token)
    )
    order = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token)).json()

    cancel = client.post(f"/orders/{order['id']}/cancel", headers=_auth_headers(customer_token))
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["state"] == "cancelled"

    box_after = client.get(f"/shops/{shop_id}/boxes", headers=_auth_headers(customer_token)).json()
    assert box_after[0]["available"] == 5  # restocked

    # Cancelling twice is rejected — no longer 'booked'.
    second_cancel = client.post(f"/orders/{order['id']}/cancel", headers=_auth_headers(customer_token))
    assert second_cancel.status_code == 409


def test_vendor_can_mark_order_picked_up():
    vendor_token, shop_id, box_id = _new_approved_vendor_with_box("vendor.order5@example.com", "Vendor Order Five")
    customer_token = _new_customer("customer.order5@example.com", "Customer Order Five")

    client.post(
        f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 1}, headers=_auth_headers(customer_token)
    )
    order = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token)).json()

    listed = client.get("/shops/me/orders", headers=_auth_headers(vendor_token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    picked_up = client.patch(
        f"/shops/me/orders/{order['id']}", json={"state": "pickedUp"}, headers=_auth_headers(vendor_token)
    )
    assert picked_up.status_code == 200, picked_up.text
    assert picked_up.json()["state"] == "pickedUp"


def test_order_state_update_rejects_invalid_target_state():
    vendor_token, shop_id, box_id = _new_approved_vendor_with_box("vendor.order6@example.com", "Vendor Order Six")
    customer_token = _new_customer("customer.order6@example.com", "Customer Order Six")
    client.post(
        f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 1}, headers=_auth_headers(customer_token)
    )
    order = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token)).json()

    bad = client.patch(
        f"/shops/me/orders/{order['id']}", json={"state": "booked"}, headers=_auth_headers(vendor_token)
    )
    assert bad.status_code == 422


# ---------------------------------------------------------------------------
# RBAC / ownership isolation
# ---------------------------------------------------------------------------

def test_customer_cannot_cancel_someone_elses_order():
    _, shop_id, box_id = _new_approved_vendor_with_box("vendor.order7@example.com", "Vendor Order Seven")
    customer_a = _new_customer("customer.order7a@example.com", "Customer Order Seven A")
    customer_b = _new_customer("customer.order7b@example.com", "Customer Order Seven B")

    client.post(f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 1}, headers=_auth_headers(customer_a))
    order = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_a)).json()

    hijack = client.post(f"/orders/{order['id']}/cancel", headers=_auth_headers(customer_b))
    assert hijack.status_code == 404

    peek = client.get(f"/orders/{order['id']}", headers=_auth_headers(customer_b))
    assert peek.status_code == 404


def test_vendor_cannot_manage_another_vendors_order():
    _, shop_id, box_id = _new_approved_vendor_with_box("vendor.order8@example.com", "Vendor Order Eight")
    other_vendor_token, _, _ = _new_approved_vendor_with_box("vendor.order9@example.com", "Vendor Order Nine")
    customer_token = _new_customer("customer.order8@example.com", "Customer Order Eight")

    client.post(
        f"/shops/{shop_id}/cart/items", json={"box_id": box_id, "quantity": 1}, headers=_auth_headers(customer_token)
    )
    order = client.post(f"/shops/{shop_id}/cart/checkout", headers=_auth_headers(customer_token)).json()

    hijack = client.patch(
        f"/shops/me/orders/{order['id']}", json={"state": "pickedUp"}, headers=_auth_headers(other_vendor_token)
    )
    assert hijack.status_code == 404
