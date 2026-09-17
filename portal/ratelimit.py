from __future__ import annotations

import threading
from contextlib import contextmanager

from flask import current_app
from flask_limiter import Limiter

_limiter: Limiter | None = None


class TransferGuard:
    """Caps how many simultaneous file transfers run, globally and per IP.

    This is the first line of defence against Cloudflare being hammered:
    browsers queue behind the semaphore instead of opening a flood of
    concurrent upload/download sockets.
    """

    def __init__(self) -> None:
        self._global = threading.BoundedSemaphore(1)
        self._per_ip: dict[str, threading.BoundedSemaphore] = {}
        self._lock = threading.Lock()
        self._active: dict[str, int] = {}

    def _configure(self):
        max_global = int(current_app.config.get("MAX_ACTIVE_TRANSFERS", 4))
        current = self._global._value + self._global._initial_value  # type: ignore[attr-defined]
        if max_global != self._global._initial_value:  # type: ignore[attr-defined]
            self._global = threading.BoundedSemaphore(max_global)

    def _ip_sem(self, ip: str) -> threading.BoundedSemaphore:
        max_per_ip = int(current_app.config.get("MAX_ACTIVE_TRANSFERS_PER_IP", 2))
        with self._lock:
            sem = self._per_ip.get(ip)
            if sem is None:
                sem = threading.BoundedSemaphore(max_per_ip)
                self._per_ip[ip] = sem
            return sem

    @contextmanager
    def transfer(self, ip: str):
        self._configure()
        acq = self._global.acquire(blocking=True, timeout=300)
        if not acq:
            raise TransferBusy("Server transfer queue is full. Please retry shortly.")
        ip_sem = self._ip_sem(ip)
        acq_ip = ip_sem.acquire(blocking=True, timeout=300)
        if not acq_ip:
            self._global.release()
            raise TransferBusy("Too many transfers from your connection. Please wait.")
        with self._lock:
            self._active[ip] = self._active.get(ip, 0) + 1
        try:
            yield
        finally:
            with self._lock:
                self._active[ip] -= 1
                if self._active[ip] <= 0:
                    self._active.pop(ip, None)
            ip_sem.release()
            self._global.release()

    def active_count(self) -> int:
        with self._lock:
            return sum(self._active.values())


class TransferBusy(Exception):
    pass


_transfer_guard = TransferGuard()


def transfer_guard() -> TransferGuard:
    return _transfer_guard


def admin_transfer_stats() -> dict:
    guard = _transfer_guard
    with guard._lock:  # noqa: SLF001
        per_ip = {ip: n for ip, n in guard._active.items()}
    return {
        "active": sum(per_ip.values()),
        "per_ip": per_ip,
        "max_global": current_app.config.get("MAX_ACTIVE_TRANSFERS", 4),
        "max_per_ip": current_app.config.get("MAX_ACTIVE_TRANSFERS_PER_IP", 2),
    }


def get_limiter() -> Limiter:
    return _limiter


def init_limiter(app) -> Limiter:
    global _limiter

    def endpoint_key():
        return request.endpoint or str(request.path)

    _limiter = Limiter(
        app=app,
        key_func=endpoint_key,
        storage_uri=app.config["RATELIMIT_STORAGE_URI"],
        enabled=app.config["RATELIMIT_ENABLED"],
        default_limits=[],
        headers_enabled=False,
    )
    return _limiter


def client_key():
    """Per-IP key that trusts Cloudflare's CF-Connecting-IP header, then
    X-Forwarded-For (handled by ProxyFix), then remote_addr."""
    from flask import request

    cf = request.headers.get("CF-Connecting-IP", "")
    if cf:
        return cf
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


def register_limiter_rules(app) -> None:
    limiter = get_limiter()

    def _rate(name: str) -> str:
        return f"{int(app.config[name])} per minute"

    rules = {
        "api.login": _rate("RATELIMIT_LOGIN_PER_MIN"),
        "api.admin_login": _rate("RATELIMIT_LOGIN_PER_MIN"),
        "api_public.share_unlock": _rate("RATELIMIT_LOGIN_PER_MIN"),
        "api_public.share_download": _rate("RATELIMIT_DOWNLOAD_PER_MIN"),
        "api_public.share_zip": _rate("RATELIMIT_DOWNLOAD_PER_MIN"),
        "api_browser.download": _rate("RATELIMIT_DOWNLOAD_PER_MIN"),
        "api_browser.zip_route": _rate("RATELIMIT_DOWNLOAD_PER_MIN"),
        "api_public.share_upload": _rate("RATELIMIT_UPLOAD_CHUNK_PER_MIN"),
        "api_browser.upload": _rate("RATELIMIT_UPLOAD_CHUNK_PER_MIN"),
        "api_browser_admin.download": _rate("RATELIMIT_DOWNLOAD_PER_MIN"),
        "api_browser_admin.zip_route": _rate("RATELIMIT_DOWNLOAD_PER_MIN"),
        "api_browser_admin.upload": _rate("RATELIMIT_UPLOAD_CHUNK_PER_MIN"),
    }

    for endpoint, limit in rules.items():
        fn = app.view_functions.get(endpoint)
        if fn is None:
            continue
        app.view_functions[endpoint] = limiter.limit(limit, key_func=client_key)(fn)

    # Broad default for every remaining /api route.
    for endpoint in list(app.view_functions):
        if endpoint.startswith(("api.", "api_public.", "api_browser.", "api_admin.")):
            if endpoint in rules:
                continue
            fn = app.view_functions[endpoint]
            app.view_functions[endpoint] = limiter.limit(
                lambda: f"{app.config['RATELIMIT_API_PER_MIN']} per minute",
                key_func=client_key,
            )(fn)


def login_limits() -> str:
    return f"{current_app.config['RATELIMIT_LOGIN_PER_MIN']} per minute"


def api_limits() -> str:
    return f"{current_app.config['RATELIMIT_API_PER_MIN']} per minute"


def download_limits() -> str:
    return f"{current_app.config['RATELIMIT_DOWNLOAD_PER_MIN']} per minute"


def upload_limits() -> str:
    return f"{current_app.config['RATELIMIT_UPLOAD_CHUNK_PER_MIN']} per minute"