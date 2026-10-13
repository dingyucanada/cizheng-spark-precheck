# 本次交付验证记录

验证日期：2026-10-14。应用版本：0.1.0。当前开发环境为 macOS / Python 3.12；新实体 DGX Spark 尚未连接。本文件记录实际执行范围，目标设备记录由部署后追加。

## 已执行

| 检查 | 实际结果 | 可核查文件 |
|---|---|---|
| 后台及规则回归 | 35 项通过；覆盖原图留存、来源匹配、引用、权限、拒绝评分、取消、超时和篡改拦截 | `pytest.txt`、`tests/` |
| 桌面浏览器操作 | 实际点击馆藏入口，生成报告，下载PDF，展开证据，刷新恢复，打开历史 | `browser-check.json`、`docs/workbench.png`、`docs/report-workbench.png` |
| 手机布局 | 390×844 视口，无横向溢出 | `mobile.png` |
| 实际照片上传及错误恢复 | 上传两张照片，连接刻意不可用的本地模型地址；明确失败、保留照片、刷新后重试，无伪造报告 | `browser-failure-check.json` |
| HTTP 完整验收 | 公开馆藏资料核查成功，PDF一页，文件哈希一致 | `catalog-acceptance.json`、`catalog-acceptance.pdf` |
| PDF目视检查 | 中文可读、原图完整、意见和评分清晰，无越界或多页 | `catalog-report.pdf`、`docs/onepage.png` |
| 馆藏在线检索 | 芝加哥艺术博物馆API返回3条龙泉窑相关记录；The Met本次返回403，系统保留降级状态 | `online-probe.json` |
| 参考图来源 | 随包9张已核对的The Met原图；本次AIC图片接口403，未复制新图片 | `knowledge/photos.json`、`online-probe.json` |
| GPU镜像架构 | 注册表清单包含linux/arm64，已保存实际摘要；未在GPU启动 | `vllm-manifest.json` |
| 代码及脚本 | Python编译检查、Shell语法检查通过 | `scripts/`、GitHub自动检查 |

测试记录有一条 Starlette/httpx 测试客户端弃用提醒，不影响当前测试结果。调用视觉模型的单元/链路测试使用明确标识的测试替身，以验证协议、状态和错误处理；这些替身只存在于tests，生产应用不能选用。浏览器馆藏体验执行真实来源匹配及规则，不宣称模型看图。

## 新 Spark 上的真实验收

1. 运行 `scripts/doctor.py`，确认ARM64、GPU、驱动、Docker、中文字体及可用磁盘。
2. 下载固定提交的视觉权重，启动容器，保存容器摘要和模型清单。
3. 运行 `scripts/probe-model.py`，确认真实双图读取和结构化输出。
4. 运行 `scripts/acceptance.py --visual --output verification/private/visual-acceptance.json`，确认实际模型调用和完整一页报告。
5. 用持有人真实新照片检查观察位置、比较对象、引用原句、理由和送检建议；邀请专家复核专业正确性。

公开资料核查的秒级耗时不能用于宣称视觉模型速度；单元测试通过不能用于宣称鉴真准确率。当前未生成真实新Spark的吞吐、显存或陶瓷辨伪准确率数字。
