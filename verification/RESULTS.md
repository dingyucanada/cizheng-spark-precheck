# 本次交付验证记录

验证日期：2026-10-14。应用版本：0.3.0。开发环境为 macOS / Python 3.12；当前没有连接新实体 DGX Spark。本文件区分本机工程验证和目标设备 GPU 验收。

## 0.3.0 用户流程及现场准备

| 检查 | 实际结果 | 可核查文件 |
|---|---|---|
| 后台回归 | 52项通过；新增用户入口分离、准备台访问限制、照片包完整性、真实排练条件和篡改拦截 | `pytest-v030.txt`、`tests/test_stage.py` |
| 真实浏览器用户流程 | 上传、视角、确认、分析API、报告、证据、返回新预检均完成；全流程模型使用隔离测试替身 | `browser-v030.json`、`tests/ui_fixture_server.py` |
| 演示真实性 | 用户首页没有预设案例或安装入口；开始本次预检强制新分析；已有报告标为已保存 | `browser-v030.json` |
| 失败与恢复 | 实际不可用设备会保存已上传照片；刷新后继续查看同一任务；打开档案不会重算 | `browser-v030.json` |
| 准备台 | 模型能连通、资料核查、旧会话报告均不能单独满足本轮完整排练；备用报告需原图和PDF完整 | `tests/test_stage.py` |
| 桌面和手机排版 | 已目视检查用户首页、确认页、报告页及准备台；390px无横向溢出，无浏览器脚本错误 | `docs/workbench.png`、`docs/confirm-workbench.png`、`docs/report-workbench.png`、`mobile.png` |

浏览器全流程测试使用独立端口和一次性测试数据目录，生产服务没有模拟模型选项。截图中的已保存资料报告仍明确标为资料核查。未连接实体Spark，不能把上述检查写成GPU或真实模型观察已通过。

## 0.2.0 已执行

| 检查 | 实际结果 | 可核查文件 |
|---|---|---|
| GitHub Linux 独立验证 | Ubuntu / Python 3.12 重新安装依赖及中文字体，47项测试及Shell检查通过；验证代码提交3822f39 | [运行记录](https://github.com/dingyucanada/cizheng-spark-precheck/actions/runs/38487343539)、`github-linux-v020.json` |
| 后台及规则回归 | 47 项通过，涵盖原图留存、引用、评分、取消、超时、并发去重、旧数据迁移和模型路由 | `pytest-v020.txt`、`tests/` |
| 三种资料核查场景 | 3分修补复核、2分常规核验、4分年代说法冲突；第三项明代说法明确标为体验设定 | `browser-v020.json`、`v020-48450.pdf`、`v020-48607.pdf`、`v020-51185.pdf` |
| 真实浏览器重复点击 | 同一案例复用器物 ID 和报告 ID；我的器物只列一条，刷新后恢复报告 | `browser-v020.json` |
| 历史数据迁移 | 已有重复档案归并显示，原图和旧报告仍可读取；并发提交也只创建一件 | `tests/test_objects.py` |
| 模型模式隔离 | 测试替身验证：本地分析进入视觉调用链，不复用资料核查固定分数；失败不切换成静态报告 | `tests/test_pipeline.py` |
| 模型健康检查 | 检查实际服务返回的模型名称；区分未配置、不可连接和名称不匹配 | `tests/test_deployment.py` |
| 完整安装入口 | 包含权重下载、GPU服务、双图探测、后台启动和真实视觉验收；安装计划和Shell语法检查通过 | `scripts/install-spark.sh`、`tests/test_deployment.py` |
| 三份 PDF 排版 | 均为一页，已逐份渲染目视检查；真实照片、意见、分数、理由及建议完整 | `docs/v020-48450.png`、`docs/v020-48607.png`、`docs/v020-51185.png` |
| 桌面及手机 | 无浏览器控制台错误，390px视口无横向溢出 | `browser-v020.json`、`mobile.png`、`docs/workbench.png` |

测试有一条 Starlette/httpx 测试客户端弃用提醒，不影响结果。视觉调用的自动测试使用仅存在于 tests 的替身，验证调用协议和规则，不代表真实模型观察效果。浏览器资料体验执行真实照片来源匹配及原文规则，不宣称已进行 GPU 推理。

## 0.1.0 保留的基础验证

上一版 Ubuntu / Python 3.12 的35项测试及脚本检查已通过，见 [GitHub运行记录](https://github.com/dingyucanada/cizheng-spark-precheck/actions/runs/38447677134) 和 `github-linux-ci.json`。这份旧记录不作为0.2.0的CI结果。

保留 `browser-failure-check.json`（真实上传及失败恢复）、`catalog-acceptance.json`（HTTP完整验收）、`online-probe.json`（馆藏API结果）、`vllm-manifest.json`（镜像ARM64清单及摘要）。公开馆藏接口本次曾返回403，系统保留降级状态，不虚构检索成功。

## 新 Spark 上的真实验收

1. 运行 `scripts/doctor.py`，确认ARM64、GPU、驱动、Docker、中文字体及可用磁盘。
2. 下载固定提交的视觉权重，启动容器，保存容器摘要和模型清单。
3. 运行 `scripts/probe-model.py`，确认真实双图读取和结构化输出。
4. 运行 `scripts/acceptance.py --visual --output verification/private/visual-acceptance.json`，确认实际模型调用和完整一页报告。
5. 用持有人真实新照片检查观察位置、比较对象、引用原句、理由和送检建议；邀请专家复核专业正确性。

公开资料核查的秒级耗时不能用于宣称视觉模型速度；单元测试通过不能用于宣称鉴真准确率。当前未生成真实新Spark的吞吐、显存或陶瓷辨伪准确率数字。
