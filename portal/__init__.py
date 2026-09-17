import os

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db
from .config import get_config, get_or_create_secret_key


def create_app():
    cfg = get_config()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        static_folder=os.path.join(project_root, "static"),
    )
    app.config.from_mapping(cfg)
    app.secret_key = cfg["SECRET_KEY"] or get_or_create_secret_key(cfg["DATA_DIR"])
    app.config["MAX_CONTENT_LENGTH"] = cfg["MAX_CONTENT_LENGTH"]

    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=0
        )

    from . import security

    security.configure_session(app)
    security.before_request_hooks(app)
    security.after_request_headers(app)

    db.init_db(cfg["DB_PATH"])

    from .auth import ensure_admin_bootstrapped

    ensure_admin_bootstrapped(cfg["ADMIN_PASSWORD"])

    from .ratelimit import init_limiter, register_limiter_rules

    init_limiter(app)
    register_limiter_rules(app)

    from .api import init_api

    init_api(app)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa_fallback(path):
        if path.startswith("api/") or path.startswith("brand/"):
            return _not_found()
        candidate = os.path.join(app.static_folder or "", path)
        if path and os.path.isfile(candidate):
            return send_from_directory(app.static_folder or "", path)
        return send_from_directory(app.static_folder or "", "index.html")

    _register_error_handlers(app)

    return app


def _register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return _not_found()

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Forbidden", "detail": "You don't have permission."}), 403
        return _not_found()

    @app.errorhandler(410)
    def gone(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Gone", "detail": "This share has expired."}), 410
        return _not_found()

    @app.errorhandler(413)
    def too_large(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Payload too large", "detail": "Uploaded data exceeds the server limit."}), 413
        return _not_found()

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({"error": "Too many requests", "detail": "Slow down and try again shortly."}), 429

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return _not_found()


def _not_found():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    try:
        static = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static"
        )
        index = os.path.join(static, "index.html")
        if os.path.isfile(index):
            return send_from_directory(static, "index.html")
    except Exception:
        pass
    return render_template("error.html", error_code=404, error_message="Page not found."), 404