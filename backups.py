"""Daily SQLite + photo archives. Download a copy to protect against volume loss."""
import json
import os
import sqlite3
import tempfile
import threading
import zipfile
from contextlib import closing
from pathlib import Path

from config import DATA_DIR, DB_FILE, UPLOAD_DIR, get_current_time

_lock = threading.Lock()

def create_backup():
    with _lock:
        directory = Path(DATA_DIR) / "backups"
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"cats-backup-{get_current_time():%Y-%m-%d}.zip"
        with tempfile.TemporaryDirectory(prefix="cats-backup-") as scratch:
            snapshot = Path(scratch) / "cats.db"
            with closing(sqlite3.connect(DB_FILE)) as source, closing(sqlite3.connect(snapshot)) as target:
                source.backup(target)
            staging = directory / (destination.name + ".tmp")
            with zipfile.ZipFile(staging, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(snapshot, "cats.db")
                for photo in sorted(Path(UPLOAD_DIR).glob("*")):
                    if photo.is_file() and not photo.is_symlink() and photo.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                        archive.write(photo, "uploads/" + photo.name)
                archive.writestr("manifest.json", json.dumps({"version": 1, "created_at": get_current_time().isoformat()}, ensure_ascii=False))
                archive.writestr("RESTORE.txt", "Stop the bot. Extract cats.db and uploads/ into DATA_DIR. Start the bot. This archive contains private family data; keep it safe.\n")
            os.replace(staging, destination)
        # Only archives produced by this module; keep seven daily restore points.
        for old in sorted(directory.glob("cats-backup-????-??-??.zip"), reverse=True)[7:]:
            old.unlink()
        return str(destination)

def ensure_daily_backup():
    destination = Path(DATA_DIR) / "backups" / f"cats-backup-{get_current_time():%Y-%m-%d}.zip"
    if not destination.exists():
        return create_backup()
    return str(destination)
