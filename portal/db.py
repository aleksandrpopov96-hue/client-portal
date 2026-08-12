from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime

_lock = threading.Lock()
_DB_PATH = None


def init_db(db_path: str) -> None:
    global _DB_PATH
    _DB_PATH = db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with _lock, sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                subfolder TEXT NOT NULL DEFAULT '/',
                enabled INTEGER NOT NULL DEFAULT 1,
                password_hash TEXT,
                expires_at TEXT,
                allow_download INTEGER NOT NULL DEFAULT 1,
                allow_upload INTEGER NOT NULL DEFAULT 0,
                allow_delete INTEGER NOT NULL DEFAULT 0,
                allowed_extensions TEXT,
                max_upload_size_mb INTEGER NOT NULL DEFAULT 100,
                branding_color TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT
            );
            """
        )


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def get_conn():
    if _DB_PATH is None:
        raise RuntimeError("Database not initialised")
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_setting(key: str, default: str | None = None) -> str | None:
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def all_settings() -> dict:
    with _lock, get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def create_share(
    token: str,
    name: str,
    subfolder: str,
    enabled: bool,
    password_hash: str | None,
    expires_at: str | None,
    allow_download: bool,
    allow_upload: bool,
    allow_delete: bool,
    allowed_extensions: str | None,
    max_upload_size_mb: int,
    branding_color: str | None,
) -> int:
    now = _now()
    with _lock, get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO shares (token, name, subfolder, enabled, password_hash, "
            "expires_at, allow_download, allow_upload, allow_delete, allowed_extensions, "
            "max_upload_size_mb, branding_color, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                token, name, subfolder, int(enabled), password_hash, expires_at,
                int(allow_download), int(allow_upload), int(allow_delete),
                allowed_extensions, max_upload_size_mb, branding_color, now, now,
            ),
        )
        return cur.lastrowid


def update_share(
    share_id: int,
    name: str,
    subfolder: str,
    enabled: bool,
    password_hash: str | None,
    expires_at: str | None,
    allow_download: bool,
    allow_upload: bool,
    allow_delete: bool,
    allowed_extensions: str | None,
    max_upload_size_mb: int,
    branding_color: str | None,
) -> None:
    now = _now()
    with _lock, get_conn() as conn:
        conn.execute(
            "UPDATE shares SET name=?, subfolder=?, enabled=?, password_hash=?, "
            "expires_at=?, allow_download=?, allow_upload=?, allow_delete=?, "
            "allowed_extensions=?, max_upload_size_mb=?, branding_color=?, updated_at=? "
            "WHERE id=?",
            (
                name, subfolder, int(enabled), password_hash, expires_at,
                int(allow_download), int(allow_upload), int(allow_delete),
                allowed_extensions, max_upload_size_mb, branding_color, now, share_id,
            ),
        )


def delete_share(share_id: int) -> None:
    with _lock, get_conn() as conn:
        conn.execute("DELETE FROM shares WHERE id=?", (share_id,))


def get_share(share_id: int):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM shares WHERE id=?", (share_id,)).fetchone()
    return row


def get_share_by_token(token: str):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM shares WHERE token=?", (token,)).fetchone()
    return row


def list_shares():
    with _lock, get_conn() as conn:
        rows = conn.execute("SELECT * FROM shares ORDER BY created_at DESC").fetchall()
    return rows


def touch_share(share_id: int) -> None:
    now = _now()
    with _lock, get_conn() as conn:
        conn.execute("UPDATE shares SET last_used_at=? WHERE id=?", (now, share_id))
