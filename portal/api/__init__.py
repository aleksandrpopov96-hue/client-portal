from __future__ import annotations

from flask import jsonify, request

from ..security import csrf_ok
from .admin import admin_bp, brand_bp
from .auth import auth_bp
from .browser import browser_bp
from .public import public_bp

blueprints = [auth_bp, public_bp, browser_bp, admin_bp]


def apply_runtime_settings(app) -> None:
    """Merge persisted runtime overrides from the DB into live config."""
    from .. import db

    for key in app.config:
        stored = db.get_setting(f"runtime_{key}")
        if stored is None:
            continue
        try:
            if stored in ("0", "1"):
                app.config[key] = stored == "1"
            else:
                app.config[key] = int(stored)
        except (TypeError, ValueError):
            pass


def init_api(app) -> None:
    apply_runtime_settings(app)

    for bp in blueprints:
        app.register_blueprint(bp, url_prefix="/api")
    app.register_blueprint(brand_bp)

    @app.before_request
    def _api_csrf_guard():
        if request.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS", "TRACE"):
            if not csrf_ok():
                return jsonify({"error": "CSRF token missing or invalid", "detail": "Reload the page."}), 403