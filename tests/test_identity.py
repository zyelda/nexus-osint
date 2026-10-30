from __future__ import annotations

from berkas.services import cases, graph
from berkas.tools.base import ToolResult, edge, entity, evidence


def _seed_case(app) -> str:
    db = app.extensions["berkas"]["db"]
    created = cases.create_case(
        db,
        "Kasus identitas",
        entities=[
            {"type": "username", "value": "budi", "normalized": "budi", "confidence": 0.9},
        ],
    )
    return created["id"]


def test_person_without_evidence_is_not_a_candidate(app):
    db = app.extensions["berkas"]["db"]
    case_id = _seed_case(app)
    run = cases.create_run(db, case_id, "public_profiles", None)
    result = ToolResult(
        status="success",
        entities=[
            entity("person", "Budi Santoso", "budi santoso", 0.8),
            entity("person", "Nama Lain", "nama lain", 0.8),
            entity("account", "budi", "budi@example", 0.7),
        ],
        edges=[
            edge("person:budi santoso", "account:budi@example", "has_account", 0.7),
            edge("account:budi@example", "input", "same_username", 0.7),
        ],
        evidence=[
            evidence(
                "profile",
                3.0,
                "https://example.test/budi",
                "Profil Budi Santoso",
                entity_key="person:budi santoso",
            )
        ],
    )
    graph.ingest_result(db, case_id, run["id"], None, result)

    findings = graph.build_findings(db, case_id)
    names = [item["name"] for item in findings["identities"]]
    assert "Budi Santoso" in names
    assert "Nama Lain" not in names
    top = findings["identities"][0]
    assert top["name"] == "Budi Santoso"
    assert top["aliases"]
    assert 0 <= top["score"] <= 100
    assert top["band"] in {"Low", "Possible", "Probable", "High"}


def test_confidence_explains_corroboration(app):
    db = app.extensions["berkas"]["db"]
    case_id = _seed_case(app)
    run = cases.create_run(db, case_id, "public_profiles", None)
    result = ToolResult(
        status="success",
        entities=[entity("person", "Budi Santoso", "budi santoso", 0.8)],
        edges=[edge("input", "person:budi santoso", "profile_of", 0.7)],
        evidence=[
            evidence("profile", 3.0, "https://a.test", "Profil A", entity_key="person:budi santoso"),
            evidence("profile", 2.0, "https://b.test", "Profil B", entity_key="person:budi santoso"),
        ],
    )
    graph.ingest_result(db, case_id, run["id"], None, result)

    findings = graph.build_findings(db, case_id)
    confidence = findings["confidence"]
    assert confidence["source_count"] == 2
    assert any("sumber" in reason for reason in confidence["why"])
    assert confidence["score"] > 0
