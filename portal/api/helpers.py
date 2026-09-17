from __future__ import annotations

from flask import jsonify, request, session
from werkzeug.security import check_password_hash

from .. import db
from ..security import csrf_ok


def json_error(message: str, status: int = 400, detail: str | None = None):
    payload = {"error": message}
    if detail:
        payload["detail"] = detail
    return jsonify(payload), status


def get_client_ip() -> str:
    cf = request.headers.get("CF-Connecting-IP", "")
    if cf:
        return cf
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or ""


def current_identity() -> dict | None:
    if session.get("admin_logged_in"):
        return {"role": "admin", "username": session.get("admin_username", "admin")}
    uid = session.get("user_id")
    if uid:
        user = db.get_user(uid)
        if user and user["enabled"]:
            return {"role": "user", "id": user["id"], "username": user["username"]}
    return None


def require_admin():
    if not session.get("admin_logged_in"):
        return json_error("Admin login required", 401)
    return None


def require_user():
    uid = session.get("user_id")
    if not uid:
        return json_error("Login required", 401)
    user = db.get_user(uid)
    if not user or not user["enabled"]:
        session.pop("user_id", None)
        return json_error("Login required", 401)
    return user


def audit(action: str, path: str = "", **kw):
    try:
        db.log_access(
            actor=kw.get("actor") or _actor(),
            action=action,
            path=path,
            ip=kw.get("ip") or get_client_ip(),
            bytes=kw.get("bytes"),
        )
    except Exception:
        pass


def _actor() -> str:
    ident = current_identity()
    if ident:
        return f"{ident['role']}:{ident['username']}"
    token = request.view_args.get("token") if request.view_args else None
    if token:
        return f"share:{token}"
    return "anon"


def check_login(username: str, password: str) -> dict | None:
    user = db.get_user_by_username(username)
    if not user or not user["enabled"]:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


def check_admin(username: str, password: str, expected: str) -> bool:
    key = "admin_password_hash"
    stored = db.get_setting(key)
    if not stored:
        return False
    if username != expected:
        return False
    return check_password_hash(stored, password)