from __future__ import annotations

import hmac
import secrets
from functools import wraps

from flask import current_app, g, jsonify, request, session

CSRF_COOKIE = "portal_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def _csrf_value() -> str:
    value = session.get("_csrf")
    if not value:
        value = secrets.token_urlsafe(32)
        session["_csrf"] = value
    return value


def issue_csrf_token() -> str:
    """Ensure the CSRF session value exists and return it. The cookie is
    attached to every /api response by an after_request hook."""
    return _csrf_value()


def get_csrf_token() -> str:
    return _csrf_value()


def csrf_ok() -> bool:
    """Double-submit cookie style check."""
    token = request.headers.get(CSRF_HEADER, "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not token or not cookie:
        return False
    return hmac.compare_digest(token, cookie)


def csrf_protect(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method not in SAFE_METHODS and not csrf_ok():
            return jsonify({"error": "CSRF token missing or invalid", "detail": "Reload the page."}), 403
        return view(*args, **kwargs)

    return wrapped


def _use_secure_cookie() -> bool:
    return (
        request.scheme == "https"
        or request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip() == "https"
    )


def configure_session(app) -> None:
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=app.config.get("SESSION_LIFETIME_HOURS", 12) * 3600,
    )


def before_request_hooks(app) -> None:
    @app.before_request
    def _secure_cookie_flag():
        g.secure_cookie = _use_secure_cookie()

    @app.before_request
    def _make_session_permanent():
        session.permanent = True


def after_request_headers(app) -> None:
    @app.after_request
    def _add_security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("X-XSS-Protection", "0")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' blob: data:; "
            "media-src 'self' blob:; "
            "frame-src 'self' blob:; "
            "object-src 'none'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "connect-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'",
        )
        return resp

    @app.after_request
    def _attach_csrf_cookie(resp):
        if request.path.startswith("/api/"):
            value = session.get("_csrf")
            if value:
                resp.set_cookie(
                    CSRF_COOKIE,
                    value,
                    httponly=False,
                    samesite="Lax",
                    secure=_use_secure_cookie(),
                    max_age=app.config.get("SESSION_LIFETIME_HOURS", 12) * 3600,
                    path="/",
                )
        return resp