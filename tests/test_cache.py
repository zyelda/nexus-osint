from __future__ import annotations

import datetime as dt

from berkas.db import ToolCache, utcnow
from berkas.services import cache
from berkas.tools.base import ToolEdge, ToolEntity, ToolEvidence, ToolResult, fail


def _result() -> ToolResult:
    return ToolResult(
        status="success",
        data={"value": "contoh"},
        entities=[ToolEntity(type="domain", value="example.com", normalized="example.com", key="domain:example.com")],
        edges=[ToolEdge(source_key="input", target_key="domain:example.com", relation="resolves_to")],
        evidence=[ToolEvidence(category="dns", weight=2.0, source_url="https://dns.google", snippet="A record")],
        warnings=["catatan"],
    )


def test_tool_cache_roundtrip(app):
    db = app.extensions["berkas"]["db"]
    cache.put_tool_result(db, "domain_dns", "Example.COM", _result())
    hit = cache.get_tool_result(db, "domain_dns", "example.com", 3600)
    assert hit is not None
    assert hit.status == "success"
    assert hit.data["value"] == "contoh"
    assert hit.entities[0].key == "domain:example.com"
    assert hit.edges[0].relation == "resolves_to"
    assert hit.evidence[0].category == "dns"
    assert any("cache lokal" in warning for warning in hit.warnings)


def test_tool_cache_respects_ttl(app):
    db = app.extensions["berkas"]["db"]
    cache.put_tool_result(db, "domain_dns", "example.com", _result())
    key = cache.tool_cache_key("domain_dns", "example.com")
    with db.session() as session:
        row = session.get(ToolCache, key)
        row.created_at = utcnow() - dt.timedelta(seconds=120)
        session.commit()
    assert cache.get_tool_result(db, "domain_dns", "example.com", 60) is None
    assert cache.get_tool_result(db, "domain_dns", "example.com", 0) is None


def test_tool_cache_skips_failures(app):
    db = app.extensions["berkas"]["db"]
    cache.put_tool_result(db, "domain_dns", "example.com", fail("timeout", "terlalu lama"))
    assert cache.get_tool_result(db, "domain_dns", "example.com", 3600) is None


def test_summary_cache_roundtrip(app):
    db = app.extensions["berkas"]["db"]
    key = cache.summary_cache_key("case-1", "public", "fingerprint")
    cache.put_summary(db, key, "case-1", "public", {"headline": "Uji", "cached": False})
    hit = cache.get_summary(db, key, 3600)
    assert hit is not None
    assert hit["headline"] == "Uji"
    assert cache.get_summary(db, key, 0) is None


def test_purge_expired_removes_old_entries(app):
    db = app.extensions["berkas"]["db"]
    cache.put_tool_result(db, "domain_dns", "example.com", _result())
    key = cache.tool_cache_key("domain_dns", "example.com")
    with db.session() as session:
        row = session.get(ToolCache, key)
        row.created_at = utcnow() - dt.timedelta(days=2)
        session.commit()
    removed = cache.purge_expired(db, 3600, 3600)
    assert removed["tools"] >= 1
