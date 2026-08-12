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


def _resolve(share, relative: str) -> Path:
    storage_root = Path(current_app.config["STORAGE_ROOT"]).resolve()
    share_root = (storage_root / share["subfolder"].lstrip("/")).resolve()
    if not share_root.is_relative_to(storage_root):
        raise StorageError("Share folder is outside storage root")

    if relative in ("", "/"):
        return share_root

    parts = [p for p in relative.split("/") if p not in _INVALID_SEGMENTS]
    target = (share_root / "/".join(parts)).resolve()
    if not target.is_relative_to(share_root):
        raise StorageError("Path escapes the share")
    return target


def share_exists(share) -> bool:
    root = Path(current_app.config["STORAGE_ROOT"]).resolve()
    share_root = (root / share["subfolder"].lstrip("/")).resolve()
    return share_root.exists()


def list_dir(share, relative: str):
    target = _resolve(share, relative)
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
                "relative": _rel(share, item),
            }
        )
    return entries, relative, target


def _rel(share, path: Path) -> str:
    root = Path(current_app.config["STORAGE_ROOT"]).resolve()
    share_root = (root / share["subfolder"].lstrip("/")).resolve()
    rel = path.resolve().relative_to(share_root)
    return "" if rel == Path(".") else rel.as_posix()


def validate_extension(share, filename: str) -> None:
    allowed = (share["allowed_extensions"] or "").strip()
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


def upload_file(share, relative: str, filename: str, stream, content_length: int) -> str:
    target_dir = _resolve(share, relative)
    if not target_dir.is_dir():
        raise StorageError("Upload target is not a directory")

    name = safe_filename(filename)
    validate_extension(share, name)

    max_bytes = int(share["max_upload_size_mb"] or 0) * 1024 * 1024
    if content_length and max_bytes and content_length > max_bytes:
        raise StorageError(
            f"File is too large (max {share['max_upload_size_mb']} MB)"
        )

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


def delete_path(share, relative: str) -> None:
    target = _resolve(share, relative)
    if target == _resolve(share, ""):
        raise StorageError("Cannot delete the share root")
    if not target.exists():
        raise StorageError("Path does not exist")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def stream_folder_zip(share, relative: str):
    target = _resolve(share, relative)
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
