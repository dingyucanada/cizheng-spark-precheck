#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" == --print-plan ]]; then
  cat <<'PLAN'
1. 检查 Linux ARM64、NVIDIA GPU、Docker 和磁盘
2. 安装应用、中文字体、Hugging Face 下载组件
3. 下载 Qwen/Qwen3-VL-8B-Instruct 多模态权重到本机
4. 启动 NVIDIA vLLM GPU 容器（原图本地推理）
5. 等待模型就绪，执行真实双图视觉请求
6. 后台启动工作台，执行完整视觉流程及 PDF 验收
重复运行会复用权重和本项目容器；不会覆盖其他项目。
PLAN
  exit 0
fi
[[ "$(uname -s)" == Linux && "$(uname -m)" == aarch64 ]] || { echo '此安装入口用于 Linux ARM64 DGX Spark。' >&2; exit 1; }
command -v nvidia-smi >/dev/null || { echo '缺少 NVIDIA 驱动，请先完成 Spark 系统初始化。' >&2; exit 1; }
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
docker info >/dev/null || { echo '当前账号无法使用 Docker，请先完成 Docker 权限配置。' >&2; exit 1; }
echo '[1/6] 安装工作台依赖和中文字体'
bash scripts/bootstrap-spark.sh "${1:-}"
.venv/bin/python -m pip install 'huggingface-hub>=0.35,<2'
set -a
source .env
set +a
[[ "${CZ_MODEL_NAME:-}" == 'Qwen/Qwen3-VL-8B-Instruct' && "${CZ_MODEL_BASE_URL:-}" == 'http://127.0.0.1:8000/v1' ]] || {
 echo '现有 .env 使用自定义模型配置，已保留。请按 docs/SPARK_DEPLOY.md 手动部署，不自动覆盖。' >&2; exit 1; }
echo '[2/6] 下载本地多模态模型（可恢复，首次需要网络）'
.venv/bin/python scripts/download-model.py --destination "${CZ_MODEL_DIR:-models/qwen3-vl-8b}"
echo '[3/6] 启动本地 GPU 推理服务'
bash scripts/start-model.sh
echo '[4/6] 等待模型加载，执行真实照片探测'
.venv/bin/python scripts/wait-model.py --timeout "${CZ_STARTUP_TIMEOUT:-900}"
.venv/bin/python scripts/probe-model.py
echo '[5/6] 后台启动预检工作台'
.venv/bin/python scripts/start-app.py
echo '[6/6] 生成真实模型报告，检查 PDF 和证据包'
.venv/bin/python scripts/acceptance.py --visual --base-url "http://127.0.0.1:${CZ_PORT:-8790}" --output verification/private/visual-acceptance.json
echo "部署及真实图片调用验收完成。打开 http://127.0.0.1:${CZ_PORT:-8790}"
echo '请再用自有器物照片检查专业效果。运行记录位于 verification/private，应用日志位于 runtime/app.log。'
