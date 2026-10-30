from __future__ import annotations

from sqlalchemy import select

from berkas.db import AuditLog, Case, Edge, Entity, Evidence, ToolRun, new_id, utcnow


def _entity_dict(entity: Entity) -> dict:
    return {
        "id": entity.id,
        "case_id": entity.case_id,
        "type": entity.type,
        "value": entity.value,
        "normalized": entity.normalized,
        "confidence": round(entity.confidence, 2),
        "status": entity.status,
        "attributes": entity.attributes or {},
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
    }


def _edge_dict(edge: Edge) -> dict:
    return {
        "id": edge.id,
        "case_id": edge.case_id,
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "relation": edge.relation,
        "confidence": round(edge.confidence, 2),
        "attributes": edge.attributes or {},
        "created_at": edge.created_at.isoformat() if edge.created_at else None,
    }


def _run_dict(run: ToolRun) -> dict:
    return {
        "id": run.id,
        "case_id": run.case_id,
        "tool_id": run.tool_id,
        "input_entity_id": run.input_entity_id,
        "status": run.status,
        "progress": run.progress,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "result": run.result or {},
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _evidence_dict(item: Evidence) -> dict:
    return {
        "id": item.id,
        "case_id": item.case_id,
        "entity_id": item.entity_id,
        "edge_id": item.edge_id,
        "tool_run_id": item.tool_run_id,
        "source_url": item.source_url,
        "snippet": item.snippet,
        "category": item.category,
        "weight": item.weight,
        "raw": item.raw or {},
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def create_case(db, title: str, purpose: str = "", authorization_note: str = "", entities: list[dict] | None = None) -> dict:
    with db.session() as session:
        case = Case(
            id=new_id(),
            title=title[:240] or "Untitled case",
            purpose=purpose[:2000],
            authorization_note=authorization_note[:2000],
        )
        session.add(case)
        session.flush()
        for item in entities or []:
            entity = Entity(
                case_id=case.id,
                type=item.get("type", "unknown")[:32],
                value=str(item.get("value", ""))[:2000],
                normalized=str(item.get("normalized", item.get("value", "")))[:2000],
                confidence=float(item.get("confidence", 0.6)),
                status=item.get("status", "hypothesis"),
                attributes=item.get("attributes", {}),
            )
            session.add(entity)
        session.add(
            AuditLog(
                action="case.create",
                target=case.id,
                detail={"title": case.title, "purpose": purpose[:200]},
            )
        )
        session.commit()
        session.refresh(case)
        return {"id": case.id, "title": case.title, "created_at": case.created_at.isoformat() if case.created_at else None}


def list_cases(db, limit: int = 30) -> list[dict]:
    with db.session() as session:
        rows = session.execute(select(Case).order_by(Case.updated_at.desc()).limit(limit)).scalars().all()
        return [
            {
                "id": row.id,
                "title": row.title,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "entity_count": len(row.entities) if row.entities else 0,
            }
            for row in rows
        ]


def get_case(db, case_id: str) -> dict | None:
    with db.session() as session:
        case = session.get(Case, case_id)
        if not case:
            return None
        entities = session.execute(select(Entity).where(Entity.case_id == case_id)).scalars().all()
        edges = session.execute(select(Edge).where(Edge.case_id == case_id)).scalars().all()
        runs = session.execute(select(ToolRun).where(ToolRun.case_id == case_id).order_by(ToolRun.started_at.desc())).scalars().all()
        evidence = session.execute(select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.created_at.desc())).scalars().all()
        return {
            "id": case.id,
            "title": case.title,
            "purpose": case.purpose,
            "authorization_note": case.authorization_note,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            "entities": [_entity_dict(item) for item in entities],
            "edges": [_edge_dict(item) for item in edges],
            "runs": [_run_dict(item) for item in runs],
            "evidence": [_evidence_dict(item) for item in evidence],
        }


def upsert_entity(
    session,
    case_id: str,
    entity_type: str,
    value: str,
    normalized: str,
    confidence: float = 0.6,
    status: str = "hypothesis",
    attributes: dict | None = None,
) -> Entity:
    existing = session.execute(
        select(Entity).where(
            Entity.case_id == case_id,
            Entity.type == entity_type,
            Entity.normalized == normalized,
        )
    ).scalar_one_or_none()
    if existing:
        existing.confidence = max(existing.confidence, confidence)
        existing.value = existing.value or value
        if attributes:
            merged = dict(existing.attributes or {})
            merged.update(attributes)
            existing.attributes = merged
        if status == "confirmed":
            existing.status = "confirmed"
        case = session.get(Case, case_id)
        if case:
            case.updated_at = utcnow()
        return existing
    entity = Entity(
        case_id=case_id,
        type=entity_type[:32],
        value=value[:2000],
        normalized=normalized[:2000],
        confidence=confidence,
        status=status,
        attributes=attributes or {},
    )
    session.add(entity)
    session.flush()
    return entity


def add_edge(session, case_id: str, source_id: str, target_id: str, relation: str, confidence: float = 0.6, attributes: dict | None = None) -> Edge:
    existing = session.execute(
        select(Edge).where(
            Edge.case_id == case_id,
            Edge.source_id == source_id,
            Edge.target_id == target_id,
            Edge.relation == relation,
        )
    ).scalar_one_or_none()
    if existing:
        existing.confidence = max(existing.confidence, confidence)
        return existing
    edge = Edge(
        case_id=case_id,
        source_id=source_id,
        target_id=target_id,
        relation=relation[:48],
        confidence=confidence,
        attributes=attributes or {},
    )
    session.add(edge)
    session.flush()
    return edge


def add_evidence(
    session,
    case_id: str,
    *,
    entity_id: str | None = None,
    edge_id: str | None = None,
    tool_run_id: str | None = None,
    source_url: str = "",
    snippet: str = "",
    category: str = "observation",
    weight: float = 1.0,
    raw: dict | None = None,
) -> Evidence:
    item = Evidence(
        case_id=case_id,
        entity_id=entity_id,
        edge_id=edge_id,
        tool_run_id=tool_run_id,
        source_url=source_url[:2000],
        snippet=snippet[:2000],
        category=category[:48],
        weight=weight,
        raw=raw or {},
    )
    session.add(item)
    session.flush()
    return item


def create_run(db, case_id: str, tool_id: str, input_entity_id: str | None) -> dict:
    with db.session() as session:
        run = ToolRun(case_id=case_id, tool_id=tool_id, input_entity_id=input_entity_id, status="queued")
        session.add(run)
        session.commit()
        session.refresh(run)
        return _run_dict(run)


def update_run(db, run_id: str, **fields) -> dict | None:
    with db.session() as session:
        run = session.get(ToolRun, run_id)
        if not run:
            return None
        for key, value in fields.items():
            if hasattr(run, key):
                setattr(run, key, value)
        session.commit()
        session.refresh(run)
        return _run_dict(run)


def get_run(db, run_id: str) -> dict | None:
    with db.session() as session:
        run = session.get(ToolRun, run_id)
        return _run_dict(run) if run else None


def delete_case(db, case_id: str) -> bool:
    with db.session() as session:
        case = session.get(Case, case_id)
        if not case:
            return False
        session.delete(case)
        session.add(AuditLog(action="case.delete", target=case_id))
        session.commit()
        return True


def get_graph_rows(db, case_id: str):
    with db.session() as session:
        entities = session.execute(select(Entity).where(Entity.case_id == case_id)).scalars().all()
        edges = session.execute(select(Edge).where(Edge.case_id == case_id)).scalars().all()
        evidence = session.execute(select(Evidence).where(Evidence.case_id == case_id)).scalars().all()
        return (
            [_entity_dict(item) for item in entities],
            [_edge_dict(item) for item in edges],
            [_evidence_dict(item) for item in evidence],
        )
