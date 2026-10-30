from __future__ import annotations

import csv
import io
import json
import zipfile
from xml.sax.saxutils import escape as xml_escape

from berkas.services import cases
from berkas.services import summary as summary_service
from berkas.services.graph import build_findings


def _safe_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    text = str(value)
    if text[:1] in {"=", "+", "-", "@"}:
        return "'" + text
    return text


def _csv_bytes(rows: list[dict], fields: list[str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _safe_cell(row.get(field)) for field in fields})
    return buffer.getvalue().encode("utf-8-sig")


def _zip_csv(case: dict, findings: dict, summary: dict | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "entities.csv",
            _csv_bytes(case["entities"], ["id", "type", "value", "normalized", "confidence", "status", "attributes", "created_at"]),
        )
        archive.writestr(
            "edges.csv",
            _csv_bytes(case["edges"], ["id", "source_id", "target_id", "relation", "confidence", "attributes", "created_at"]),
        )
        archive.writestr(
            "evidence.csv",
            _csv_bytes(case["evidence"], ["id", "entity_id", "edge_id", "tool_run_id", "category", "weight", "source_url", "snippet", "created_at"]),
        )
        archive.writestr(
            "runs.csv",
            _csv_bytes(case["runs"], ["id", "tool_id", "input_entity_id", "status", "progress", "error_code", "error_message", "started_at", "finished_at"]),
        )
        archive.writestr("findings.json", json.dumps(findings, ensure_ascii=False, indent=2))
        if summary:
            archive.writestr("summary-public.json", json.dumps(summary, ensure_ascii=False, indent=2))
    return buffer.getvalue()


def _graphml(case: dict) -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '<key id="label" for="node" attr.name="label" attr.type="string"/>',
        '<key id="type" for="node" attr.name="type" attr.type="string"/>',
        '<key id="confidence" for="node" attr.name="confidence" attr.type="double"/>',
        '<key id="relation" for="edge" attr.name="relation" attr.type="string"/>',
        '<key id="weight" for="edge" attr.name="weight" attr.type="double"/>',
        '<graph id="berkas" edgedefault="directed">',
    ]
    for item in case["entities"]:
        lines.append(
            f'<node id="{xml_escape(item["id"])}">'
            f'<data key="label">{xml_escape(str(item["value"]))}</data>'
            f'<data key="type">{xml_escape(item["type"])}</data>'
            f'<data key="confidence">{float(item["confidence"]):.3f}</data>'
            "</node>"
        )
    for item in case["edges"]:
        lines.append(
            f'<edge source="{xml_escape(item["source_id"])}" target="{xml_escape(item["target_id"])}">'
            f'<data key="relation">{xml_escape(item["relation"])}</data>'
            f'<data key="weight">{float(item["confidence"]):.3f}</data>'
            "</edge>"
        )
    lines.append("</graph></graphml>")
    return "\n".join(lines).encode("utf-8")


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _wrap(text: str, width: int = 96) -> list[str]:
    words = str(text).replace("\r", "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _content_stream(lines: list[str]) -> bytes:
    parts = ["BT", "/F1 10 Tf", "14 TL", "45 800 Td"]
    for line in lines:
        parts.append(f"({_pdf_escape(line)}) Tj")
        parts.append("T*")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", "replace")


def _pdf(title: str, body: list[str]) -> bytes:
    lines = [title, ""] + body
    per_page = 48
    pages = [lines[index : index + per_page] for index in range(0, max(1, len(lines)), per_page)]
    objects: dict[int, bytes] = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{4 + 2 * index} 0 R" for index in range(len(pages)))
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode()
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for index, page_lines in enumerate(pages):
        page_num = 4 + 2 * index
        content_num = page_num + 1
        objects[page_num] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_num} 0 R >>"
        ).encode()
        stream = _content_stream(page_lines)
        objects[content_num] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
    total = 3 + 2 * len(pages)
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (total + 1)
    for number in range(1, total + 1):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {total + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for number in range(1, total + 1):
        out += f"{offsets[number]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {total + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return bytes(out)


def _summary_lines(summary: dict) -> list[str]:
    citations = {item.get("id"): item for item in summary.get("citations", [])}
    lines = ["RINGKASAN UNTUK PEMBACA AWAM", ""]
    headline = summary.get("headline") or "Ringkasan kasus"
    lines.extend(_wrap(headline, 92))
    lines.append("")
    plain = summary.get("confidence", {}).get("plain", "")
    if plain:
        lines.extend(_wrap(plain, 92))
        lines.append("")
    for point in summary.get("points", []):
        lines.extend(_wrap(f"- {point.get('text', '')}", 92))
        labels = [
            citations[item].get("category", "bukti")
            for item in point.get("citation_ids", [])
            if item in citations
        ]
        if labels:
            lines.extend(_wrap(f"    Bukti: {', '.join(labels)}", 92))
    narrative = summary.get("narrative", [])
    if narrative:
        lines.append("")
        lines.append("NARATIF")
        for paragraph in narrative:
            lines.extend(_wrap(paragraph.get("text", ""), 92))
            lines.append("")
    glossary = summary.get("glossary", [])
    if glossary:
        lines.append("ISTILAH")
        for item in glossary[:6]:
            lines.extend(_wrap(f"- {item.get('term')}: {item.get('meaning')}", 92))
        lines.append("")
    limits = summary.get("limits", [])
    if limits:
        lines.append("BATASAN")
        for item in limits[:5]:
            lines.extend(_wrap(f"- {item}", 92))
        lines.append("")
    analyst = summary.get("analyst", {})
    notes = analyst.get("notes", [])
    if notes:
        lines.append("LAMPIRAN ANALIS")
        for item in notes[:6]:
            lines.extend(_wrap(f"- {item.get('text', '')}", 92))
        steps = analyst.get("next_steps", [])
        if steps:
            lines.append("")
            lines.append("Pemeriksaan berikutnya")
            for item in steps[:6]:
                lines.extend(_wrap(f"- {item}", 92))
        lines.append("")
    notice = summary.get("notice")
    if notice:
        lines.extend(_wrap(notice, 92))
    lines.append("")
    return lines


def _report_lines(case: dict, findings: dict, summary: dict | None = None) -> list[str]:
    confidence = findings.get("confidence", {})
    lines = [
        f"Case ID: {case['id']}",
        f"Dibuat: {case.get('created_at') or '-'}",
        f"Diperbarui: {case.get('updated_at') or '-'}",
        f"Tujuan: {case.get('purpose') or '-'}",
        f"Dasar kewenangan: {case.get('authorization_note') or '-'}",
        "",
    ]
    if summary:
        lines.extend(_summary_lines(summary))
    lines.extend([
        "RINGKASAN TEMUAN",
        f"Skor keyakinan: {confidence.get('score', 0)}/100 ({confidence.get('band', 'Low')})",
        f"Entity: {findings.get('counts', {}).get('entities', 0)} | "
        f"Relasi: {findings.get('counts', {}).get('edges', 0)} | "
        f"Bukti: {findings.get('counts', {}).get('evidence', 0)} | "
        f"Sumber: {confidence.get('source_count', 0)}",
    ])
    for reason in confidence.get("why", []):
        lines.append(f"  {reason}")
    lines.append("")
    lines.append("IDENTITAS KANDIDAT")
    identities = findings.get("identities", [])
    if identities:
        for item in identities[:8]:
            lines.append(f"  [{item.get('score')}/100 {item.get('band')}] {item.get('name')}: {item.get('connections')} relasi")
            for alias in item.get("aliases", [])[:5]:
                lines.append(f"      {alias.get('type')}: {alias.get('value')}")
    else:
        lines.append("  Belum ada kandidat identitas.")
    lines.append("")
    lines.append("CLUE UTAMA")
    clues = findings.get("clues", [])
    if clues:
        for item in clues[:12]:
            lines.append(f"  - [{item.get('category')}] {item.get('snippet')}")
            if item.get("source_url"):
                lines.append(f"      {item.get('source_url')}")
    else:
        lines.append("  Belum ada bukti.")
    lines.append("")
    lines.append("PERINGATAN")
    for warning in findings.get("warnings", [])[:10]:
        lines.extend(_wrap(f"- {warning}"))
    lines.append("")
    lines.append("PIVOT BERIKUTNYA")
    for item in findings.get("next_pivots", [])[:10]:
        lines.append(f"  - {item.get('label')} untuk {item.get('entity_type')}: {item.get('entity_value')}")
    lines.append("")
    lines.append("DAFTAR ENTITY")
    for item in case["entities"][:160]:
        lines.append(f"  [{item['type']}] {item['value']} (conf {item['confidence']})")
    lines.append("")
    lines.append("RELASI")
    entity_by_id = {item["id"]: item for item in case["entities"]}
    for item in case["edges"][:160]:
        source = entity_by_id.get(item["source_id"], {}).get("value", item["source_id"])
        target = entity_by_id.get(item["target_id"], {}).get("value", item["target_id"])
        lines.append(f"  {source} --{item['relation']}--> {target}")
    return lines


def build_export(db, case_id: str, fmt: str, settings=None) -> tuple[bytes, str, str] | None:
    case = cases.get_case(db, case_id)
    if not case:
        return None
    findings = build_findings(db, case_id)
    public_summary = None
    if settings is not None:
        try:
            public_summary = summary_service.build_summary(db, settings, case, findings, "public")
        except Exception:  # noqa: BLE001 - export must still work without AI or cache
            public_summary = None
    base = f"berkas-{case_id[:8]}"
    fmt = (fmt or "json").lower()
    if fmt == "json":
        payload = {"case": case, "findings": findings, "summary": public_summary, "exported_by": "Berkas"}
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "application/json", f"{base}.json"
    if fmt == "csv":
        return _zip_csv(case, findings, public_summary), "application/zip", f"{base}-csv.zip"
    if fmt == "graphml":
        return _graphml(case), "application/graphml+xml", f"{base}.graphml"
    if fmt == "pdf":
        title = f"BERKAS - {case['title']}"
        return _pdf(title, _report_lines(case, findings, public_summary)), "application/pdf", f"{base}.pdf"
    return None
