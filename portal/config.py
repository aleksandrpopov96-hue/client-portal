import os
import secrets


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
        "MAX_CONTENT_LENGTH": int(os.environ.get("PORTAL_MAX_CONTENT_LENGTH", 8 * 1024 * 1024 * 1024)),
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
