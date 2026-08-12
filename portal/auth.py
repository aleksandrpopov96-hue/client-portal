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


def ensure_admin_bootstrapped() -> None:
    from . import db
    from flask import current_app

    if db.get_setting("admin_password_hash"):
        return
    default = current_app.config["ADMIN_PASSWORD"]
    if default:
        set_admin_password(default)
    else:
        set_admin_password("admin")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login", next=request_path()))
        return view(*args, **kwargs)

    return wrapped


def request_path():
    from flask import request

    return request.path + (("?" + request.query_string.decode()) if request.query_string else "")
