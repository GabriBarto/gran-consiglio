"""
Tests for the AI "scheda di recupero pianta" endpoints. Gemini, Claude and
PlantNet are never actually called: the router tests stub plant_care's two
network functions, and the generate_sheet tests stub the Gemini / Anthropic
clients to check what is sent and how stop reasons are handled.

Run from the backend/ directory with: pytest (see conftest.py).
"""
from __future__ import annotations

import asyncio
import io
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app import plant_care
from app.config import settings
from app.main import app

client = TestClient(app).__enter__()

FAKE_SHEET = {
    "species": "Monstera (Monstera deliciosa)",
    "identification_confidence": "alta",
    "health_assessment": "Foglie gialle per eccesso d'acqua.",
    "likely_causes": ["Ristagno idrico"],
    "recovery_steps": ["Sospendi le annaffiature", "Controlla le radici"],
    "care_tips": ["Annaffia quando il terriccio è asciutto in superficie"],
    "warning_signs": ["Radici molli e scure"],
}

PNG_PHOTO = {"photo": ("pianta.png", io.BytesIO(b"\x89PNG fake"), "image/png")}


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _customer_token(email: str, username: str) -> str:
    r = client.post(
        "/auth/register/customer",
        json={"email": email, "username": username, "password": "Password123", "password_confirm": "Password123"},
    )
    assert r.status_code == 201, r.text
    login = client.post("/auth/login", json={"email": email, "password": "Password123"})
    return login.json()["access_token"]


@pytest.fixture(scope="module")
def token() -> str:
    return _customer_token("plant.care@example.com", "Plant Care User")


@pytest.fixture
def calls(monkeypatch):
    """Stubs both network calls and records what generate_sheet received."""
    recorded = {"generate": [], "plantnet": []}

    async def fake_generate(*, species_hint, symptoms, photo):
        recorded["generate"].append({"species_hint": species_hint, "symptoms": symptoms, "photo": photo})
        return dict(FAKE_SHEET)

    async def fake_plantnet(photo):
        recorded["plantnet"].append(photo)
        return recorded.get("plantnet_result")

    monkeypatch.setattr(plant_care, "generate_sheet", fake_generate)
    monkeypatch.setattr(plant_care, "identify_with_plantnet", fake_plantnet)
    return recorded


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def test_species_list_is_public():
    r = client.get("/plant-care/species")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert "monstera" in ids


def test_recovery_sheet_requires_login(calls):
    r = client.post("/plant-care/recovery-sheet", data={"species_id": "monstera"})
    assert r.status_code == 401
    assert calls["generate"] == []


def test_recovery_sheet_from_catalog_species(token, calls):
    r = client.post(
        "/plant-care/recovery-sheet",
        headers=_auth_headers(token),
        data={"species_id": "monstera", "symptoms": "  foglie gialle  "},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["identification_source"] == "catalog"
    assert body["disclaimer"] == plant_care.DISCLAIMER
    assert body["recovery_steps"] == FAKE_SHEET["recovery_steps"]
    assert calls["generate"][0]["species_hint"] == "Monstera (Monstera deliciosa)"
    assert calls["generate"][0]["symptoms"] == "foglie gialle"
    assert calls["plantnet"] == []  # catalog choice wins, no identification needed


def test_recovery_sheet_photo_identified_by_plantnet(token, calls):
    calls["plantnet_result"] = plant_care.Identification("Ficus elastica", "Albero della gomma", 0.91)
    r = client.post("/plant-care/recovery-sheet", headers=_auth_headers(token), files=PNG_PHOTO)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["identification_source"] == "plantnet"
    assert body["identification_score"] == pytest.approx(0.91)
    assert "Ficus elastica" in calls["generate"][0]["species_hint"]
    assert calls["generate"][0]["photo"].media_type == "image/png"


def test_recovery_sheet_photo_falls_back_to_ai_vision(token, calls):
    r = client.post("/plant-care/recovery-sheet", headers=_auth_headers(token), files=PNG_PHOTO)
    assert r.status_code == 200, r.text
    assert r.json()["identification_source"] == "ai_vision"
    assert calls["generate"][0]["species_hint"] is None


def test_recovery_sheet_octet_stream_photo_uses_extension(token, calls):
    files = {"photo": ("pianta.jpg", io.BytesIO(b"\xff\xd8 fake"), "application/octet-stream")}
    r = client.post("/plant-care/recovery-sheet", headers=_auth_headers(token), files=files)
    assert r.status_code == 200, r.text
    assert calls["generate"][0]["photo"].media_type == "image/jpeg"


@pytest.mark.parametrize(
    "data,files,expected",
    [
        ({}, None, 422),  # neither species nor photo
        ({"species_id": "not-a-plant"}, None, 422),
        ({"species_id": "monstera", "symptoms": "x" * 1001}, None, 422),
        ({}, {"photo": ("doc.pdf", io.BytesIO(b"%PDF"), "application/pdf")}, 400),
        ({}, {"photo": ("vuota.png", io.BytesIO(b""), "image/png")}, 400),
    ],
)
def test_recovery_sheet_validation(token, calls, data, files, expected):
    r = client.post("/plant-care/recovery-sheet", headers=_auth_headers(token), data=data, files=files)
    assert r.status_code == expected, r.text
    assert calls["generate"] == []


def test_recovery_sheet_ai_unavailable_is_503(token, monkeypatch):
    async def failing_generate(**_):
        raise plant_care.PlantCareUnavailable("Servizio AI non disponibile al momento.")

    monkeypatch.setattr(plant_care, "generate_sheet", failing_generate)
    r = client.post("/plant-care/recovery-sheet", headers=_auth_headers(token), data={"species_id": "aloe"})
    assert r.status_code == 503
    assert r.json()["detail"] == "Servizio AI non disponibile al momento."


# ---------------------------------------------------------------------------
# generate_sheet — Gemini (client stubbed)
# ---------------------------------------------------------------------------

def _stub_gemini(monkeypatch, *, finish_reason=genai_types.FinishReason.STOP, text=json.dumps(FAKE_SHEET)):
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    sent = {}

    async def generate_content(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason=finish_reason)], text=text, prompt_feedback=None
        )

    fake = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    monkeypatch.setattr(plant_care, "_gemini_client", lambda: fake)
    return sent


def test_gemini_sends_photo_and_schema(monkeypatch):
    sent = _stub_gemini(monkeypatch)
    photo = plant_care.Photo(data=b"abc", media_type="image/png")
    sheet = asyncio.run(plant_care.generate_sheet(species_hint=None, symptoms="macchie", photo=photo))

    assert sheet == FAKE_SHEET
    image_part, text = sent["contents"]
    assert image_part.inline_data.data == b"abc"
    assert image_part.inline_data.mime_type == "image/png"
    assert "<sintomi>\nmacchie\n</sintomi>" in text
    assert sent["model"] == settings.gemini_model
    assert sent["config"].response_mime_type == "application/json"
    assert sent["config"].response_json_schema == plant_care._SHEET_SCHEMA


def test_gemini_overloaded_falls_back_to_second_model(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_model", "primary")
    monkeypatch.setattr(settings, "gemini_fallback_model", "backup")
    tried = []

    async def generate_content(*, model, **_):
        tried.append(model)
        if model == "primary":
            raise genai_errors.ServerError(503, {"error": {"message": "high demand"}})
        return SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason=genai_types.FinishReason.STOP)],
            text=json.dumps(FAKE_SHEET),
            prompt_feedback=None,
        )

    fake = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    monkeypatch.setattr(plant_care, "_gemini_client", lambda: fake)
    sheet = asyncio.run(plant_care.generate_sheet(species_hint="Aloe vera", symptoms=None, photo=None))
    assert sheet == FAKE_SHEET
    assert tried == ["primary", "backup"]


def test_gemini_safety_block_raises(monkeypatch):
    _stub_gemini(monkeypatch, finish_reason=genai_types.FinishReason.SAFETY, text=None)
    with pytest.raises(plant_care.PlantCareUnavailable):
        asyncio.run(plant_care.generate_sheet(species_hint="Aloe vera", symptoms=None, photo=None))


def test_gemini_without_key_is_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", None)
    with pytest.raises(plant_care.PlantCareUnavailable, match="non configurato"):
        asyncio.run(plant_care.generate_sheet(species_hint="Aloe vera", symptoms=None, photo=None))


# ---------------------------------------------------------------------------
# generate_sheet — Claude (Anthropic client stubbed)
# ---------------------------------------------------------------------------

def _stub_claude(monkeypatch, *, stop_reason="end_turn", text=json.dumps(FAKE_SHEET)):
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    sent = {}

    async def create(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(plant_care, "_client", lambda: fake)
    return sent


def test_claude_sends_photo_and_schema(monkeypatch):
    sent = _stub_claude(monkeypatch)
    photo = plant_care.Photo(data=b"abc", media_type="image/png")
    sheet = asyncio.run(plant_care.generate_sheet(species_hint=None, symptoms="macchie", photo=photo))

    assert sheet == FAKE_SHEET
    content = sent["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"] == {"type": "base64", "media_type": "image/png", "data": "YWJj"}
    assert "<sintomi>\nmacchie\n</sintomi>" in content[1]["text"]
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["fallbacks"] == "default"


def test_claude_refusal_raises(monkeypatch):
    _stub_claude(monkeypatch, stop_reason="refusal", text="")
    with pytest.raises(plant_care.PlantCareUnavailable):
        asyncio.run(plant_care.generate_sheet(species_hint="Aloe vera", symptoms=None, photo=None))
