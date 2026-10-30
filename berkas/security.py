from __future__ import annotations

import ipaddress
import re
import socket
import time
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse, urlunparse

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 BerkasOSINT/2.0"
)
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}
MAX_BYTES = 2_500_000


class SafeHttpError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class SafeResponse:
    url: str
    status: int
    headers: Mapping[str, str]
    content: bytes
    elapsed_ms: int
    history: list[str]

    @property
    def text(self) -> str:
        content_type = self.headers.get("content-type", "")
        encoding = "utf-8"
        match = re.search(r"charset=([\w-]+)", content_type, re.I)
        if match:
            encoding = match.group(1)
        try:
            return self.content.decode(encoding, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")

    def json(self):
        import json

        return json.loads(self.text)


NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")


def is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if ip.version == 6 and ip in NAT64_PREFIX:
        # NAT64 well-known prefix embeds an IPv4 address in the last 32 bits.
        embedded = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        return is_public_ip(str(embedded))
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def resolve_public_host(host: str, port: int = 443) -> list[str]:
    """Resolve a hostname and refuse it unless every address is public."""
    normalized = (host or "").strip().lower().rstrip(".")
    if not normalized:
        raise SafeHttpError("invalid_url", "URL tidak memiliki host.")
    if normalized in {"localhost", "localhost.localdomain"} or normalized.endswith(".local"):
        raise SafeHttpError("private_host", "Host lokal tidak diizinkan.")
    try:
        infos = socket.getaddrinfo(normalized, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SafeHttpError("dns_error", f"Host tidak bisa di-resolve: {exc}") from exc
    addresses = sorted({info[4][0] for info in infos})
    if not addresses or any(not is_public_ip(addr) for addr in addresses):
        raise SafeHttpError("private_host", "Host mengarah ke alamat privat atau reserved.")
    return addresses


def validate_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SafeHttpError("invalid_scheme", "Hanya URL http dan https yang diizinkan.")
    if not parsed.hostname:
        raise SafeHttpError("invalid_url", "URL tidak memiliki host.")
    if parsed.username or parsed.password:
        raise SafeHttpError("invalid_url", "URL dengan kredensial tidak diizinkan.")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise SafeHttpError("invalid_port", f"Port {port} tidak diizinkan untuk request keluar.")
    resolve_public_host(parsed.hostname, port)
    return urlunparse(parsed._replace(fragment=""))


def safe_request(
    method: str,
    url: str,
    *,
    timeout: float = 12.0,
    max_redirects: int = 3,
    headers: Mapping[str, str] | None = None,
    data=None,
    json=None,
    allow_http: bool = True,
) -> SafeResponse:
    current = validate_public_url(url)
    if not allow_http and current.startswith("http://"):
        raise SafeHttpError("invalid_scheme", "HTTPS wajib untuk request ini.")
    history: list[str] = []
    request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        request_headers.update(headers)
    started = time.perf_counter()
    for _ in range(max_redirects + 1):
        try:
            response = requests.request(
                method,
                current,
                timeout=timeout,
                allow_redirects=False,
                headers=request_headers,
                data=data,
                json=json,
                stream=True,
            )
        except requests.RequestException as exc:
            raise SafeHttpError("upstream_error", f"Request gagal: {exc}") from exc
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("location", "")
            response.close()
            if not location:
                raise SafeHttpError("upstream_error", "Redirect tanpa tujuan.")
            from urllib.parse import urljoin

            next_url = urljoin(current, location)
            current = validate_public_url(next_url)
            if not allow_http and current.startswith("http://"):
                raise SafeHttpError("invalid_scheme", "Redirect ke HTTP tidak diizinkan.")
            history.append(current)
            continue
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_BYTES:
                response.close()
                raise SafeHttpError("response_too_large", "Respons melebihi batas 2.5 MB.")
            chunks.append(chunk)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        response.close()
        return SafeResponse(
            url=current,
            status=response.status_code,
            headers=dict(response.headers),
            content=b"".join(chunks),
            elapsed_ms=elapsed_ms,
            history=history,
        )
    raise SafeHttpError("too_many_redirects", "Terlalu banyak redirect.")


def safe_get(url: str, **kwargs) -> SafeResponse:
    return safe_request("GET", url, **kwargs)


def safe_head(url: str, **kwargs) -> SafeResponse:
    return safe_request("HEAD", url, **kwargs)


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned[:120] or "file"


def safe_external_url(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES or not parsed.hostname:
        return None
    return value.strip()
