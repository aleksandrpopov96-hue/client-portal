import os
import secrets
from datetime import datetime

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    send_from_directory, session, url_for,
)
from werkzeug.security import generate_password_hash

from . import db
from .auth import ensure_admin_bootstrapped, login_required, verify_admin_password

admin_bp = Blueprint("admin", __name__)


def _bool(value) -> bool:
    return value == "on"


def _parse_share_form():
    def dt(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).isoformat()
        except ValueError:
            return None

    subfolder = "/" + (request.form.get("subfolder", "").strip().lstrip("/"))
    if subfolder == "//":
        subfolder = "/"

    password = request.form.get("password", "")
    password_hash = generate_password_hash(password, method="pbkdf2") if password else None

    exts = ",".join(
        e.strip().lower().lstrip(".")
        for e in request.form.get("allowed_extensions", "").split(",")
        if e.strip()
    )

    return {
        "name": request.form.get("name", "").strip() or "Untitled share",
        "subfolder": subfolder,
        "enabled": _bool(request.form.get("enabled")),
        "password_hash": password_hash,
        "expires_at": dt(request.form.get("expires_at")),
        "allow_download": _bool(request.form.get("allow_download")),
        "allow_upload": _bool(request.form.get("allow_upload")),
        "allow_delete": _bool(request.form.get("allow_delete")),
        "allowed_extensions": exts or None,
        "max_upload_size_mb": int(request.form.get("max_upload_size_mb") or 100),
        "branding_color": (request.form.get("branding_color") or "").strip() or None,
    }


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def login():
    ensure_admin_bootstrapped()
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == current_app.config["ADMIN_USERNAME"] and verify_admin_password(password):
            session.clear()
            session["admin_logged_in"] = True
            return redirect(url_for("admin.dashboard"))
        flash("Invalid username or password", "error")
    return render_template("admin_login.html")


@admin_bp.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@admin_bp.route("/admin")
@login_required
def dashboard():
    shares = db.list_shares()
    for share in shares:
        share["_used"] = datetime.now() < datetime.fromisoformat(share["expires_at"]) if share["expires_at"] else True
    return render_template("admin_dashboard.html", shares=shares)


@admin_bp.route("/admin/shares/new")
@login_required
def share_new():
    return render_template(
        "admin_share_form.html",
        share=None,
        share_url_base=request.url_root.rstrip("/"),
    )


@admin_bp.route("/admin/shares/<int:share_id>/edit")
@login_required
def share_edit(share_id):
    share = db.get_share(share_id)
    if share is None:
        flash("Share not found", "error")
        return redirect(url_for("admin.dashboard"))
    return render_template(
        "admin_share_form.html",
        share=share,
        share_url_base=request.url_root.rstrip("/"),
    )


@admin_bp.route("/admin/shares", methods=["POST"])
@login_required
def share_create():
    data = _parse_share_form()
    token = secrets.token_urlsafe(9)
    db.create_share(
        token=token,
        name=data["name"],
        subfolder=data["subfolder"],
        enabled=data["enabled"],
        password_hash=data["password_hash"],
        expires_at=data["expires_at"],
        allow_download=data["allow_download"],
        allow_upload=data["allow_upload"],
        allow_delete=data["allow_delete"],
        allowed_extensions=data["allowed_extensions"],
        max_upload_size_mb=data["max_upload_size_mb"],
        branding_color=data["branding_color"],
    )
    flash(f"Share created. Link: {request.url_root.rstrip('/')}/s/{token}", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/admin/shares/<int:share_id>", methods=["POST"])
@login_required
def share_update(share_id):
    share = db.get_share(share_id)
    if share is None:
        flash("Share not found", "error")
        return redirect(url_for("admin.dashboard"))
    data = _parse_share_form()
    password_hash = data["password_hash"]
    if not password_hash and request.form.get("keep_password") == "on":
        password_hash = share["password_hash"]
    db.update_share(
        share_id=share_id,
        name=data["name"],
        subfolder=data["subfolder"],
        enabled=data["enabled"],
        password_hash=password_hash,
        expires_at=data["expires_at"],
        allow_download=data["allow_download"],
        allow_upload=data["allow_upload"],
        allow_delete=data["allow_delete"],
        allowed_extensions=data["allowed_extensions"],
        max_upload_size_mb=data["max_upload_size_mb"],
        branding_color=data["branding_color"],
    )
    flash("Share updated", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/admin/shares/<int:share_id>/delete", methods=["POST"])
@login_required
def share_delete(share_id):
    db.delete_share(share_id)
    flash("Share deleted", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/admin/branding", methods=["GET", "POST"])
@login_required
def branding():
    from .branding import get_branding

    if request.method == "POST":
        fields = [
            "site_name", "tagline", "logo", "primary_color", "accent_color",
            "background_color", "card_color", "text_color", "welcome_title",
            "welcome_message", "footer_text",
        ]
        for field in fields:
            value = request.form.get(field, "").strip()
            if field in ("primary_color", "accent_color", "background_color", "card_color", "text_color"):
                value = value or None
            db.set_setting(field, value)
        flash("Branding saved", "success")
        return redirect(url_for("admin.branding"))
    return render_template("admin_branding.html", brand=get_branding())


@admin_bp.route("/admin/branding/logo", methods=["POST"])
@login_required
def logo_upload():
    logo = request.files.get("logo")
    if not logo or not logo.filename:
        flash("No file selected", "error")
        return redirect(url_for("admin.branding"))
    uploads_dir = current_app.config["UPLOADS_DIR"]
    os.makedirs(uploads_dir, exist_ok=True)
    for old in os.listdir(uploads_dir):
        os.unlink(os.path.join(uploads_dir, old))
    safe = "logo" + os.path.splitext(logo.filename)[1].lower()
    logo.save(os.path.join(uploads_dir, safe))
    db.set_setting("logo", f"/brand/{safe}")
    flash("Logo uploaded", "success")
    return redirect(url_for("admin.branding"))


@admin_bp.route("/brand/<path:filename>")
def brand_file(filename):
    return send_from_directory(current_app.config["UPLOADS_DIR"], filename)
