from __future__ import annotations

import pytest

from berkas.security import (
    SafeHttpError,
    is_public_ip,
    resolve_public_host,
    sanitize_filename,
    validate_public_url,
)
from berkas.tools.network import domain_ssl


def test_sanitize_filename_strips_paths_and_control_chars():
    cleaned = sanitize_filename("../../etc/passwd")
    assert "/" not in cleaned and "\\" not in cleaned
    assert ".." not in cleaned
    null_name = sanitize_filename("laporan\x00.txt")
    assert "\x00" not in null_name and null_name.endswith(".txt")
    assert sanitize_filename("") == "file"
    assert len(sanitize_filename("a" * 400)) <= 120


def test_private_ips_are_rejected():
    for value in ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.1.1", "::1", "not-an-ip"]:
        assert is_public_ip(value) is False
    assert is_public_ip("8.8.8.8") is True


def test_validate_public_url_blocks_internal_targets():
    for url in [
        "http://127.0.0.1/admin",
        "http://localhost:5000/",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "javascript:alert(1)",
    ]:
        try:
            validate_public_url(url)
        except (ValueError, SafeHttpError):
            continue
        raise AssertionError(f"{url} seharusnya ditolak")

    assert validate_public_url("https://example.com/path").startswith("https://example.com/path")


def test_resolve_public_host_blocks_local_and_empty_names():
    for host in ["localhost", "localhost.localdomain", "printer.local", "", "   "]:
        with pytest.raises(SafeHttpError):
            resolve_public_host(host)


def test_resolve_public_host_returns_public_addresses():
    addresses = resolve_public_host("example.com")
    assert addresses
    assert all(is_public_ip(address) for address in addresses)


def test_domain_ssl_rejects_private_targets_before_connecting():
    for value in ["127.0.0.1", "localhost", "http://169.254.169.254/", "http://10.0.0.5:8443"]:
        result = domain_ssl(value, {})
        assert result.status == "error", value
        assert result.error_code in {"private_host", "dns_error"}, result.error_code
