from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone

_lock = threading.Lock()
_DB_PATH = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db(db_path: str) -> None:
    global _DB_PATH
    _DB_PATH = db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with _lock, sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
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
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                allow_download INTEGER NOT NULL DEFAULT 1,
                allow_upload INTEGER NOT NULL DEFAULT 0,
                allow_delete INTEGER NOT NULL DEFAULT 0,
                max_upload_size_mb INTEGER NOT NULL DEFAULT 100,
                allowed_extensions TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            );
            CREATE TABLE IF NOT EXISTS access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                path TEXT NOT NULL DEFAULT '',
                ip TEXT,
                bytes INTEGER,
                created_at TEXT NOT NULL
            );
            """
        )
        _migrate(conn)


def _migrate(conn) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(shares)")}
    if "mode" not in cols:
        conn.execute(
            "ALTER TABLE shares ADD COLUMN mode TEXT NOT NULL DEFAULT 'both'"
        )
        conn.execute(
            "UPDATE shares SET mode='upload' WHERE allow_download=0 AND allow_upload=1"
        )
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "subfolder" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN subfolder TEXT NOT NULL DEFAULT '/'")
    if "note" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN note TEXT")
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(shares)")}
    if "note" not in cols:
        conn.execute("ALTER TABLE shares ADD COLUMN note TEXT")


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


# ---------------------------------------------------------------------------
# Shares
# ---------------------------------------------------------------------------


def create_share(
    token: str,
    name: str,
    subfolder: str,
    enabled: bool,
    password_hash: str | None,
    expires_at: str | None,
    mode: str,
    allow_download: bool,
    allow_upload: bool,
    allow_delete: bool,
    allowed_extensions: str | None,
    max_upload_size_mb: int,
    branding_color: str | None,
    note: str | None,
) -> int:
    now = _now()
    with _lock, get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO shares (token, name, subfolder, enabled, password_hash, "
            "expires_at, mode, allow_download, allow_upload, allow_delete, "
            "allowed_extensions, max_upload_size_mb, branding_color, note, "
            "created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                token, name, subfolder, int(enabled), password_hash, expires_at,
                mode, int(allow_download), int(allow_upload), int(allow_delete),
                allowed_extensions, max_upload_size_mb, branding_color, note, now, now,
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
    mode: str,
    allow_download: bool,
    allow_upload: bool,
    allow_delete: bool,
    allowed_extensions: str | None,
    max_upload_size_mb: int,
    branding_color: str | None,
    note: str | None,
) -> None:
    now = _now()
    with _lock, get_conn() as conn:
        conn.execute(
            "UPDATE shares SET name=?, subfolder=?, enabled=?, password_hash=?, "
            "expires_at=?, mode=?, allow_download=?, allow_upload=?, allow_delete=?, "
            "allowed_extensions=?, max_upload_size_mb=?, branding_color=?, note=?, "
            "updated_at=? WHERE id=?",
            (
                name, subfolder, int(enabled), password_hash, expires_at, mode,
                int(allow_download), int(allow_upload), int(allow_delete),
                allowed_extensions, max_upload_size_mb, branding_color, note, now,
                share_id,
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


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def create_user(
    username: str,
    password_hash: str,
    enabled: bool,
    allow_download: bool,
    allow_upload: bool,
    allow_delete: bool,
    max_upload_size_mb: int,
    allowed_extensions: str | None,
    subfolder: str,
    note: str | None,
) -> int:
    now = _now()
    with _lock, get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, enabled, allow_download, "
            "allow_upload, allow_delete, max_upload_size_mb, allowed_extensions, "
            "subfolder, note, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                username, password_hash, int(enabled), int(allow_download),
                int(allow_upload), int(allow_delete), max_upload_size_mb,
                allowed_extensions, subfolder, note, now, now,
            ),
        )
        return cur.lastrowid


def update_user(
    user_id: int,
    username: str,
    password_hash: str | None,
    enabled: bool,
    allow_download: bool,
    allow_upload: bool,
    allow_delete: bool,
    max_upload_size_mb: int,
    allowed_extensions: str | None,
    subfolder: str,
    note: str | None,
) -> None:
    now = _now()
    with _lock, get_conn() as conn:
        if password_hash:
            conn.execute(
                "UPDATE users SET username=?, password_hash=?, enabled=?, "
                "allow_download=?, allow_upload=?, allow_delete=?, "
                "max_upload_size_mb=?, allowed_extensions=?, subfolder=?, note=?, "
                "updated_at=? WHERE id=?",
                (
                    username, password_hash, int(enabled), int(allow_download),
                    int(allow_upload), int(allow_delete), max_upload_size_mb,
                    allowed_extensions, subfolder, note, now, user_id,
                ),
            )
        else:
            conn.execute(
                "UPDATE users SET username=?, enabled=?, allow_download=?, "
                "allow_upload=?, allow_delete=?, max_upload_size_mb=?, "
                "allowed_extensions=?, subfolder=?, note=?, updated_at=? WHERE id=?",
                (
                    username, int(enabled), int(allow_download), int(allow_upload),
                    int(allow_delete), max_upload_size_mb, allowed_extensions,
                    subfolder, note, now, user_id,
                ),
            )


def delete_user(user_id: int) -> None:
    with _lock, get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))


def get_user(user_id: int):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return row


def get_user_by_username(username: str):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return row


def list_users():
    with _lock, get_conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY username").fetchall()
    return rows


def touch_user_login(user_id: int) -> None:
    now = _now()
    with _lock, get_conn() as conn:
        conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (now, user_id))


# ---------------------------------------------------------------------------
# Access log
# ---------------------------------------------------------------------------


def log_access(actor: str, action: str, path: str = "", ip: str | None = None, bytes: int | None = None) -> None:
    now = _now()
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT INTO access_log (actor, action, path, ip, bytes, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (actor, action, path, ip, bytes, now),
        )


def list_access_log(limit: int = 200):
    with _lock, get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM access_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return rows


def stats_summary():
    with _lock, get_conn() as conn:
        actors = conn.execute(
            "SELECT actor, COUNT(*) AS n, "
            "SUM(CASE WHEN action LIKE 'download:%' THEN 1 ELSE 0 END) AS downloads, "
            "SUM(CASE WHEN action LIKE 'upload:%' THEN 1 ELSE 0 END) AS uploads, "
            "SUM(bytes) AS total_bytes "
            "FROM access_log GROUP BY actor ORDER BY n DESC"
        ).fetchall()
        total_entries = conn.execute("SELECT COUNT(*) AS n FROM access_log").fetchone()["n"]
    return {"actors": actors, "total_entries": total_entries}