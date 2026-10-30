"""Create a zip backup of the SQLite database and uploads folder.

Usage:
    python scripts/backup.py
    python scripts/backup.py --output D:/backups
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from berkas.config import load_settings  # noqa: E402 - path setup must run first


def sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw = database_url[len(prefix) :]
    if not raw or raw == ":memory:":
        return None
    return Path(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup database SQLite dan folder unggahan.")
    parser.add_argument("--output", default="backups", help="Folder tujuan arsip zip.")
    args = parser.parse_args()

    settings = load_settings()
    db_path = sqlite_path(settings.database_url)
    uploads = Path(settings.upload_folder)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = out_dir / f"berkas-backup-{stamp}.zip"

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        if db_path and db_path.exists():
            with tempfile.TemporaryDirectory() as tmp:
                snapshot = Path(tmp) / "berkas.db"
                with closing(sqlite3.connect(db_path)) as source, closing(sqlite3.connect(snapshot)) as target:
                    source.backup(target)
                archive.write(snapshot, "berkas.db")
        else:
            print("Database SQLite tidak ditemukan. Hanya folder unggahan yang dibackup.")

        if uploads.exists():
            for path in sorted(uploads.rglob("*")):
                if path.is_file():
                    archive.write(path, Path("uploads") / path.relative_to(uploads))
        else:
            print(f"Folder unggahan tidak ditemukan: {uploads}")

    print(f"Backup selesai: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
