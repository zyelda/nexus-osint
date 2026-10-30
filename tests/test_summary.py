from __future__ import annotations

import io
import json

import pytest

from types import SimpleNamespace

from berkas.services.summary import _ai_payload, _from_ai, _redact_value, redact_pii


def create_case(client, text="email: budi.santoso@example.com\nphone: 081234567890", title="Kasus Uji"):
    response = client.post(
        "/api/v1/cases",
        json={"text": text, "autorun": False, "title": title},
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["case"]["id"]


def upload_contact(client, case_id: str) -> None:
    csv_bytes = b"name,email,phone\nBudi,budi.santoso@example.com,081234567890\n"
    response = client.post(
        f"/api/v1/cases/{case_id}/files",
        data={"files": (io.BytesIO(csv_bytes), "kontak.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    assert response.get_json()["files"][0]["status"] == "success"


def test_redact_pii_masks_identifiers():
    text = "Email budi.santoso@example.com, HP 081234567890, NIK 3273010101900001, NPWP 12.345.678.9-012.000."
    redacted, fields = redact_pii(text)
    assert "budi.santoso@example.com" not in redacted
    assert "081234567890" not in redacted
    assert "3273010101900001" not in redacted
    assert "12.345.678.9-012.000" not in redacted
    assert {"email", "phone", "nik", "npwp"} <= fields
    assert "b***@example.com" in redacted


def test_redaction_never_masks_citation_ids():
    evidence_id = "222fdf1e8ed04be2b086963542e18127"
    payload = {
        "points": [
            {
                "text": "Kontak budi.santoso@example.com dan 081234567890",
                "citation_ids": [evidence_id],
            }
        ]
    }
    fields: set[str] = set()
    redacted = _redact_value(payload, fields)
    assert redacted["points"][0]["citation_ids"] == [evidence_id]
    assert "budi.santoso@example.com" not in redacted["points"][0]["text"]
    assert {"email", "phone"} <= fields


def test_ai_payload_redacts_public_pii_before_sending():
    case = {
        "title": "Kasus budi.santoso@example.com",
        "purpose": "Hubungi 081234567890",
    }
    findings = {
        "confidence": {"score": 10, "band": "Low", "source_count": 1},
        "counts": {"entities": 1, "edges": 0, "evidence": 1},
        "identities": [],
        "warnings": [],
        "next_pivots": [],
        "clues": [
            {
                "id": "ev-1",
                "category": "profile",
                "snippet": "Kontak budi.santoso@example.com dan 081234567890",
                "source_url": "https://example.com",
                "weight": 1.0,
            }
        ],
    }
    settings = SimpleNamespace(public_redaction=True)
    request = _ai_payload(case, findings, "public", settings)
    assert request is not None
    assert "budi.santoso@example.com" not in request["user"]
    assert "081234567890" not in request["user"]
    assert "b***@example.com" in request["user"]

    analyst_request = _ai_payload(case, findings, "analyst", settings)
    assert analyst_request is not None
    assert "budi.santoso@example.com" in analyst_request["user"]


def test_ai_payload_requires_valid_citations():
    findings = {
        "clues": [
            {"id": "ev-1", "category": "profile", "snippet": "Profil publik", "source_url": "https://example.com"},
        ]
    }
    valid = {
        "headline": "Ringkasan",
        "points": [
            {"text": "Poin satu", "citation_ids": ["ev-1"]},
            {"text": "Poin dua", "citation_ids": ["ev-1"]},
            {"text": "Poin tiga", "citation_ids": ["ev-1"]},
        ],
        "narrative": [
            {"text": "Paragraf satu", "citation_ids": ["ev-1"]},
            {"text": "Paragraf dua", "citation_ids": ["ev-1"]},
        ],
    }
    result = _from_ai(valid, findings)
    assert len(result["points"]) == 3

    invalid = json.loads(json.dumps(valid))
    invalid["points"][0]["citation_ids"] = ["tidak-ada"]
    with pytest.raises(ValueError):
        _from_ai(invalid, findings)


def test_summary_endpoint_public_and_analyst(client):
    case_id = create_case(client, title="Kasus budi.santoso@example.com")
    upload_contact(client, case_id)

    public = client.get(f"/api/v1/cases/{case_id}/summary?audience=public")
    assert public.status_code == 200
    payload = public.get_json()
    assert payload["audience"] == "public"
    assert payload["generated_by"] == "local"
    assert payload["redaction"]["applied"] is True
    assert payload["redaction"]["policy"] == "partial"
    assert "email" in payload["redaction"]["fields"]
    assert len(payload["points"]) >= 3
    assert len(payload["narrative"]) >= 2
    citation_ids = {item["id"] for item in payload["citations"]}
    for point in payload["points"]:
        assert set(point["citation_ids"]) <= citation_ids
    assert "budi.santoso@example.com" not in json.dumps(payload, ensure_ascii=False)

    analyst = client.get(f"/api/v1/cases/{case_id}/summary?audience=analyst")
    assert analyst.status_code == 200
    analyst_payload = analyst.get_json()
    assert analyst_payload["redaction"]["applied"] is False
    assert analyst_payload["redaction"]["policy"] == "none"
    assert "budi.santoso@example.com" in json.dumps(analyst_payload, ensure_ascii=False)


def test_summary_cache_and_refresh(client):
    case_id = create_case(client)
    upload_contact(client, case_id)

    first = client.get(f"/api/v1/cases/{case_id}/summary?audience=public").get_json()
    assert first["cached"] is False
    second = client.get(f"/api/v1/cases/{case_id}/summary?audience=public").get_json()
    assert second["cached"] is True
    refreshed = client.get(f"/api/v1/cases/{case_id}/summary?audience=public&refresh=1").get_json()
    assert refreshed["cached"] is False


def test_summary_rejects_unknown_audience(client):
    case_id = create_case(client)
    response = client.get(f"/api/v1/cases/{case_id}/summary?audience=warga")
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_audience"


def test_export_pdf_contains_public_summary(client):
    case_id = create_case(client)
    upload_contact(client, case_id)
    response = client.get(f"/api/v1/cases/{case_id}/export?format=pdf")
    assert response.status_code == 200
    assert b"RINGKASAN UNTUK PEMBACA AWAM" in response.data


def test_keys_health_hides_secret_values(client):
    response = client.get("/api/v1/keys/health")
    assert response.status_code == 200
    payload = response.get_json()
    names = {item["name"] for item in payload["keys"]}
    assert {"GROQ_API_KEY", "VT_API_KEY", "HIBP_API_KEY"} <= names
    assert all(isinstance(item["configured"], bool) for item in payload["keys"])
    assert "keys" in payload and "ai" in payload
