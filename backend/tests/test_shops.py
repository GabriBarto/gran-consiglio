"""
Tests for shop CRUD, admin license-status moderation, and Haversine-based
search (address-substring filter + lat/lng/radius, ordering, pagination,
visibility of unapproved shops) against the real (test) MySQL database.

Becoming a vendor (register/vendor or upgrade-to-vendor) auto-creates a
placeholder shop (lat=0, lng=0) — see routers/auth.py and routers/users.py
— so most tests here start from that shop rather than calling POST /shops
themselves; POST /shops is exercised directly in its own tests (recreating
after a delete, and the "already has a shop" 409).

Run from the backend/ directory with: pytest (conftest.py points this at a
dedicated toogood_test database, reloaded fresh from
backend/db/projectwork_en_v2.sql before the session starts).
"""
from __future__ import annotations

import io
import math

from fastapi.testclient import TestClient

from app.database import db
from app.main import app

client = TestClient(app).__enter__()

VALID_LICENSE_FILE = {"license_file": ("lic.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")}


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _new_vendor(email: str, username: str, *, shop_address: str = "Via Test 1", phone: str = "+39 333 1230000"):
    """Registers+logs in a fresh vendor via upgrade-to-vendor (customer
    registration is JSON-only). Returns (user_id, access_token) — the
    vendor already has a placeholder shop at lat=0/lng=0 afterwards."""
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
        data={"phone": phone, "shop_address": shop_address},
        files=VALID_LICENSE_FILE,
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
    _, token = _new_vendor("shop.owner1@example.com", "Shop Owner One", shop_address="Via Roma 1, Siena")

    # Already has a placeholder shop from upgrade-to-vendor.
    me = client.get("/shops/me", headers=_auth_headers(token))
    assert me.status_code == 200
    body = me.json()
    assert body["license_status"] == "pending_review"
    assert body["address"] == "Via Roma 1, Siena"
    assert body["lat"] == 0.0 and body["lng"] == 0.0

    update_payload = {
        "name": "Bottega Test Rinominata",
        "address": "Via Roma 1, Siena",
        "lat": 43.3188,
        "lng": 11.3307,
        "phone": "+39 333 1112222",
        "opening_time": "08:00",
        "pickup_window_start": "17:00",
        "pickup_window_end": "18:00",
    }
    put = client.put("/shops/me", json=update_payload, headers=_auth_headers(token))
    assert put.status_code == 200, put.text
    assert put.json()["name"] == "Bottega Test Rinominata"
    assert put.json()["lat"] == 43.3188
    # PUT cannot touch license_status (it's not even in the payload schema)
    assert put.json()["license_status"] == "pending_review"

    delete = client.delete("/shops/me", headers=_auth_headers(token))
    assert delete.status_code == 204

    gone = client.get("/shops/me", headers=_auth_headers(token))
    assert gone.status_code == 404

    # Recreate from scratch via the multipart create endpoint.
    create = client.post(
        "/shops",
        data={
            "name": "Bottega Ricreata", "address": "Via Roma 1, Siena",
            "lat": "43.3188", "lng": "11.3307", "phone": "+39 333 1112222",
            "opening_time": "08:00", "pickup_window_start": "17:00", "pickup_window_end": "18:00",
        },
        files=VALID_LICENSE_FILE,
        headers=_auth_headers(token),
    )
    assert create.status_code == 201, create.text
    assert create.json()["name"] == "Bottega Ricreata"

    # A vendor can only have one shop.
    dup = client.post(
        "/shops",
        data={
            "name": "Altro Negozio", "address": "Via Roma 1, Siena",
            "lat": "43.3188", "lng": "11.3307", "phone": "+39 333 1112222",
            "opening_time": "08:00", "pickup_window_start": "17:00", "pickup_window_end": "18:00",
        },
        files=VALID_LICENSE_FILE,
        headers=_auth_headers(token),
    )
    assert dup.status_code == 409, dup.text


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

    r = client.post(
        "/shops",
        data={
            "name": "Negozio Abusivo", "address": "Via X",
            "lat": "41.9", "lng": "12.5", "phone": "+39 333 0000000",
            "opening_time": "09:00", "pickup_window_start": "18:00", "pickup_window_end": "19:00",
        },
        files=VALID_LICENSE_FILE,
        headers=_auth_headers(token),
    )
    assert r.status_code == 403, r.text


def test_shop_validation_errors():
    # Validation runs before the "already has a shop" 409 check, so this
    # works fine even though this vendor already has a placeholder shop.
    _, token = _new_vendor("shop.owner2@example.com", "Shop Owner Two")

    base = {
        "name": "Negozio Valido", "address": "Via X", "phone": "+39 333 0000001",
        "opening_time": "09:00", "pickup_window_start": "18:00", "pickup_window_end": "19:00",
    }

    def post(overrides):
        data = {**base, "lat": "41.9", "lng": "12.5", **overrides}
        return client.post("/shops", data=data, files=VALID_LICENSE_FILE, headers=_auth_headers(token))

    assert post({"lat": "999"}).status_code == 422
    assert post({"phone": "abc"}).status_code == 422
    assert post({"opening_time": "9am"}).status_code == 422
    assert post({"pickup_window_start": "18:00", "pickup_window_end": "09:00"}).status_code == 422
    assert post({"name": "A"}).status_code == 422  # too short


def test_replace_shop_license():
    _, token = _new_vendor("shop.owner3b@example.com", "Shop Owner Three B")
    admin_token = _admin_token()

    me = client.get("/shops/me", headers=_auth_headers(token)).json()
    approve = client.patch(
        f"/admin/shops/{me['id']}/license-status", json={"status": "approved"}, headers=_auth_headers(admin_token)
    )
    assert approve.status_code == 200
    assert approve.json()["license_status"] == "approved"

    replaced = client.put(
        "/shops/me/license",
        files={"license_file": ("nuova.pdf", io.BytesIO(b"%PDF-1.4 nuova"), "application/pdf")},
        headers=_auth_headers(token),
    )
    assert replaced.status_code == 200, replaced.text
    # Re-uploading resets the review status back to pending.
    assert replaced.json()["license_status"] == "pending_review"
    assert replaced.json()["license_url"] != me["license_url"]

    # vendor-only
    cust_login = client.post("/auth/login", json={"email": "cliente.demo@example.com", "password": "Password123"})
    cust_token = cust_login.json()["access_token"]
    forbidden = client.put(
        "/shops/me/license",
        files={"license_file": ("x.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
        headers=_auth_headers(cust_token),
    )
    assert forbidden.status_code == 403


def test_license_download_is_private():
    """License files aren't publicly served: only an admin or the shop's own
    vendor can get a (short-lived) download link, and only that link works."""
    _, vendor_token = _new_vendor("shop.owner.lic@example.com", "Shop Owner Lic")
    _, other_vendor_token = _new_vendor("shop.owner.lic2@example.com", "Shop Owner Lic Two")
    admin_token = _admin_token()
    me = client.get("/shops/me", headers=_auth_headers(vendor_token)).json()

    # The stored URL itself no longer downloads anything.
    stored_path = "/" + me["license_url"].split("://", 1)[1].split("/", 1)[1]
    assert client.get(stored_path).status_code == 404

    # Anonymous / another vendor can't get a link.
    assert client.post(f"/shops/{me['id']}/license/link").status_code == 401
    other = client.post(f"/shops/{me['id']}/license/link", headers=_auth_headers(other_vendor_token))
    assert other.status_code == 404

    for token in (admin_token, vendor_token):
        link = client.post(f"/shops/{me['id']}/license/link", headers=_auth_headers(token))
        assert link.status_code == 200, link.text
        download = client.get(link.json()["path"])
        assert download.status_code == 200
        assert download.content == b"%PDF-1.4 x"
        assert download.headers["content-type"] == "application/pdf"
        assert download.headers["content-disposition"].startswith("inline")

    # Missing, tampered, or another shop's token is rejected.
    assert client.get(f"/shops/{me['id']}/license").status_code == 422
    assert client.get(f"/shops/{me['id']}/license?token=nope").status_code == 403
    other_shop = client.get("/shops/me", headers=_auth_headers(other_vendor_token)).json()
    other_link = client.post(f"/shops/{other_shop['id']}/license/link", headers=_auth_headers(admin_token)).json()
    other_token = other_link["path"].split("token=", 1)[1]
    assert client.get(f"/shops/{me['id']}/license?token={other_token}").status_code == 403


# ---------------------------------------------------------------------------
# Admin moderation
# ---------------------------------------------------------------------------

def test_admin_only_can_change_license_status():
    _, vendor_token = _new_vendor("shop.owner3@example.com", "Shop Owner Three", shop_address="Via Y, Napoli")
    shop = client.get("/shops/me", headers=_auth_headers(vendor_token)).json()

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
# Public search (address substring + haversine distance + radius + pagination)
# ---------------------------------------------------------------------------

def test_search_hides_unapproved_and_filters_by_address():
    # From seed data: "Vivaio Rossi - Centro" (Firenze, approved) is
    # visible; "Ortofrutta Bianchi" (Bologna, pending_review) is not.
    r = client.get("/shops")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()["items"]}
    assert "Vivaio Rossi - Centro" in names
    assert "Ortofrutta Bianchi" not in names

    r_city = client.get("/shops", params={"city": "firenze"})
    assert all("firenze" in s["address"].lower() for s in r_city.json()["items"])
    assert any(s["name"] == "Vivaio Rossi - Centro" for s in r_city.json()["items"])

    r_other_city = client.get("/shops", params={"city": "Bolzano"})
    assert r_other_city.json()["items"] == []


def test_search_distance_and_radius_and_pagination():
    _, token_a = _new_vendor("geo.a@example.com", "Geo Near", shop_address="Via Equatore 1, Geoville")
    _, token_b = _new_vendor("geo.b@example.com", "Geo Far", shop_address="Via Equatore 2, Geoville")
    admin_token = _admin_token()

    # "Geo Near" is already at the placeholder (0, 0) — exactly the search
    # origin below. Move "Geo Far" 5 degrees of longitude away: at the
    # equator that's a stable, hand-checkable ~555.95 km.
    move_far = client.put(
        "/shops/me",
        json={
            "name": "Geo Far", "address": "Via Equatore 2, Geoville",
            "lat": 0.0, "lng": 5.0, "phone": "+39 333 5552222",
            "opening_time": "09:00", "pickup_window_start": "18:00", "pickup_window_end": "19:00",
        },
        headers=_auth_headers(token_b),
    )
    assert move_far.status_code == 200, move_far.text

    for token in (token_a, token_b):
        shop_id = client.get("/shops/me", headers=_auth_headers(token)).json()["id"]
        approve = client.patch(
            f"/admin/shops/{shop_id}/license-status", json={"status": "approved"}, headers=_auth_headers(admin_token)
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
