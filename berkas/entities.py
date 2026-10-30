from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field

import phonenumbers
from phonenumbers import PhoneNumberFormat


@dataclass
class ParsedEntity:
    type: str
    value: str
    normalized: str
    confidence: float
    start: int = 0
    end: int = 0
    source: str = "text"
    attributes: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "type": self.type,
            "value": self.value,
            "normalized": self.normalized,
            "confidence": round(self.confidence, 2),
            "start": self.start,
            "end": self.end,
            "source": self.source,
            "attributes": self.attributes,
        }


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}\b")
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
BTC_RE = re.compile(r"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b")
NIK_RE = re.compile(r"\b\d{16}\b")
NPWP_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}\b")
PHONE_RE = re.compile(r"(?:\+?62|0)[\s().-]?8[\d\s().-]{7,15}")
DOMAIN_RE = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,24}\b"
)
USERNAME_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_.]{2,32})\b")
PREFIX_RE = re.compile(
    r"(?im)^\s*(name|nama|email|phone|telepon|hp|user|username|domain|ip|url|nik|npwp|nim)\s*:\s*(.+?)\s*$"
)

DISPOSABLE_HINTS = {
    "mailinator.com",
    "guerrillamail.com",
    "10minutemail.com",
    "tempmail.com",
    "yopmail.com",
    "trashmail.com",
}

TYPE_ALIASES = {
    "nama": "person",
    "name": "person",
    "telepon": "phone",
    "hp": "phone",
    "phone": "phone",
    "user": "username",
    "username": "username",
    "email": "email",
    "domain": "domain",
    "ip": "ip",
    "url": "url",
    "nik": "nik",
    "npwp": "npwp",
    "nim": "nim",
}


def normalize_phone(value: str) -> tuple[str, bool]:
    cleaned = re.sub(r"[^\d+]", "", value)
    try:
        number = phonenumbers.parse(cleaned, "ID")
        valid = phonenumbers.is_valid_number(number)
        if valid:
            return phonenumbers.format_number(number, PhoneNumberFormat.E164), True
    except phonenumbers.NumberParseException:
        pass
    return cleaned, False


def normalize_domain(value: str) -> str:
    value = value.strip().lower().rstrip(".")
    value = re.sub(r"^https?://", "", value)
    value = value.split("/")[0].split("?")[0]
    try:
        return value.encode("idna").decode("ascii")
    except UnicodeError:
        return value


def normalize_value(entity_type: str, value: str) -> str:
    value = value.strip()
    if entity_type == "email":
        return value.lower()
    if entity_type == "phone":
        return normalize_phone(value)[0]
    if entity_type in {"domain", "url"}:
        return normalize_domain(value) if entity_type == "domain" else value.strip()
    if entity_type == "username":
        return value.lstrip("@").lower()
    if entity_type in {"nik", "npwp", "nim"}:
        return re.sub(r"[^0-9A-Za-z]", "", value).upper()
    if entity_type == "mac":
        return value.replace("-", ":").upper()
    if entity_type == "ip":
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            return value
    return value.lower() if entity_type in {"person", "org"} else value


def _add(store: dict, entity: ParsedEntity) -> None:
    key = (entity.type, entity.normalized)
    existing = store.get(key)
    if existing is None or entity.confidence > existing.confidence:
        store[key] = entity


def _extract_prefixed(text: str, store: dict) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        match = PREFIX_RE.match(line)
        if not match:
            kept.append(line)
            continue
        raw_type, raw_value = match.group(1).lower(), match.group(2).strip()
        entity_type = TYPE_ALIASES.get(raw_type, raw_type)
        if entity_type == "person":
            normalized = raw_value.strip()
        else:
            normalized = normalize_value(entity_type, raw_value)
        _add(
            store,
            ParsedEntity(
                type=entity_type,
                value=raw_value,
                normalized=normalized,
                confidence=0.92,
                source="explicit",
            ),
        )
    return "\n".join(kept)


def _extract_names(text: str, store: dict) -> None:
    for line in text.splitlines():
        candidate = line.strip().strip(",;")
        if not candidate or len(candidate) > 80:
            continue
        if any(ch in candidate for ch in "@:/\\"):
            continue
        if re.search(r"\d", candidate):
            continue
        words = candidate.split()
        if not 2 <= len(words) <= 5:
            continue
        if not all(re.match(r"^[A-ZÀ-Ý][a-zà-ÿ'.-]*$", word) for word in words):
            continue
        normalized = " ".join(words)
        _add(
            store,
            ParsedEntity(
                type="person",
                value=normalized,
                normalized=normalized.lower(),
                confidence=0.55,
                source="heuristic",
            ),
        )


def parse_text(text: str) -> list[ParsedEntity]:
    store: dict = {}
    text = text or ""
    cleaned = _extract_prefixed(text, store)

    for match in EMAIL_RE.finditer(cleaned):
        value = match.group(0)
        _add(store, ParsedEntity("email", value, value.lower(), 0.95, match.start(), match.end()))

    email_spans = [(m.start(), m.end()) for m in EMAIL_RE.finditer(cleaned)]

    for match in URL_RE.finditer(cleaned):
        value = match.group(0).rstrip(".,;)")
        _add(store, ParsedEntity("url", value, value, 0.95, match.start(), match.end()))

    for match in IP_RE.finditer(cleaned):
        value = match.group(0)
        try:
            ipaddress.ip_address(value)
        except ValueError:
            continue
        _add(store, ParsedEntity("ip", value, value, 0.95, match.start(), match.end()))

    for match in MAC_RE.finditer(cleaned):
        value = match.group(0)
        _add(store, ParsedEntity("mac", value, normalize_value("mac", value), 0.95, match.start(), match.end()))

    for match in BTC_RE.finditer(cleaned):
        value = match.group(0)
        _add(store, ParsedEntity("btc", value, value, 0.9, match.start(), match.end()))

    for match in NPWP_RE.finditer(cleaned):
        value = match.group(0)
        _add(store, ParsedEntity("npwp", value, normalize_value("npwp", value), 0.9, match.start(), match.end()))

    for match in NIK_RE.finditer(cleaned):
        value = match.group(0)
        _add(store, ParsedEntity("nik", value, value, 0.9, match.start(), match.end()))

    for match in PHONE_RE.finditer(cleaned):
        value = match.group(0).strip()
        normalized, valid = normalize_phone(value)
        if not valid:
            continue
        _add(store, ParsedEntity("phone", value, normalized, 0.9, match.start(), match.end()))

    for match in USERNAME_RE.finditer(cleaned):
        value = match.group(1)
        _add(store, ParsedEntity("username", value, value.lower(), 0.7, match.start(), match.end()))

    for match in DOMAIN_RE.finditer(cleaned):
        value = match.group(0).lower()
        if any(start <= match.start() < end for start, end in email_spans):
            continue
        if value.endswith((".jpg", ".png", ".gif", ".webp", ".pdf", ".docx")):
            continue
        _add(store, ParsedEntity("domain", value, normalize_domain(value), 0.85, match.start(), match.end()))

    _extract_names(cleaned, store)

    if not store and cleaned.strip():
        token = cleaned.strip()
        if re.match(r"^[A-Za-z0-9_.-]{2,32}$", token):
            _add(store, ParsedEntity("username", token, token.lower(), 0.55, source="fallback"))
        elif " " in token and len(token) <= 80:
            _add(store, ParsedEntity("person", token, token.lower(), 0.5, source="fallback"))

    return sorted(store.values(), key=lambda item: (item.start, item.type))


def entity_from_value(value: str, type_hint: str | None = None) -> ParsedEntity | None:
    value = (value or "").strip()
    if not value:
        return None
    if type_hint:
        if type_hint not in KNOWN_TYPES:
            return None
        normalized = normalize_value(type_hint, value)
        return ParsedEntity(type_hint, value, normalized, 0.9, source="pivot")
    parsed = parse_text(value)
    if not parsed:
        return None
    best = max(parsed, key=lambda item: item.confidence)
    return ParsedEntity(
        type=best.type,
        value=value,
        normalized=best.normalized,
        confidence=best.confidence,
        source="pivot",
    )


TOOL_PLAN = {
    "email": ["email_intel", "email_breach", "paste_search", "person_search"],
    "phone": ["phone_intel"],
    "username": ["username_enum", "github_user", "public_profiles", "paste_search", "person_search"],
    "person": ["person_search", "pddikti"],
    "domain": ["domain_rdap", "domain_dns", "domain_ssl", "domain_http", "domain_crtsh", "domain_wayback"],
    "ip": ["ip_geo", "ip_reputation", "ip_shodan"],
    "url": ["url_reputation", "shortlink_expand"],
    "nik": ["nik_parse"],
    "npwp": ["npwp_parse"],
    "nim": ["pddikti"],
    "btc": ["crypto_btc"],
    "mac": ["mac_vendor"],
}


def tools_for_type(entity_type: str) -> list[str]:
    return TOOL_PLAN.get(entity_type, [])


KNOWN_TYPES = set(TOOL_PLAN) | {
    "account",
    "alias",
    "breach",
    "document",
    "image",
    "location",
    "org",
    "unknown",
}
