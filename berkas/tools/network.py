from __future__ import annotations

import base64
import datetime as dt
import re
import socket
import ssl
from urllib.parse import quote, urlparse

import certifi
import dns.exception
import dns.resolver
from cryptography import x509

from berkas.security import SafeHttpError, resolve_public_host, safe_get
from berkas.tools.base import (
    ToolResult,
    edge,
    entity,
    evidence,
    fail,
    missing_key,
    not_found,
    ok,
    partial,
)

TECH_SIGNATURES = {
    "WordPress": [r"wp-content", r"wp-includes"],
    "Next.js": [r"_next/static", r"__NEXT_DATA__"],
    "React": [r"react-dom", r"__REACT_"],
    "Vue.js": [r"vue(?:\.min)?\.js", r"__VUE__"],
    "Laravel": [r"laravel", r"XSRF-TOKEN"],
    "Django": [r"csrfmiddlewaretoken", r"django-admin"],
    "Cloudflare": [r"cloudflare", r"cf-ray"],
    "nginx": [r"server: nginx"],
    "Apache": [r"server: apache"],
    "Bootstrap": [r"bootstrap(?:\.min)?\.(?:css|js)"],
    "Google Analytics": [r"gtag\(", r"google-analytics\.com"],
    "Shopify": [r"cdn\.shopify\.com", r"shopify"],
}


def _resolver() -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 6.0
    resolver.timeout = 4.0
    return resolver


def domain_rdap(value: str, ctx: dict) -> ToolResult:
    url = f"https://rdap.org/domain/{quote(value)}"
    try:
        response = safe_get(url, timeout=12)
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    if response.status == 404:
        return not_found({"domain": value, "status": "RDAP tidak menemukan domain."})
    if response.status != 200:
        return fail("upstream_error", f"RDAP mengembalikan status {response.status}.")
    try:
        payload = response.json()
    except ValueError:
        return fail("invalid_response", "Respons RDAP bukan JSON.")
    events = []
    for event in payload.get("events", []):
        events.append({"action": event.get("eventAction"), "date": event.get("eventDate")})
    nameservers = [ns.get("ldhName", "") for ns in payload.get("nameservers", []) if ns.get("ldhName")]
    orgs = []
    entities = []
    edges = []
    ev = [evidence("registration", 3.0, url, f"RDAP record untuk {value}", entity_key=f"domain:{value}")]
    for item in payload.get("entities", [])[:5]:
        vcard = item.get("vcardArray", [])
        name = ""
        if len(vcard) > 1 and isinstance(vcard[1], list):
            for field in vcard[1]:
                if len(field) >= 4 and field[0] == "fn":
                    name = str(field[3])
                    break
        if not name:
            continue
        orgs.append({"name": name, "roles": item.get("roles", [])})
        org_entity = entity("org", name, name.lower(), 0.7, source="rdap", roles=item.get("roles", []))
        entities.append(org_entity)
        edges.append(edge("input", org_entity.key, "registered_by", 0.65))
        ev.append(evidence("registration", 3.0, url, f"Registrant: {name}", entity_key=org_entity.key))
    data = {
        "domain": value,
        "handle": payload.get("handle", ""),
        "status": payload.get("status", []),
        "events": events,
        "nameservers": nameservers,
        "entities": orgs,
        "source": url,
    }
    return ok(data, entities=entities, edges=edges, evidence=ev)


def domain_dns(value: str, ctx: dict) -> ToolResult:
    resolver = _resolver()
    records: dict = {}
    entities = []
    edges = []
    ev = []
    for record_type in ["A", "AAAA", "MX", "NS", "TXT", "SOA", "CAA", "DS"]:
        try:
            answers = resolver.resolve(value, record_type)
            records[record_type] = [answer.to_text().strip('"') for answer in answers]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
            records[record_type] = []
        except Exception:
            records[record_type] = []
    for ip_value in records.get("A", []) + records.get("AAAA", []):
        ip_entity = entity("ip", ip_value, ip_value, 0.85, source="dns")
        entities.append(ip_entity)
        edges.append(edge("input", ip_entity.key, "resolves_to", 0.85))
        ev.append(evidence("dns", 2.0, f"https://dns.google/query?name={quote(value)}&type=A", f"{value} -> {ip_value}", entity_key=ip_entity.key))
    for mx in records.get("MX", []):
        host = mx.split()[-1].rstrip(".")
        mx_entity = entity("domain", host, host.lower(), 0.7, source="dns", role="mail")
        entities.append(mx_entity)
        edges.append(edge("input", mx_entity.key, "mail_exchange", 0.7))
    spf = next((txt for txt in records.get("TXT", []) if "v=spf1" in txt.lower()), "")
    dmarc = ""
    try:
        dmarc_answers = resolver.resolve(f"_dmarc.{value}", "TXT")
        dmarc = " ".join(answer.to_text().strip('"') for answer in dmarc_answers)
    except Exception:
        dmarc = ""
    data = {
        "domain": value,
        "records": records,
        "spf": spf,
        "dmarc": dmarc,
        "dnssec": bool(records.get("DS")),
    }
    if not any(records.values()):
        return partial(data, warnings=["Tidak ada record DNS yang bisa dibaca."], entities=entities, edges=edges, evidence=ev)
    ev.append(evidence("dns", 1.5, f"https://dns.google/query?name={quote(value)}", "DNS records resolved", entity_key=f"domain:{value}"))
    return ok(data, entities=entities, edges=edges, evidence=ev)


def _certificate_name(name: x509.Name) -> str:
    for oid in (x509.oid.NameOID.ORGANIZATION_NAME, x509.oid.NameOID.COMMON_NAME):
        attributes = name.get_attributes_for_oid(oid)
        if attributes:
            return str(attributes[0].value)
    return name.rfc4514_string() or "Unknown"


def _unverified_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _verified_context() -> ssl.SSLContext:
    try:
        return ssl.create_default_context(cafile=certifi.where())
    except (OSError, ssl.SSLError):
        return ssl.create_default_context()


def _tls_peer_certificate(host: str) -> tuple[bytes, bool]:
    addresses = resolve_public_host(host, 443)
    last_error: Exception | None = None
    for verified in (True, False):
        context = _verified_context() if verified else _unverified_context()
        for address in addresses[:2]:
            try:
                with socket.create_connection((address, 443), timeout=8) as raw:
                    with context.wrap_socket(raw, server_hostname=host) as tls:
                        der = tls.getpeercert(binary_form=True)
                if der:
                    return der, verified
            except ssl.SSLCertVerificationError as exc:
                last_error = exc
            except (OSError, ssl.SSLError) as exc:
                last_error = exc
    if last_error:
        raise last_error
    raise ssl.SSLError("Tidak ada sertifikat yang dikembalikan server.")


def domain_ssl(value: str, ctx: dict) -> ToolResult:
    raw_host = urlparse(value).hostname if "://" in value else value.split("/")[0]
    host = (raw_host or "").strip().lower().rstrip(".")
    if not host:
        return fail("invalid_input", "Domain kosong atau tidak valid.")
    try:
        der, verified = _tls_peer_certificate(host)
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    except Exception as exc:  # noqa: BLE001 - network and TLS boundary
        return fail("upstream_error", f"Tidak bisa membaca sertifikat TLS: {exc}")
    try:
        certificate = x509.load_der_x509_certificate(der)
    except ValueError:
        return fail("invalid_response", "Sertifikat TLS tidak bisa dibaca.")
    try:
        san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        san = []
    now = dt.datetime.now(dt.timezone.utc)
    not_before = certificate.not_valid_before_utc
    not_after = certificate.not_valid_after_utc
    days_remaining = (not_after - now).days
    data = {
        "host": host,
        "issuer": _certificate_name(certificate.issuer),
        "subject": _certificate_name(certificate.subject),
        "valid_from": not_before.isoformat(),
        "valid_until": not_after.isoformat(),
        "days_remaining": days_remaining,
        "serial": format(certificate.serial_number, "x"),
        "san": san[:50],
        "chain_verified": verified,
    }
    warnings = []
    if not verified:
        warnings.append("Rantai sertifikat tidak terverifikasi penuh, data dibaca tanpa validasi.")
    if days_remaining < 0:
        warnings.append("Sertifikat sudah kedaluwarsa.")
    elif days_remaining < 30:
        warnings.append(f"Sertifikat akan kedaluwarsa dalam {days_remaining} hari.")
    return ok(
        data,
        warnings=warnings,
        evidence=[
            evidence(
                "certificate",
                2.0,
                f"https://crt.sh/?q={quote(host)}",
                f"Issuer: {data['issuer']}",
                entity_key=f"domain:{host}",
            )
        ],
    )


def domain_http(value: str, ctx: dict) -> ToolResult:
    errors = []
    response = None
    for scheme in ["https", "http"]:
        try:
            response = safe_get(f"{scheme}://{value}", timeout=12)
            break
        except SafeHttpError as exc:
            errors.append(f"{scheme}: {exc.message}")
    if response is None:
        return fail("upstream_error", "Tidak bisa mengambil halaman: " + "; ".join(errors))
    body = response.text
    lower = body.lower()
    headers_text = str(response.headers).lower()
    detected = []
    for tech, patterns in TECH_SIGNATURES.items():
        if any(re.search(pattern, headers_text) or re.search(pattern, lower) for pattern in patterns):
            detected.append(tech)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    description_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', body, re.I | re.S)
    security_headers = {
        "strict-transport-security": "HSTS",
        "content-security-policy": "CSP",
        "x-frame-options": "Clickjacking protection",
        "x-content-type-options": "MIME sniffing protection",
        "referrer-policy": "Referrer policy",
    }
    present = [label for header, label in security_headers.items() if header in response.headers]
    missing = [header for header in security_headers if header not in response.headers]
    data = {
        "url": response.url,
        "status": response.status,
        "title": re.sub(r"\s+", " ", title_match.group(1)).strip()[:200] if title_match else "",
        "description": re.sub(r"\s+", " ", description_match.group(1)).strip()[:300] if description_match else "",
        "technologies": sorted(set(detected)),
        "server": response.headers.get("server", ""),
        "content_type": response.headers.get("content-type", ""),
        "security_headers_present": present,
        "security_headers_missing": missing,
        "response_ms": response.elapsed_ms,
    }
    return ok(
        data,
        evidence=[evidence("http", 1.5, response.url, f"HTTP {response.status}, {len(present)} security headers", entity_key=f"domain:{value}")],
    )


def domain_crtsh(value: str, ctx: dict) -> ToolResult:
    url = f"https://crt.sh/?q=%25.{quote(value)}&output=json"
    try:
        response = safe_get(url, timeout=20)
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    if response.status != 200:
        return fail("upstream_error", f"crt.sh mengembalikan status {response.status}.")
    try:
        rows = response.json()
    except ValueError:
        return partial({"domain": value}, warnings=["crt.sh tidak mengembalikan JSON, mungkin sedang dibatasi."])
    names: set[str] = set()
    for row in rows[:500]:
        for name in str(row.get("name_value", "")).splitlines():
            name = name.strip().lower().lstrip("*.")
            if name.endswith(value) and name != value:
                names.add(name)
    entities = []
    edges = []
    ev = []
    for name in sorted(names)[:60]:
        sub = entity("domain", name, name, 0.75, source="crt.sh", role="subdomain")
        entities.append(sub)
        edges.append(edge("input", sub.key, "subdomain_of", 0.8))
    if names:
        ev.append(evidence("certificate_transparency", 2.5, url, f"{len(names)} subdomain ditemukan", entity_key=f"domain:{value}"))
    data = {"domain": value, "subdomains": sorted(names)[:200], "count": len(names), "source": url}
    return ok(data, entities=entities, edges=edges, evidence=ev)


def domain_wayback(value: str, ctx: dict) -> ToolResult:
    url = f"https://web.archive.org/cdx/search/cdx?url={quote(value)}&output=json&limit=20&collapse=timestamp:6"
    try:
        response = safe_get(url, timeout=20)
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    if response.status != 200:
        return fail("upstream_error", f"Wayback mengembalikan status {response.status}.")
    try:
        rows = response.json()
    except ValueError:
        return partial({"domain": value}, warnings=["Wayback tidak mengembalikan JSON."])
    snapshots = []
    for row in rows[1:]:
        if len(row) < 5:
            continue
        snapshots.append(
            {
                "timestamp": row[1],
                "url": row[2],
                "status": row[4],
                "archive_url": f"https://web.archive.org/web/{row[1]}/{row[2]}",
            }
        )
    data = {"domain": value, "snapshots": snapshots, "count": len(snapshots)}
    return ok(
        data,
        evidence=[evidence("archive", 1.5, url, f"{len(snapshots)} snapshot ditemukan", entity_key=f"domain:{value}")] if snapshots else [],
    )


def ip_geo(value: str, ctx: dict) -> ToolResult:
    url = f"https://ipwho.is/{quote(value)}"
    try:
        response = safe_get(url, timeout=10, allow_http=False)
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    try:
        payload = response.json()
    except ValueError:
        return fail("invalid_response", "ipwho.is tidak mengembalikan JSON.")
    if not payload.get("success"):
        return not_found({"ip": value, "message": payload.get("message", "Tidak ditemukan")})
    connection = payload.get("connection") or {}
    timezone = payload.get("timezone") or {}
    org = connection.get("org") or connection.get("isp") or ""
    data = {
        "ip": payload.get("ip", value),
        "country": payload.get("country", ""),
        "region": payload.get("region", ""),
        "city": payload.get("city", ""),
        "isp": connection.get("isp", ""),
        "org": org,
        "as": connection.get("asn", ""),
        "lat": payload.get("latitude"),
        "lon": payload.get("longitude"),
        "timezone": timezone.get("id", ""),
        "source": url,
    }
    entities = []
    edges = []
    ev = [
        evidence(
            "geolocation",
            2.0,
            url,
            f"{data.get('city')}, {data.get('country')}".strip(", "),
            entity_key=f"ip:{value}",
        )
    ]
    if org:
        org_entity = entity("org", org, org.lower(), 0.65, source="ipwho.is")
        entities.append(org_entity)
        edges.append(edge("input", org_entity.key, "operated_by", 0.6))
    return ok(data, entities=entities, edges=edges, evidence=ev)


def ip_reputation(value: str, ctx: dict) -> ToolResult:
    data: dict = {"ip": value}
    warnings = []
    ev = []
    try:
        response = safe_get("https://check.torproject.org/torbulkexitlist", timeout=10)
        nodes = set(response.text.splitlines())
        data["tor_exit_node"] = value in nodes
    except SafeHttpError as exc:
        data["tor_exit_node"] = None
        warnings.append(f"Tor check gagal: {exc.message}")
    key = ctx.get("abuseipdb_api_key", "")
    if not key:
        warnings.append("ABUSEIPDB_API_KEY belum diset, reputasi AbuseIPDB dilewati.")
    else:
        try:
            response = safe_get(
                f"https://api.abuseipdb.com/api/v2/check?ipAddress={quote(value)}&maxAgeInDays=90",
                timeout=12,
                headers={"Key": key, "Accept": "application/json"},
            )
            payload = response.json().get("data", {})
            data["abuse_confidence"] = payload.get("abuseConfidenceScore")
            data["total_reports"] = payload.get("totalReports")
            data["last_reported"] = payload.get("lastReportedAt")
            if payload.get("abuseConfidenceScore", 0) > 0:
                ev.append(evidence("reputation", 2.5, "https://www.abuseipdb.com", f"Abuse score {payload.get('abuseConfidenceScore')}/100", entity_key=f"ip:{value}"))
        except Exception as exc:
            warnings.append(f"AbuseIPDB gagal: {exc}")
    return partial(data, warnings=warnings, evidence=ev)


def ip_shodan(value: str, ctx: dict) -> ToolResult:
    key = ctx.get("shodan_api_key", "")
    if not key:
        return missing_key("SHODAN_API_KEY")
    try:
        response = safe_get(
            f"https://api.shodan.io/shodan/host/{quote(value)}?key={quote(key)}",
            timeout=15,
        )
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    if response.status == 404:
        return not_found({"ip": value, "status": "Tidak ada data Shodan untuk IP ini."})
    if response.status != 200:
        return fail("upstream_error", f"Shodan mengembalikan status {response.status}.")
    payload = response.json()
    services = [
        {
            "port": item.get("port"),
            "transport": item.get("transport"),
            "product": item.get("product", ""),
            "version": item.get("version", ""),
            "banner": (item.get("data", "") or "")[:160],
        }
        for item in (payload.get("data") or [])[:20]
    ]
    data = {
        "ip": value,
        "organization": payload.get("org", ""),
        "isp": payload.get("isp", ""),
        "country": payload.get("country_name", ""),
        "city": payload.get("city", ""),
        "os": payload.get("os", ""),
        "hostnames": payload.get("hostnames", [])[:20],
        "domains": payload.get("domains", [])[:20],
        "open_ports": payload.get("ports", [])[:40],
        "services": services,
        "last_update": payload.get("last_update"),
        "source": f"https://www.shodan.io/host/{value}",
    }
    entities = []
    edges = []
    ev = []
    org_name = data["organization"] or data["isp"]
    if org_name:
        org_entity = entity("org", org_name, org_name.lower(), 0.8, source="shodan")
        entities.append(org_entity)
        edges.append(edge("input", org_entity.key, "operated_by", 0.7))
    for hostname in data["hostnames"][:10]:
        domain_entity = entity("domain", hostname, hostname.lower(), 0.7, source="shodan")
        entities.append(domain_entity)
        edges.append(edge(domain_entity.key, "input", "resolves_to", 0.65))
    if data["open_ports"]:
        ev.append(
            evidence(
                "exposure",
                1.5,
                data["source"],
                f"{len(data['open_ports'])} port terbuka tercatat di Shodan",
                entity_key=f"ip:{value}",
            )
        )
    return ok(data, entities=entities, edges=edges, evidence=ev)


def shortlink_expand(value: str, ctx: dict) -> ToolResult:
    try:
        response = safe_get(value, timeout=12, max_redirects=5)
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    if response.url == value:
        return not_found({"input": value, "final_url": response.url, "redirects": response.history}, warnings=["Tidak ada redirect yang terdeteksi."])
    domain = re.sub(r"^https?://", "", response.url).split("/")[0].lower()
    url_entity = entity("url", response.url, response.url, 0.9, source="redirect")
    domain_entity = entity("domain", domain, domain, 0.85, source="redirect")
    return ok(
        {"input": value, "final_url": response.url, "redirects": response.history, "status": response.status},
        entities=[url_entity, domain_entity],
        edges=[edge("input", url_entity.key, "redirects_to", 0.9), edge("input", domain_entity.key, "resolves_to", 0.8)],
        evidence=[evidence("redirect", 2.0, value, f"Redirect ke {response.url}", entity_key=url_entity.key)],
    )


def url_reputation(value: str, ctx: dict) -> ToolResult:
    key = ctx.get("vt_api_key", "")
    if not key:
        return missing_key("VT_API_KEY")
    url_id = base64.urlsafe_b64encode(value.encode()).decode().strip("=")
    try:
        response = safe_get(
            f"https://www.virustotal.com/api/v3/urls/{url_id}",
            timeout=15,
            headers={"x-apikey": key, "Accept": "application/json"},
        )
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    if response.status == 404:
        return not_found({"url": value, "status": "URL belum ada di VirusTotal."})
    if response.status != 200:
        return fail("upstream_error", f"VirusTotal mengembalikan status {response.status}.")
    payload = response.json().get("data", {}).get("attributes", {})
    stats = payload.get("last_analysis_stats", {})
    data = {
        "url": value,
        "malicious": stats.get("malicious", 0),
        "harmless": stats.get("harmless", 0),
        "suspicious": stats.get("suspicious", 0),
        "reputation": payload.get("reputation", 0),
        "last_analysis": payload.get("last_analysis_date"),
        "source": f"https://www.virustotal.com/gui/url/{url_id}",
    }
    return ok(data, evidence=[evidence("reputation", 2.0, data["source"], f"Malicious: {data['malicious']}", entity_key=f"url:{value}")])
