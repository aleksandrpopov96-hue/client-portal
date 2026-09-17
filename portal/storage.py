from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from flask import current_app

_INVALID_SEGMENTS = {".", "..", ""}


class StorageError(Exception):
    pass


class ShareDisabled(Exception):
    pass


class ShareExpired(Exception):
    pass


class ShareNotFound(Exception):
    pass


def share_root(share) -> Path:
    storage_root = Path(current_app.config["STORAGE_ROOT"]).resolve()
    share_path = (storage_root / share["subfolder"].lstrip("/")).resolve()
    if not share_path.is_relative_to(storage_root):
        raise StorageError("Share folder is outside storage root")
    return share_path


def user_root(user) -> Path:
    storage_root = Path(current_app.config["STORAGE_ROOT"]).resolve()
    subfolder = (user["subfolder"] or "/").lstrip("/")
    user_path = (storage_root / subfolder).resolve()
    if not user_path.is_relative_to(storage_root):
        raise StorageError("User folder is outside storage root")
    return user_path


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
        if item.is_symlink():
            continue
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


def safe_dirname(filename: str) -> str:
    base = os.path.basename(filename.replace("\\", "/")).strip()
    base = re.sub(r"[^A-Za-z0-9._ ()+\-@]", "_", base)
    base = re.sub(r"\s+", " ", base).strip(" .")
    return base or "folder"


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


def upload_chunk(
    root: Path,
    relative: str,
    filename: str,
    stream,
    content_length: int,
    max_upload_size_mb: int,
    allowed_extensions: str | None,
    chunk_index: int,
    chunk_total: int,
    resume_basename: str,
) -> dict:
    target_dir = _resolve(root, relative)
    if not target_dir.is_dir():
        raise StorageError("Upload target is not a directory")

    if chunk_index == 0:
        name = safe_filename(filename)
        validate_extension(allowed_extensions, name)
        if content_length and not _within_limit(content_length, max_upload_size_mb):
            raise StorageError(f"Chunk is too large (max {max_upload_size_mb} MB)")
        partial = target_dir / f".{name}.upload"
        partial.unlink(missing_ok=True)
    else:
        name = resume_basename
        if not name:
            raise StorageError("Filename required on subsequent chunks")
        partial = target_dir / f".{name}.upload"
        if not partial.exists():
            raise StorageError("Upload session not found. Start from the first chunk.")

    remaining = (int(max_upload_size_mb or 0) * 1024 * 1024) or current_app.config["MAX_CONTENT_LENGTH"]
    if chunk_index > 0 and partial.stat().st_size >= remaining:
        raise StorageError("File is too large")

    with open(partial, "ab") as out:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            if partial.stat().st_size > (int(max_upload_size_mb or 0) * 1024 * 1024 or current_app.config["MAX_CONTENT_LENGTH"]):
                out.close()
                partial.unlink(missing_ok=True)
                raise StorageError("File is too large")

    if chunk_index + 1 >= chunk_total:
        dest = _unique_path(target_dir / name)
        os.replace(partial, dest)
        return {"done": True, "name": dest.name}

    return {"done": False, "name": name}


def _within_limit(size: int, max_upload_size_mb: int) -> bool:
    max_bytes = int(max_upload_size_mb or 0) * 1024 * 1024
    return not max_bytes or size <= max_bytes


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


# ---------------------------------------------------------------------------
# Preview support
# ---------------------------------------------------------------------------

PREVIEW_IMAGE = {"png", "jpg", "jpeg", "gif", "webp", "avif", "bmp", "svg"}
PREVIEW_VIDEO = {"mp4", "webm", "mov", "m4v", "ogv"}
PREVIEW_AUDIO = {"mp3", "wav", "ogg", "oga", "m4a", "flac", "aac", "opus"}
PREVIEW_TEXT = {"txt", "md", "markdown", "json", "csv", "log", "py", "js", "ts",
                "html", "css", "sh", "yaml", "yml", "toml", "ini", "xml", "conf",
                "sql", "java", "c", "cpp", "h", "go", "rs", "rb", "php", "svg"}
PREVIEW_PDF = {"pdf"}

# Extensions we refuse to render inline (XSS risk) even if technically previewable.
_NO_INLINE = {"html", "htm", "svg", "xml"}


def preview_kind(filename: str) -> str | None:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in PREVIEW_IMAGE:
        return "image"
    if ext in PREVIEW_VIDEO:
        return "video"
    if ext in PREVIEW_AUDIO:
        return "audio"
    if ext in PREVIEW_PDF:
        return "pdf"
    if ext in PREVIEW_TEXT:
        return "text"
    return None


def preview_mimetype(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in PREVIEW_IMAGE | {"svg"}:
        import mimetypes

        return mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if ext in PREVIEW_VIDEO:
        import mimetypes

        return mimetypes.guess_type(filename)[0] or "video/mp4"
    if ext in PREVIEW_AUDIO:
        import mimetypes

        return mimetypes.guess_type(filename)[0] or "audio/mpeg"
    if ext in PREVIEW_PDF:
        return "application/pdf"
    return "text/plain; charset=utf-8"


def mkdir(root: Path, relative: str, name: str) -> str:
    target_dir = _resolve(root, relative)
    if not target_dir.is_dir():
        raise StorageError("Target is not a directory")
    safe = safe_dirname(name)
    dest = _unique_path(target_dir / safe)
    dest.mkdir(parents=False, exist_ok=False)
    return dest.name


# ---------------------------------------------------------------------------
# Zip / streaming
# ---------------------------------------------------------------------------


def build_folder_zip(root: Path, relative: str) -> tuple[Any, str]:
    """Build a zip of a folder/file into a tempfile (not memory), so huge
    folders only touch disk, never RAM. Returns (stream, download_name)."""
    target = _resolve(root, relative)
    if not target.exists():
        raise StorageError("Path does not exist")

    base_name = target.name or "files"
    fd, tmp_path = tempfile.mkstemp(prefix="portal_zip_", suffix=".zip")
    os.close(fd)

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        if target.is_file():
            zf.write(target, arcname=target.name)
        else:
            for file_path in sorted(target.rglob("*")):
                if file_path.is_file() and not file_path.is_symlink():
                    arc = file_path.relative_to(target.parent).as_posix()
                    zf.write(file_path, arcname=arc)

    return open(tmp_path, "rb"), f"{base_name}.zip"


def cleanup_later(path: str):
    """Return a callable to delete the tempfile once the response finishes."""

    def _cleanup():
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass

    return _cleanup


# ---------------------------------------------------------------------------
# Sync helpers kept for API usage
# ---------------------------------------------------------------------------

stream_folder_zip = build_folder_zip


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