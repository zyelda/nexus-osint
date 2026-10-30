from __future__ import annotations

from berkas.entities import entity_from_value, parse_text, tools_for_type


def test_parse_mixed_entities_in_one_input():
    text = (
        "Nama: Budi Santoso\n"
        "email: Budi@Example.com\n"
        "hp: 0812-3456-7890\n"
        "username: budi_s\n"
        "https://example.com/profil\n"
    )
    parsed = parse_text(text)
    by_type = {item.type: item for item in parsed}

    assert by_type["email"].normalized == "budi@example.com"
    assert by_type["phone"].normalized == "+6281234567890"
    assert by_type["username"].normalized == "budi_s"
    assert by_type["domain"].normalized == "example.com"
    assert by_type["url"].normalized.startswith("https://example.com")
    assert by_type["person"].value == "Budi Santoso"
    assert all(0 <= item.confidence <= 1 for item in parsed)


def test_parse_deduplicates_repeated_values():
    parsed = parse_text("a@example.com\na@example.com\nA@example.com")
    emails = [item for item in parsed if item.type == "email"]
    assert len(emails) == 1


def test_entity_from_value_rejects_unknown_type_and_empty_value():
    assert entity_from_value("bukan-entity", "tipe-tidak-ada") is None
    assert entity_from_value("   ", "email") is None


def test_entity_from_value_respects_explicit_type():
    item = entity_from_value("3173010101900001", "nik")
    assert item is not None
    assert item.type == "nik"


def test_tools_for_type_are_registered():
    email_tools = tools_for_type("email")
    assert "email_intel" in email_tools
    assert "github_user" not in email_tools
    assert tools_for_type("tidak-ada") == []
