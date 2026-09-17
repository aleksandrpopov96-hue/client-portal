from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from .. import db
from ..auth import ensure_admin_bootstrapped
from ..security import CSRF_COOKIE, get_csrf_token, issue_csrf_token
from .helpers import (
    check_admin,
    check_login,
    current_identity,
    get_client_ip,
    json_error,
)

auth_bp = Blueprint("api", __name__)


@auth_bp.get("/csrf")
def csrf():
    value = issue_csrf_token()
    return jsonify({"token": value, "cookie": CSRF_COOKIE})


@auth_bp.get("/branding")
def branding():
    from ..branding import get_branding

    return jsonify(get_branding())


@auth_bp.get("/config")
def site_config():
    cfg = current_app.config
    return jsonify(
        {
            "upload_chunk_mb": cfg["UPLOAD_CHUNK_MB"],
            "max_active_transfers": cfg["MAX_ACTIVE_TRANSFERS"],
            "preview_enabled": cfg["PREVIEW_ENABLED"],
        }
    )


@auth_bp.get("/session")
def session_info():
    return jsonify({"identity": current_identity(), "csrf": {"cookie": CSRF_COOKIE, "token": get_csrf_token()}})


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = check_login(username, password)
    if not user:
        db.log_access("anon", "login:fail", path=username, ip=get_client_ip())
        return json_error("Invalid username or password", 401)
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    db.touch_user_login(user["id"])
    db.log_access(f"user:{user['username']}", "login:ok", path="", ip=get_client_ip())
    return jsonify({"identity": current_identity()})


@auth_bp.post("/logout")
def logout():
    ident = current_identity()
    session.clear()
    return jsonify({"ok": True, "previous": ident})


@auth_bp.post("/admin/login")
def admin_login():
    ensure_admin_bootstrapped(current_app.config["ADMIN_PASSWORD"])
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not check_admin(username, password, current_app.config["ADMIN_USERNAME"]):
        db.log_access("anon", "admin_login:fail", path=username, ip=get_client_ip())
        return json_error("Invalid username or password", 401)
    session.clear()
    session.permanent = True
    session["admin_logged_in"] = True
    session["admin_username"] = username
    db.log_access(f"admin:{username}", "admin_login:ok", ip=get_client_ip())
    return jsonify({"identity": current_identity()})


@auth_bp.post("/admin/logout")
def admin_logout():
    session.clear()
    return jsonify({"ok": True})