from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file, session
from werkzeug.security import check_password_hash

from .. import db
from ..storage import (
    StorageError, delete_path, list_dir, preview_kind, preview_mimetype,
    share_root, upload_chunk, upload_file, cleanup_later, thumbnail,
)
from ..ratelimit import transfer_guard
from .helpers import get_client_ip, audit, json_error

public_bp = Blueprint("api_public", __name__)


def _load_share(token: str):
    share = db.get_share_by_token(token)
    if share is None or not share["enabled"]:
        return None, ("Share not found", 404)
    if share["expires_at"]:
        try:
            if datetime.now(timezone.utc) > datetime.fromisoformat(share["expires_at"]):
                return None, ("Share has expired", 410)
        except ValueError:
            pass
    return share, None


def _unlocked(share) -> bool:
    if not share["password_hash"]:
        return True
    return session.get(f"unlocked:{share['token']}") is True


def _public_share_payload(share) -> dict:
    return {
        "token": share["token"],
        "name": share["name"],
        "mode": share["mode"],
        "subfolder": share["subfolder"],
        "allow_download": bool(share["allow_download"]),
        "allow_upload": bool(share["allow_upload"]),
        "allow_delete": bool(share["allow_delete"]),
        "max_upload_size_mb": share["max_upload_size_mb"],
        "allowed_extensions": share["allowed_extensions"],
        "branding_color": share["branding_color"],
        "requires_password": bool(share["password_hash"]),
        "expires_at": share["expires_at"],
        "last_used_at": share["last_used_at"],
    }


@public_bp.get("/s/<token>/meta")
def share_meta(token):
    share, err = _load_share(token)
    if share is None:
        status = err[1] if err else 404
        return json_error(err[0], status)
    unlocked = _unlocked(share)
    if not unlocked:
        payload = _public_share_payload(share)
        payload["locked"] = True
        return jsonify(payload)
    payload = _public_share_payload(share)
    payload["locked"] = False
    payload["root_exists"] = share_root(share).exists()
    return jsonify(payload)


@public_bp.post("/s/<token>/unlock")
def share_unlock(token):
    share, err = _load_share(token)
    if share is None:
        return json_error(err[0], err[1])
    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    if not share["password_hash"]:
        session[f"unlocked:{token}"] = True
        return jsonify({"ok": True})
    if check_password_hash(share["password_hash"], password):
        session[f"unlocked:{token}"] = True
        db.touch_share(share["id"])
        audit("share:unlock", "", actor=f"share:{token}")
        return jsonify({"ok": True})
    db.log_access(f"share:{token}", "share:unlock:fail", ip=get_client_ip())
    return json_error("Incorrect password", 401)


@public_bp.get("/s/<token>/ls")
def share_ls(token):
    share, err = _load_share(token)
    if share is None:
        return json_error(err[0], err[1])
    if not _unlocked(share):
        return json_error("Share is password protected", 401)
    root = share_root(share)
    db.touch_share(share["id"])
    relative = request.args.get("path", "")
    try:
        entries, current_rel, _t = list_dir(root, relative)
    except StorageError as exc:
        return json_error(str(exc), 404)
    return jsonify({"path": current_rel, "parent": _parent_of(current_rel), "entries": entries})


@public_bp.get("/s/<token>/download")
def share_download(token):
    share, err = _load_share(token)
    if share is None:
        return json_error(err[0], err[1])
    if not _unlocked(share):
        return json_error("Share is password protected", 401)
    if not share["allow_download"]:
        return json_error("Downloads are disabled for this share", 403)
    relative = request.args.get("path", "")
    from ..storage import _resolve

    try:
        target = _resolve(share_root(share), relative)
    except StorageError:
        return json_error("Path does not exist", 404)
    if not target.is_file():
        return json_error("Can only download files", 400)
    with transfer_guard().transfer(get_client_ip()):
        db.touch_share(share["id"])
        audit("download:file", relative, actor=f"share:{token}")
        return send_file(
            target,
            as_attachment=True,
            download_name=target.name,
            mimetype=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
            max_age=0,
        )


@public_bp.get("/s/<token>/preview")
def share_preview(token):
    share, err = _load_share(token)
    if share is None:
        return json_error(err[0], err[1])
    if not _unlocked(share):
        return json_error("Share is password protected", 401)
    if not share["allow_download"]:
        return json_error("Downloads are disabled for this share", 403)
    if not current_app.config.get("PREVIEW_ENABLED", True):
        return json_error("Preview is disabled", 403)
    relative = request.args.get("path", "")
    from ..storage import _resolve

    try:
        target = _resolve(share_root(share), relative)
    except StorageError:
        return json_error("Path does not exist", 404)
    if not target.is_file():
        return json_error("Can only preview files", 400)
    kind = preview_kind(target.name)
    if not kind or kind == "text" and target.name.lower().endswith((".html", ".htm", ".svg", ".xml")):
        return json_error("This file type cannot be previewed", 409)
    mime = preview_mimetype(target.name)
    db.touch_share(share["id"])
    audit("preview", relative, actor=f"share:{token}")
    resp = send_file(
        target,
        as_attachment=False,
        download_name=target.name,
        mimetype=mime,
        conditional=True,
        max_age=0,
    )
    resp.headers["Accept-Ranges"] = "bytes"
    return resp


@public_bp.get("/s/<token>/thumbnail")
def share_thumbnail(token):
    share, err = _load_share(token)
    if share is None:
        return json_error(err[0], err[1])
    if not _unlocked(share):
        return json_error("Share is password protected", 401)
    if not share["allow_download"]:
        return json_error("Downloads are disabled for this share", 403)
    if share["mode"] == "upload":
        return json_error("Browsing is disabled for this share", 403)
    relative = request.args.get("path", "")
    try:
        data, mime = thumbnail(share_root(share), relative)
    except StorageError as exc:
        return json_error(str(exc), 404)
    if isinstance(data, Path):
        return send_file(data, mimetype=mime, max_age=86400)
    return Response(data, mimetype=mime, headers={"Cache-Control": "public, max-age=86400"})


@public_bp.get("/s/<token>/zip")
def share_zip(token):
    share, err = _load_share(token)
    if share is None:
        return json_error(err[0], err[1])
    if not _unlocked(share):
        return json_error("Share is password protected", 401)
    if not share["allow_download"]:
        return json_error("Downloads are disabled for this share", 403)
    relative = request.args.get("path", "")
    from ..storage import build_folder_zip

    with transfer_guard().transfer(get_client_ip()):
        try:
            buf, name = build_folder_zip(share_root(share), relative)
        except StorageError as exc:
            return json_error(str(exc), 404)
        db.touch_share(share["id"])
        audit("download:zip", relative, actor=f"share:{token}")
        resp = send_file(
            buf,
            as_attachment=True,
            download_name=name,
            mimetype="application/zip",
            max_age=0,
        )
        resp.call_on_close(cleanup_later(buf.name))
        return resp


@public_bp.post("/s/<token>/upload")
def share_upload(token):
    share, err = _load_share(token)
    if share is None:
        return json_error(err[0], err[1])
    if not _unlocked(share):
        return json_error("Share is password protected", 401)
    if not share["allow_upload"]:
        return json_error("Uploads are disabled for this share", 403)

    relative = request.form.get("path", "")
    file = request.files.get("file")
    if not file or not file.filename:
        return json_error("No file provided", 400)

    chunk_index = _int_form("chunk_index")
    chunk_total = _int_form("chunk_total")
    resume = (request.form.get("resume") or "").lower() in ("1", "true", "yes")

    with transfer_guard().transfer(get_client_ip()):
        try:
            if chunk_total and chunk_total > 1:
                result = upload_chunk(
                    share_root(share), relative, file.filename, file.stream,
                    file.content_length or 0, share["max_upload_size_mb"],
                    share["allowed_extensions"], chunk_index, chunk_total,
                    request.form.get("basename") or "",
                )
                db.touch_share(share["id"])
                if result["done"]:
                    audit("upload:file", f'{relative}/{result["name"]}'.lstrip("/"), actor=f"share:{token}", bytes=file.content_length)
                return jsonify(result)
            saved = upload_file(
                share_root(share), relative, file.filename, file.stream,
                request.content_length or 0, share["max_upload_size_mb"],
                share["allowed_extensions"],
            )
        except StorageError as exc:
            return json_error(str(exc), 400)
        db.touch_share(share["id"])
        audit("upload:file", f'{relative}/{saved}'.lstrip("/"), actor=f"share:{token}", bytes=file.content_length)
        return jsonify({"done": True, "name": saved})


@public_bp.post("/s/<token>/delete")
def share_delete(token):
    share, err = _load_share(token)
    if share is None:
        return json_error(err[0], err[1])
    if not _unlocked(share):
        return json_error("Share is password protected", 401)
    if not share["allow_delete"]:
        return json_error("Deletion is disabled for this share", 403)
    relative = request.form.get("path", "")
    try:
        delete_path(share_root(share), relative)
    except StorageError as exc:
        return json_error(str(exc), 400)
    db.touch_share(share["id"])
    audit("delete", relative, actor=f"share:{token}")
    return jsonify({"ok": True})


def _int_form(key: str) -> int:
    try:
        return int(request.form.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _parent_of(rel: str) -> str:
    return "/".join([p for p in rel.split("/") if p][:-1])
