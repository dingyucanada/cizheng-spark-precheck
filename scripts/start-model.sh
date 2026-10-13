#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CZ_VLLM_IMAGE="${CZ_VLLM_IMAGE:-nvcr.io/nvidia/vllm:26.01-py3}"
CZ_MODEL_DIR="${CZ_MODEL_DIR:-$(pwd)/models/qwen3-vl-8b}"
CZ_SERVED_MODEL="${CZ_SERVED_MODEL:-Qwen/Qwen3-VL-8B-Instruct}"
if [[ ! -f "$CZ_MODEL_DIR/config.json" ]]; then
  echo "找不到本地模型。请先运行 scripts/download-model.py。" >&2
  exit 1
fi
if docker container inspect cizheng-vision >/dev/null 2>&1; then
  echo "cizheng-vision 已存在。先检查 docker logs cizheng-vision；本脚本不会覆盖已有容器。" >&2
  exit 1
fi
docker pull "$CZ_VLLM_IMAGE"
mkdir -p verification/private
docker image inspect "$CZ_VLLM_IMAGE" --format '{{json .RepoDigests}}' > verification/private/vllm-image-digest.json
docker run -d --name cizheng-vision --restart unless-stopped --gpus all --shm-size 8g \
  -p 127.0.0.1:8000:8000 \
  -v "$CZ_MODEL_DIR:/models/qwen:ro" \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e OMP_NUM_THREADS=1 \
  --entrypoint vllm "$CZ_VLLM_IMAGE" \
  serve /models/qwen --served-model-name "$CZ_SERVED_MODEL" --host 0.0.0.0 --port 8000 \
  --dtype bfloat16 --max-model-len 16384 --max-num-seqs 1 --max-num-batched-tokens 4096 \
  --gpu-memory-utilization 0.60 --enforce-eager \
  --limit-mm-per-prompt '{"image":6,"video":0}' \
  --mm-processor-kwargs '{"max_pixels":786432}'
echo "模型正在加载。用 docker logs -f cizheng-vision 查看进度，API 就绪后运行模型探测。"
