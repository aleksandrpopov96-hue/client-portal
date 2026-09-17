# Installing on TrueNAS SCALE

This guide installs the portal as a Docker container that reads and writes the
dataset shared over SMB. The portal runs as a non-root user whose UID/GID
(`PUID`/`PGID`) matches the numeric owner of the dataset, so every file the
portal uploads is owned by the same user that owns your SMB share.

Tested against TrueNAS SCALE 24.10+ (Docker command line support).

---

## 0. Requirements

- TrueNAS SCALE 24.10 or newer.
- Docker enabled. If you do not see a **Docker** item in **Applications**,
  enable it under **System Settings → Advanced → Allow Docker command line interface**
  or run:
  ```
  midclt call system.advanced.update '{"allow_docker_cli": true}'
  ```
  The container does **not** have to be managed by the TrueNAS Apps UI - the
  `docker compose` CLI is enough.
- A pool with space for:
  - **the served files** (your SMB dataset), and
  - a small **app-data** folder for the portal database/logo/secret key.

---

## 1. Create the datasets

In **Storage → Create Datasets**, create (adjust names/pool to taste):

| Dataset path                 | Purpose                          |
|------------------------------|----------------------------------|
| `tank/clients`               | The files the portal serves. This is the dataset you share over SMB. |
| `tank/portal-data`           | Small folder: SQLite DB, logo, secret key. |

> If you already have an SMB dataset, skip creating `tank/clients` and use the
> path of the existing dataset below.

## 2. Note the dataset owner (uid:gid)

The container will run with this identity. On a TrueNAS shell:

```
ls -dn /mnt/tank/clients /mnt/tank/portal-data
```

The output lists `uid gid` for each path (e.g. `3000 3000`). If the datasets are
owned by root, either change the owner in **Storage → Datasets → Edit
Permissions** or set `PUID=0` ... do **not** use `0`; instead create a dataset
owned by a regular user (TrueNAS defaults many app datasets to `apps`, uid/gid
3000). Write the numbers down - they go into `.env` as `PUID`/`PGID`.

## 3. Create / verify the SMB share

In **Shares → Windows Shares (SMB) → Add**, create a share pointing at
`tank/clients`. Under the share's **Advanced Options → Who can Access**, grant
the user(s) you intend to use read+write access.

The container writes files as `PUID:PGID`. For those files to be visible and
editable from a Windows/other machine through the share, that uid must have
permissions in the dataset ACL. Simplest setup:

- Dataset **Edit Permissions** → Set the Apply Owner / ACL to the user matching
  `PUID` (or the `apps` group) with **Full Control**, and check
  "Apply User", "Apply Group", "Apply permissions recursively" (only needed on
  a fresh dataset).

For a *Unix permissions* dataset, just make sure the owner is `PUID:PGID` with
`rwx` (755/775).

> Tip: TrueNAS "SMB share" permissions are separate from the portal's own
> per-user/share rules. The portal adds an extra access layer on top (login,
> share links, rate limits) - it does not replace the SMB ACL.

---

## 4. Get the code onto the NAS

On the TrueNAS shell, where you keep apps (or anywhere you want):

```
cd /mnt/portal-apps   # any folder that persists
git clone https://github.com/aleksandrpopov96-hue/client-portal.git
cd client-portal
```

No `git` on the box? Upload the repo as a zip and unpack it, or copy it with
`scp -r`.

## 5. Configure

```
cp .env.example .env
```

Edit `.env`:

```
PORTAL_FILES_PATH=/mnt/tank/clients     # the SMB dataset the portal serves
PORTAL_DATA_PATH=/mnt/tank/portal-data  # small folder for DB/logo/secret
PUID=3000                               # uid from step 2
PGID=3000                               # gid from step 2
PORTAL_ADMIN_PASSWORD=change-me-to-something-strong
```

`PORTAL_ADMIN_PASSWORD` is used on first boot to create the admin account and
re-applied on every start (changing it rotates the admin password). The login
username is `admin`.

## 6. Build and start

```
./deploy.sh
```

`deploy.sh` checks Docker, creates the mount-point folders, sets ownership to
`PUID:PGID`, builds the image, starts the stack and verifies the container can
**write into your dataset** before calling it done.

First build downloads the base images and compiles the frontend; expect a few
minutes. Subsequent runs are fast.

## 7. Log in and create shares

- Open `http://<nas-ip>:8080/admin` and sign in as `admin`.
- **Users**: create a portal user (optional - for the credential-based browser).
- **Shares**: pick a subfolder of the dataset, choose a mode:
  - *browse* - clients can browse + download,
  - *upload* - link is upload-only (no folder visible),
  - *both* - browse + download + upload.
- Hand the generated `/s/<token>` link to the client. Set a password and copy
  a token as needed. Size caps, allowed extensions and max limits are set per
  share; global rate/upload limits live in **Settings**.

Local-only access needs the `ports:` line in `docker-compose.yml` uncommented
(it is commented by default because the intended route is the tunnel).

---

## 8. Expose via a Cloudflare tunnel

Instead of opening a port, route everything through Cloudflare. The stack ships
a commented `cloudflared` service; the flow:

1. In `https://one.dash.cloudflare.com → Networks → Tunnels → Create a tunnel`,
   choose **Cloudflared**, give it a name and finish.
2. Copy its **token** (the long string in the install command) into `.env`:
   ```
   CLOUDFLARED_TOKEN=eyJhIjoi...
   ```
3. In `docker-compose.yml`, uncomment the whole `cloudflared:` service block.
4. In the tunnel's **Public Hostname** tab add a route:
   - Subdomain: `files`, Domain: your site, Path: (empty)
   - **Service: `http://localhost:8080`**
5. `docker compose up -d` and check both containers are healthy:
   ```
   docker compose ps
   ```

When the tunnel is active the portal is reached only through Cloudflare; no
host port is published. All rate limits, CSRF protection and password rules
were designed for the Cloudflare 100 MB request cap: uploads are chunked
(default 20 MB) and ZIP downloads stream from a tempfile.

## 9. Updating

```
git pull
./deploy.sh        # rebuilds image, keeps .env and data
```

---

## Troubleshooting

**The portal cannot write files / uploads fail (Permission denied)**
The container user `PUID:PGID` lacks rights on the dataset. In
**Storage → Datasets → Edit Permissions**, grant that user/group Full Control,
or (Unix mode) chown the dataset: on the shell:
```
chown 3000:3000 /mnt/tank/clients
```
Re-run `docker compose up -d`; `deploy.sh` will confirm write access.

**Files uploaded by the portal are not visible on the SMB share**
The share ACL and the dataset owner must both accept the container uid. If the
share uses Windows ACLs, add the `PUID` user (or the group it belongs to) to
the share's access list with read/write.

**Where is the admin page?**
`http://<nas-ip>:8080/admin`. Behind the tunnel: `https://files.yourdomain.com/admin`.

**I forgot the admin password**
Edit `.env`, set a new `PORTAL_ADMIN_PASSWORD`, restart:
```
docker compose up -d
```

**Slow uploads/downloads over the tunnel**
Uploads are chunk-limited to the Cloudflare 100 MB cap. The portal does
*not* stream your whole dataset - keep each served `share` subfolder reasonably
sized, or use the built-in download (the portal streams and rate-limits
transfers to be gentle on the tunnel).

**Backup the portal state**
Everything the portal owns lives in `PORTAL_DATA_PATH` (DB, logo, secret) and,
of course, `PORTAL_FILES_PATH` is your dataset. Back those up with your normal
dataset snapshots:
```
zfs snapshot tank/portal-data@pre-update
```