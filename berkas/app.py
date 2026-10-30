from __future__ import annotations

import os

from flask import Flask, jsonify, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from berkas.api import api
from berkas.config import Settings, load_settings
from berkas.db import Database

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")
LEGACY_DATABASE_FILENAME = "nexus_osint.db"


def _migrate_legacy_database(settings: Settings) -> None:
    """Rename the pre-rename SQLite file once so existing cases survive."""
    if settings.database_url not in {"sqlite:///berkas.db", "sqlite:///./berkas.db"}:
        return
    target = os.path.join(os.getcwd(), "berkas.db")
    legacy = os.path.join(os.getcwd(), LEGACY_DATABASE_FILENAME)
    if not os.path.exists(target) and os.path.exists(legacy):
        os.replace(legacy, target)


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or load_settings()
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SECRET_KEY=settings.resolved_secret(),
        MAX_CONTENT_LENGTH=settings.max_content_length,
        JSON_SORT_KEYS=False,
    )

    _migrate_legacy_database(settings)
    database = Database(settings.database_url)
    database.init()
    app.extensions["berkas"] = {"settings": settings, "db": database}

    Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["600 per hour", "120 per minute"],
        storage_uri="memory://",
    )

    app.register_blueprint(api)
    allowed_origins = set(settings.cors_origins)

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        origin = request.headers.get("Origin")
        if origin and origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Berkas-Token, X-Nexus-Token"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
            response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
            response.headers["Access-Control-Max-Age"] = "600"
            response.headers.add("Vary", "Origin")
        if response.mimetype == "text/html":
            # The backend address can be set at runtime in the browser, so a
            # fixed allowlist would block every origin except the built one.
            connect_sources = " ".join(["'self'", "https:", "http:", *settings.cors_origins])
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: blob: https:; "
                "style-src 'self' 'unsafe-inline'; script-src 'self'; "
                f"connect-src {connect_sources}; font-src 'self' data:; frame-ancestors 'none'",
            )
        return response

    @app.errorhandler(413)
    def _too_large(_error):
        return jsonify({"error": "file_too_large", "message": "Ukuran upload melebihi batas."}), 413

    @app.get("/")
    def _index():
        if os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
            return send_from_directory(FRONTEND_DIST, "index.html")
        return jsonify(
            {
                "name": "Berkas",
                "status": "backend_only",
                "message": "Frontend belum dibuild. Jalankan: cd frontend && npm install && npm run build",
                "api": "/api/v1/health",
            }
        )

    @app.get("/<path:path>")
    def _spa(path: str):
        if path.startswith("api/"):
            return jsonify({"error": "not_found", "message": "Endpoint tidak ditemukan."}), 404
        candidate = os.path.join(FRONTEND_DIST, path)
        if os.path.isfile(candidate):
            return send_from_directory(FRONTEND_DIST, path)
        if os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
            return send_from_directory(FRONTEND_DIST, "index.html")
        return jsonify({"error": "not_found", "message": "Aset tidak ditemukan."}), 404

    return app
