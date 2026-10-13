# 实体 DGX Spark 部署步骤

目标：在新 Spark 上本地运行视觉模型、资料索引、预检后台和网页，用户提交照片后生成一页 PDF。以下为待在目标机器执行的部署配方；当前开发电脑没有这台新 Spark 的 GPU。

## 推荐：一条命令安装完整本地推理系统

取得代码或解压安装包后：

```bash
bash scripts/install-spark.sh --with-system-packages
```

本入口依次安装应用、下载 **Qwen3-VL-8B-Instruct 多模态大语言模型**、启动 NVIDIA vLLM GPU 服务、检查模型名称、执行真实双图请求、后台启动网页，再执行 `acceptance.py --visual`。同一模型既能看图也能推理文字，无需外部大模型 API。各步出错即停止，不自动替换成资料体验。

之后启动：`bash scripts/run-spark.sh`。应用日志在 `runtime/app.log`；初次模型启动最多等待15分钟，可通过 `CZ_STARTUP_TIMEOUT` 调整。脚本复用已下载权重和本项目容器，遇到其他项目同名容器会退出。

以下是分步部署及排错说明，适用于自定义模型或查看每个环节。

## 1. 取得代码

```bash
gh auth login
gh repo clone dingyucanada/cizheng-spark-precheck
cd cizheng-spark-precheck
uname -m
nvidia-smi
docker version
df -h .
```

Spark 应是 Linux aarch64。保留当前驱动和 Docker 状态；不要在未查明原因时直接更换系统 CUDA 或 GPU 驱动。

## 2. 安装应用

```bash
bash scripts/bootstrap-spark.sh --with-system-packages
```

脚本建立 `.venv`，安装锁定应用依赖和中文字体；已有 `.env` 不会覆盖。若系统组件已经具备，省略 `--with-system-packages`。没有 sudo 时先让管理员安装 `python3-venv fonts-wqy-zenhei poppler-utils`。

先只启动应用体验公开资料核查：

```bash
bash scripts/start.sh
```

另一终端运行：

```bash
.venv/bin/python scripts/acceptance.py
```

打开 `http://127.0.0.1:8790`。即使 `.env` 已有模型名称，配置存在也不代表模型已经可用；公开馆藏核查可以独立运行。

## 3. 下载视觉模型

先使用 **Qwen3-VL-8B-Instruct BF16** 建立稳定基线，之后再通过同一批照片比较更大模型。主干支持 OpenAI 兼容多图服务，可更换模型；不要把纯文字模型用于视觉观察。

```bash
.venv/bin/python -m pip install 'huggingface-hub>=0.35,<2'
.venv/bin/python scripts/download-model.py --inspect-only
.venv/bin/python scripts/download-model.py
```

脚本会解析并固定下载时的实际模型提交哈希，保存版本清单。大文件下载量和耗时取决于该版本及网络；仓库不附带模型权重。

## 4. 准备 GPU 容器并启动

起始镜像为 `nvcr.io/nvidia/vllm:26.01-py3`。该版本官方说明列有 vLLM 0.11.1、Transformers 4.57.1 和 CUDA 13.1.1；需要在目标机器检查 ARM64 镜像及驱动兼容。该组合针对当前基线给出，不表示已在新机器验证。

```bash
docker manifest inspect nvcr.io/nvidia/vllm:26.01-py3
bash scripts/start-model.sh
docker logs -f cizheng-vision
```

服务端口仅绑定 `127.0.0.1:8000`。脚本启用 BF16、单请求并发、16K 上下文、最多6图、60% 显存预算和 eager 模式，先保证可运行。若存在本项目且配置相同的容器，脚本复用；其他同名容器不会被覆盖。

模型准备好后：

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/v1/models
set -a
source .env
set +a
.venv/bin/python scripts/probe-model.py
```

如果镜像不支持当前驱动，依据 NVIDIA 官方兼容说明选择已确认支持该设备的镜像，通过 `CZ_VLLM_IMAGE` 覆盖。若镜像内入口或参数发生变化，用 `docker run --rm --entrypoint vllm IMAGE serve --help` 核对再修订。不得把换镜像、换模型写成已经成功，必须重新做双图探测。

## 5. 完整视觉验收

模型已配置后，重启应用并运行：

```bash
.venv/bin/python scripts/acceptance.py --visual --output verification/private/visual-acceptance.json
.venv/bin/python -m pytest -q
```

实际检查：不同视角均有观察、疑点框落在对应位置、引用原句存在、风格相似未转为身份确认、评分理由可复核、PDF只有一页且没有截字。再用自己的2–3件真实器物运行；训练资料不作为独立测试真值。

## 6. 从笔记本或采集端访问

推荐 SSH 隧道，不对公网直接开放开发服务：

```bash
ssh -L 8790:127.0.0.1:8790 你的Spark主机别名
```

随后在笔记本打开 `http://127.0.0.1:8790`。手机或 Jetson 采集端部署在受控局域网时，需要设置强随机 `CZ_ACCESS_TOKEN`、`CZ_ALLOWED_HOSTS` 和实际监听地址，并通过机构网关提供 HTTPS。现有版本是单机构、单实例工作台，未实现多租户隔离。

## 7. 开机启动和维护

先手动验收，再按真实用户名、项目路径修改 `deploy/cizheng.service.example`，复制到 `/etc/systemd/system/cizheng.service` 后启动。不要原样安装带占位符的文件。模型容器自带 `unless-stopped` 重启策略。

应用数据位于 `runtime/`，包含私人照片，应按实际机构规则备份。`.env` 和 `runtime/` 已加入忽略清单。更新代码前备份；同一数据目录只运行一个服务进程，不设置多 worker。

## 超时和效果处理

- 界面提交是异步任务；刷新仍能找回记录。启动时把中断任务标记为可重试，不冒充成功。
- 首次请求可能包含模型编译或预热。先运行双图探测；正式演示前用公开照片预热。
- 默认单个模型请求85秒、整件任务260秒。需依据实测调整；缩图仅用于模型预览，原图保留。
- 先用2–3张清晰照片。遇超时检查模型日志、内存、上下文和输出长度，再决定调参数或升级模型。
- 不为追求速度跳过引用核验或悄悄改用预先生成的意见。

## 官方参考

- [NVIDIA Spark vLLM 操作指南](https://build.nvidia.com/spark/vllm/instructions)
- [NVIDIA vLLM 26.01 版本说明](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/rel-26-01.html)
- [Qwen3-VL 官方模型卡](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
- [vLLM Qwen3-VL 配置说明](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3-VL.html)

这些资料支持模型和服务接口选型；不证明陶瓷辨伪效果或本机部署成功。

## 升级和资料归并

更新应用前备份 runtime，并停止本项目正在运行的应用进程。保留 .env、models、runtime 后更新代码及应用依赖，再启动工作台。启动时按照片解码像素集合将旧重复档案归并显示，不删除原图和旧报告。模型配置变化不会重用旧的分析结果；明确重新分析会保存新报告版本。

当前未连接新实体 Spark，因此本仓库记录的工程测试不等于该机器已完成GPU部署。最终以安装程序在目标机器产生的真实图像验收记录为准。
