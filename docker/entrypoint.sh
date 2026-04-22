#!/bin/sh
set -e

DB_PATH="${DJANGO_DB_PATH:-/app/db.sqlite3}"
DB_DIR="$(dirname "$DB_PATH")"

mkdir -p "$DB_DIR"

python manage.py migrate --noinput

exec gunicorn core.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-120}"
