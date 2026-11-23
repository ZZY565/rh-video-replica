# RunningHub 接入（2026-11-23 核验）

凭据仅从环境变量 `RUNNINGHUB_API_KEY` 读取；默认域名 `https://www.runninghub.cn`，国际账号可设 `RUNNINGHUB_BASE_URL=https://www.runninghub.ai`。账号与站点应匹配。不要将 key 写进 JSON、Skill、报告或压缩包。

## 参考生视频模型通道

`rh-model-run job.json --journal project/task.json`，job 内路径相对 job 文件：

```json
{
  "endpoint":"alibaba/wan-3.0/reference-to-video",
  "video_paths":["reference.mp4"],
  "image_paths":["product.png"],
  "prompt":"参考视频1的镜头结构，以图1商品为准；画面不生成文字，字幕后期添加。",
  "settings":{"duration":15,"resolution":"720P","aspectRatio":"9:16","audio":false,"promptExtend":false,"watermark":false,"seed":11222026}
}
```

V2 二进制上传：`POST /openapi/v2/media/upload/binary`，Bearer 鉴权，multipart `file`；使用 `data.download_url`。模型提交：`POST /openapi/v2/alibaba/wan-3.0/reference-to-video`。查询：`POST /openapi/v2/query`，JSON taskId。参考视频总时长+输出时长≤30秒；脚本先检查这一约束。协议依据：RH官网链接的 [官方脚本](https://github.com/HM-RunningHub/OpenClaw_RH_Skills/blob/main/runninghub/scripts/runninghub.py) 与 [模型页](https://www.runninghub.cn/call-api/api-detail/2133100000000700019)。当前账号是否可调用、模型是否仍在售需按返回确认。

## ComfyUI 工作流通道

用 RunningHub 导出的 API 图校验覆盖项，禁止改写代表连线的列表：

```sh
python3 scripts/replica.py rh-plan request.json --graph workflow-api.json --out checked-request.json
python3 scripts/replica.py rh-upload product.png --out upload.json
python3 scripts/replica.py rh-submit checked-request.json --graph workflow-api.json --journal project/task.json
```

上传后将真实 fileName 填入 request 的 nodeInfoList。旧工作流上传 `/task/openapi/upload` 和结果 `/task/openapi/outputs` 已在文档标为将废弃；本包旧图上传保留兼容入口，查询统一用V2。请优先使用模型V2上传；旧图接口若拒绝，不要未经验证自行替换字段。

高级工作流提交依据 [官方文档](https://www.runninghub.cn/runninghub-api-doc-cn/api-425749013)，nodeInfoList 依据 [官方参数说明](https://www.runninghub.cn/runninghub-api-doc-cn/doc-8287336)。新导入的本地图须先在平台保存获得自己的 workflowId，导入JSON不等于云端已部署或已实测。

## 恢复与下载

```sh
python3 scripts/replica.py rh-poll project/task.json --timeout 900 --interval 10
python3 scripts/replica.py rh-download project/task.json --out project/raw
```

提交前独占创建 journal；请求发出后响应丢失标 `submission_unknown`，禁止自动重试。查询超时保留 taskId（远端可能仍在运行），之后用同一个 journal 继续查询。只有成功且有结果URL才进入下载。journal 的结果URL可能临时授权访问素材，应保存在项目私有目录，分享前只保留 taskId、usage、下载文件哈希，删除原URL。

模型/LLM需企业级共享Key；工作流可用Key类别不同，见 [官方开始页](https://www.runninghub.cn/runninghub-api-doc-cn/doc-8287334)。Skill不包含模型费用，费用不会因封装成Skill而免除。

## 本地未配置Key时的网页接回

在官方API Playground提交已准备的素材和参数；成功后复制结果区JSON，打开技能的 `assets/import-result.html` 粘贴并检查，下载去凭据记录和原片。这个入口只解析当前页面中的数据，不联网、不提交新任务。要持续无人值守执行，仍需配置自己的API Key，不能将网页演示称为独立Python客户端实测。

## 两种条件模式

默认`conditioning:"reference_video_and_product"`要求video_paths和image_paths都有素材。`conditioning:"storyboard_and_product"`要求video_paths为空，image_paths包含商品图；真实广告仅供Agent分析，模型收到Agent改编后的分镜描述。后者用于避免直接保留原人物/场景，报告不得写成模型看过原片。

官方Playground连续运行时，JSON面板可能暂时显示上一轮成功结果。新任务必须核对不同taskId、参数与创建时间，必要时从控制台任务历史确认；页面“创建成功”不等于旧taskId就是本次ID，禁止因JSON滞后再次提交。
