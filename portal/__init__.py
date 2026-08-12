import os

from flask import Flask, render_template

from . import db
from .config import get_config, get_or_create_secret_key
from .admin import admin_bp
from .public import public_bp


def create_app():
    cfg = get_config()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, "templates"),
        static_folder=os.path.join(project_root, "static"),
    )
    app.config.from_mapping(cfg)
    app.secret_key = cfg["SECRET_KEY"] or get_or_create_secret_key(cfg["DATA_DIR"])
    app.config["MAX_CONTENT_LENGTH"] = cfg["MAX_CONTENT_LENGTH"]

    db.init_db(cfg["DB_PATH"])

    from . import template_filters

    template_filters.init_app(app)

    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)

    @app.context_processor
    def inject_brand():
        from .branding import get_branding

        return {"brand": get_branding()}

    @app.errorhandler(403)
    def forbidden(e):
        return render_error(403, "You don't have permission to access this.")

    @app.errorhandler(404)
    def not_found(e):
        return render_error(404, "Page not found.")

    @app.errorhandler(410)
    def gone(e):
        return render_error(410, "This share has expired.")

    @app.errorhandler(413)
    def too_large(e):
        return render_error(413, "Uploaded file is too large.")

    return app


def render_error(code: int, message: str):
    from .branding import public_context

    return (
        render_template(
            "error.html", error_code=code, error_message=message, **public_context()
        ),
        code,
    )
