from __future__ import annotations

import io
import json
import os
import zipfile

from pypdf import PdfReader

from berkas.app import create_app
from berkas.config import Settings


def create_case(client, text="email: budi@example.com\nusername: budi_s", **extra):
    payload = {"text": text, "autorun": False, "title": "Kasus Uji"}
    payload.update(extra)
    response = client.post("/api/v1/cases", json=payload)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()


def test_health_reports_registered_tools(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["tools"] >= 20
    assert payload["auth_required"] is False


def test_parse_endpoint_returns_plan(client):
    response = client.post("/api/v1/intake/parse", json={"text": "domain: example.com\nhp: 081234567890"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 2
    types = {item["type"] for item in payload["entities"]}
    assert types == {"domain", "phone"}
    assert any(plan["tools"] for plan in payload["plan"])


def test_create_case_requires_entities(client):
    response = client.post("/api/v1/cases", json={"text": "   "})
    assert response.status_code == 400
    assert response.get_json()["error"] == "no_entities"


def test_create_case_accepts_explicit_entities(client):
    payload = create_case(
        client,
        text="",
        entities=[{"type": "email", "value": "a@example.com", "confidence": 0.8}],
    )
    entities = payload["case"]["entities"]
    assert len(entities) == 1
    assert entities[0]["type"] == "email"
    assert entities[0]["confidence"] == 0.8


def test_graph_and_findings_shape(client):
    case = create_case(client)
    case_id = case["case"]["id"]
    graph = client.get(f"/api/v1/cases/{case_id}/graph").get_json()
    assert len(graph["nodes"]) == 2
    assert graph["edges"] == []
    findings = graph["findings"]
    assert findings["confidence"]["band"] in {"Low", "Possible", "Probable", "High"}
    assert findings["counts"]["entities"] == 2
    assert isinstance(findings["next_pivots"], list)
    assert client.get(f"/api/v1/cases/{case_id}/findings").status_code == 200


def test_add_entity_and_pivot_validation(client):
    case_id = create_case(client)["case"]["id"]
    response = client.post(f"/api/v1/cases/{case_id}/entities", json={"value": "example.com", "type": "domain"})
    assert response.status_code == 201
    assert response.get_json()["entity"]["type"] == "domain"

    graph = client.get(f"/api/v1/cases/{case_id}/graph").get_json()
    email = next(node for node in graph["nodes"] if node["data"]["type"] == "email")
    bad = client.post(
        f"/api/v1/cases/{case_id}/pivot",
        json={"entity_id": email["data"]["id"], "tool_id": "domain_dns"},
    )
    assert bad.status_code == 400
    assert bad.get_json()["error"] == "invalid_tool"

    good = client.post(
        f"/api/v1/cases/{case_id}/pivot",
        json={"entity_id": email["data"]["id"], "tool_id": "email_intel"},
    )
    assert good.status_code == 201
    assert len(good.get_json()["runs"]) == 1


def test_upload_csv_extracts_entities_and_links_them(client):
    case_id = create_case(client, text="domain: example.com")["case"]["id"]
    csv_bytes = b"name,email,phone\nBudi,budi@example.com,081234567890\n"
    response = client.post(
        f"/api/v1/cases/{case_id}/files",
        data={"files": (io.BytesIO(csv_bytes), "kontak.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    files = response.get_json()["files"]
    assert files[0]["status"] == "success"

    graph = client.get(f"/api/v1/cases/{case_id}/graph").get_json()
    types = {node["data"]["type"] for node in graph["nodes"]}
    assert {"document", "email", "phone"} <= types
    assert len(graph["edges"]) >= 2
    assert graph["findings"]["counts"]["evidence"] >= 2


def test_upload_rejects_unsupported_file(client):
    case_id = create_case(client)["case"]["id"]
    response = client.post(
        f"/api/v1/cases/{case_id}/files",
        data={"files": (io.BytesIO(b"\x00\x01\x02binary"), "payload.bin")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    assert response.get_json()["files"][0]["status"] == "error"


def test_exports_are_valid(client):
    case_id = create_case(client)["case"]["id"]

    payload = client.get(f"/api/v1/cases/{case_id}/export?format=json")
    assert payload.status_code == 200
    assert json.loads(payload.data)["case"]["id"] == case_id

    archive = client.get(f"/api/v1/cases/{case_id}/export?format=csv")
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.data)) as bundle:
        names = set(bundle.namelist())
    assert {"entities.csv", "edges.csv", "evidence.csv", "runs.csv", "findings.json"} <= names

    pdf = client.get(f"/api/v1/cases/{case_id}/export?format=pdf")
    assert pdf.status_code == 200
    assert len(PdfReader(io.BytesIO(pdf.data)).pages) >= 1

    graphml = client.get(f"/api/v1/cases/{case_id}/export?format=graphml")
    assert graphml.status_code == 200
    assert b"<graphml" in graphml.data

    bad = client.get(f"/api/v1/cases/{case_id}/export?format=docx")
    assert bad.status_code == 400


def test_delete_case_removes_upload_folder(client, app):
    case_id = create_case(client)["case"]["id"]
    upload_folder = app.extensions["berkas"]["settings"].upload_folder
    case_folder = os.path.join(upload_folder, case_id)
    os.makedirs(case_folder, exist_ok=True)

    response = client.delete(f"/api/v1/cases/{case_id}")
    assert response.status_code == 200
    assert not os.path.isdir(case_folder)
    assert client.get(f"/api/v1/cases/{case_id}").status_code == 404


def test_unknown_case_returns_404(client):
    assert client.get("/api/v1/cases/tidak-ada").status_code == 404
    assert client.get("/api/v1/cases/tidak-ada/graph").status_code == 404


def test_token_auth_enforced(tmp_path):
    settings = Settings(
        database_url="sqlite:///" + os.path.join(tmp_path, "auth.db").replace("\\", "/"),
        upload_folder=os.path.join(tmp_path, "uploads"),
        api_token="rahasia",
        environment="test",
    )
    client = create_app(settings).test_client()
    assert client.get("/api/v1/cases").status_code == 401
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/cases", headers={"X-Berkas-Token": "rahasia"}).status_code == 200
    assert client.get("/api/v1/cases", headers={"X-Nexus-Token": "rahasia"}).status_code == 200
    assert client.get("/api/v1/cases", headers={"X-Berkas-Token": "salah"}).status_code == 401


def test_cors_origin_is_allowed(tmp_path):
    settings = Settings(
        database_url="sqlite:///" + os.path.join(tmp_path, "cors.db").replace("\\", "/"),
        upload_folder=os.path.join(tmp_path, "uploads"),
        environment="test",
        cors_origins=("https://berkas.vercel.app",),
    )
    client = create_app(settings).test_client()
    response = client.get("/api/v1/health", headers={"Origin": "https://berkas.vercel.app"})
    assert response.headers["Access-Control-Allow-Origin"] == "https://berkas.vercel.app"
    blocked = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in blocked.headers

    preflight = client.options(
        "/api/v1/cases",
        headers={
            "Origin": "https://berkas.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == "https://berkas.vercel.app"
    assert "X-Berkas-Token" in preflight.headers["Access-Control-Allow-Headers"]
    assert "ngrok-skip-browser-warning" in preflight.headers["Access-Control-Allow-Headers"]
