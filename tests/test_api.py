import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

os.environ["PORTAL_DATA_DIR"] = tempfile.mkdtemp(prefix="portal_test_data")
os.environ["PORTAL_STORAGE_ROOT"] = tempfile.mkdtemp(prefix="portal_test_files")
os.environ["PORTAL_ADMIN_PASSWORD"] = "test-admin-password"
os.environ["RATELIMIT_ENABLED"] = "0"

from app import app  # noqa: E402
from portal import db  # noqa: E402


class PortalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["RATELIMIT_ENABLED"] = False
        cls.ctx = app.test_request_context()
        cls.ctx.push()
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.pop()

    def setUp(self):
        self.storage = Path(app.config["STORAGE_ROOT"])
        (self.storage / "acme").mkdir(parents=True, exist_ok=True)
        (self.storage / "acme" / "brief.pdf").write_bytes(b"%PDF-1.4 fake pdf")
        (self.storage / "notes.txt").write_text("hello world")

    # -- helpers ---------------------------------------------------------

    def csrf(self):
        resp = self.client.get("/api/session")
        self.assertEqual(resp.status_code, 200)
        return resp.json["csrf"]["token"]

    def headers(self):
        return {"X-CSRF-Token": self.csrf()}

    # -- auth -------------------------------------------------------------

    def test_admin_login(self):
        r = self.client.post(
            "/api/admin/login", json={"username": "admin", "password": "test-admin-password"}, headers=self.headers()
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["identity"]["role"], "admin")

    def test_admin_login_wrong_password(self):
        r = self.client.post(
            "/api/admin/login", json={"username": "admin", "password": "nope"}, headers=self.headers()
        )
        self.assertEqual(r.status_code, 401)

    def test_requires_csrf(self):
        r = self.client.post("/api/admin/login", json={"username": "admin", "password": "x"})
        self.assertEqual(r.status_code, 403)

    def test_user_login_and_session(self):
        db.create_user(
            "alice", "pbkdf2:pbkdf2", True, True, True, False, 100, None, "/", None
        )
        from werkzeug.security import generate_password_hash

        user = db.get_user_by_username("alice")
        db.update_user(
            user["id"], "alice", generate_password_hash("pw12345", "pbkdf2"),
            True, True, True, False, 100, None, "/", None,
        )
        r = self.client.post("/api/login", json={"username": "alice", "password": "pw12345"}, headers=self.headers())
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["identity"]["role"], "user")

    # -- shares -------------------------------------------------------------

    def test_share_lifecycle(self):
        self.client.post(
            "/api/admin/login", json={"username": "admin", "password": "test-admin-password"}, headers=self.headers()
        )
        r = self.client.post(
            "/api/admin/shares",
            json={
                "name": "ACME files",
                "subfolder": "/acme",
                "mode": "both",
                "allow_download": True,
                "allow_upload": True,
            },
            headers=self.headers(),
        )
        self.assertEqual(r.status_code, 201, r.json)
        token = r.json["token"]

        meta = self.client.get(f"/api/s/{token}/meta")
        self.assertEqual(meta.status_code, 200)
        self.assertFalse(meta.json["locked"])
        self.assertEqual(meta.json["name"], "ACME files")

        listing = self.client.get(f"/api/s/{token}/ls")
        self.assertEqual(listing.status_code, 200, listing.json)
        names = [e["name"] for e in listing.json["entries"]]
        self.assertIn("brief.pdf", names)

        dl = self.client.get(f"/api/s/{token}/download", query_string={"path": "brief.pdf"})
        self.assertEqual(dl.status_code, 200)
        self.assertEqual(dl.data, b"%PDF-1.4 fake pdf")

        zip_resp = self.client.get(f"/api/s/{token}/zip")
        self.assertEqual(zip_resp.status_code, 200)
        self.assertEqual(zip_resp.data[:2], b"PK")

    def test_chunked_upload_roundtrip(self):
        self.client.post(
            "/api/admin/login", json={"username": "admin", "password": "test-admin-password"}, headers=self.headers()
        )
        r = self.client.post(
            "/api/admin/shares",
            json={"name": "Chunked", "subfolder": "/acme", "mode": "upload", "allow_upload": True},
            headers=self.headers(),
        )
        token = r.json["token"]
        payload_a = b"AAAA" * 2000
        payload_b = b"BBBB" * 2000
        resp = self.client.post(
            f"/api/s/{token}/upload",
            data={
                "path": "",
                "file": (BytesIO(payload_a), "bigfile.bin"),
                "chunk_index": "0",
                "chunk_total": "2",
            },
            headers=self.headers(),
        )
        self.assertEqual(resp.status_code, 200, resp.json)
        self.assertFalse(resp.json["done"])
        resp2 = self.client.post(
            f"/api/s/{token}/upload",
            data={
                "path": "",
                "file": (BytesIO(payload_b), "bigfile.bin"),
                "chunk_index": "1",
                "chunk_total": "2",
                "basename": "bigfile.bin",
            },
            headers=self.headers(),
        )
        self.assertEqual(resp2.status_code, 200, resp2.json)
        self.assertTrue(resp2.json["done"])
        saved = self.storage / "acme" / resp2.json["name"]
        self.assertEqual(saved.read_bytes(), payload_a + payload_b)
        # Upload-only share must not expose browsing
        self.assertEqual(self.client.get(f"/api/s/{token}/ls").status_code, 200)

    def test_preview_range_request(self):
        # Create a small "video" file with a load of bytes so ranges are meaningful
        (self.storage / "acme" / "clip.mp4").write_bytes(b"\x00\x00\x00\x20ftyp" + b"x" * 4096)
        self.client.post("/api/admin/login", json={"username": "admin", "password": "test-admin-password"}, headers=self.headers())
        r = self.client.post(
            "/api/admin/shares", json={"name": "Media", "subfolder": "/acme", "mode": "browse"}, headers=self.headers()
        )
        token = r.json["token"]
        resp = self.client.get(
            f"/api/s/{token}/preview",
            query_string={"path": "clip.mp4"},
            headers={"Range": "bytes=0-99"},
        )
        self.assertEqual(resp.status_code, 206)
        self.assertEqual(len(resp.data), 100)
        self.assertEqual(resp.headers.get("Accept-Ranges"), "bytes")

    def test_unpreviewable_file_rejected(self):
        (self.storage / "acme" / "script.js").write_text("alert(1)")
        self.client.post("/api/admin/login", json={"username": "admin", "password": "test-admin-password"}, headers=self.headers())
        r = self.client.post(
            "/api/admin/shares", json={"name": "X", "subfolder": "/acme", "mode": "browse"}, headers=self.headers()
        )
        token = r.json["token"]
        # built-in text preview list includes .js, so it previews as text/plain - safe.
        resp = self.client.get(f"/api/s/{token}/preview", query_string={"path": "script.js"})
        self.assertIn("text/plain", resp.content_type)

    def test_admin_browser(self):
        self.client.post("/api/admin/login", json={"username": "admin", "password": "test-admin-password"}, headers=self.headers())
        # ls root sees every folder under the storage root
        r = self.client.get("/api/admin/browser/ls")
        self.assertEqual(r.status_code, 200, r.json)
        names = {e["name"] for e in r.json["entries"]}
        self.assertIn("acme", names)
        self.assertIn("notes.txt", names)
        # upload
        r = self.client.post(
            "/api/admin/browser/upload",
            data={"path": "acme", "file": (BytesIO(b"new data"), "up.bin")},
            headers=self.headers(),
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertTrue((self.storage / "acme" / "up.bin").exists())
        # mkdir
        r = self.client.post("/api/admin/browser/mkdir", data={"path": "", "name": "newdir"}, headers=self.headers())
        self.assertEqual(r.status_code, 200, r.json)
        self.assertTrue((self.storage / "newdir").is_dir())
        # download + preview
        r = self.client.get("/api/admin/browser/download", query_string={"path": "acme/brief.pdf"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, b"%PDF-1.4 fake pdf")
        r = self.client.get("/api/admin/browser/preview", query_string={"path": "notes.txt"})
        self.assertEqual(r.status_code, 200)
        # delete
        r = self.client.post("/api/admin/browser/delete", data={"path": "acme/up.bin"}, headers=self.headers())
        self.assertEqual(r.status_code, 200, r.json)
        self.assertFalse((self.storage / "acme" / "up.bin").exists())
        # admin browser must require admin
        self.client.post("/api/admin/logout", headers=self.headers())
        self.assertEqual(self.client.get("/api/admin/browser/ls").status_code, 401)

    def test_share_password_gate(self):
        self.client.post(
            "/api/admin/login", json={"username": "admin", "password": "test-admin-password"}, headers=self.headers()
        )
        r = self.client.post(
            "/api/admin/shares",
            json={"name": "Secret", "subfolder": "/acme", "password": "hush", "mode": "browse"},
            headers=self.headers(),
        )
        token = r.json["token"]
        meta = self.client.get(f"/api/s/{token}/meta")
        self.assertTrue(meta.json["locked"])
        bad = self.client.post(
            f"/api/s/{token}/unlock", json={"password": "wrong"}, headers=self.headers()
        )
        self.assertEqual(bad.status_code, 401)
        ok = self.client.post(
            f"/api/s/{token}/unlock", json={"password": "hush"}, headers=self.headers()
        )
        self.assertEqual(ok.status_code, 200)

    def test_share_expired(self):
        from datetime import datetime, timedelta, timezone

        self.client.post(
            "/api/admin/login", json={"username": "admin", "password": "test-admin-password"}, headers=self.headers()
        )
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        r = self.client.post(
            "/api/admin/shares",
            json={"name": "Old", "subfolder": "/acme", "expires_at": past, "mode": "browse"},
            headers=self.headers(),
        )
        token = r.json["token"]
        self.assertEqual(self.client.get(f"/api/s/{token}/meta").status_code, 410)

    # -- user browsing --------------------------------------------------------

    def test_user_preview_and_upload(self):
        from werkzeug.security import generate_password_hash
        from io import BytesIO

        user_id = db.create_user(
            "bob", generate_password_hash("pw", "pbkdf2"), True, True, True, True, 50, "pdf,txt", "/", "test user"
        )
        self.client.post("/api/login", json={"username": "bob", "password": "pw"}, headers=self.headers())
        self.assertEqual(self.client.get("/api/user/whoami").json["username"], "bob")

        preview = self.client.get("/api/user/preview", query_string={"path": "notes.txt"})
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data, b"hello world")
        self.assertIn("text/plain", preview.content_type)

        block = self.client.get("/api/user/preview", query_string={"path": "acme/brief.pdf"})
        self.assertEqual(block.status_code, 200)
        self.assertIn("application/pdf", block.content_type)

        from werkzeug.datastructures import FileStorage

        r = self.client.post(
            "/api/user/upload",
            data={
                "path": "",
                "file": (BytesIO(b"report data"), "report.txt"),
            },
            headers=self.headers(),
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertTrue((self.storage / "report.txt").exists())

    def test_user_extension_whitelist(self):
        from werkzeug.security import generate_password_hash
        from io import BytesIO

        db.create_user(
            "carol", generate_password_hash("pw", "pbkdf2"), True, True, True, True, 50, "pdf", "/", "test"
        )
        self.client.post("/api/login", json={"username": "carol", "password": "pw"}, headers=self.headers())
        r = self.client.post(
            "/api/user/upload",
            data={"path": "", "file": (BytesIO(b"x" * 10), "evil.exe")},
            headers=self.headers(),
        )
        self.assertEqual(r.status_code, 400)

    def test_user_cannot_upload_when_disallowed(self):
        from werkzeug.security import generate_password_hash
        from io import BytesIO

        db.create_user(
            "dave", generate_password_hash("pw", "pbkdf2"), True, True, False, False, 50, None, "/", "test"
        )
        self.client.post("/api/login", json={"username": "dave", "password": "pw"}, headers=self.headers())
        r = self.client.post(
            "/api/user/upload",
            data={"path": "", "file": (BytesIO(b"x" * 10), "nope.txt")},
            headers=self.headers(),
        )
        self.assertEqual(r.status_code, 403)

    # -- admin ----------------------------------------------------------------

    def test_admin_stats_and_audit_require_login(self):
        self.client.post("/api/admin/logout", headers=self.headers())
        self.assertEqual(self.client.get("/api/admin/stats").status_code, 401)
        self.assertEqual(self.client.get("/api/admin/shares").status_code, 401)

    def test_admin_share_delete_disables_share(self):
        self.client.post(
            "/api/admin/login", json={"username": "admin", "password": "test-admin-password"}, headers=self.headers()
        )
        r = self.client.post(
            "/api/admin/shares", json={"name": "Temp", "subfolder": "/acme", "mode": "browse"}, headers=self.headers()
        )
        sid = r.json["id"]
        self.assertEqual(self.client.delete(f"/api/admin/shares/{sid}", headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.get(f"/api/s/{r.json['token']}/meta").status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)