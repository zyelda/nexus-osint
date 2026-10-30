from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from berkas.db import utcnow
from berkas.entities import tools_for_type
from berkas.services import cache, cases
from berkas.services.graph import build_findings, ingest_result
from berkas.tools.base import ToolResult, fail
from berkas.tools.registry import registry


class EventBus:
    """In-process fan-out for Server-Sent Events per case."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[queue.Queue]] = {}
        self._lock = threading.Lock()

    def subscribe(self, case_id: str) -> queue.Queue:
        channel: queue.Queue = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.setdefault(case_id, set()).add(channel)
        return channel

    def unsubscribe(self, case_id: str, channel: queue.Queue) -> None:
        with self._lock:
            bucket = self._subscribers.get(case_id)
            if not bucket:
                return
            bucket.discard(channel)
            if not bucket:
                self._subscribers.pop(case_id, None)

    def publish(self, case_id: str, event: dict) -> None:
        payload = {"at": utcnow().isoformat(), **event}
        with self._lock:
            channels = list(self._subscribers.get(case_id, ()))
        for channel in channels:
            try:
                channel.put_nowait(payload)
            except queue.Full:
                try:
                    channel.get_nowait()
                    channel.put_nowait(payload)
                except queue.Empty:
                    pass


bus = EventBus()

_DB_LOCK = threading.RLock()
_ACTIVE: dict[str, threading.Thread] = {}
_ACTIVE_LOCK = threading.Lock()


def tool_context(settings) -> dict:
    return {
        "vt_api_key": settings.vt_api_key,
        "shodan_api_key": settings.shodan_api_key,
        "abuseipdb_api_key": settings.abuseipdb_api_key,
        "hibp_api_key": settings.hibp_api_key,
        "groq_api_key": settings.groq_api_key,
    }


def _spec_for(entity_type: str, value: str) -> list[str]:
    tool_ids = list(tools_for_type(entity_type))
    lowered = value.lower()
    if entity_type == "url" and ("youtube.com" in lowered or "youtu.be" in lowered):
        tool_ids.append("youtube_intel")
    return tool_ids


def plan_jobs(
    db,
    case_id: str,
    entity_ids: list[str] | None = None,
    tool_ids: list[str] | None = None,
    skip_existing: bool = True,
) -> list[dict]:
    case = cases.get_case(db, case_id)
    if not case:
        return []
    selected = case["entities"]
    if entity_ids:
        wanted = set(entity_ids)
        selected = [item for item in selected if item["id"] in wanted]
    finished = set()
    if skip_existing:
        for run in case["runs"]:
            if run["status"] in {"success", "partial", "not_found"}:
                finished.add((run["tool_id"], run["input_entity_id"]))
    wanted_tools = set(tool_ids) if tool_ids else None
    jobs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in selected:
        for tool_id in _spec_for(item["type"], item["value"]):
            spec = registry.get(tool_id)
            if not spec:
                continue
            if wanted_tools is not None and tool_id not in wanted_tools:
                continue
            key = (tool_id, item["id"])
            if key in seen or (skip_existing and key in finished):
                continue
            seen.add(key)
            jobs.append(
                {
                    "tool_id": tool_id,
                    "tool_label": spec.label,
                    "entity_id": item["id"],
                    "entity_type": item["type"],
                    "entity_value": item["value"],
                    "timeout_s": spec.timeout_s,
                }
            )
    return jobs


def _run_tool_with_timeout(spec, value: str, ctx: dict, timeout_s: int) -> ToolResult:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(spec.run, value, ctx)
    try:
        return future.result(timeout=timeout_s)
    except FutureTimeout:
        return fail("timeout", f"{spec.label} melebihi batas {timeout_s} detik.")
    except Exception as exc:  # noqa: BLE001 - tool isolation boundary
        return fail("tool_error", f"{type(exc).__name__}: {exc}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _execute_job(db, settings, case_id: str, run_id: str, job: dict, ctx: dict) -> None:
    spec = registry.get(job["tool_id"])
    started = utcnow()
    with _DB_LOCK:
        cases.update_run(db, run_id, status="running", progress=10, started_at=started)
    bus.publish(case_id, {"type": "run.started", "run_id": run_id, "tool_id": job["tool_id"], "entity_id": job["entity_id"]})

    if spec is None:
        result = fail("unknown_tool", f"Tool {job['tool_id']} tidak terdaftar.")
    else:
        result = cache.get_tool_result(db, spec.id, job["entity_value"], settings.tool_cache_ttl)
        if result is None:
            result = _run_tool_with_timeout(spec, job["entity_value"], ctx, job["timeout_s"])
            with _DB_LOCK:
                try:
                    cache.put_tool_result(db, spec.id, job["entity_value"], result)
                except Exception:  # noqa: BLE001 - cache is an optimization, never fatal
                    pass

    with _DB_LOCK:
        try:
            delta = ingest_result(db, case_id, run_id, job["entity_id"], result)
        except Exception as exc:  # noqa: BLE001 - keep worker alive
            delta = {"entities": 0, "edges": 0, "evidence": 0}
            result = fail("ingest_error", f"Gagal menyimpan hasil: {exc}")
        status = result.status if result.status != "error" else "error"
        cases.update_run(
            db,
            run_id,
            status=status,
            progress=100,
            finished_at=utcnow(),
            error_code=result.error_code,
            error_message=result.error_message,
        )
        try:
            findings = build_findings(db, case_id)
        except Exception:  # noqa: BLE001 - findings are derived, never fatal
            findings = {}

    bus.publish(
        case_id,
        {
            "type": "run.finished",
            "run_id": run_id,
            "tool_id": job["tool_id"],
            "entity_id": job["entity_id"],
            "status": status,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "warnings": result.warnings[:4],
            "delta": delta,
        },
    )
    bus.publish(case_id, {"type": "graph.updated", "run_id": run_id, "delta": delta})
    if findings:
        bus.publish(case_id, {"type": "findings.updated", "findings": findings})


def _coordinator(db, settings, case_id: str, run_ids: list[str], jobs: list[dict], ctx: dict) -> None:
    try:
        with ThreadPoolExecutor(max_workers=max(1, settings.max_workers)) as executor:
            futures = [
                executor.submit(_execute_job, db, settings, case_id, run_id, job, ctx)
                for run_id, job in zip(run_ids, jobs)
            ]
            for future in futures:
                future.result()
    finally:
        with _DB_LOCK:
            try:
                findings = build_findings(db, case_id)
            except Exception:  # noqa: BLE001
                findings = {}
        bus.publish(case_id, {"type": "runs.completed", "case_id": case_id, "findings": findings})
        with _ACTIVE_LOCK:
            _ACTIVE.pop(case_id, None)


def batch_limit(settings) -> int:
    return max(1, int(getattr(settings, "max_runs_per_batch", 12)))


def start_runs(db, settings, case_id: str, jobs: list[dict], limit: int | None = None) -> list[dict]:
    if not jobs:
        return []
    cap = batch_limit(settings) if limit is None else max(1, limit)
    jobs = jobs[:cap]
    created: list[dict] = []
    for job in jobs:
        run = cases.create_run(db, case_id, job["tool_id"], job["entity_id"])
        created.append(run)
    ctx = tool_context(settings)
    run_ids = [item["id"] for item in created]
    thread = threading.Thread(
        target=_coordinator,
        args=(db, settings, case_id, run_ids, jobs, ctx),
        name=f"berkas-runs-{case_id[:8]}",
        daemon=True,
    )
    with _ACTIVE_LOCK:
        _ACTIVE[case_id] = thread
    thread.start()
    bus.publish(case_id, {"type": "runs.queued", "count": len(created), "case_id": case_id})
    return created


def is_running(case_id: str) -> bool:
    with _ACTIVE_LOCK:
        thread = _ACTIVE.get(case_id)
    return bool(thread and thread.is_alive())


def ingest_file_run(db, settings, case_id: str, filename: str, result: ToolResult, input_entity_id: str | None = None) -> dict:
    run = cases.create_run(db, case_id, "file_ingest", input_entity_id)
    run_id = run["id"]
    with _DB_LOCK:
        cases.update_run(db, run_id, status="running", progress=20, started_at=utcnow())
    bus.publish(case_id, {"type": "run.started", "run_id": run_id, "tool_id": "file_ingest", "entity_id": input_entity_id})
    with _DB_LOCK:
        delta = ingest_result(db, case_id, run_id, input_entity_id, result)
        cases.update_run(
            db,
            run_id,
            status=result.status,
            progress=100,
            finished_at=utcnow(),
            error_code=result.error_code,
            error_message=result.error_message,
        )
        try:
            findings = build_findings(db, case_id)
        except Exception:  # noqa: BLE001
            findings = {}
    bus.publish(
        case_id,
        {
            "type": "run.finished",
            "run_id": run_id,
            "tool_id": "file_ingest",
            "entity_id": input_entity_id,
            "status": result.status,
            "filename": filename,
            "warnings": result.warnings[:4],
            "delta": delta,
        },
    )
    bus.publish(case_id, {"type": "graph.updated", "run_id": run_id, "delta": delta})
    if findings:
        bus.publish(case_id, {"type": "findings.updated", "findings": findings})
    return {"run_id": run_id, "delta": delta, "status": result.status}
