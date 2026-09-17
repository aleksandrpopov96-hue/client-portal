# ---- Frontend build stage -------------------------------------------------
FROM node:20-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ .
# vite.config.js outputs to ../static relative to this dir -> /build/static
RUN npm run build

# ---- Python runtime stage -------------------------------------------------
# PUID/PGID must match the numeric owner of the dataset the container serves
# (TrueNAS datasets often use UID/GID 3000). Override with --build-arg or via
# build.args in docker-compose.yml. Do NOT use 0 (root).
FROM python:3.12-slim
ARG PUID=3000
ARG PGID=3000

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --gid ${PGID} portal \
    && adduser --disabled-password --gecos "" --uid ${PUID} --ingroup portal portal \
    && install -d -o portal -g portal /data/files /data/portal

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY portal/ portal/
COPY templates/ templates/
COPY --from=frontend /build/static/ /app/static/

ENV PORTAL_STORAGE_ROOT=/data/files \
    PORTAL_DATA_DIR=/data/portal \
    PORTAL_ADMIN_PASSWORD=CHANGE_ME \
    PYTHONUNBUFFERED=1

USER portal

# Single worker + threads: needed for the in-memory rate limiter and SQLite.
CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "1", "--threads", "8", "--timeout", "900", "app:create_app()"]