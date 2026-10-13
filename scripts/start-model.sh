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
CZ_DEPLOYMENT_KEY=$(printf '%s' "$(pwd)|$CZ_MODEL_DIR|$CZ_SERVED_MODEL|$CZ_VLLM_IMAGE" | sha256sum | cut -d' ' -f1)
if docker container inspect cizheng-vision >/dev/null 2>&1; then
  CZ_EXISTING_KEY=$(docker inspect --format '{{ index .Config.Labels "cizheng.deployment" }}' cizheng-vision)
  if [[ "$CZ_EXISTING_KEY" != "$CZ_DEPLOYMENT_KEY" ]]; then
    echo "同名容器属于其他配置或旧版，请先检查；不会覆盖或删除。" >&2
    exit 1
  fi
  docker start cizheng-vision >/dev/null
  echo "复用本项目已有的视觉模型容器。"
  exit 0
fi
if ! docker image inspect "$CZ_VLLM_IMAGE" >/dev/null 2>&1; then
  docker pull "$CZ_VLLM_IMAGE"
fi
mkdir -p verification/private
docker image inspect "$CZ_VLLM_IMAGE" --format '{{json .RepoDigests}}' > verification/private/vllm-image-digest.json
docker run -d --label "cizheng.deployment=$CZ_DEPLOYMENT_KEY" --name cizheng-vision --restart unless-stopped --gpus all --shm-size 8g \
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
