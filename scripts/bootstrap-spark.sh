#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux ]]; then
  echo "本脚本用于 Spark 的 Linux 环境；macOS 请按 README 安装。" >&2
  exit 1
fi
if [[ "${1:-}" == --with-system-packages ]]; then
  sudo apt-get update
  sudo apt-get install -y python3-venv python3-pip fonts-wqy-zenhei poppler-utils
fi
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
fi
mkdir -p runtime verification/private
.venv/bin/python scripts/doctor.py
echo "应用依赖已准备。接下来执行模型下载和启动步骤，见 docs/SPARK_DEPLOY.md。"
