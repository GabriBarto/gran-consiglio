"""
Tests for shop CRUD, admin license-status moderation, and Haversine-based
search (city filter + lat/lng/radius, ordering, pagination, visibility of
unapproved shops).

Run from the backend/ directory with: pytest
"""
from __future__ import annotations

import math

from fastapi.testclient import TestClient

from app.database import db
from app.main import app

client = TestClient(app).__enter__()

VALID_HOURS = [{"day": "mon", "start": "09:00", "end": "18:00"}]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _new_vendor_token(email: str, username: str) -> tuple[str, str]:
    """Registers+verifies+logs in a fresh vendor via the upgrade-to-vendor
    path (customer registration is JSON-only, no file upload needed) and
    returns (user_id, access_token)."""
    import io

    r = client.post(
        "/auth/register/customer",
        json={"email": email, "username": username, "password": "Password123", "password_confirm": "Password123"},
    )
    assert r.status_code == 201, r.text
    user_id = r.json()["id"]

    login = client.post("/auth/login", json={"email": email, "password": "Password123"})
    token = login.json()["access_token"]

    up = client.post(
        "/users/me/upgrade-to-vendor",
        headers=_auth_headers(token),
        data={"phone": "+39 333 1230000", "shop_address": "Via Test 1"},
        files={"license_file": ("lic.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
    )
    assert up.status_code == 200, up.text
    return user_id, token


def _admin_token() -> str:
    r = client.post("/auth/login", json={"email": "admin@example.com", "password": "Password123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def test_shop_crud_happy_path():
    _, token = _new_vendor_token("shop.owner1@example.com", "Shop Owner One")

    payload = {
        "name": "Bottega Test",
        "address": "Via Roma 1",
        "city": "Siena",
        "lat": 43.3188,
        "lng": 11.3307,
        "phone": "+39 333 1112222",
        "opening_hours": VALID_HOURS,
        "pickup_window": [{"day": "mon", "start": "17:00", "end": "18:00"}],
    }
    r = client.post("/shops", json=payload, headers=_auth_headers(token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["license_status"] == "pending_review"
    assert body["name"] == "Bottega Test"
    shop_id = body["id"]

    # a vendor can only have one shop
    dup = client.post("/shops", json=payload, headers=_auth_headers(token))
    assert dup.status_code == 409, dup.text

    me = client.get("/shops/me", headers=_auth_headers(token))
    assert me.status_code == 200
    assert me.json()["id"] == shop_id

    updated = dict(payload, name="Bottega Test Rinominata", city="Firenze")
    put = client.put("/shops/me", json=updated, headers=_auth_headers(token))
    assert put.status_code == 200, put.text
    assert put.json()["name"] == "Bottega Test Rinominata"
    assert put.json()["city"] == "Firenze"
    # PUT cannot touch license_status (it's not even in the payload schema)
    assert put.json()["license_status"] == "pending_review"

    delete = client.delete("/shops/me", headers=_auth_headers(token))
    assert delete.status_code == 204

    gone = client.get("/shops/me", headers=_auth_headers(token))
    assert gone.status_code == 404


def test_shop_requires_vendor_role():
    r = client.post(
        "/auth/register/customer",
        json={
            "email": "plain.customer@example.com",
            "username": "Plain Customer",
            "password": "Password123",
            "password_confirm": "Password123",
        },
    )
    login = client.post("/auth/login", json={"email": "plain.customer@example.com", "password": "Password123"})
    token = login.json()["access_token"]

    payload = {
        "name": "Negozio Abusivo", "address": "Via X", "city": "Roma",
        "lat": 41.9, "lng": 12.5, "phone": "+39 333 0000000",
        "opening_hours": [], "pickup_window": [],
    }
    r = client.post("/shops", json=payload, headers=_auth_headers(token))
    assert r.status_code == 403, r.text


def test_shop_validation_errors():
    _, token = _new_vendor_token("shop.owner2@example.com", "Shop Owner Two")

    base = {
        "name": "Negozio Valido", "address": "Via X", "city": "Roma",
        "lat": 41.9, "lng": 12.5, "phone": "+39 333 0000001",
        "opening_hours": [], "pickup_window": [],
    }

    bad_lat = dict(base, lat=999)
    assert client.post("/shops", json=bad_lat, headers=_auth_headers(token)).status_code == 422

    bad_phone = dict(base, phone="abc")
    assert client.post("/shops", json=bad_phone, headers=_auth_headers(token)).status_code == 422

    bad_time = dict(base, opening_hours=[{"day": "mon", "start": "9am", "end": "18:00"}])
    assert client.post("/shops", json=bad_time, headers=_auth_headers(token)).status_code == 422

    inverted = dict(base, opening_hours=[{"day": "mon", "start": "18:00", "end": "09:00"}])
    assert client.post("/shops", json=inverted, headers=_auth_headers(token)).status_code == 422

    dup_day = dict(base, opening_hours=[
        {"day": "mon", "start": "09:00", "end": "12:00"},
        {"day": "mon", "start": "14:00", "end": "18:00"},
    ])
    assert client.post("/shops", json=dup_day, headers=_auth_headers(token)).status_code == 422

    missing_times = dict(base, opening_hours=[{"day": "mon", "closed": False}])
    assert client.post("/shops", json=missing_times, headers=_auth_headers(token)).status_code == 422

    ok_closed = dict(base, opening_hours=[{"day": "sun", "closed": True}])
    assert client.post("/shops", json=ok_closed, headers=_auth_headers(token)).status_code == 201


# ---------------------------------------------------------------------------
# Admin moderation
# ---------------------------------------------------------------------------

def test_admin_only_can_change_license_status():
    _, vendor_token = _new_vendor_token("shop.owner3@example.com", "Shop Owner Three")
    payload = {
        "name": "Da Moderare", "address": "Via Y", "city": "Napoli",
        "lat": 40.85, "lng": 14.27, "phone": "+39 333 0000002",
        "opening_hours": [], "pickup_window": [],
    }
    shop = client.post("/shops", json=payload, headers=_auth_headers(vendor_token)).json()

    # vendor itself cannot call the admin endpoint
    forbidden = client.patch(
        f"/admin/shops/{shop['id']}/license-status",
        json={"status": "approved"},
        headers=_auth_headers(vendor_token),
    )
    assert forbidden.status_code == 403, forbidden.text

    admin_token = _admin_token()
    approve = client.patch(
        f"/admin/shops/{shop['id']}/license-status",
        json={"status": "approved"},
        headers=_auth_headers(admin_token),
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["license_status"] == "approved"

    # side effect: the vendor's account-level license status is kept in sync
    vendor_user = db.get_by_id(shop["vendor_id"])
    assert vendor_user.license.status.value == "approved"

    # now visible via plain GET /shops/{id} to an anonymous caller
    public = client.get(f"/shops/{shop['id']}")
    assert public.status_code == 200

    reject = client.patch(
        f"/admin/shops/{shop['id']}/license-status",
        json={"status": "rejected"},
        headers=_auth_headers(admin_token),
    )
    assert reject.status_code == 200
    assert reject.json()["license_status"] == "rejected"

    hidden_again = client.get(f"/shops/{shop['id']}")
    assert hidden_again.status_code == 404

    # owner can still see their own rejected shop
    owner_view = client.get(f"/shops/{shop['id']}", headers=_auth_headers(vendor_token))
    assert owner_view.status_code == 200


def test_admin_list_shops_filtered_by_status():
    admin_token = _admin_token()
    r = client.get("/admin/shops", params={"status": "pending_review"}, headers=_auth_headers(admin_token))
    assert r.status_code == 200, r.text
    assert all(s["license_status"] == "pending_review" for s in r.json())

    r_unauth = client.get("/admin/shops")
    assert r_unauth.status_code == 401


# ---------------------------------------------------------------------------
# Public search (city + haversine distance + radius + pagination)
# ---------------------------------------------------------------------------

def test_search_hides_unapproved_and_filters_by_city():
    # From seed data: "Vivaio Rossi" (Firenze, approved) is visible;
    # "Ortofrutta Bianchi" (Bologna, pending_review) is not.
    r = client.get("/shops")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()["items"]}
    assert "Vivaio Rossi" in names
    assert "Ortofrutta Bianchi" not in names

    r_city = client.get("/shops", params={"city": "firenze"})
    assert all(s["city"].lower() == "firenze" for s in r_city.json()["items"])
    assert any(s["name"] == "Vivaio Rossi" for s in r_city.json()["items"])

    r_other_city = client.get("/shops", params={"city": "Bolzano"})
    assert r_other_city.json()["items"] == []


def test_search_distance_and_radius_and_pagination():
    _, token_a = _new_vendor_token("geo.a@example.com", "Geo Vendor A")
    _, token_b = _new_vendor_token("geo.b@example.com", "Geo Vendor B")
    admin_token = _admin_token()

    # Two points exactly 1 degree of longitude apart on the equator are
    # ~111.19 km apart (great-circle) — a stable, hand-checkable fixture.
    shop_near = client.post(
        "/shops",
        json={
            "name": "Geo Near", "address": "Via Equatore 1", "city": "Geoville",
            "lat": 0.0, "lng": 0.0, "phone": "+39 333 5551111",
            "opening_hours": [], "pickup_window": [],
        },
        headers=_auth_headers(token_a),
    ).json()
    shop_far = client.post(
        "/shops",
        json={
            "name": "Geo Far", "address": "Via Equatore 2", "city": "Geoville",
            "lat": 0.0, "lng": 5.0, "phone": "+39 333 5552222",
            "opening_hours": [], "pickup_window": [],
        },
        headers=_auth_headers(token_b),
    ).json()

    for sid in (shop_near["id"], shop_far["id"]):
        approve = client.patch(
            f"/admin/shops/{sid}/license-status", json={"status": "approved"}, headers=_auth_headers(admin_token)
        )
        assert approve.status_code == 200

    r = client.get("/shops", params={"lat": 0.0, "lng": 0.0, "city": "Geoville"})
    items = r.json()["items"]
    assert [i["name"] for i in items] == ["Geo Near", "Geo Far"]  # sorted by distance
    assert items[0]["distance_km"] == 0.0
    expected_far_km = 5 * 111.19  # ~5 degrees at the equator
    assert math.isclose(items[1]["distance_km"], expected_far_km, rel_tol=0.01)

    # radius excludes the far one
    r_radius = client.get("/shops", params={"lat": 0.0, "lng": 0.0, "city": "Geoville", "radius_km": 200})
    names = [i["name"] for i in r_radius.json()["items"]]
    assert names == ["Geo Near"]

    # pagination
    r_page = client.get("/shops", params={"lat": 0.0, "lng": 0.0, "city": "Geoville", "limit": 1, "offset": 1})
    body = r_page.json()
    assert body["total"] == 2
    assert [i["name"] for i in body["items"]] == ["Geo Far"]

    # lat without lng is rejected
    bad = client.get("/shops", params={"lat": 0.0})
    assert bad.status_code == 422
