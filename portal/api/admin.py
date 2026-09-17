from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.security import generate_password_hash

from .. import db
from ..auth import ensure_admin_bootstrapped
from ..branding import get_branding
from ..ratelimit import admin_transfer_stats
from .helpers import audit, json_error, require_admin

admin_bp = Blueprint("api_admin", __name__)
brand_bp = Blueprint("brand_files", __name__)


def _guard():
    return require_admin()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bool(value) -> bool:
    return value in (True, "on", "1", "true", "yes")


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def _exts(value):
    if not value:
        return None
    if isinstance(value, (list, tuple)):
        parts = [str(x) for x in value]
    else:
        parts = str(value).split(",")
    cleaned = ",".join(
        e.strip().lower().lstrip(".")
        for e in parts
        if e.strip()
    )
    return cleaned or None


def _share_payload(share) -> dict:
    return {
        "id": share["id"],
        "token": share["token"],
        "name": share["name"],
        "subfolder": share["subfolder"],
        "enabled": bool(share["enabled"]),
        "mode": share["mode"],
        "password_hash": share["password_hash"],
        "has_password": bool(share["password_hash"]),
        "expires_at": share["expires_at"],
        "allow_download": bool(share["allow_download"]),
        "allow_upload": bool(share["allow_upload"]),
        "allow_delete": bool(share["allow_delete"]),
        "allowed_extensions": share["allowed_extensions"],
        "max_upload_size_mb": share["max_upload_size_mb"],
        "branding_color": share["branding_color"],
        "note": share["note"],
        "created_at": share["created_at"],
        "updated_at": share["updated_at"],
        "last_used_at": share["last_used_at"],
    }


def _user_payload(user) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "enabled": bool(user["enabled"]),
        "allow_download": bool(user["allow_download"]),
        "allow_upload": bool(user["allow_upload"]),
        "allow_delete": bool(user["allow_delete"]),
        "max_upload_size_mb": user["max_upload_size_mb"],
        "allowed_extensions": user["allowed_extensions"],
        "subfolder": user["subfolder"],
        "note": user["note"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
        "last_login_at": user["last_login_at"],
    }


@admin_bp.get("/admin/stats")
def stats():
    err = _guard()
    if err:
        return err
    shares = db.list_shares()
    users = db.list_users()
    summary = db.stats_summary()
    summary = {
        "total_entries": summary["total_entries"],
        "actors": [dict(a) for a in summary["actors"]],
    }
    return jsonify(
        {
            "shares": {"total": len(shares), "enabled": sum(1 for s in shares if s["enabled"])},
            "users": {"total": len(users), "enabled": sum(1 for u in users if u["enabled"])},
            "access_log": summary,
            "transfers": admin_transfer_stats(),
            "storage_root": current_app.config["STORAGE_ROOT"],
        }
    )


@admin_bp.get("/admin/audit")
def audit_log():
    err = _guard()
    if err:
        return err
    try:
        limit = int(request.args.get("limit", 200))
    except (TypeError, ValueError):
        limit = 200
    limit = min(max(limit, 1), 1000)
    rows = db.list_access_log(limit)
    return jsonify(
        {
            "entries": [
                {
                    "id": r["id"],
                    "actor": r["actor"],
                    "action": r["action"],
                    "path": r["path"],
                    "ip": r["ip"],
                    "bytes": r["bytes"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        }
    )


# ---------------------------------------------------------------------------
# Shares
# ---------------------------------------------------------------------------


@admin_bp.get("/admin/shares")
def shares_list():
    err = _guard()
    if err:
        return err
    rows = db.list_shares()
    base = request.url_root.rstrip("/")
    return jsonify(
        {
            "base_url": base,
            "shares": [
                {**_share_payload(s), "url": f"{base}/s/{s['token']}"}
                for s in rows
            ],
        }
    )


@admin_bp.post("/admin/shares")
def shares_create():
    err = _guard()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    token = data.get("token") or secrets.token_urlsafe(9)
    share_id = db.create_share(
        token=token,
        name=(str(data.get("name") or "Untitled share")).strip(),
        subfolder=_norm_subfolder(data.get("subfolder") or "/"),
        enabled=_bool(data.get("enabled", True)),
        password_hash=generate_password_hash(password, method="pbkdf2") if password else None,
        expires_at=_parse_datetime(data.get("expires_at")),
        mode=_norm_mode(data.get("mode")),
        allow_download=_bool(data.get("allow_download", True)),
        allow_upload=_bool(data.get("allow_upload", False)),
        allow_delete=_bool(data.get("allow_delete", False)),
        allowed_extensions=_exts(data.get("allowed_extensions")),
        max_upload_size_mb=int(data.get("max_upload_size_mb") or 100),
        branding_color=(str(data.get("branding_color") or "").strip() or None),
        note=(str(data.get("note") or "")).strip() or None,
    )
    share = db.get_share(share_id)
    audit("admin:share:create", share["subfolder"], actor="admin")
    return jsonify(_share_payload(share)), 201


@admin_bp.put("/admin/shares/<int:share_id>")
def shares_update(share_id):
    err = _guard()
    if err:
        return err
    share = db.get_share(share_id)
    if share is None:
        return json_error("Share not found", 404)
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    password_hash = None
    if password:
        password_hash = generate_password_hash(password, method="pbkdf2")
    elif data.get("keep_password"):
        password_hash = share["password_hash"]
    db.update_share(
        share_id=share_id,
        name=(str(data.get("name") or share["name"])).strip(),
        subfolder=_norm_subfolder(data.get("subfolder") or share["subfolder"]),
        enabled=_bool(data.get("enabled", share["enabled"])),
        password_hash=password_hash,
        expires_at=_parse_datetime(data.get("expires_at")),
        mode=_norm_mode(data.get("mode") or share["mode"]),
        allow_download=_bool(data.get("allow_download", share["allow_download"])),
        allow_upload=_bool(data.get("allow_upload", share["allow_upload"])),
        allow_delete=_bool(data.get("allow_delete", share["allow_delete"])),
        allowed_extensions=_exts(data.get("allowed_extensions")) or share["allowed_extensions"],
        max_upload_size_mb=int(data.get("max_upload_size_mb") or share["max_upload_size_mb"]),
        branding_color=(str(data.get("branding_color") or share["branding_color"])).strip() or None,
        note=data.get("note", share["note"]) or None,
    )
    audit("admin:share:update", share["subfolder"], actor="admin")
    return jsonify(_share_payload(db.get_share(share_id)))


@admin_bp.delete("/admin/shares/<int:share_id>")
def shares_delete(share_id):
    err = _guard()
    if err:
        return err
    share = db.get_share(share_id)
    if share is None:
        return json_error("Share not found", 404)
    db.delete_share(share_id)
    audit("admin:share:delete", share["subfolder"], actor="admin")
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@admin_bp.get("/admin/users")
def users_list():
    err = _guard()
    if err:
        return err
    rows = db.list_users()
    return jsonify({"users": [_user_payload(u) for u in rows]})


@admin_bp.post("/admin/users")
def users_create():
    err = _guard()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    username = (str(data.get("username") or "")).strip()
    password = data.get("password") or ""
    if not username:
        return json_error("Username is required", 400)
    if not password:
        return json_error("A password is required when creating a user", 400)
    if db.get_user_by_username(username):
        return json_error("That username is already taken", 400)
    user_id = db.create_user(
        username=username,
        password_hash=generate_password_hash(password, method="pbkdf2"),
        enabled=_bool(data.get("enabled", True)),
        allow_download=_bool(data.get("allow_download", True)),
        allow_upload=_bool(data.get("allow_upload", False)),
        allow_delete=_bool(data.get("allow_delete", False)),
        max_upload_size_mb=int(data.get("max_upload_size_mb") or 100),
        allowed_extensions=_exts(data.get("allowed_extensions")),
        subfolder=_norm_subfolder(data.get("subfolder") or "/"),
        note=(str(data.get("note") or "")).strip() or None,
    )
    audit("admin:user:create", username, actor="admin")
    return jsonify(_user_payload(db.get_user(user_id))), 201


@admin_bp.put("/admin/users/<int:user_id>")
def users_update(user_id):
    err = _guard()
    if err:
        return err
    user = db.get_user(user_id)
    if user is None:
        return json_error("User not found", 404)
    data = request.get_json(silent=True) or {}
    username = (str(data.get("username") or user["username"])).strip()
    duplicate = db.get_user_by_username(username)
    if duplicate and duplicate["id"] != user_id:
        return json_error("That username is already taken", 400)
    password = data.get("password") or ""
    password_hash = generate_password_hash(password, method="pbkdf2") if password else None
    db.update_user(
        user_id=user_id,
        username=username,
        password_hash=password_hash,
        enabled=_bool(data.get("enabled", user["enabled"])),
        allow_download=_bool(data.get("allow_download", user["allow_download"])),
        allow_upload=_bool(data.get("allow_upload", user["allow_upload"])),
        allow_delete=_bool(data.get("allow_delete", user["allow_delete"])),
        max_upload_size_mb=int(data.get("max_upload_size_mb") or user["max_upload_size_mb"]),
        allowed_extensions=_exts(data.get("allowed_extensions")) or user["allowed_extensions"],
        subfolder=_norm_subfolder(data.get("subfolder") or user["subfolder"]),
        note=data.get("note", user["note"]) or None,
    )
    audit("admin:user:update", username, actor="admin")
    return jsonify(_user_payload(db.get_user(user_id)))


@admin_bp.delete("/admin/users/<int:user_id>")
def users_delete(user_id):
    err = _guard()
    if err:
        return err
    user = db.get_user(user_id)
    if user is None:
        return json_error("User not found", 404)
    db.delete_user(user_id)
    audit("admin:user:delete", user["username"], actor="admin")
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------


@admin_bp.get("/admin/branding")
def branding_get():
    err = _guard()
    if err:
        return err
    return jsonify(get_branding())


@admin_bp.post("/admin/branding")
def branding_set():
    err = _guard()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    fields = [
        "site_name", "tagline", "primary_color", "accent_color",
        "background_color", "card_color", "text_color", "welcome_title",
        "welcome_message", "footer_text",
    ]
    for field in fields:
        value = data.get(field)
        if value is None:
            continue
        value = str(value).strip()
        if field in ("primary_color", "accent_color", "background_color", "card_color", "text_color"):
            value = value or None
        db.set_setting(field, value)
    audit("admin:branding:update", "", actor="admin")
    return jsonify(get_branding())


@admin_bp.post("/admin/branding/logo")
def branding_logo():
    err = _guard()
    if err:
        return err
    logo = request.files.get("logo")
    if not logo or not logo.filename:
        return json_error("No file selected", 400)
    uploads_dir = current_app.config["UPLOADS_DIR"]
    os.makedirs(uploads_dir, exist_ok=True)
    for old in os.listdir(uploads_dir):
        os.unlink(os.path.join(uploads_dir, old))
    ext = os.path.splitext(logo.filename)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"):
        ext = ".png"
    safe = "logo" + ext
    logo.save(os.path.join(uploads_dir, safe))
    db.set_setting("logo", f"/brand/{safe}")
    audit("admin:branding:logo", "", actor="admin")
    return jsonify({"logo": f"/brand/{safe}"})


@brand_bp.get("/brand/<path:filename>")
def brand_file(filename):
    return send_from_directory(current_app.config["UPLOADS_DIR"], filename)


# ---------------------------------------------------------------------------
# Runtime settings (rate limits / caps) — persisted in DB, applied to live app
# ---------------------------------------------------------------------------

RUNTIME_KEYS = [
    "MAX_ACTIVE_TRANSFERS", "MAX_ACTIVE_TRANSFERS_PER_IP", "UPLOAD_CHUNK_MB",
    "RATELIMIT_LOGIN_PER_MIN", "RATELIMIT_API_PER_MIN",
    "RATELIMIT_DOWNLOAD_PER_MIN", "RATELIMIT_UPLOAD_CHUNK_PER_MIN",
]


@admin_bp.get("/admin/settings")
def settings_get():
    err = _guard()
    if err:
        return err
    cfg = current_app.config
    return jsonify(
        {
            "max_active_transfers": cfg["MAX_ACTIVE_TRANSFERS"],
            "max_active_transfers_per_ip": cfg["MAX_ACTIVE_TRANSFERS_PER_IP"],
            "upload_chunk_mb": cfg["UPLOAD_CHUNK_MB"],
            "ratelimit_login_per_min": cfg["RATELIMIT_LOGIN_PER_MIN"],
            "ratelimit_api_per_min": cfg["RATELIMIT_API_PER_MIN"],
            "ratelimit_download_per_min": cfg["RATELIMIT_DOWNLOAD_PER_MIN"],
            "ratelimit_upload_chunk_per_min": cfg["RATELIMIT_UPLOAD_CHUNK_PER_MIN"],
            "ratelimit_enabled": cfg["RATELIMIT_ENABLED"],
            "preview_enabled": cfg["PREVIEW_ENABLED"],
            "session_lifetime_hours": cfg["SESSION_LIFETIME_HOURS"],
        }
    )


@admin_bp.post("/admin/settings")
def settings_set():
    err = _guard()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    mapping = {
        "max_active_transfers": "MAX_ACTIVE_TRANSFERS",
        "max_active_transfers_per_ip": "MAX_ACTIVE_TRANSFERS_PER_IP",
        "upload_chunk_mb": "UPLOAD_CHUNK_MB",
        "ratelimit_login_per_min": "RATELIMIT_LOGIN_PER_MIN",
        "ratelimit_api_per_min": "RATELIMIT_API_PER_MIN",
        "ratelimit_download_per_min": "RATELIMIT_DOWNLOAD_PER_MIN",
        "ratelimit_upload_chunk_per_min": "RATELIMIT_UPLOAD_CHUNK_PER_MIN",
        "ratelimit_enabled": "RATELIMIT_ENABLED",
        "preview_enabled": "PREVIEW_ENABLED",
        "session_lifetime_hours": "SESSION_LIFETIME_HOURS",
    }
    for key, cfg_key in mapping.items():
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, bool):
            current_app.config[cfg_key] = value
            db.set_setting(f"runtime_{cfg_key}", "1" if value else "0")
        else:
            try:
                num = int(value)
            except (TypeError, ValueError):
                continue
            current_app.config[cfg_key] = num
            db.set_setting(f"runtime_{cfg_key}", str(num))
    audit("admin:settings:update", "", actor="admin")
    return settings_get()


def _norm_subfolder(value: str) -> str:
    sub = "/" + str(value or "").strip().lstrip("/")
    return "/" if sub == "//" else sub


def _norm_mode(value) -> str:
    mode = str(value or "both").lower()
    if mode not in ("browse", "upload", "both"):
        return "both"
    return mode