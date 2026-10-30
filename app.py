"""Berkas entrypoint.

Development:
    python app.py

Production (Linux container):
    gunicorn --workers 2 --threads 8 --timeout 120 "berkas.app:create_app()"
"""

from __future__ import annotations

import os

from berkas.app import create_app
from berkas.config import load_settings

settings = load_settings()
app = create_app(settings)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=settings.debug, threaded=True)
