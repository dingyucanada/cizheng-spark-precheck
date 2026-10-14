# 在新实体 Spark 上接续部署

也可直接将安装包交给其他 Spark 用户，按 [START_HERE.md](START_HERE.md) 安装。完整入口为 `bash scripts/install-spark.sh --with-system-packages`，包括本地多模态权重下载和 GPU 推理服务。

这是完整代码交接。新机器上的 Codex 可以直接从仓库安装和验收，不依赖上一台 Spark、不依赖本次开发电脑的绝对路径，也不依赖原来的比赛网站。

## 给 Codex 的任务

复制下面这段话：

> 请在这台 DGX Spark 部署“瓷证·一页预检”。先阅读 AGENTS.md、README.md、docs/SPARK_DEPLOY.md 和 verification/RESULTS.md。检查环境，建立独立虚拟环境，安装中文字体和项目依赖，启动本地工作台；执行完整安装入口，准备 Qwen3-VL-8B-Instruct 或经验证的兼容视觉模型，启动本地多模态服务，真实运行双图探测和完整视觉预检。把遇到的问题修复好，确认一页 PDF 可读、评分有理由、引用可回查、原图哈希正确。保留模型提交、容器摘要、实测耗时和失败信息到 verification/private。最后给我可访问地址和启动方法。不要把模型未运行的资料核查写成真实模型完成，不要把原图发到云端，不要覆盖其他项目或暴露密钥。

## 你只需要准备

- 在 Spark 上安装 Git，或下载并解压公开发行包；克隆代码不需要 GitHub 账号。
- 可用网络用于首次下载 Python 依赖、容器和模型。模型下载后可以离线使用。
- 初次安装可能需要 sudo 安装中文字体和 Python 虚拟环境组件。
- 建议先准备约 60 GB 以上可用磁盘作为模型、容器、缓存及案例余量；最终以脚本查询的实际模型文件大小为准。

HF 上公开非门控模型通常可匿名下载；若遇限流或组织网络要求，登录操作留在设备上完成，不把令牌贴入对话或源码。

## 接续完成的验收结果

| 验收 | 记录位置 |
|---|---|
| 新机器硬件和依赖检查 | `verification/private/hardware-inventory.json` |
| 实际使用的容器摘要 | `verification/private/vllm-image-digest.json` |
| 权重版本 | `models/qwen3-vl-8b/cizheng-checkpoint.json` |
| 模型真实读取两张照片 | `verification/private/model-probe.json` |
| 上传、任务、模型、引用、评分、PDF 完整链路 | `verification/private/visual-acceptance.json` 及 PDF |

只有图像服务健康检查不够；必须执行真实图片请求。工程验收也不能替代专业鉴定准确率测试。
