import mimetypes
from pathlib import Path

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    send_file, session, url_for,
)
from werkzeug.security import check_password_hash

from . import db
from .auth import user_login_required
from .branding import public_context
from .storage import (
    StorageError, delete_path, list_dir, stream_folder_zip, upload_file,
)

browser_bp = Blueprint("browser", __name__)


def _root() -> Path:
    return Path(current_app.config["STORAGE_ROOT"]).resolve()


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.get_user(user_id)


@browser_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.get_user_by_username(username)
        if user and user["enabled"] and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            db.touch_user_login(user["id"])
            next_url = request.args.get("next") or url_for("browser.index")
            return redirect(next_url)
        flash("Invalid username or password", "error")
    return render_template("browser_login.html", **public_context())


@browser_bp.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("browser.login"))


@browser_bp.route("/browser")
@user_login_required
def index():
    user = _current_user()
    if not user:
        abort(404)

    relative = request.args.get("path", "")
    try:
        entries, current_rel, target = list_dir(_root(), relative)
    except StorageError as exc:
        return render_template(
            "browser_empty.html",
            user=user,
            reason=str(exc),
            **public_context(),
        )

    crumbs = []
    acc = ""
    if current_rel:
        for part in current_rel.split("/"):
            acc = f"{acc}/{part}" if acc else part
            crumbs.append((part, acc))

    return render_template(
        "browser.html",
        user=user,
        entries=entries,
        current_path=current_rel,
        crumbs=crumbs,
        **public_context(),
    )


@browser_bp.route("/browser/download")
@user_login_required
def download():
    user = _current_user()
    if not user:
        abort(404)
    if not user["allow_download"]:
        abort(403)

    relative = request.args.get("path", "")
    from .storage import _resolve

    try:
        target = _resolve(_root(), relative)
    except StorageError:
        abort(404)
    if not target.is_file():
        abort(404)
    return send_file(
        target,
        as_attachment=True,
        download_name=target.name,
        mimetype=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
    )


@browser_bp.route("/browser/zip")
@user_login_required
def download_zip():
    user = _current_user()
    if not user:
        abort(404)
    if not user["allow_download"]:
        abort(403)

    relative = request.args.get("path", "")
    try:
        buf, name = stream_folder_zip(_root(), relative)
    except StorageError:
        abort(404)
    return send_file(
        buf,
        as_attachment=True,
        download_name=name,
        mimetype="application/zip",
    )


@browser_bp.route("/browser/upload", methods=["POST"])
@user_login_required
def upload():
    user = _current_user()
    if not user:
        abort(404)
    if not user["allow_upload"]:
        abort(403)

    relative = request.form.get("path", "")
    file = request.files.get("file")
    if not file or not file.filename:
        abort(400)
    try:
        saved = upload_file(
            _root(),
            relative,
            file.filename,
            file.stream,
            request.content_length or 0,
            user["max_upload_size_mb"],
            user["allowed_extensions"],
        )
    except StorageError as exc:
        flash(str(exc), "error")
        return redirect(url_for("browser.index", path=relative))
    flash(f"Uploaded {saved}", "success")
    return redirect(url_for("browser.index", path=relative))


@browser_bp.route("/browser/delete", methods=["POST"])
@user_login_required
def delete():
    user = _current_user()
    if not user:
        abort(404)
    if not user["allow_delete"]:
        abort(403)

    relative = request.form.get("path", "")
    parent = "/".join(relative.split("/")[:-1])
    try:
        delete_path(_root(), relative)
    except StorageError as exc:
        flash(str(exc), "error")
        return redirect(url_for("browser.index", path=parent))
    flash("Deleted", "success")
    return redirect(url_for("browser.index", path=parent))
