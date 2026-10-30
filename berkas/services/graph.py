from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select

from berkas.db import Case, Entity, ToolRun, utcnow
from berkas.entities import tools_for_type
from berkas.services import cases
from berkas.tools.base import ToolResult
from berkas.tools.registry import registry

IDENTIFIER_CATEGORIES = {"identity_document", "phone", "email", "breach"}
PROFILE_CATEGORIES = {"profile", "registration", "document_metadata", "academic", "certificate"}
LINK_RELATIONS = {
    "same_username",
    "candidate_email",
    "candidate_username",
    "uses_domain",
    "profile_of",
    "has_account",
    "registered_by",
    "member_of",
    "resolves_to",
    "subdomain_of",
    "operated_by",
    "authored_by",
}
OFFICIAL_DOMAINS = {
    "github.com",
    "keybase.io",
    "haveibeenpwned.com",
    "rdap.org",
    "kemdikbud.go.id",
    "pddikti.kemdikbud.go.id",
}
GENERIC_NAMES = {"john doe", "jane doe", "budi santoso", "admin", "user", "test"}


def _domain(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def ingest_result(db, case_id: str, run_id: str, input_entity_id: str | None, result: ToolResult) -> dict:
    with db.session() as session:
        key_map: dict[str, str] = {}
        if input_entity_id:
            key_map["input"] = input_entity_id
            input_row = session.get(Entity, input_entity_id)
            if input_row:
                key_map[f"{input_row.type}:{input_row.normalized}"] = input_entity_id
        created_entities = 0
        for item in result.entities:
            entity = cases.upsert_entity(
                session,
                case_id,
                item.type,
                item.value,
                item.normalized,
                item.confidence,
                attributes=item.attributes,
            )
            key_map[item.key or f"{item.type}:{item.normalized}"] = entity.id
            key_map[f"{item.type}:{item.normalized}"] = entity.id
            created_entities += 1
        created_edges = 0
        edge_ids: dict[tuple[str, str, str], str] = {}
        for item in result.edges:
            source = key_map.get(item.source_key)
            target = key_map.get(item.target_key)
            if not source or not target or source == target:
                continue
            edge = cases.add_edge(session, case_id, source, target, item.relation, item.confidence, item.attributes)
            edge_ids[(source, target, item.relation)] = edge.id
            created_edges += 1
        for item in result.evidence:
            entity_id = key_map.get(item.entity_key) if item.entity_key else input_entity_id
            if entity_id is None:
                entity_id = input_entity_id
            edge_id = None
            if item.edge_key:
                edge_id = edge_ids.get((item.edge_key, "", ""))
            cases.add_evidence(
                session,
                case_id,
                entity_id=entity_id,
                edge_id=edge_id,
                tool_run_id=run_id,
                source_url=item.source_url,
                snippet=item.snippet,
                category=item.category,
                weight=item.weight,
                raw=item.raw,
            )
        run = session.get(ToolRun, run_id)
        if run:
            run.result = {
                "status": result.status,
                "data": result.data,
                "warnings": result.warnings,
                "entity_count": len(result.entities),
                "edge_count": len(result.edges),
            }
            run.error_code = result.error_code
            run.error_message = result.error_message
        case = session.get(Case, case_id)
        if case:
            case.updated_at = utcnow()
        session.commit()
        return {"entities": created_entities, "edges": created_edges, "evidence": len(result.evidence)}


def build_findings(db, case_id: str) -> dict:
    case = cases.get_case(db, case_id)
    if not case:
        return {}
    entities = case["entities"]
    edges = case["edges"]
    evidence = case["evidence"]
    runs = case["runs"]
    entity_by_id = {item["id"]: item for item in entities}
    source_domains = {_domain(item["source_url"]) for item in evidence if item["source_url"]}
    source_domains.discard("")
    profile_domains = {
        _domain(item["source_url"])
        for item in evidence
        if item["category"] in PROFILE_CATEGORIES and item["source_url"]
    }
    profile_domains.discard("")

    identifier_weight = sum(item["weight"] for item in evidence if item["category"] in IDENTIFIER_CATEGORIES)
    unique_score = min(45.0, identifier_weight * 10)
    cross_score = min(24.0, len(profile_domains) * 8)
    profile_score = min(18.0, sum(1 for item in evidence if item["category"] in PROFILE_CATEGORIES) * 6)
    link_score = min(20.0, sum(1 for item in edges if item["relation"] in LINK_RELATIONS) * 10)
    temporal_score = 5.0 if len({item["created_at"][:10] for item in evidence if item["created_at"]}) > 1 else 0.0
    official_score = 5.0 if source_domains & OFFICIAL_DOMAINS else 0.0
    category_count = len({item["category"] for item in evidence})
    corroboration_score = min(12.0, len(source_domains) * 2 + max(0, category_count - 1) * 1.5)

    penalties = 0.0
    why = []
    if unique_score:
        why.append(f"+{unique_score:.0f} identifier unik atau dokumen identitas")
    if cross_score:
        why.append(f"+{cross_score:.0f} konsistensi profil lintas sumber")
    if profile_score:
        why.append(f"+{profile_score:.0f} atribut profil yang saling menguatkan")
    if link_score:
        why.append(f"+{link_score:.0f} relasi antar entity")
    if temporal_score:
        why.append("+5 aktivitas pada rentang waktu berbeda")
    if official_score:
        why.append("+5 sumber resmi atau API publik")
    if corroboration_score:
        why.append(
            f"+{corroboration_score:.0f} bukti dari {len(source_domains)} sumber dan {category_count} kategori"
        )
    if len(source_domains) <= 1 and evidence:
        penalties -= 10
        why.append("-10 hanya satu domain sumber")
    blocked_runs = [run for run in runs if run["status"] in {"blocked", "missing_key", "error"}]
    if blocked_runs:
        penalty = min(15, len(blocked_runs) * 5)
        penalties -= penalty
        why.append(f"-{penalty} ada sumber yang gagal atau butuh key")
    person_entities = [item for item in entities if item["type"] == "person"]
    if person_entities and any(item["normalized"] in GENERIC_NAMES for item in person_entities):
        penalties -= 8
        why.append("-8 nama terlalu umum")
    if not evidence:
        penalties -= 20
        why.append("-20 belum ada bukti")

    score = max(
        0,
        min(
            100,
            unique_score
            + cross_score
            + profile_score
            + link_score
            + temporal_score
            + official_score
            + corroboration_score
            + penalties,
        ),
    )
    if score >= 80:
        band = "High"
    elif score >= 60:
        band = "Probable"
    elif score >= 30:
        band = "Possible"
    else:
        band = "Low"

    clues = sorted(evidence, key=lambda item: (item["weight"], item["created_at"] or ""), reverse=True)[:8]
    clues_payload = [
        {
            "id": item["id"],
            "category": item["category"],
            "snippet": item["snippet"],
            "source_url": item["source_url"],
            "weight": item["weight"],
            "entity_id": item["entity_id"],
            "edge_id": item["edge_id"],
            "created_at": item["created_at"],
        }
        for item in clues
    ]

    identities = []
    for person in person_entities[:12]:
        connected = [edge for edge in edges if person["id"] in {edge["source_id"], edge["target_id"]}]
        direct = [item for item in evidence if item["entity_id"] == person["id"]]
        aliases = []
        for edge in connected:
            other_id = edge["target_id"] if edge["source_id"] == person["id"] else edge["source_id"]
            other = entity_by_id.get(other_id)
            if other and other["type"] in {"username", "email", "phone", "account", "alias"}:
                aliases.append({"type": other["type"], "value": other["value"], "id": other["id"]})
        if not direct and len(connected) < 2:
            continue
        direct_weight = sum(item["weight"] for item in direct)
        own_score = min(45.0, len(direct) * 10 + direct_weight * 3)
        link_score_local = min(30.0, len(connected) * 8 + len(aliases) * 4)
        base_score = min(20.0, score * 0.2)
        local_score = min(100.0, own_score + link_score_local + base_score + person["confidence"] * 10)
        if local_score >= 80:
            local_band = "High"
        elif local_score >= 60:
            local_band = "Probable"
        elif local_score >= 30:
            local_band = "Possible"
        else:
            local_band = "Low"
        identities.append(
            {
                "entity_id": person["id"],
                "name": person["value"],
                "score": round(local_score),
                "band": local_band,
                "aliases": aliases[:12],
                "connections": len(connected),
                "evidence_count": len(direct),
            }
        )
    identities.sort(key=lambda item: (item["score"], item["connections"]), reverse=True)
    if not identities:
        identity_types = {"username", "email", "phone", "account", "nik", "npwp", "nim"}
        identities = [
            {
                "entity_id": item["id"],
                "name": item["value"],
                "score": round(min(45.0, score * 0.4 + item["confidence"] * 10)),
                "band": "Possible" if score >= 30 else "Low",
                "aliases": [],
                "connections": len([edge for edge in edges if item["id"] in {edge["source_id"], edge["target_id"]}]),
                "evidence_count": len([ev for ev in evidence if ev["entity_id"] == item["id"]]),
            }
            for item in sorted(entities, key=lambda row: row["confidence"], reverse=True)
            if item["type"] in identity_types
        ][:3]

    warnings = []
    for run in blocked_runs[:6]:
        warnings.append(f"{run['tool_id']}: {run['status']} {run['error_message'] or run['error_code']}".strip())
    if len(source_domains) <= 1 and evidence:
        warnings.append("Sebagian besar temuan berasal dari satu sumber. Verifikasi independen diperlukan.")
    if score < 40:
        warnings.append("Skor identitas masih rendah. Jangan gunakan sebagai kesimpulan.")
    if person_entities and any(item["normalized"] in GENERIC_NAMES for item in person_entities):
        warnings.append("Nama target terlalu umum, risiko false positive tinggi.")

    run_keys = {
        (run["tool_id"], run["input_entity_id"])
        for run in runs
        if run["status"] not in {"error", "timeout"}
    }
    next_pivots = []
    for item in entities:
        for tool_id in tools_for_type(item["type"]):
            if (tool_id, item["id"]) in run_keys:
                continue
            spec = registry.get(tool_id)
            if not spec:
                continue
            next_pivots.append(
                {
                    "entity_id": item["id"],
                    "entity_type": item["type"],
                    "entity_value": item["value"],
                    "tool_id": tool_id,
                    "label": spec.label,
                    "reason": f"{spec.label} untuk {item['type']} {item['value']}",
                }
            )
            if len(next_pivots) >= 10:
                break
        if len(next_pivots) >= 10:
            break

    timeline = [
        {
            "id": item["id"],
            "category": item["category"],
            "title": item["snippet"] or item["category"],
            "source_url": item["source_url"],
            "created_at": item["created_at"],
            "entity_id": item["entity_id"],
        }
        for item in sorted(evidence, key=lambda row: row["created_at"] or "", reverse=True)[:20]
    ]

    return {
        "case_id": case_id,
        "case_title": case["title"],
        "confidence": {
            "score": round(score),
            "band": band,
            "evidence_count": len(evidence),
            "source_count": len(source_domains),
            "conflicts": 0,
            "why": why,
        },
        "clues": clues_payload,
        "identities": identities,
        "timeline": timeline,
        "warnings": warnings,
        "next_pivots": next_pivots,
        "counts": {
            "entities": len(entities),
            "edges": len(edges),
            "evidence": len(evidence),
            "runs": len(runs),
        },
    }
