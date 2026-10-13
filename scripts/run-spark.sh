#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env && -x .venv/bin/python ]] || { echo '请先运行 scripts/install-spark.sh。' >&2; exit 1; }
set -a
source .env
set +a
bash scripts/start-model.sh
.venv/bin/python scripts/wait-model.py --timeout "${CZ_STARTUP_TIMEOUT:-900}"
.venv/bin/python scripts/start-app.py
