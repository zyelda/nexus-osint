from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from berkas.services import ai, cache

AUDIENCES = {"public", "analyst"}

EMAIL_RE = re.compile(r"([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
NIK_RE = re.compile(r"(?<!\d)(\d{4})\d{8}(\d{4})(?!\d)")
NPWP_RE = re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)((?:\+?62|0)8)\d{6,10}(?!\d)")

GLOSSARY = [
    {
        "term": "Entity",
        "meaning": "Satu potong data yang bisa diuji, misalnya domain, email, nomor, atau nama pengguna.",
    },
    {
        "term": "Bukti",
        "meaning": "Catatan hasil tool yang menyimpan sumber, waktu, dan potongan data aslinya.",
    },
    {
        "term": "Skor keyakinan",
        "meaning": "Angka 0 sampai 100 yang menilai kekuatan bukti, bukan status hukum seseorang.",
    },
    {
        "term": "Pivot",
        "meaning": "Pemeriksaan lanjutan dari entity yang sudah ada, dengan tool yang relevan.",
    },
]

SKIP_REDACTION_KEYS = {
    "source_url",
    "id",
    "case_id",
    "citation_ids",
    "audience",
    "generated_by",
    "model",
    "fingerprint",
    "generated_at",
    "created_at",
    "updated_at",
    "category",
    "term",
    "policy",
    "fields",
}


def redact_pii(text: str) -> tuple[str, set[str]]:
    if not isinstance(text, str) or not text:
        return text, set()
    fields: set[str] = set()
    value = text

    def mask_email(match: re.Match) -> str:
        fields.add("email")
        return f"{match.group(1)}***@{match.group(2)}"

    def mask_nik(match: re.Match) -> str:
        fields.add("nik")
        return f"{match.group(1)}********{match.group(2)}"

    def mask_npwp(_match: re.Match) -> str:
        fields.add("npwp")
        return "**.***.***.*-***.***"

    def mask_phone(match: re.Match) -> str:
        fields.add("phone")
        digits = re.sub(r"\D", "", match.group(0))
        prefix = match.group(1)
        return f"{prefix}****{digits[-2:]}"

    value = EMAIL_RE.sub(mask_email, value)
    value = NIK_RE.sub(mask_nik, value)
    value = NPWP_RE.sub(mask_npwp, value)
    value = PHONE_RE.sub(mask_phone, value)
    return value, fields


def _redact_value(value: Any, fields: set[str], key: str = "") -> Any:
    if isinstance(value, str):
        if key in SKIP_REDACTION_KEYS:
            return value
        redacted, found = redact_pii(value)
        fields.update(found)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item, fields, key) for item in value]
    if isinstance(value, dict):
        return {name: _redact_value(item, fields, name) for name, item in value.items()}
    return value


def _clean(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = text.replace("—", "-").replace("–", "-")
    replacements = {
        "pelaku": "pihak yang disebut dalam bukti",
        "tersangka": "pihak yang disebut dalam bukti",
        "terbukti bersalah": "belum dinilai secara hukum",
    }
    lowered = text.lower()
    for word, replacement in replacements.items():
        if word in lowered:
            text = re.sub(word, replacement, text, flags=re.I)
    return text[:limit]


def _citation_ids(value: Any, valid_ids: set[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        identifier = str(item or "").strip()
        if identifier in valid_ids and identifier not in output:
            output.append(identifier)
    return output


def _items(value: Any, valid_ids: set[str], limit: int, text_limit: int, require_citation: bool) -> list[dict]:
    if not isinstance(value, list):
        return []
    output = []
    for item in value[:limit]:
        if isinstance(item, str):
            text = _clean(item, text_limit)
            citations: list[str] = []
        elif isinstance(item, dict):
            text = _clean(item.get("text"), text_limit)
            citations = _citation_ids(item.get("citation_ids"), valid_ids)
        else:
            continue
        if not text:
            continue
        if require_citation and not citations:
            continue
        output.append({"text": text, "citation_ids": citations})
    return output


def _fingerprint(case: dict, findings: dict) -> str:
    evidence_ids = sorted(str(item.get("id", "")) for item in case.get("evidence", []))
    clue_ids = sorted(str(item.get("id", "")) for item in findings.get("clues", []))
    raw = json.dumps(
        {
            "updated": case.get("updated_at"),
            "evidence": evidence_ids,
            "clues": clue_ids,
            "score": findings.get("confidence", {}).get("score"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _citation_catalog(findings: dict) -> list[dict]:
    catalog = []
    for item in findings.get("clues", []):
        snippet = _clean(item.get("snippet") or item.get("category"), 160)
        catalog.append(
            {
                "id": item.get("id", ""),
                "category": item.get("category", "observation"),
                "label": snippet,
                "source_url": item.get("source_url", ""),
            }
        )
    return catalog


def _confidence_plain(confidence: dict) -> str:
    score = int(confidence.get("score", 0) or 0)
    band = confidence.get("band", "Low")
    return (
        f"Keyakinan bukti {score} dari 100 ({band}). "
        "Angka ini menilai kekuatan bukti yang terkumpul, bukan identitas atau kesalahan seseorang."
    )


def _local_payload(case: dict, findings: dict) -> dict:
    confidence = findings.get("confidence", {})
    counts = findings.get("counts", {})
    identities = findings.get("identities", [])
    clues = findings.get("clues", [])
    warnings = findings.get("warnings", [])
    pivots = findings.get("next_pivots", [])
    evidence_count = int(counts.get("evidence", 0) or 0)
    source_count = int(confidence.get("source_count", 0) or 0)
    source_phrase = f"{source_count} sumber" if source_count else "sumber yang belum tercatat"
    all_citations = [item.get("id", "") for item in clues if item.get("id")]

    def cites(count: int) -> list[str]:
        return all_citations[:count]

    points = [
        {
            "text": (
                f"Berkas ini mencatat {counts.get('entities', 0)} entity, "
                f"{counts.get('edges', 0)} relasi, dan {evidence_count} bukti dari {source_phrase}."
            ),
            "citation_ids": cites(2),
        }
    ]
    if identities:
        top = identities[0]
        points.append(
            {
                "text": (
                    f"Kandidat identitas terkuat adalah {top.get('name')} dengan skor {top.get('score')}/100 "
                    f"({top.get('band')}) dan {top.get('connections', 0)} relasi."
                ),
                "citation_ids": cites(2),
            }
        )
    points.append(
        {
            "text": _confidence_plain(confidence),
            "citation_ids": cites(1),
        }
    )
    if warnings:
        points.append({"text": f"Batasan utama: {_clean(warnings[0], 240)}", "citation_ids": cites(1)})
    if pivots:
        first = pivots[0]
        points.append(
            {
                "text": (
                    f"Pemeriksaan berikutnya: {first.get('label')} untuk "
                    f"{first.get('entity_type')} {first.get('entity_value')}."
                ),
                "citation_ids": cites(1),
            }
        )

    purpose = _clean(case.get("purpose"), 240)
    narrative = [
        {
            "text": (
                f"Berkas \"{_clean(case.get('title'), 160)}\" dibuka"
                + (f" untuk {purpose}" if purpose else " untuk pengumpulan bukti publik")
                + f". Sistem mengumpulkan {evidence_count} bukti dari {source_phrase} "
                "dan menyimpannya bersama sumber serta waktu pengambilan."
            ),
            "citation_ids": cites(2),
        }
    ]
    if clues:
        strongest = clues[:3]
        detail = "; ".join(_clean(item.get("snippet"), 120) for item in strongest)
        narrative.append(
            {
                "text": f"Bukti dengan bobot tertinggi: {detail}.",
                "citation_ids": [item.get("id", "") for item in strongest if item.get("id")],
            }
        )
    else:
        narrative.append(
            {
                "text": "Belum ada bukti tersimpan. Ringkasan ini hanya mencatat entity awal dan belum bisa menilai keterkaitan.",
                "citation_ids": [],
            }
        )
    if warnings or pivots:
        limit_text = _clean(warnings[0], 200) if warnings else "Bukti masih terbatas pada satu jalur pemeriksaan."
        next_text = (
            f" Langkah berikutnya adalah {pivots[0].get('label')} untuk {pivots[0].get('entity_value')}."
            if pivots
            else ""
        )
        narrative.append({"text": f"Yang perlu dijaga: {limit_text}.{next_text}", "citation_ids": cites(1)})

    analyst_notes = [
        {
            "text": f"[{item.get('category')}] {_clean(item.get('snippet'), 220)}",
            "citation_ids": [item.get("id", "")] if item.get("id") else [],
        }
        for item in clues[:6]
    ]
    next_steps = [
        f"{item.get('label')} untuk {item.get('entity_type')} {item.get('entity_value')}"
        for item in pivots[:6]
    ]
    method = [
        f"Ringkasan disusun dari {evidence_count} bukti yang tersimpan di kasus ini.",
        "Tidak ada data di luar kasus yang ditambahkan.",
        "Setiap poin menyebut bukti yang mendukung bila bukti tersedia.",
    ]
    return {
        "headline": _clean(case.get("title"), 180) or "Ringkasan kasus",
        "points": points,
        "narrative": narrative,
        "glossary": GLOSSARY,
        "analyst_notes": analyst_notes,
        "next_steps": next_steps,
        "method": method,
    }


SYSTEM_PROMPT = """Anda penyusun ringkasan investigasi OSINT dalam Bahasa Indonesia.
Aturan wajib:
- Gunakan hanya fakta dari data yang diberikan.
- Jangan menambah nama, angka, tanggal, lokasi, atau klaim baru.
- Jangan menyebut siapa pun sebagai pelaku, tersangka, atau terbukti bersalah.
- Setiap poin dan paragraf naratif wajib menyertakan citation_ids yang diambil dari daftar bukti.
- Jangan mengarang id bukti. Id yang tidak ada akan dibuang dan ringkasan ditolak.
- Tulis kalimat pendek, netral, dan bisa dipahami pembaca awam.
- Jangan memakai tanda pisah panjang, istilah pemasaran, atau klaim tanpa bukti.
Balas hanya dengan objek JSON valid, tanpa teks lain."""

SCHEMA_HINT = """Skema JSON:
{
  "headline": "string, maksimal 180 karakter",
  "points": [{"text": "string, maksimal 320 karakter", "citation_ids": ["id bukti"]}],
  "narrative": [{"text": "string, maksimal 700 karakter", "citation_ids": ["id bukti"]}],
  "glossary": [{"term": "string", "meaning": "string"}],
  "analyst_notes": [{"text": "string", "citation_ids": ["id bukti"]}],
  "next_steps": ["string"]
}
Isi 3 sampai 5 points, 2 sampai 4 narrative, maksimal 6 glossary, maksimal 6 analyst_notes."""


def _ai_payload(case: dict, findings: dict, audience: str, settings=None) -> dict | None:
    clues = findings.get("clues", [])
    if not clues:
        return None
    evidence = [
        {
            "id": item.get("id"),
            "category": item.get("category"),
            "snippet": _clean(item.get("snippet"), 300),
            "source_url": item.get("source_url", ""),
            "weight": item.get("weight"),
        }
        for item in clues[:10]
    ]
    data = {
        "audience": audience,
        "case": {
            "title": _clean(case.get("title"), 180),
            "purpose": _clean(case.get("purpose"), 300),
        },
        "confidence": findings.get("confidence", {}),
        "counts": findings.get("counts", {}),
        "identities": [
            {
                "name": _clean(item.get("name"), 120),
                "score": item.get("score"),
                "band": item.get("band"),
                "connections": item.get("connections"),
            }
            for item in findings.get("identities", [])[:5]
        ],
        "evidence": evidence,
        "warnings": [_clean(item, 240) for item in findings.get("warnings", [])[:5]],
        "next_pivots": [
            {
                "label": item.get("label"),
                "entity_type": item.get("entity_type"),
                "entity_value": _clean(item.get("entity_value"), 120),
            }
            for item in findings.get("next_pivots", [])[:5]
        ],
    }
    if audience == "public" and getattr(settings, "public_redaction", True):
        fields: set[str] = set()
        data = _redact_value(data, fields)
    user = (
        f"Target pembaca: {'pembaca awam, data PII sudah disamarkan' if audience == 'public' else 'analis'}.\n"
        f"{SCHEMA_HINT}\nData kasus:\n{json.dumps(data, ensure_ascii=False)}"
    )
    return {"system": SYSTEM_PROMPT, "user": user}


def _from_ai(raw: dict, findings: dict) -> dict:
    valid_ids = {item.get("id", "") for item in findings.get("clues", []) if item.get("id")}
    headline = _clean(raw.get("headline"), 180) or "Ringkasan kasus"
    points = _items(raw.get("points"), valid_ids, 5, 320, require_citation=True)
    narrative = _items(raw.get("narrative"), valid_ids, 4, 700, require_citation=True)
    if len(points) < 3 or len(narrative) < 2:
        raise ValueError("Struktur ringkasan AI tidak lengkap atau sitasi tidak valid.")
    glossary = []
    for item in raw.get("glossary") or []:
        if isinstance(item, dict):
            term = _clean(item.get("term"), 60)
            meaning = _clean(item.get("meaning"), 240)
            if term and meaning:
                glossary.append({"term": term, "meaning": meaning})
        if len(glossary) >= 6:
            break
    analyst_notes = _items(raw.get("analyst_notes"), valid_ids, 6, 360, require_citation=False)
    next_steps = [_clean(item, 200) for item in (raw.get("next_steps") or []) if _clean(item, 200)][:6]
    return {
        "headline": headline,
        "points": points,
        "narrative": narrative,
        "glossary": glossary or GLOSSARY,
        "analyst_notes": analyst_notes,
        "next_steps": next_steps,
        "method": [
            "Ringkasan disusun oleh model bahasa dari bukti yang tersimpan di kasus ini.",
            "Setiap sitasi diperiksa terhadap daftar bukti. Sitasi yang tidak dikenal dibuang.",
            "Draf ini perlu diperiksa analis sebelum dipakai di luar workspace.",
        ],
    }


def _finalize(
    raw: dict,
    case: dict,
    findings: dict,
    audience: str,
    settings,
    generated_by: str,
    model: str,
) -> dict:
    catalog = _citation_catalog(findings)
    by_id = {item["id"]: item for item in catalog}
    payload = {
        "case_id": case.get("id", ""),
        "case_title": _clean(case.get("title"), 200),
        "audience": audience,
        "generated_by": generated_by,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": _fingerprint(case, findings),
        "headline": raw.get("headline", ""),
        "confidence": {
            "score": findings.get("confidence", {}).get("score", 0),
            "band": findings.get("confidence", {}).get("band", "Low"),
            "plain": _confidence_plain(findings.get("confidence", {})),
        },
        "points": raw.get("points", []),
        "limits": [_clean(item, 300) for item in findings.get("warnings", [])[:5]],
        "narrative": raw.get("narrative", []),
        "glossary": raw.get("glossary", []),
        "analyst": {
            "notes": raw.get("analyst_notes", []),
            "next_steps": raw.get("next_steps", []),
            "method": raw.get("method", []),
        },
        "citations": [by_id[item] for item in sorted(by_id)],
        "redaction": {"applied": False, "policy": "none", "fields": []},
        "notice": (
            "Ringkasan disusun dari bukti yang tersimpan. Skor menilai kekuatan bukti, "
            "bukan status hukum seseorang."
        ),
        "cached": False,
    }
    if generated_by != "local":
        payload["notice"] += " Draf AI perlu diperiksa analis."
    if audience == "public" and getattr(settings, "public_redaction", True):
        fields: set[str] = set()
        redacted = _redact_value(payload, fields)
        redacted["redaction"] = {
            "applied": bool(fields),
            "policy": "partial",
            "fields": sorted(fields),
        }
        payload = redacted
    return payload


def build_summary(
    db,
    settings,
    case: dict,
    findings: dict,
    audience: str = "public",
    refresh: bool = False,
) -> dict:
    audience = audience if audience in AUDIENCES else "public"
    fingerprint = _fingerprint(case, findings)
    key = cache.summary_cache_key(case.get("id", ""), audience, fingerprint)
    if not refresh:
        cached = cache.get_summary(db, key, settings.summary_cache_ttl)
        if cached:
            cached["cached"] = True
            redaction = dict(cached.get("redaction") or {})
            if "policy" not in redaction:
                redaction["policy"] = (
                    "partial" if audience == "public" and getattr(settings, "public_redaction", True) else "none"
                )
                cached["redaction"] = redaction
            return cached

    generated_by = "local"
    model = ""
    raw = None
    request = _ai_payload(case, findings, audience, settings)
    if request is not None and ai.resolve_provider(settings) is not None:
        try:
            completion = ai.complete_json(settings, request["system"], request["user"])
            raw = _from_ai(ai.parse_completion(completion), findings)
            generated_by = completion.provider
            model = completion.model
        except (ai.AiUnavailable, ValueError, TypeError, KeyError):
            raw = None
    if raw is None:
        raw = _local_payload(case, findings)

    payload = _finalize(raw, case, findings, audience, settings, generated_by, model)
    cache.put_summary(db, key, case.get("id", ""), audience, payload)
    return payload
