#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# First installation is intentionally separate from the collector-facing application.
bash scripts/run-spark.sh
set -a
source .env
set +a
.venv/bin/python scripts/probe-model.py
.venv/bin/python scripts/acceptance.py --visual --base-url "http://127.0.0.1:${CZ_PORT:-8790}" --output verification/private/stage-rehearsal.json
.venv/bin/python scripts/stage-check.py --export-photos
printf '设备排练已完成。打开用户界面：http://127.0.0.1:%s/?new=1\n' "${CZ_PORT:-8790}"
echo '请人工确认报告内容、投屏分辨率和现场时长；预先打开备用PDF，意外时明确展示已保存报告。'
