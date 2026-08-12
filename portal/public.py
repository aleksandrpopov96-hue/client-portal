import mimetypes
from datetime import datetime

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    send_file, session, url_for,
)
from werkzeug.security import check_password_hash

from . import db
from .branding import public_context
from .storage import (
    StorageError, delete_path, list_dir, share_exists, stream_folder_zip,
    upload_file,
)

public_bp = Blueprint("public", __name__)


def _load_share(token: str):
    share = db.get_share_by_token(token)
    if share is None:
        abort(404)
    if not share["enabled"]:
        abort(404)
    if share["expires_at"]:
        try:
            if datetime.now() > datetime.fromisoformat(share["expires_at"]):
                abort(410)
        except ValueError:
            pass
    return share


def _is_unlocked(share) -> bool:
    if not share["password_hash"]:
        return True
    return session.get(f"unlocked:{share['token']}") is True


@public_bp.route("/s/<token>", methods=["GET", "POST"])
def share(token):
    share = _load_share(token)
    db.touch_share(share["id"])

    if request.method == "POST":
        password = request.form.get("password", "")
        if check_password_hash(share["password_hash"], password):
            session[f"unlocked:{share['token']}"] = True
            return redirect(url_for("public.share", token=token))
        flash("Incorrect password", "error")
        return render_template(
            "share_gate.html",
            token=token,
            share=share,
            **public_context(share),
        )

    if not _is_unlocked(share):
        return render_template(
            "share_gate.html",
            token=token,
            share=share,
            **public_context(share),
        )

    if not share_exists(share):
        return render_template(
            "share_empty.html",
            share=share,
            reason="This share's folder has not been created yet.",
            **public_context(share),
        )

    relative = request.args.get("path", "")
    try:
        entries, current_rel, target = list_dir(share, relative)
    except StorageError as exc:
        return render_template(
            "share_empty.html",
            share=share,
            reason=str(exc),
            **public_context(share),
        )

    crumbs = []
    acc = ""
    if current_rel:
        for part in current_rel.split("/"):
            acc = f"{acc}/{part}" if acc else part
            crumbs.append((part, acc))

    return render_template(
        "share.html",
        share=share,
        entries=entries,
        current_path=current_rel,
        crumbs=crumbs,
        **public_context(share),
    )


@public_bp.route("/s/<token>/download")
def download(token):
    share = _load_share(token)
    if not _is_unlocked(share):
        return redirect(url_for("public.share", token=token))
    if not share["allow_download"]:
        abort(403)

    relative = request.args.get("path", "")
    from .storage import _resolve

    try:
        target = _resolve(share, relative)
    except StorageError:
        abort(404)
    if not target.is_file():
        abort(404)
    db.touch_share(share["id"])
    return send_file(
        target,
        as_attachment=True,
        download_name=target.name,
        mimetype=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
    )


@public_bp.route("/s/<token>/zip")
def download_zip(token):
    share = _load_share(token)
    if not _is_unlocked(share):
        return redirect(url_for("public.share", token=token))
    if not share["allow_download"]:
        abort(403)

    relative = request.args.get("path", "")
    try:
        buf, name = stream_folder_zip(share, relative)
    except StorageError:
        abort(404)
    db.touch_share(share["id"])
    return send_file(
        buf,
        as_attachment=True,
        download_name=name,
        mimetype="application/zip",
    )


@public_bp.route("/s/<token>/upload", methods=["POST"])
def upload(token):
    share = _load_share(token)
    if not _is_unlocked(share):
        abort(403)
    if not share["allow_upload"]:
        abort(403)

    relative = request.form.get("path", "")
    file = request.files.get("file")
    if not file or not file.filename:
        abort(400)
    try:
        saved = upload_file(
            share,
            relative,
            file.filename,
            file.stream,
            request.content_length or 0,
        )
    except StorageError as exc:
        flash(str(exc), "error")
        return redirect(url_for("public.share", token=token, path=relative))
    db.touch_share(share["id"])
    flash(f"Uploaded {saved}", "success")
    return redirect(url_for("public.share", token=token, path=relative))


@public_bp.route("/s/<token>/delete", methods=["POST"])
def delete(token):
    share = _load_share(token)
    if not _is_unlocked(share):
        abort(403)
    if not share["allow_delete"]:
        abort(403)
    relative = request.form.get("path", "")
    parent = "/".join(relative.split("/")[:-1])
    try:
        delete_path(share, relative)
    except StorageError as exc:
        flash(str(exc), "error")
        return redirect(url_for("public.share", token=token, path=parent))
    flash("Deleted", "success")
    return redirect(url_for("public.share", token=token, path=parent))
