from __future__ import annotations

import mimetypes
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file

from ..storage import (
    StorageError, build_folder_zip, cleanup_later, delete_path, list_dir, mkdir,
    preview_kind, preview_mimetype, upload_chunk, upload_file, _resolve,
    thumbnail,
)
from ..ratelimit import transfer_guard
from .helpers import audit, get_client_ip, json_error, require_admin

browser_admin_bp = Blueprint("api_browser_admin", __name__)


def _root() -> Path:
    return Path(current_app.config["STORAGE_ROOT"]).resolve()


def _max_upload_mb() -> int:
    fallback = current_app.config.get("MAX_CONTENT_LENGTH") or (8 * 1024 ** 3)
    try:
        return max(1, int(fallback) // (1024 * 1024))
    except (TypeError, ValueError):
        return 8192


@browser_admin_bp.get("/admin/browser/ls")
def ls():
    if req := require_admin():
        return req
    relative = request.args.get("path", "")
    try:
        entries, current_rel, _t = list_dir(_root(), relative)
    except StorageError as exc:
        return json_error(str(exc), 404)
    return jsonify({"path": current_rel, "entries": entries})


@browser_admin_bp.get("/admin/browser/download")
def download():
    if req := require_admin():
        return req
    relative = request.args.get("path", "")
    try:
        target = _resolve(_root(), relative)
    except StorageError:
        return json_error("Path does not exist", 404)
    if not target.is_file():
        return json_error("Can only download files", 400)
    with transfer_guard().transfer(get_client_ip()):
        audit("admin:browser:download", relative, actor="admin")
        return send_file(
            target,
            as_attachment=True,
            download_name=target.name,
            mimetype=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
            max_age=0,
        )


@browser_admin_bp.get("/admin/browser/preview")
def preview():
    if req := require_admin():
        return req
    if not current_app.config.get("PREVIEW_ENABLED", True):
        return json_error("Preview is disabled", 403)
    relative = request.args.get("path", "")
    try:
        target = _resolve(_root(), relative)
    except StorageError:
        return json_error("Path does not exist", 404)
    if not target.is_file():
        return json_error("Can only preview files", 400)
    if not preview_kind(target.name):
        return json_error("This file type cannot be previewed", 409)
    mime = preview_mimetype(target.name)
    audit("admin:browser:preview", relative, actor="admin")
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


@browser_admin_bp.get("/admin/browser/thumbnail")
def thumbnail_route():
    if req := require_admin():
        return req
    relative = request.args.get("path", "")
    try:
        data, mime = thumbnail(_root(), relative)
    except StorageError as exc:
        return json_error(str(exc), 404)
    if isinstance(data, Path):
        return send_file(data, mimetype=mime, max_age=86400)
    return Response(data, mimetype=mime, headers={"Cache-Control": "public, max-age=86400"})


@browser_admin_bp.get("/admin/browser/zip")
def zip_route():
    if req := require_admin():
        return req
    relative = request.args.get("path", "")
    with transfer_guard().transfer(get_client_ip()):
        try:
            buf, name = build_folder_zip(_root(), relative)
        except StorageError as exc:
            return json_error(str(exc), 404)
        audit("admin:browser:zip", relative, actor="admin")
        resp = send_file(
            buf,
            as_attachment=True,
            download_name=name,
            mimetype="application/zip",
            max_age=0,
        )
        resp.call_on_close(cleanup_later(buf.name))
        return resp


@browser_admin_bp.post("/admin/browser/mkdir")
def mkdir_route():
    if req := require_admin():
        return req
    relative = request.form.get("path", "")
    name = request.form.get("name", "")
    if not name:
        return json_error("Folder name is required", 400)
    try:
        created = mkdir(_root(), relative, name)
    except StorageError as exc:
        return json_error(str(exc), 400)
    audit("admin:browser:mkdir", f"{relative}/{created}".lstrip("/"), actor="admin")
    return jsonify({"done": True, "name": created})


@browser_admin_bp.post("/admin/browser/upload")
def upload():
    if req := require_admin():
        return req
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
                    _root(), relative, file.filename, file.stream,
                    file.content_length or 0, _max_upload_mb(),
                    None, chunk_index, chunk_total,
                    request.form.get("basename") or "",
                )
                if result["done"]:
                    audit("admin:browser:upload", f'{relative}/{result["name"]}'.lstrip("/"), actor="admin", bytes=file.content_length)
                return jsonify(result)
            saved = upload_file(
                _root(), relative, file.filename, file.stream,
                request.content_length or 0, _max_upload_mb(), None,
            )
        except StorageError as exc:
            return json_error(str(exc), 400)
        audit("admin:browser:upload", f'{relative}/{saved}'.lstrip("/"), actor="admin", bytes=file.content_length)
        return jsonify({"done": True, "name": saved})


@browser_admin_bp.post("/admin/browser/delete")
def delete_route():
    if req := require_admin():
        return req
    relative = request.form.get("path", "")
    try:
        delete_path(_root(), relative)
    except StorageError as exc:
        return json_error(str(exc), 400)
    audit("admin:browser:delete", relative, actor="admin")
    return jsonify({"ok": True})


def _int_form(key: str) -> int:
    try:
        return int(request.form.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0
