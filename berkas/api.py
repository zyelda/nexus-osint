from __future__ import annotations

import hmac
import json
import os
import queue
import shutil
import uuid

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from werkzeug.exceptions import HTTPException

from berkas.entities import entity_from_value, parse_text, tools_for_type
from berkas.security import sanitize_filename
from berkas.services import ai, cache, cases, orchestrator, reports
from berkas.services import summary as summary_service
from berkas.services.graph import build_findings
from berkas.tools.files import ingest_file
from berkas.tools.registry import registry

api = Blueprint("api", __name__, url_prefix="/api/v1")


def _ctx() -> dict:
    return current_app.extensions["berkas"]


def _db():
    return _ctx()["db"]


def _settings():
    return _ctx()["settings"]


@api.before_request
def _check_token():
    token = _settings().api_token
    if not token:
        return None
    if request.method == "OPTIONS" or request.path == "/api/v1/health":
        return None
    supplied = (
        request.headers.get("X-Berkas-Token")
        or request.headers.get("X-Nexus-Token")
        or request.args.get("token", "")
    )
    if not hmac.compare_digest(token, supplied or ""):
        return jsonify({"error": "unauthorized", "message": "Token tidak valid."}), 401
    return None


@api.errorhandler(Exception)
def _api_error(exc):
    if isinstance(exc, HTTPException):
        return jsonify({"error": exc.name.lower().replace(" ", "_"), "message": exc.description}), exc.code
    current_app.logger.exception("API error")
    return jsonify({"error": "internal_error", "message": "Terjadi kesalahan internal. Periksa log server."}), 500


def _entity_payload(item) -> dict:
    return {
        "type": item.type,
        "value": item.value,
        "normalized": item.normalized,
        "confidence": round(item.confidence, 2),
        "source": item.source,
        "attributes": item.attributes,
    }


def _dedupe(entities: list[dict]) -> list[dict]:
    seen = set()
    output = []
    for item in entities:
        key = (item.get("type"), item.get("normalized") or item.get("value"))
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


@api.get("/health")
def health():
    settings = _settings()
    return jsonify(
        {
            "status": "ok",
            "version": "2.0.0",
            "environment": settings.environment,
            "tools": len(registry.all()),
            "auth_required": bool(settings.api_token),
            "cache": cache.cache_stats(_db()),
        }
    )


@api.get("/keys/health")
def keys_health():
    settings = _settings()
    provider = ai.resolve_provider(settings)
    key_specs = [
        ("GROQ_API_KEY", "groq_api_key", "Ringkasan AI lewat Groq"),
        ("OPENAI_API_KEY", "openai_api_key", "Ringkasan AI lewat provider OpenAI-compatible"),
        ("VT_API_KEY", "vt_api_key", "Reputasi URL VirusTotal"),
        ("SHODAN_API_KEY", "shodan_api_key", "Data host Shodan"),
        ("ABUSEIPDB_API_KEY", "abuseipdb_api_key", "Reputasi IP AbuseIPDB"),
        ("HIBP_API_KEY", "hibp_api_key", "Cek kebocoran email"),
    ]
    keys = [
        {"name": name, "configured": bool(getattr(settings, attribute, "")), "purpose": purpose}
        for name, attribute, purpose in key_specs
    ]
    return jsonify(
        {
            "keys": keys,
            "ai": {
                "provider": provider.name if provider else "local",
                "model": provider.model if provider else "",
                "ready": provider is not None,
            },
            "public_redaction": settings.public_redaction,
            "tool_cache_ttl": settings.tool_cache_ttl,
            "summary_cache_ttl": settings.summary_cache_ttl,
            "max_runs_per_batch": settings.max_runs_per_batch,
        }
    )


@api.get("/tools")
def tools():
    return jsonify({"tools": registry.public(_settings())})


@api.post("/intake/parse")
def intake_parse():
    body = request.get_json(silent=True) or {}
    text = str(body.get("text", ""))[:20000]
    parsed = [_entity_payload(item) for item in parse_text(text)]
    plan = []
    for item in parsed:
        plan.append(
            {
                "type": item["type"],
                "value": item["value"],
                "tools": [
                    {"id": tool_id, "label": registry.get(tool_id).label if registry.get(tool_id) else tool_id}
                    for tool_id in tools_for_type(item["type"])
                ],
            }
        )
    return jsonify({"entities": parsed, "plan": plan, "count": len(parsed)})


@api.get("/cases")
def list_cases():
    return jsonify({"cases": cases.list_cases(_db())})


@api.post("/cases")
def create_case():
    body = request.get_json(silent=True) or {}
    text = str(body.get("text", ""))[:20000]
    parsed = [_entity_payload(item) for item in parse_text(text)]
    explicit = body.get("entities") or []
    for item in explicit:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        if not value:
            continue
        entity_type = str(item.get("type", "")).strip() or None
        candidate = entity_from_value(value, entity_type)
        if not candidate:
            continue
        payload = _entity_payload(candidate)
        if item.get("normalized"):
            payload["normalized"] = str(item["normalized"])[:2000]
        try:
            payload["confidence"] = max(0.0, min(1.0, float(item.get("confidence", payload["confidence"]))))
        except (TypeError, ValueError):
            pass
        payload["source"] = str(item.get("source", "explicit"))[:32]
        parsed.append(payload)
    parsed = _dedupe(parsed)
    if not parsed:
        return jsonify({"error": "no_entities", "message": "Tidak ada entity yang bisa diparse dari input."}), 400

    title = str(body.get("title", "")).strip()
    if not title:
        first = next((item for item in parsed if item["type"] in {"person", "email", "domain", "username", "phone"}), parsed[0])
        title = f"Kasus {first['value']}"[:240]
    case = cases.create_case(
        _db(),
        title=title,
        purpose=str(body.get("purpose", ""))[:2000],
        authorization_note=str(body.get("authorization_note", ""))[:2000],
        entities=parsed,
    )
    detail = cases.get_case(_db(), case["id"])
    jobs = orchestrator.plan_jobs(_db(), case["id"], skip_existing=True)
    runs = []
    if body.get("autorun", True) and jobs:
        runs = orchestrator.start_runs(_db(), _settings(), case["id"], jobs)
    return jsonify({"case": detail, "jobs": jobs, "runs": runs, "deferred": max(0, len(jobs) - len(runs))}), 201


@api.get("/cases/<case_id>")
def get_case(case_id: str):
    detail = cases.get_case(_db(), case_id)
    if not detail:
        return jsonify({"error": "not_found", "message": "Kasus tidak ditemukan."}), 404
    return jsonify({"case": detail})


@api.delete("/cases/<case_id>")
def delete_case(case_id: str):
    if not cases.delete_case(_db(), case_id):
        return jsonify({"error": "not_found", "message": "Kasus tidak ditemukan."}), 404
    folder = os.path.join(_settings().upload_folder, case_id)
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)
    return jsonify({"deleted": True})


@api.post("/cases/<case_id>/entities")
def add_entity(case_id: str):
    if not cases.get_case(_db(), case_id):
        return jsonify({"error": "not_found", "message": "Kasus tidak ditemukan."}), 404
    body = request.get_json(silent=True) or {}
    value = str(body.get("value", "")).strip()
    if not value:
        return jsonify({"error": "invalid_input", "message": "Value wajib diisi."}), 400
    candidate = entity_from_value(value, body.get("type") or None)
    if not candidate:
        return jsonify({"error": "invalid_input", "message": "Entity tidak bisa diparse."}), 400
    with _db().session() as session:
        row = cases.upsert_entity(
            session,
            case_id,
            candidate.type,
            candidate.value,
            candidate.normalized,
            candidate.confidence,
            attributes=candidate.attributes,
        )
        session.commit()
        entity = {
            "id": row.id,
            "type": row.type,
            "value": row.value,
            "normalized": row.normalized,
            "confidence": round(row.confidence, 2),
            "status": row.status,
            "attributes": row.attributes or {},
        }
    orchestrator.bus.publish(case_id, {"type": "graph.updated", "delta": {"entities": 1, "edges": 0, "evidence": 0}})
    return jsonify({"entity": entity}), 201


@api.post("/cases/<case_id>/runs")
def start_runs(case_id: str):
    if not cases.get_case(_db(), case_id):
        return jsonify({"error": "not_found", "message": "Kasus tidak ditemukan."}), 404
    if orchestrator.is_running(case_id):
        return jsonify({"error": "busy", "message": "Masih ada tool yang berjalan untuk kasus ini."}), 409
    body = request.get_json(silent=True) or {}
    jobs = orchestrator.plan_jobs(
        _db(),
        case_id,
        entity_ids=body.get("entity_ids") or None,
        tool_ids=body.get("tool_ids") or None,
        skip_existing=bool(body.get("skip_existing", True)),
    )
    runs = orchestrator.start_runs(_db(), _settings(), case_id, jobs)
    return jsonify(
        {
            "jobs": jobs[: len(runs)],
            "runs": runs,
            "count": len(runs),
            "deferred": max(0, len(jobs) - len(runs)),
            "limit": orchestrator.batch_limit(_settings()),
        }
    ), 201


@api.post("/cases/<case_id>/pivot")
def pivot(case_id: str):
    detail = cases.get_case(_db(), case_id)
    if not detail:
        return jsonify({"error": "not_found", "message": "Kasus tidak ditemukan."}), 404
    if orchestrator.is_running(case_id):
        return jsonify({"error": "busy", "message": "Masih ada tool yang berjalan untuk kasus ini."}), 409
    body = request.get_json(silent=True) or {}
    entity_id = str(body.get("entity_id", ""))
    tool_id = str(body.get("tool_id", ""))
    entity = next((item for item in detail["entities"] if item["id"] == entity_id), None)
    if not entity:
        return jsonify({"error": "invalid_entity", "message": "Entity bukan bagian dari kasus ini."}), 400
    spec = registry.get(tool_id)
    if not spec or entity["type"] not in spec.inputs:
        return jsonify({"error": "invalid_tool", "message": "Tool tidak cocok dengan tipe entity."}), 400
    jobs = [
        {
            "tool_id": tool_id,
            "tool_label": spec.label,
            "entity_id": entity["id"],
            "entity_type": entity["type"],
            "entity_value": entity["value"],
            "timeout_s": spec.timeout_s,
        }
    ]
    runs = orchestrator.start_runs(_db(), _settings(), case_id, jobs)
    return jsonify({"jobs": jobs, "runs": runs}), 201


@api.post("/cases/<case_id>/files")
def upload_files(case_id: str):
    if not cases.get_case(_db(), case_id):
        return jsonify({"error": "not_found", "message": "Kasus tidak ditemukan."}), 404
    uploads = request.files.getlist("files")
    if not uploads:
        return jsonify({"error": "no_files", "message": "Tidak ada file yang diunggah."}), 400
    settings = _settings()
    target_dir = os.path.join(settings.upload_folder, case_id)
    os.makedirs(target_dir, exist_ok=True)
    results = []
    for storage in uploads[:8]:
        if not storage or not storage.filename:
            continue
        safe_name = sanitize_filename(storage.filename)
        stored_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        path = os.path.join(target_dir, stored_name)
        storage.save(path)
        result = ingest_file(path, storage.filename)
        run_info = orchestrator.ingest_file_run(_db(), settings, case_id, storage.filename, result)
        results.append(
            {
                "filename": storage.filename,
                "stored_as": stored_name,
                "status": result.status,
                "error": result.error_message,
                "warnings": result.warnings,
                "data": result.data,
                "entities": [item.key for item in result.entities],
                "run": run_info,
            }
        )
    return jsonify({"files": results, "count": len(results)}), 201


@api.get("/cases/<case_id>/graph")
def graph(case_id: str):
    detail = cases.get_case(_db(), case_id)
    if not detail:
        return jsonify({"error": "not_found", "message": "Kasus tidak ditemukan."}), 404
    nodes = [
        {
            "data": {
                "id": item["id"],
                "label": item["value"],
                "type": item["type"],
                "confidence": item["confidence"],
                "status": item["status"],
                "normalized": item["normalized"],
                "attributes": item["attributes"],
            }
        }
        for item in detail["entities"]
    ]
    edges = [
        {
            "data": {
                "id": item["id"],
                "source": item["source_id"],
                "target": item["target_id"],
                "relation": item["relation"],
                "confidence": item["confidence"],
            }
        }
        for item in detail["edges"]
    ]
    findings = build_findings(_db(), case_id)
    return jsonify(
        {
            "case": {
                "id": detail["id"],
                "title": detail["title"],
                "purpose": detail["purpose"],
                "authorization_note": detail["authorization_note"],
                "created_at": detail["created_at"],
                "updated_at": detail["updated_at"],
            },
            "nodes": nodes,
            "edges": edges,
            "findings": findings,
            "runs": detail["runs"],
        }
    )


@api.get("/cases/<case_id>/findings")
def findings(case_id: str):
    if not cases.get_case(_db(), case_id):
        return jsonify({"error": "not_found", "message": "Kasus tidak ditemukan."}), 404
    return jsonify({"findings": build_findings(_db(), case_id)})


@api.get("/cases/<case_id>/summary")
def summary(case_id: str):
    detail = cases.get_case(_db(), case_id)
    if not detail:
        return jsonify({"error": "not_found", "message": "Kasus tidak ditemukan."}), 404
    audience = request.args.get("audience", "public").strip().lower()
    if audience not in summary_service.AUDIENCES:
        return jsonify({"error": "invalid_audience", "message": "Audience harus public atau analyst."}), 400
    refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
    findings = build_findings(_db(), case_id)
    return jsonify(summary_service.build_summary(_db(), _settings(), detail, findings, audience, refresh))


@api.get("/cases/<case_id>/events")
def events(case_id: str):
    if not cases.get_case(_db(), case_id):
        return jsonify({"error": "not_found", "message": "Kasus tidak ditemukan."}), 404
    channel = orchestrator.bus.subscribe(case_id)

    @stream_with_context
    def stream():
        try:
            snapshot = build_findings(_db(), case_id)
            yield f"retry: 3000\ndata: {json.dumps({'type': 'hello', 'case_id': case_id, 'findings': snapshot}, ensure_ascii=False)}\n\n"
            while True:
                try:
                    event = channel.get(timeout=15)
                except queue.Empty:
                    yield ": heartbeat\n\n"
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except GeneratorExit:
            raise
        finally:
            orchestrator.bus.unsubscribe(case_id, channel)

    response = Response(stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response


@api.get("/cases/<case_id>/export")
def export_case(case_id: str):
    fmt = request.args.get("format", "json")
    payload = reports.build_export(_db(), case_id, fmt, _settings())
    if not payload:
        return jsonify({"error": "invalid_format", "message": "Format harus json, csv, pdf, atau graphml."}), 400
    data, mimetype, filename = payload
    return Response(
        data,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
