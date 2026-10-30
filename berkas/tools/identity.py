from __future__ import annotations

import datetime as dt
import hashlib
import re
from urllib.parse import quote

import dns.exception
import dns.resolver
import phonenumbers
from phonenumbers import carrier, geocoder, number_type, timezone

from berkas.security import SafeHttpError, safe_get
from berkas.tools.base import (
    ToolResult,
    edge,
    entity,
    evidence,
    fail,
    missing_key,
    not_found,
    ok,
)

DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "10minutemail.com",
    "tempmail.com",
    "yopmail.com",
    "trashmail.com",
    "sharklasers.com",
    "getnada.com",
    "maildrop.cc",
    "dispostable.com",
    "fakeinbox.com",
}

PROVINCES = {
    "11": "Aceh",
    "12": "Sumatera Utara",
    "13": "Sumatera Barat",
    "14": "Riau",
    "15": "Jambi",
    "16": "Sumatera Selatan",
    "17": "Bengkulu",
    "18": "Lampung",
    "19": "Kepulauan Bangka Belitung",
    "21": "Kepulauan Riau",
    "31": "DKI Jakarta",
    "32": "Jawa Barat",
    "33": "Jawa Tengah",
    "34": "DI Yogyakarta",
    "35": "Jawa Timur",
    "36": "Banten",
    "51": "Bali",
    "52": "Nusa Tenggara Barat",
    "53": "Nusa Tenggara Timur",
    "61": "Kalimantan Barat",
    "62": "Kalimantan Tengah",
    "63": "Kalimantan Selatan",
    "64": "Kalimantan Timur",
    "65": "Kalimantan Utara",
    "71": "Sulawesi Utara",
    "72": "Sulawesi Tengah",
    "73": "Sulawesi Selatan",
    "74": "Sulawesi Tenggara",
    "75": "Gorontalo",
    "76": "Sulawesi Barat",
    "81": "Maluku",
    "82": "Maluku Utara",
    "91": "Papua",
    "92": "Papua Barat",
}

PHONE_TYPES = {
    phonenumbers.PhoneNumberType.MOBILE: "Seluler",
    phonenumbers.PhoneNumberType.FIXED_LINE: "Telepon tetap",
    phonenumbers.PhoneNumberType.VOIP: "VOIP",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium rate",
    phonenumbers.PhoneNumberType.TOLL_FREE: "Toll free",
    phonenumbers.PhoneNumberType.SHARED_COST: "Shared cost",
    phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Personal number",
    phonenumbers.PhoneNumberType.PAGER: "Pager",
    phonenumbers.PhoneNumberType.UAN: "UAN",
    phonenumbers.PhoneNumberType.VOICEMAIL: "Voicemail",
}


def _resolver() -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 6.0
    resolver.timeout = 4.0
    return resolver


def email_intel(value: str, ctx: dict) -> ToolResult:
    if "@" not in value:
        return fail("invalid_input", "Email tidak valid.")
    local_part, domain = value.rsplit("@", 1)
    domain = domain.lower()
    resolver = _resolver()
    data: dict = {"email": value, "domain": domain, "provider": "custom"}
    warnings = []
    ev = []
    entities = []
    edges = []

    mx = []
    try:
        mx = [answer.to_text().split()[-1].rstrip(".") for answer in resolver.resolve(domain, "MX")]
    except Exception:
        warnings.append("MX record tidak ditemukan.")
    data["mx"] = mx

    spf = ""
    dmarc = ""
    try:
        for answer in resolver.resolve(domain, "TXT"):
            text = answer.to_text().strip('"')
            if "v=spf1" in text.lower():
                spf = text
        data["spf"] = spf
    except Exception:
        pass
    try:
        for answer in resolver.resolve(f"_dmarc.{domain}", "TXT"):
            text = answer.to_text().strip('"')
            if "v=dmarc1" in text.lower():
                dmarc = text
        data["dmarc"] = dmarc
    except Exception:
        pass

    if domain in DISPOSABLE_DOMAINS:
        data["disposable"] = True
        warnings.append("Domain email terdeteksi sebagai layanan disposable.")
    else:
        data["disposable"] = False
    if any(provider in domain for provider in ["gmail", "yahoo", "outlook", "hotmail", "icloud", "proton"]):
        data["provider"] = "personal"
    elif domain.endswith((".ac.id", ".edu")):
        data["provider"] = "education"
    elif domain.endswith((".go.id", ".gov")):
        data["provider"] = "government"
    else:
        data["provider"] = "corporate"

    domain_entity = entity("domain", domain, domain, 0.9, source="email")
    entities.append(domain_entity)
    edges.append(edge("input", domain_entity.key, "uses_domain", 0.95))
    ev.append(evidence("email", 2.0, f"https://dns.google/query?name={quote(domain)}&type=MX", f"MX: {', '.join(mx) or 'tidak ada'}", entity_key=domain_entity.key))

    username_entity = entity("username", local_part, local_part.lower(), 0.45, source="email_local_part", note="Hipotesis, belum diverifikasi")
    entities.append(username_entity)
    edges.append(edge("input", username_entity.key, "candidate_username", 0.4))
    ev.append(evidence("username_candidate", 1.0, "", f"Local part email: {local_part}", entity_key=username_entity.key))

    gravatar_hash = hashlib.md5(value.lower().encode()).hexdigest()
    gravatar_url = f"https://www.gravatar.com/avatar/{gravatar_hash}?d=404"
    try:
        response = safe_get(gravatar_url, timeout=8)
        if response.status == 200:
            avatar = entity("url", gravatar_url, gravatar_url, 0.7, source="gravatar", kind="avatar")
            entities.append(avatar)
            edges.append(edge("input", avatar.key, "has_avatar", 0.75))
            ev.append(evidence("profile", 3.0, gravatar_url, "Gravatar ditemukan", entity_key=avatar.key))
            data["gravatar"] = True
        else:
            data["gravatar"] = False
    except SafeHttpError:
        data["gravatar"] = None

    data["links"] = {
        "google": f"https://www.google.com/search?q={quote('\"' + value + '\"')}",
        "github": f"https://github.com/search?q={quote(value)}&type=users",
        "hibp": f"https://haveibeenpwned.com/account/{quote(value)}",
    }
    return ok(data, entities=entities, edges=edges, evidence=ev, warnings=warnings)


def email_breach(value: str, ctx: dict) -> ToolResult:
    key = ctx.get("hibp_api_key", "")
    if not key:
        return missing_key("HIBP_API_KEY")
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(value, safe='')}?truncateResponse=false"
    try:
        response = safe_get(
            url,
            timeout=15,
            headers={"hibp-api-key": key, "User-Agent": "BerkasOSINT/2.0"},
        )
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    if response.status == 404:
        return not_found({"email": value, "breaches": [], "count": 0})
    if response.status == 401:
        return fail("unauthorized", "HIBP menolak API key. Periksa HIBP_API_KEY.")
    if response.status == 429:
        return fail("rate_limited", "Kuota HIBP tercapai. Coba lagi nanti.")
    if response.status != 200:
        return fail("upstream_error", f"HIBP mengembalikan status {response.status}.")
    try:
        payload = response.json()
    except ValueError:
        return fail("invalid_response", "HIBP tidak mengembalikan JSON.")
    entities = []
    edges = []
    ev = []
    for breach in payload[:30]:
        name = breach.get("Name", "Unknown")
        breach_entity = entity(
            "breach",
            name,
            name.lower(),
            0.9,
            source="hibp",
            title=breach.get("Title", ""),
            domain=breach.get("Domain", ""),
            breach_date=breach.get("BreachDate", ""),
            pwn_count=breach.get("PwnCount", 0),
        )
        entities.append(breach_entity)
        edges.append(edge("input", breach_entity.key, "leaked_in", 0.95))
        ev.append(
            evidence(
                "breach",
                4.0,
                "https://haveibeenpwned.com",
                f"{name} ({breach.get('BreachDate', '')})",
                entity_key=breach_entity.key,
            )
        )
    return ok({"email": value, "breaches": payload, "count": len(payload)}, entities=entities, edges=edges, evidence=ev)


def phone_intel(value: str, ctx: dict) -> ToolResult:
    try:
        parsed = phonenumbers.parse(value, "ID")
    except phonenumbers.NumberParseException as exc:
        return fail("invalid_input", f"Nomor tidak bisa diparse: {exc}")
    if not phonenumbers.is_valid_number(parsed):
        return not_found({"phone": value, "message": "Nomor tidak valid menurut libphonenumber."})
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
    data = {
        "phone": e164,
        "national": national,
        "carrier": carrier.name_for_number(parsed, "en") or "Tidak teridentifikasi",
        "region": geocoder.description_for_number(parsed, "id") or "Tidak diketahui",
        "type": PHONE_TYPES.get(number_type(parsed), "Tidak diketahui"),
        "timezones": list(timezone.time_zones_for_number(parsed)),
        "links": {
            "whatsapp": f"https://wa.me/{e164.lstrip('+')}",
            "telegram": f"https://t.me/{e164.lstrip('+')}",
            "truecaller": f"https://www.truecaller.com/search/id/{e164.lstrip('+')}",
        },
    }
    return ok(
        data,
        evidence=[evidence("phone", 3.0, "", f"{e164}, {data['carrier']}, {data['region']}", entity_key=f"phone:{e164}")],
        warnings=["Tidak ada lookup pemilik nomor. Data yang tersedia hanya metadata publik."],
    )


def nik_parse(value: str, ctx: dict) -> ToolResult:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 16:
        return fail("invalid_input", "NIK harus 16 digit.")
    province_code = digits[:2]
    city_code = digits[2:4]
    district_code = digits[4:6]
    day = int(digits[6:8])
    month = int(digits[8:10])
    year = int(digits[10:12])
    gender = "Laki-laki"
    if day > 40:
        gender = "Perempuan"
        day -= 40
    now = dt.date.today()
    century = 2000 if (2000 + year) <= now.year else 1900
    birth_year = century + year
    try:
        birth = dt.date(birth_year, month, day)
    except ValueError:
        return fail("invalid_input", "Tanggal lahir pada NIK tidak valid.")
    age = now.year - birth.year - ((now.month, now.day) < (birth.month, birth.day))
    data = {
        "nik": digits,
        "gender": gender,
        "birth_date": birth.isoformat(),
        "age": age,
        "province_code": province_code,
        "province": PROVINCES.get(province_code, "Tidak terdaftar"),
        "city_code": f"{province_code}.{city_code}",
        "district_code": f"{province_code}.{city_code}.{district_code}",
        "sequence": digits[12:],
        "note": "Validasi format saja. Tidak ada lookup pemilik.",
    }
    return ok(
        data,
        evidence=[evidence("identity_document", 3.0, "", f"NIK valid secara format, {data['province']}", entity_key=f"nik:{digits}")],
        warnings=["NIK tidak diverifikasi ke Dukcapil. Jangan mengklaim kepemilikan tanpa otoritas."],
    )


def npwp_parse(value: str, ctx: dict) -> ToolResult:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 15:
        return fail("invalid_input", "NPWP harus 15 digit.")
    formatted = f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}.{digits[8]}-{digits[9:12]}.{digits[12:15]}"
    branch_code = digits[12:15]
    status = "Pusat" if branch_code == "000" else "Cabang"
    data = {
        "npwp": formatted,
        "digits": digits,
        "taxpayer_code": digits[:9],
        "kpp_code": digits[9:12],
        "status_code": digits[8],
        "branch_code": branch_code,
        "status": status,
        "note": "Validasi format saja. Status aktif harus dicek ke DJP.",
    }
    return ok(
        data,
        evidence=[evidence("identity_document", 2.5, "", f"NPWP valid secara format: {formatted}", entity_key=f"npwp:{digits}")],
        warnings=["NPWP tidak diverifikasi ke DJP."],
    )
