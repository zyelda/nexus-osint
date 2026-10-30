from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import asdict

from sqlalchemy import delete, select

from berkas.db import SummaryCache, ToolCache, json_default, utcnow
from berkas.tools.base import ToolEdge, ToolEntity, ToolEvidence, ToolResult

CACHEABLE_STATUSES = {"success", "partial", "not_found"}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _age_seconds(created_at: dt.datetime | None) -> float:
    if created_at is None:
        return float("inf")
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=dt.timezone.utc)
    return (utcnow() - created_at).total_seconds()


def _json_safe(value):
    return json.loads(json.dumps(value, default=json_default, ensure_ascii=False))


def _normalize_value(value: str) -> str:
    text = value.strip()
    # URL paths can be case sensitive, so only fold case for hosts, emails,
    # usernames, and other plain values.
    return text if "://" in text else text.lower()


def tool_cache_key(tool_id: str, value: str) -> str:
    return _digest(f"tool|{tool_id}|{_normalize_value(value)}")


def _result_to_payload(result: ToolResult) -> dict:
    return _json_safe(
        {
            "status": result.status,
            "data": result.data,
            "warnings": result.warnings,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "entities": [asdict(item) for item in result.entities],
            "edges": [asdict(item) for item in result.edges],
            "evidence": [asdict(item) for item in result.evidence],
        }
    )


def _payload_to_result(payload: dict) -> ToolResult:
    return ToolResult(
        status=str(payload.get("status", "success")),
        data=payload.get("data") or {},
        warnings=[str(item) for item in payload.get("warnings") or []],
        error_code=str(payload.get("error_code", "")),
        error_message=str(payload.get("error_message", "")),
        entities=[ToolEntity(**item) for item in payload.get("entities") or []],
        edges=[ToolEdge(**item) for item in payload.get("edges") or []],
        evidence=[ToolEvidence(**item) for item in payload.get("evidence") or []],
    )


def get_tool_result(db, tool_id: str, value: str, ttl: int) -> ToolResult | None:
    if ttl <= 0:
        return None
    key = tool_cache_key(tool_id, value)
    with db.session() as session:
        row = session.get(ToolCache, key)
        if not row:
            return None
        if _age_seconds(row.created_at) > ttl:
            session.delete(row)
            session.commit()
            return None
        try:
            result = _payload_to_result(row.payload or {})
        except (TypeError, ValueError):
            session.delete(row)
            session.commit()
            return None
    result.warnings.append("Hasil diambil dari cache lokal, bukan pengambilan baru.")
    return result


def put_tool_result(db, tool_id: str, value: str, result: ToolResult) -> None:
    if result.status not in CACHEABLE_STATUSES:
        return
    key = tool_cache_key(tool_id, value)
    payload = _result_to_payload(result)
    with db.session() as session:
        row = session.get(ToolCache, key)
        if row:
            row.payload = payload
            row.created_at = utcnow()
        else:
            session.add(ToolCache(key=key, tool_id=tool_id, payload=payload))
        session.commit()


def summary_cache_key(case_id: str, audience: str, fingerprint: str) -> str:
    return _digest(f"summary-v3|{case_id}|{audience}|{fingerprint}")


def get_summary(db, key: str, ttl: int) -> dict | None:
    if ttl <= 0:
        return None
    with db.session() as session:
        row = session.get(SummaryCache, key)
        if not row:
            return None
        if _age_seconds(row.created_at) > ttl:
            session.delete(row)
            session.commit()
            return None
        return dict(row.payload or {})


def put_summary(db, key: str, case_id: str, audience: str, payload: dict) -> None:
    with db.session() as session:
        row = session.get(SummaryCache, key)
        if row:
            row.payload = _json_safe(payload)
            row.created_at = utcnow()
        else:
            session.add(
                SummaryCache(
                    key=key,
                    case_id=case_id,
                    audience=audience,
                    payload=_json_safe(payload),
                )
            )
        session.commit()


def clear_case_summaries(db, case_id: str) -> None:
    with db.session() as session:
        session.execute(delete(SummaryCache).where(SummaryCache.case_id == case_id))
        session.commit()


def purge_expired(db, tool_ttl: int, summary_ttl: int) -> dict:
    now = utcnow()
    removed = {"tools": 0, "summaries": 0}
    with db.session() as session:
        if tool_ttl > 0:
            cutoff = now - dt.timedelta(seconds=tool_ttl)
            result = session.execute(delete(ToolCache).where(ToolCache.created_at < cutoff))
            removed["tools"] = result.rowcount or 0
        if summary_ttl > 0:
            cutoff = now - dt.timedelta(seconds=summary_ttl)
            result = session.execute(delete(SummaryCache).where(SummaryCache.created_at < cutoff))
            removed["summaries"] = result.rowcount or 0
        session.commit()
    return removed


def cache_stats(db) -> dict:
    with db.session() as session:
        tools = session.execute(select(ToolCache)).scalars().all()
        summaries = session.execute(select(SummaryCache)).scalars().all()
    oldest_tool = min((item.created_at for item in tools), default=None)
    oldest_summary = min((item.created_at for item in summaries), default=None)
    return {
        "tool_entries": len(tools),
        "summary_entries": len(summaries),
        "oldest_tool": oldest_tool.isoformat() if oldest_tool else None,
        "oldest_summary": oldest_summary.isoformat() if oldest_summary else None,
    }
