FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORTAL_STORAGE_ROOT=/data/files \
    PORTAL_DATA_DIR=/data/portal \
    PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "2", "--threads", "4", "app:create_app()"]
