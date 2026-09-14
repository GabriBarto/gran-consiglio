"""
Tests for box ("surprise bag") CRUD by the owning vendor, RBAC (only the
shop's own vendor can manage its boxes — a customer or another vendor
can't), validation, and public browsing of a shop's boxes (only ever
visible once the shop itself is admin-approved, same as GET /shops/{id}) —
against the real (test) MySQL database.

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


def _new_vendor(email: str, username: str, *, shop_address: str = "Via Test 1") -> str:
    """Registers+logs in a fresh vendor via upgrade-to-vendor. Returns the
    access token — the vendor already has a placeholder shop afterwards."""
    r = client.post(
        "/auth/register/customer",
        json={"email": email, "username": username, "password": "Password123", "password_confirm": "Password123"},
    )
    assert r.status_code == 201, r.text

    login = client.post("/auth/login", json={"email": email, "password": "Password123"})
    token = login.json()["access_token"]

    up = client.post(
        "/users/me/upgrade-to-vendor",
        headers=_auth_headers(token),
        data={"phone": "+39 333 1230000", "shop_address": shop_address},
        files=VALID_LICENSE_FILE,
    )
    assert up.status_code == 200, up.text
    return token


def _admin_token() -> str:
    r = client.post("/auth/login", json={"email": "admin@example.com", "password": "Password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _future_iso(hours: int = 6) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _box_payload(**overrides) -> dict:
    payload = {
        "name": "Box Sorpresa",
        "price": 4.99,
        "description": "Frutta e verdura di stagione in eccedenza",
        "category": "Frutta e Verdura",
        "allergens": "Nessuno",
        "max_boxes": 5,
        "pickup_window_start": "18:00",
        "pickup_window_end": "19:00",
        "expire_at": _future_iso(),
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# CRUD (owning vendor)
# ---------------------------------------------------------------------------

def test_box_crud_happy_path():
    token = _new_vendor("box.owner1@example.com", "Box Owner One")

    create = client.post("/shops/me/boxes", json=_box_payload(), headers=_auth_headers(token))
    assert create.status_code == 201, create.text
    box = create.json()
    assert box["max_boxes"] == 5
    assert box["sold_boxes"] == 0
    assert box["available"] == 5  # max_boxes - sold_boxes, computed server-side

    listed = client.get("/shops/me/boxes", headers=_auth_headers(token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    update = client.put(
        f"/shops/me/boxes/{box['id']}",
        json=_box_payload(name="Box Sorpresa Aggiornata", price=3.99, max_boxes=8),
        headers=_auth_headers(token),
    )
    assert update.status_code == 200, update.text
    assert update.json()["name"] == "Box Sorpresa Aggiornata"
    assert update.json()["price"] == 3.99
    assert update.json()["available"] == 8

    delete = client.delete(f"/shops/me/boxes/{box['id']}", headers=_auth_headers(token))
    assert delete.status_code == 204

    listed_after = client.get("/shops/me/boxes", headers=_auth_headers(token))
    assert listed_after.json() == []

    missing = client.put(f"/shops/me/boxes/{box['id']}", json=_box_payload(), headers=_auth_headers(token))
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# RBAC / ownership isolation
# ---------------------------------------------------------------------------

def test_box_management_requires_vendor_role():
    r = client.post(
        "/auth/register/customer",
        json={
            "email": "not.a.vendor@example.com",
            "username": "Not Vendor",
            "password": "Password123",
            "password_confirm": "Password123",
        },
    )
    assert r.status_code == 201, r.text
    login = client.post("/auth/login", json={"email": "not.a.vendor@example.com", "password": "Password123"})
    token = login.json()["access_token"]

    create = client.post("/shops/me/boxes", json=_box_payload(), headers=_auth_headers(token))
    assert create.status_code == 403


def test_vendor_cannot_manage_another_vendors_box():
    token_a = _new_vendor("box.owner2@example.com", "Box Owner Two")
    token_b = _new_vendor("box.owner3@example.com", "Box Owner Three")

    create = client.post("/shops/me/boxes", json=_box_payload(), headers=_auth_headers(token_a))
    assert create.status_code == 201, create.text
    box_id = create.json()["id"]

    update = client.put(
        f"/shops/me/boxes/{box_id}", json=_box_payload(name="Hijack"), headers=_auth_headers(token_b)
    )
    assert update.status_code == 404

    delete = client.delete(f"/shops/me/boxes/{box_id}", headers=_auth_headers(token_b))
    assert delete.status_code == 404

    # ... and untouched from vendor A's point of view.
    still_there = client.get("/shops/me/boxes", headers=_auth_headers(token_a))
    assert len(still_there.json()) == 1
    assert still_there.json()[0]["name"] == "Box Sorpresa"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_box_validation_errors():
    token = _new_vendor("box.owner4@example.com", "Box Owner Four")

    bad_price = client.post("/shops/me/boxes", json=_box_payload(price=0), headers=_auth_headers(token))
    assert bad_price.status_code == 422

    bad_quantity = client.post("/shops/me/boxes", json=_box_payload(max_boxes=0), headers=_auth_headers(token))
    assert bad_quantity.status_code == 422

    bad_window = client.post(
        "/shops/me/boxes",
        json=_box_payload(pickup_window_start="19:00", pickup_window_end="18:00"),
        headers=_auth_headers(token),
    )
    assert bad_window.status_code == 422

    bad_time_format = client.post(
        "/shops/me/boxes", json=_box_payload(pickup_window_start="9:00"), headers=_auth_headers(token)
    )
    assert bad_time_format.status_code == 422


# ---------------------------------------------------------------------------
# Public browsing
# ---------------------------------------------------------------------------

def test_public_box_listing_only_for_approved_shops():
    token = _new_vendor("box.owner5@example.com", "Box Owner Five", shop_address="Via Pubblica 1, Pisa")
    shop_id = client.get("/shops/me", headers=_auth_headers(token)).json()["id"]

    create = client.post("/shops/me/boxes", json=_box_payload(), headers=_auth_headers(token))
    assert create.status_code == 201, create.text

    # Fresh vendor's shop is still pending_review -> boxes hidden, same as
    # the shop itself would be at GET /shops/{id}.
    hidden = client.get(f"/shops/{shop_id}/boxes")
    assert hidden.status_code == 404

    admin_token = _admin_token()
    approve = client.patch(
        f"/admin/shops/{shop_id}/license-status", json={"status": "approved"}, headers=_auth_headers(admin_token)
    )
    assert approve.status_code == 200, approve.text

    visible = client.get(f"/shops/{shop_id}/boxes")
    assert visible.status_code == 200
    assert len(visible.json()) == 1
    assert visible.json()[0]["name"] == "Box Sorpresa"


def test_public_box_listing_404_for_unknown_shop():
    resp = client.get("/shops/999999/boxes")
    assert resp.status_code == 404


def test_seeded_shop_already_has_boxes_visible_publicly():
    # Vivaio Rossi - Centro (store id 1, approved) has one seeded box —
    # guards against the lifespan/seed-data gotcha noted in test_shops.py.
    resp = client.get("/shops/1/boxes")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
