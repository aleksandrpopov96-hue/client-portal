from __future__ import annotations

from datetime import datetime


def human_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return ""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def fmt_datetime(value: str | None) -> str:
    if not value:
        return "never"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def init_app(app) -> None:
    app.jinja_env.filters["humansize"] = human_size
    app.jinja_env.filters["fmtdate"] = fmt_datetime
