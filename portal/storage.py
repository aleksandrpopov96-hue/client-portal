from __future__ import annotations

import io
import os
import re
import shutil
import zipfile
from pathlib import Path

from flask import current_app

_INVALID_SEGMENTS = {".", "..", ""}


class StorageError(Exception):
    pass


class ShareDisabled(Exception):
    pass


class ShareExpired(Exception):
    pass


def share_root(share) -> Path:
    storage_root = Path(current_app.config["STORAGE_ROOT"]).resolve()
    share_path = (storage_root / share["subfolder"].lstrip("/")).resolve()
    if not share_path.is_relative_to(storage_root):
        raise StorageError("Share folder is outside storage root")
    return share_path


def _resolve(root: Path, relative: str) -> Path:
    root = root.resolve()
    if relative in ("", "/"):
        return root

    parts = [p for p in relative.split("/") if p not in _INVALID_SEGMENTS]
    target = (root / "/".join(parts)).resolve()
    if not target.is_relative_to(root):
        raise StorageError("Path escapes the allowed area")
    return target


def _rel(root: Path, path: Path) -> str:
    root = root.resolve()
    rel = path.resolve().relative_to(root)
    return "" if rel == Path(".") else rel.as_posix()


def list_dir(root: Path, relative: str):
    target = _resolve(root, relative)
    if not target.exists():
        raise StorageError("Path does not exist")
    if not target.is_dir():
        raise StorageError("Not a directory")

    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        stat = item.stat()
        entries.append(
            {
                "name": item.name,
                "is_dir": item.is_dir(),
                "size": stat.st_size if item.is_file() else None,
                "mtime": stat.st_mtime,
                "relative": _rel(root, item),
            }
        )
    return entries, relative, target


def validate_extension(allowed_extensions: str | None, filename: str) -> None:
    allowed = (allowed_extensions or "").strip()
    if not allowed:
        return
    ext = Path(filename).suffix.lower().lstrip(".")
    if not ext:
        raise StorageError("Files without an extension are not allowed here")
    allowed_list = [e.strip().lower().lstrip(".") for e in allowed.split(",") if e.strip()]
    if ext not in allowed_list:
        raise StorageError(
            f"Extension .{ext} is not allowed. Allowed: {', '.join(allowed_list)}"
        )


def safe_filename(filename: str) -> str:
    base = os.path.basename(filename.replace("\\", "/")).strip()
    base = re.sub(r"[^A-Za-z0-9._ ()+\-@]", "_", base)
    base = re.sub(r"\s+", " ", base).strip(" .")
    return base or "file"


def upload_file(
    root: Path,
    relative: str,
    filename: str,
    stream,
    content_length: int,
    max_upload_size_mb: int,
    allowed_extensions: str | None,
) -> str:
    target_dir = _resolve(root, relative)
    if not target_dir.is_dir():
        raise StorageError("Upload target is not a directory")

    name = safe_filename(filename)
    validate_extension(allowed_extensions, name)

    max_bytes = int(max_upload_size_mb or 0) * 1024 * 1024
    if content_length and max_bytes and content_length > max_bytes:
        raise StorageError(f"File is too large (max {max_upload_size_mb} MB)")

    dest = target_dir / name
    dest = _unique_path(dest)

    remaining = max_bytes or current_app.config["MAX_CONTENT_LENGTH"]
    with open(dest, "wb") as out:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            remaining -= len(chunk)
            if remaining < 0:
                out.close()
                dest.unlink(missing_ok=True)
                raise StorageError("File is too large")
            out.write(chunk)
    return dest.name


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def delete_path(root: Path, relative: str) -> None:
    target = _resolve(root, relative)
    if target == root.resolve():
        raise StorageError("Cannot delete the root folder")
    if not target.exists():
        raise StorageError("Path does not exist")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def stream_folder_zip(root: Path, relative: str):
    target = _resolve(root, relative)
    if not target.exists():
        raise StorageError("Path does not exist")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        base_name = target.name or "files"
        if target.is_file():
            zf.write(target, arcname=target.name)
        else:
            for file_path in target.rglob("*"):
                if file_path.is_file():
                    arc = file_path.relative_to(target.parent).as_posix()
                    zf.write(file_path, arcname=arc)
    buf.seek(0)
    return buf, f"{base_name}.zip"
