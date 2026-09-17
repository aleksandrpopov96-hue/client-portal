# Client Portal v2

A self-hosted file portal for TrueNAS Scale, served behind a **Cloudflare tunnel**.
Upload and download big files through a sleek Material Design web app without
overwhelming Cloudflare's proxy.

## Features

- **Web file browser** — browse, preview, download, upload, zip folders, create folders, delete.
- **File previews** — images, PDF, text, video & audio (range-request scrubbing, no full download).
- **Client share links** — token-based, expiring, password-optional, per-share permissions.
  Each share can be `browse`, `upload` (dropzone only), or `both`.
- **Admin + user access** — separate admin panel, per-user accounts scoped to a folder
  subtree with download/upload/delete permissions and extension whitelists.
- **Cloudflare-friendly transfers**
  - Uploads are **chunked** (default 20 MB slices) so nothing ever exceeds Cloudflare's
    100 MB proxy limit.
  - **ZIP downloads stream from a temp file** (disk, not RAM) in a chunked response.
  - **Global + per-connection transfer quotas** (configurable) queue browsers instead of
    opening hundreds of sockets at once.
  - **Per-connection rate limits** on login, downloads, and upload chunks.
  - **Brute-force protection** on the tunnel-exposed login pages.
- **Security** — CSRF double-submit protection, strict CSP, HttpOnly+Secure session
  cookies, path-traversal guards, audit log of logins/transfers/deletions.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python / Flask / SQLite / gunicorn |
| Rate limiting | flask-limiter (in-memory, single worker) |
| Frontend | Vue 3 + Vuetify 3 (Material Design) built with Vite |
| Packaging | Multi-stage Docker (Node build → Python runtime) |

## Deployment on TrueNAS Scale

> **Full step-by-step guide (datasets, SMB share, permissions, tunnel):
> [`docs/TRUENAS.md`](docs/TRUENAS.md)** — read it if this is your first install.

Short version:

1. **Get the project onto the NAS** (or copy this folder).

2. **Create the two datasets** in the TrueNAS UI (e.g. `tank/clients` for the
   served files — share it over SMB — and `tank/portal-data` for the DB).

3. **Create `.env`:**
   ```bash
   cp .env.example .env
   ```
   Edit it — the important values are:
   - `PORTAL_FILES_PATH` — the SMB dataset the portal serves (e.g. `/mnt/tank/clients`)
   - `PORTAL_DATA_PATH` — a small persistent folder for the DB (e.g. `/mnt/tank/portal-data`)
   - `PUID` / `PGID` — the numeric owner of those datasets
     (find it with `ls -dn /mnt/tank/clients`). The container runs as this user
     so uploaded files stay readable/editable through your SMB share.
   - `PORTAL_ADMIN_PASSWORD` — your admin password

4. **Run the deploy script** (needs the Docker CLI enabled in TrueNAS):
   ```bash
   ./deploy.sh
   ```
   It builds the Vue app + Flask API, starts the stack on port 8080, and
   verifies the container can write into your dataset.

5. Open `http://<nas-ip>:8080/admin` — first run creates the admin + database.

## Exposing through a Cloudflare tunnel

1. In Cloudflare Zero Trust → **Networks → Tunnels**, create a tunnel and copy its token.
2. Add the token to your `.env`:
   ```
   CLOUDFLARED_TOKEN=eyJhIjoi...
   ```
3. Uncomment the `cloudflared` service in `docker-compose.yml`.
4. In the tunnel's **Public Hostname** tab, create a hostname (e.g.
   `files.example.com`) and point its service at **`http://localhost:8080`**.
5. `./deploy.sh` again. The tunnel container shares the portal's network, so
   Cloudflare routes straight to the Flask app.

> The app reads `CF-Connecting-IP` for per-visitor rate limiting and trusts the
> forwarded proto so session cookies are flagged `Secure`, even though origin is HTTP.

## Admin panel

- **Shares** — create/edit/delete client links. Configure:
  - Link type: browse-only, upload-dropzone-only, or both.
  - Folder path relative to the storage root.
  - Password, expiry, brand color, note.
  - Download/upload/delete toggles, extension whitelist, max upload size.
- **Users** — accounts that sign in via `/login` and browse their own folder scope.
- **Branding** — site name, colors, logo, welcome text (used on share pages).
- **Activity log** — logins, downloads, uploads, previews, deletions, by actor/IP.
- **Settings** — live-tunable transfer quotas and request rate limits (no restart).

## Share link types

| `mode` | What the client sees |
|---|---|
| `browse` | A file browser with download (read-only unless upload/delete also enabled) |
| `upload` | A single dropzone — clients send files, they can't see the folder |
| `both` | Browse + download + upload |

Upload-only links are perfect for intake: share `https://files.example.com/s/<token>`
and clients drag files in without seeing anything else in the share root.

## API (JSON)

- `GET/POST /api/session`, `POST /api/login`, `POST /api/logout`
- `POST /api/admin/login`, `POST /api/admin/logout`
- `GET /api/s/<token>/meta | ls | download | preview | zip`, `POST .../unlock | upload | delete`
- `GET /api/user/whoami | ls | download | preview | zip`, `POST .../upload | delete | mkdir`
- `GET/POST ... /api/admin/{stats,audit,shares,users,branding,settings}`

All mutating endpoints require the `X-CSRF-Token` header (the SPA handles this
automatically via the `portal_csrf` cookie).

## Development

```bash
# Backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Frontend (watch mode, proxies /api to the Flask dev server on :8080)
cd frontend && npm install && npm run dev

# Tests
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## Cloudflare limits to keep in mind

| Limit | How the app handles it |
|---|---|
| 100 MB max upload (free proxy) | Chunked uploads (default 20 MB), configurable in Settings |
| Large downloads | Streamed with `Transfer-Encoding: chunked`; no full buffering |
| Bursts of requests | Per-IP rate limits + transfer quotas queue traffic |
| Static assets | Self-hosted — the browser never hits a third-party CDN |

## Notes on scaling

- The Docker image intentionally runs **one gunicorn worker / 8 threads** so the
  in-memory rate limiter and SQLite remain consistent. That comfortably saturates a
  home-NAS tunnel uplink. If you need more capacity, switch the rate limiter to a
  shared storage URI (e.g. `memory://` → Redis) and raise the worker count in the
  `Dockerfile`.