from __future__ import annotations

import mimetypes
import secrets

from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file, session

from .. import db
from ..storage import (
    StorageError, delete_path, list_dir, mkdir, preview_kind, preview_mimetype,
    upload_chunk, upload_file, user_root, cleanup_later, thumbnail, _resolve,
)
from ..ratelimit import transfer_guard
from .helpers import get_client_ip, audit, json_error, require_user

browser_bp = Blueprint("api_browser", __name__)


@browser_bp.get("/user/whoami")
def whoami():
    user = require_user()
    if isinstance(user, tuple):
        return user
    return jsonify({
        "username": user["username"],
        "subfolder": user["subfolder"],
        "allow_download": bool(user["allow_download"]),
        "allow_upload": bool(user["allow_upload"]),
        "allow_delete": bool(user["allow_delete"]),
        "allow_share": bool(user["allow_share"]),
        "max_upload_size_mb": user["max_upload_size_mb"],
        "allowed_extensions": user["allowed_extensions"],
    })


@browser_bp.get("/user/ls")
def ls():
    user = require_user()
    if isinstance(user, tuple):
        return user
    root = user_root(user)
    relative = request.args.get("path", "")
    try:
        entries, current_rel, _t = list_dir(root, relative)
    except StorageError as exc:
        return json_error(str(exc), 404)
    return jsonify({"path": current_rel, "parent": _parent_of(current_rel), "entries": entries})


@browser_bp.post("/user/mkdir")
def mkdir_route():
    user = require_user()
    if isinstance(user, tuple):
        return user
    if not user["allow_upload"]:
        return json_error("Creating folders is not allowed for this account", 403)
    relative = request.form.get("path", "")
    name = request.form.get("name", "")
    if not name:
        return json_error("Folder name is required", 400)
    try:
        created = mkdir(user_root(user), relative, name)
    except StorageError as exc:
        return json_error(str(exc), 400)
    audit("mkdir", f'{relative}/{created}'.lstrip("/"), actor=f"user:{user['username']}")
    return jsonify({"done": True, "name": created})


@browser_bp.get("/user/download")
def download():
    user = require_user()
    if isinstance(user, tuple):
        return user
    if not user["allow_download"]:
        return json_error("Downloads are disabled for this account", 403)
    relative = request.args.get("path", "")
    from ..storage import _resolve

    try:
        target = _resolve(user_root(user), relative)
    except StorageError:
        return json_error("Path does not exist", 404)
    if not target.is_file():
        return json_error("Can only download files", 400)
    with transfer_guard().transfer(get_client_ip()):
        audit("download:file", relative, actor=f"user:{user['username']}")
        return send_file(
            target,
            as_attachment=True,
            download_name=target.name,
            mimetype=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
            max_age=0,
        )


@browser_bp.get("/user/preview")
def preview():
    user = require_user()
    if isinstance(user, tuple):
        return user
    if not user["allow_download"]:
        return json_error("Downloads are disabled for this account", 403)
    if not current_app.config.get("PREVIEW_ENABLED", True):
        return json_error("Preview is disabled", 403)
    relative = request.args.get("path", "")
    from ..storage import _resolve

    try:
        target = _resolve(user_root(user), relative)
    except StorageError:
        return json_error("Path does not exist", 404)
    if not target.is_file():
        return json_error("Can only preview files", 400)
    if not preview_kind(target.name):
        return json_error("This file type cannot be previewed", 409)
    mime = preview_mimetype(target.name)
    audit("preview", relative, actor=f"user:{user['username']}")
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


@browser_bp.get("/user/thumbnail")
def thumbnail_route():
    user = require_user()
    if isinstance(user, tuple):
        return user
    if not user["allow_download"]:
        return json_error("Downloads are disabled for this account", 403)
    relative = request.args.get("path", "")
    try:
        data, mime = thumbnail(user_root(user), relative)
    except StorageError as exc:
        return json_error(str(exc), 404)
    if isinstance(data, Path):
        return send_file(data, mimetype=mime, max_age=86400)
    return Response(data, mimetype=mime, headers={"Cache-Control": "public, max-age=86400"})


@browser_bp.get("/user/zip")
def zip_route():
    user = require_user()
    if isinstance(user, tuple):
        return user
    if not user["allow_download"]:
        return json_error("Downloads are disabled for this account", 403)
    relative = request.args.get("path", "")
    from ..storage import build_folder_zip

    with transfer_guard().transfer(get_client_ip()):
        try:
            buf, name = build_folder_zip(user_root(user), relative)
        except StorageError as exc:
            return json_error(str(exc), 404)
        audit("download:zip", relative, actor=f"user:{user['username']}")
        resp = send_file(
            buf,
            as_attachment=True,
            download_name=name,
            mimetype="application/zip",
            max_age=0,
        )
        resp.call_on_close(cleanup_later(buf.name))
        return resp


@browser_bp.post("/user/upload")
def upload():
    user = require_user()
    if isinstance(user, tuple):
        return user
    if not user["allow_upload"]:
        return json_error("Uploads are disabled for this account", 403)
    relative = request.form.get("path", "")
    file = request.files.get("file")
    if not file or not file.filename:
        return json_error("No file provided", 400)

    chunk_index = _int_form("chunk_index")
    chunk_total = _int_form("chunk_total")

    with transfer_guard().transfer(get_client_ip()):
        try:
            if chunk_total and chunk_total > 1:
                result = upload_chunk(
                    user_root(user), relative, file.filename, file.stream,
                    file.content_length or 0, user["max_upload_size_mb"],
                    user["allowed_extensions"], chunk_index, chunk_total,
                    request.form.get("basename") or "",
                )
                if result["done"]:
                    audit("upload:file", f'{relative}/{result["name"]}'.lstrip("/"), actor=f"user:{user['username']}", bytes=file.content_length)
                return jsonify(result)
            saved = upload_file(
                user_root(user), relative, file.filename, file.stream,
                request.content_length or 0, user["max_upload_size_mb"],
                user["allowed_extensions"],
            )
        except StorageError as exc:
            return json_error(str(exc), 400)
        audit("upload:file", f'{relative}/{saved}'.lstrip("/"), actor=f"user:{user['username']}", bytes=file.content_length)
        return jsonify({"done": True, "name": saved})


@browser_bp.post("/user/delete")
def delete_route():
    user = require_user()
    if isinstance(user, tuple):
        return user
    if not user["allow_delete"]:
        return json_error("Deletion is disabled for this account", 403)
    relative = request.form.get("path", "")
    try:
        delete_path(user_root(user), relative)
    except StorageError as exc:
        return json_error(str(exc), 400)
    audit("delete", relative, actor=f"user:{user['username']}")
    return jsonify({"ok": True})


@browser_bp.post("/user/share")
def share_route():
    user = require_user()
    if isinstance(user, tuple):
        return user
    if not user["allow_share"]:
        return json_error("Creating public shares is not allowed for this account", 403)

    data = request.get_json(silent=True) or {}
    relative = data.get("path") or ""
    try:
        target = _resolve(user_root(user), relative)
    except StorageError:
        return json_error("Path does not exist", 404)
    if not target.exists():
        return json_error("Path does not exist", 404)

    share_id = db.create_share(
        token=secrets.token_urlsafe(9),
        name=str(data.get("name") or target.name or f"{user['username']} share").strip(),
        subfolder=_subfolder_for(target),
        enabled=True,
        password_hash=None,
        expires_at=None,
        mode="browse",
        allow_download=True,
        allow_upload=False,
        allow_delete=False,
        allowed_extensions=None,
        max_upload_size_mb=100,
        branding_color=None,
        note=f"Created by user {user['username']}",
    )
    share = db.get_share(share_id)
    audit("share:create", share["subfolder"], actor=f"user:{user['username']}")
    base = request.url_root.rstrip("/")
    return jsonify({"token": share["token"], "url": f"{base}/s/{share['token']}", "share": {"id": share["id"], "name": share["name"], "subfolder": share["subfolder"]}}), 201


def _int_form(key: str) -> int:
    try:
        return int(request.form.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _parent_of(rel: str) -> str:
    return "/".join([p for p in rel.split("/") if p][:-1])


def _subfolder_for(target: Path) -> str:
    storage_root = Path(current_app.config["STORAGE_ROOT"]).resolve()
    rel = target.resolve().relative_to(storage_root)
    if rel == Path("."):
        return "/"
    return "/" + rel.as_posix()
