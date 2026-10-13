# 来源、许可及技术依据

## 实物照片及馆藏记录

随包9张照片均来自The Metropolitan Museum of Art公开馆藏，不使用AI生成图。原始URL、SHA-256、尺寸和许可记于 `knowledge/photos.json`；馆方JSON原始记录在 `knowledge/records/`。

- [青釉碗，馆藏17.57.1](https://www.metmuseum.org/art/collection/search/48450)
- [青花觚，馆藏18.61.4](https://www.metmuseum.org/art/collection/search/48607)
- [馆藏79.2.1202a,b](https://www.metmuseum.org/art/collection/search/51185)
- [The Met Open Access API](https://metmuseum.github.io/)
- [The Met Open Access](https://www.metmuseum.org/about-the-met/policies-and-documents/open-access)

记录中的 `isPublicDomain` 为true；照片按馆方Open Access条件提供。项目保留源链接和许可信息，不声称馆方对本应用背书。三件图片属于资料核查输入，不代表民间持有人实物采集。参考资料日期为馆方归属，不是本项目独立测年。

## 模型和运行框架

- [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)：基线视觉模型，权重另行下载，按模型仓库许可使用。
- [vLLM Qwen3-VL recipe](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3-VL.html)：多模态服务及参数依据。
- [NVIDIA vLLM 26.01](https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/rel-26-01.html)：容器内容及统一内存配置注意事项。
- [NVIDIA DGX Spark 官方指南](https://docs.nvidia.com/dgx/dgx-spark/)：设备部署和管理参考。

FastAPI、Starlette、Uvicorn、HTTPX、Pydantic、Pillow、NumPy和ReportLab按各自上游许可分发。源码包不拷贝平台中文字体；Linux使用系统安装的文泉驿字体。`requirements.lock` 记录开发验证的实际依赖版本，ARM64环境仍应完成安装和测试。

## 芝加哥艺术博物馆参考记录

- [API 官方说明](https://api.artic.edu/docs/)
- [龙泉窑花口杯及托](https://www.artic.edu/artworks/21653)
- [龙泉窑鹤鹿云纹花口盘](https://www.artic.edu/artworks/12476)
- [龙泉窑犀牛望月纹花口盘](https://www.artic.edu/artworks/12483)

保存的题名、材质、年代等字段来自官方API，按其返回的CC0资料说明使用；未包含description字段。不同器型只用于工艺背景比较。当前网络对其图片服务返回403，因此没有复制该机构图像；参考图适配器会在允许访问时处理公开授权图片。
