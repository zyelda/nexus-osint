from __future__ import annotations

from berkas.tools.identity import nik_parse, npwp_parse
from berkas.tools.registry import registry


def test_registry_has_unique_ids_and_public_metadata():
    specs = registry.all()
    ids = [spec.id for spec in specs]
    assert len(ids) == len(set(ids))
    public = registry.public(type("S", (), {"vt_api_key": "", "shodan_api_key": "", "abuseipdb_api_key": "", "hibp_api_key": "", "urlscan_api_key": "", "groq_api_key": ""})())
    assert len(public) == len(specs)
    for item in public:
        assert item["id"] and item["label"] and item["inputs"]
        assert isinstance(item["configured"], bool)


def test_nik_parse_extracts_region_and_birth_date():
    result = nik_parse("3173010101900001", {})
    assert result.status == "success"
    assert result.data["province"] == "DKI Jakarta"
    assert result.data["birth_date"].startswith("1990-01-01")
    assert result.data["gender"] == "Laki-laki"
    assert result.evidence
    assert result.evidence[0].entity_key == "nik:3173010101900001"


def test_nik_parse_rejects_bad_length():
    result = nik_parse("123", {})
    assert result.status == "error"
    assert result.error_code == "invalid_input"


def test_npwp_parse_formats_and_flags_branch():
    result = npwp_parse("09.254.294.3-407.000", {})
    assert result.status == "success"
    assert result.data["npwp"] == "09.254.294.3-407.000"
    assert result.data["status"] == "Pusat"

    branch = npwp_parse("092542943407001", {})
    assert branch.status == "success"
    assert branch.data["status"] == "Cabang"


def test_npwp_parse_rejects_wrong_length():
    result = npwp_parse("12345", {})
    assert result.status == "error"
