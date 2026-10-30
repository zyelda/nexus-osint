from __future__ import annotations

from berkas.config import Settings


def test_blank_env_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("UPLOAD_FOLDER", "   ")
    settings = Settings()
    assert settings.database_url == "sqlite:///berkas.db"
    assert settings.upload_folder.endswith("uploads")


def test_production_requires_secret_key(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("FLASK_SECRET_KEY", "")
    settings = Settings()
    assert settings.is_production is True
    try:
        settings.resolved_secret()
    except RuntimeError:
        pass
    else:
        raise AssertionError("production tanpa secret harus gagal")


def test_legacy_token_env_is_still_read(monkeypatch):
    monkeypatch.delenv("BERKAS_API_TOKEN", raising=False)
    monkeypatch.setenv("NEXUS_API_TOKEN", "token-lama")
    assert Settings().api_token == "token-lama"


def test_new_token_env_wins_over_legacy(monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", "token-lama")
    monkeypatch.setenv("BERKAS_API_TOKEN", "token-baru")
    assert Settings().api_token == "token-baru"


def test_cors_origins_are_normalized(monkeypatch):
    monkeypatch.setenv("BERKAS_CORS_ORIGINS", "https://a.vercel.app/, https://b.example.com")
    assert Settings().cors_origins == ("https://a.vercel.app", "https://b.example.com")
