import os
import secrets
from dataclasses import dataclass, field


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _str(name: str, default: str = "") -> str:
    value = os.environ.get(name, "")
    return value if value.strip() else default


def _env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "")
        if value.strip():
            return value
    return ""


@dataclass(frozen=True)
class Settings:
    environment: str = field(default_factory=lambda: _str("FLASK_ENV", "development"))
    debug: bool = field(default_factory=lambda: _bool("FLASK_DEBUG", False))
    secret_key: str = field(default_factory=lambda: _str("FLASK_SECRET_KEY", ""))
    database_url: str = field(
        default_factory=lambda: _str("DATABASE_URL", "sqlite:///berkas.db")
    )
    upload_folder: str = field(
        default_factory=lambda: _str("UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
    )
    max_content_length: int = field(default_factory=lambda: _int("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    max_workers: int = field(default_factory=lambda: _int("MAX_WORKERS", 6))
    max_runs_per_batch: int = field(default_factory=lambda: max(1, _int("MAX_RUNS_PER_BATCH", 12)))
    api_token: str = field(default_factory=lambda: _env("BERKAS_API_TOKEN", "NEXUS_API_TOKEN"))
    tool_cache_ttl: int = field(default_factory=lambda: max(0, _int("TOOL_CACHE_TTL", 3600)))
    summary_cache_ttl: int = field(default_factory=lambda: max(0, _int("SUMMARY_CACHE_TTL", 86400)))
    public_redaction: bool = field(default_factory=lambda: _bool("PUBLIC_REDACTION", True))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip().rstrip("/")
            for origin in _str("BERKAS_CORS_ORIGINS", "").split(",")
            if origin.strip()
        )
    )

    groq_api_key: str = field(default_factory=lambda: os.environ.get("GROQ_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    ai_provider: str = field(default_factory=lambda: _str("AI_PROVIDER", "auto"))
    ai_model: str = field(default_factory=lambda: _str("AI_MODEL", ""))
    ai_base_url: str = field(default_factory=lambda: _str("AI_BASE_URL", ""))
    ai_timeout_s: int = field(default_factory=lambda: max(5, _int("AI_TIMEOUT_S", 30)))

    vt_api_key: str = field(default_factory=lambda: os.environ.get("VT_API_KEY", ""))
    shodan_api_key: str = field(default_factory=lambda: os.environ.get("SHODAN_API_KEY", ""))
    abuseipdb_api_key: str = field(default_factory=lambda: os.environ.get("ABUSEIPDB_API_KEY", ""))
    hibp_api_key: str = field(default_factory=lambda: os.environ.get("HIBP_API_KEY", ""))

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def resolved_secret(self) -> str:
        if self.secret_key:
            return self.secret_key
        if self.is_production:
            raise RuntimeError("FLASK_SECRET_KEY wajib diset di production.")
        return secrets.token_hex(32)


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    return Settings()
