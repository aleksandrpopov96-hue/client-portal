from __future__ import annotations

from functools import wraps

from flask import redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


def set_admin_password(password: str) -> None:
    from . import db

    db.set_setting("admin_password_hash", generate_password_hash(password, method="pbkdf2"))


def verify_admin_password(password: str) -> bool:
    from . import db

    stored = db.get_setting("admin_password_hash")
    if not stored:
        return False
    return check_password_hash(stored, password)


def ensure_admin_bootstrapped(configured_password: str | None = None) -> None:
    """Make PORTAL_ADMIN_PASSWORD the source of truth for the admin login.

    If the env var is set (and not the placeholder), always apply it so that
    changing .env takes effect on redeploy. Only fall back to 'admin' when
    nothing is configured.
    """
    from . import db

    if configured_password and configured_password != "CHANGE_ME":
        set_admin_password(configured_password)
    elif not db.get_setting("admin_password_hash"):
        set_admin_password("admin")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login", next=request_path()))
        return view(*args, **kwargs)

    return wrapped


def user_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        from . import db

        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("browser.login", next=request_path()))
        user = db.get_user(user_id)
        if not user or not user["enabled"]:
            session.pop("user_id", None)
            return redirect(url_for("browser.login", next=request_path()))
        return view(*args, **kwargs)

    return wrapped


def request_path():
    from flask import request

    return request.path + (("?" + request.query_string.decode()) if request.query_string else "")
