import os
import secrets


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def get_config() -> dict:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    storage_root = os.environ.get("PORTAL_STORAGE_ROOT", os.path.join(base, "files"))
    data_dir = os.environ.get("PORTAL_DATA_DIR", os.path.join(base, "data"))
    return {
        "STORAGE_ROOT": storage_root,
        "DATA_DIR": data_dir,
        "DB_PATH": os.path.join(data_dir, "portal.db"),
        "UPLOADS_DIR": os.path.join(data_dir, "brand"),
        "ADMIN_USERNAME": os.environ.get("PORTAL_ADMIN_USERNAME", "admin"),
        "ADMIN_PASSWORD": os.environ.get("PORTAL_ADMIN_PASSWORD", None),
        "SECRET_KEY": os.environ.get("PORTAL_SECRET_KEY", None),
        "MAX_CONTENT_LENGTH": _int("PORTAL_MAX_CONTENT_LENGTH", 8 * 1024 * 1024 * 1024),
        "RATELIMIT_STORAGE_URI": os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
        "RATELIMIT_ENABLED": _bool("PORTAL_RATELIMIT_ENABLED", True),
        "RATELIMIT_LOGIN_PER_MIN": _int("PORTAL_RATELIMIT_LOGIN_PER_MIN", 10),
        "RATELIMIT_API_PER_MIN": _int("PORTAL_RATELIMIT_API_PER_MIN", 120),
        "RATELIMIT_DOWNLOAD_PER_MIN": _int("PORTAL_RATELIMIT_DOWNLOAD_PER_MIN", 60),
        "RATELIMIT_UPLOAD_CHUNK_PER_MIN": _int("PORTAL_RATELIMIT_UPLOAD_CHUNK_PER_MIN", 60),
        "MAX_ACTIVE_TRANSFERS": _int("PORTAL_MAX_ACTIVE_TRANSFERS", 4),
        "MAX_ACTIVE_TRANSFERS_PER_IP": _int("PORTAL_MAX_ACTIVE_TRANSFERS_PER_IP", 2),
        "UPLOAD_CHUNK_MB": _int("PORTAL_UPLOAD_CHUNK_MB", 20),
        "PREVIEW_ENABLED": _bool("PORTAL_PREVIEW_ENABLED", True),
        "TRUST_PROXY": _bool("PORTAL_TRUST_PROXY", True),
        "SESSION_LIFETIME_HOURS": _int("PORTAL_SESSION_LIFETIME_HOURS", 12),
    }


def get_or_create_secret_key(data_dir: str) -> str:
    key_file = os.path.join(data_dir, ".secret_key")
    if os.path.exists(key_file):
        with open(key_file) as fh:
            value = fh.read().strip()
            if value:
                return value
    value = secrets.token_hex(32)
    os.makedirs(data_dir, exist_ok=True)
    with open(key_file, "w") as fh:
        fh.write(value)
    return value