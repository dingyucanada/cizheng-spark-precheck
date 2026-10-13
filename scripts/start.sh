#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
CZ_PYTHON="${CZ_PYTHON:-.venv/bin/python}"
exec "$CZ_PYTHON" -m uvicorn cizheng_precheck.api:create_app --factory --host "${CZ_HOST:-127.0.0.1}" --port "${CZ_PORT:-8790}" --workers 1
