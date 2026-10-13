# 采集端接入接口

手机、Jetson、相机采集程序可以复用下面接口。当前为一台设备或一个受控机构工作台，不含多租户认证。

1. 若设置 `CZ_ACCESS_TOKEN`，先 `POST /api/login`，JSON为 `{"token":"本机配置的口令"}`，保留返回cookie；自动客户端也可在每个请求使用Bearer token。
2. `GET /api/status` 读取当前 `csrf`；所有后续POST带 `x-cz-csrf`。
3. `POST /api/cases`，multipart字段 `metadata` 是JSON字符串，`photos` 是重复的图片字段。最多6图，每图8MB，请求总量40MB。支持JPEG/PNG/WebP。
4. `POST /api/cases/{case_id}/jobs`，JSON `{"mode":"analyze"}`。返回202及任务编号，不同步等待模型。
5. `GET /api/jobs/{job_id}` 查询状态，终态为complete/failed/cancelled/interrupted。
6. 完成后下载 `/api/jobs/{job_id}/report.pdf`；完整JSON为 `/report`，证据包为 `/evidence.zip`。

metadata示意：

```json
{
  "name": "青釉碗",
  "claim": "希望核对口沿是否有修补",
  "source": "现场拍摄",
  "roles": ["overall", "base", "detail"],
  "online": false,
  "cloud_review": false
}
```

视角值：overall/base/mouth/detail/mark/unknown。视角由上传端声明，视觉步骤会另行检查；不要把声明写成已核实的设备测量。

照片保留原始字节及哈希。当前未核验相机签名、GPS、拍摄时间或光学倍率；未提供的信息保持空值。设备端可以加标尺、色卡和规范视角，但不得伪造采集元信息。

可从现有FastAPI系统反向代理本模块；新应用独立启动在8790端口，避免改坏原比赛网站。若必须在同一Python进程中挂载，请另行检查挂载前缀、静态资源及认证路由；本版网页默认部署在站点根目录。

## v0.2 变化

- `GET /api/model-health`：真实请求本地 `/v1/models`，返回就绪、未配置、不可用或模型名不匹配；配置存在不再等同在线。
- `POST /api/demos` 和重复上传按相同照片像素集合复用器物ID。修改上传说明保留原报告，下一次分析使用新的输入。
- `POST /api/cases/{id}/jobs` 默认复用相同输入、模式、模型和资料版本的进行中/已完成任务；传 `force_new: true` 明确创建新报告。失败任务可重新开始。
- `GET /api/cases` 返回器物清单及 report_count，不把每次访问当成一个器物。`GET /api/cases/{id}` 包含其所有报告任务。
- 原始重复记录作为别名保留，旧的照片及报告链接继续有效。
