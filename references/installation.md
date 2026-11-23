# 安装与使用

WorkBuddy：专家·技能·连接器 → 技能 → 添加技能 → 上传技能，选择本技能文件夹或ZIP；导入后在已安装列表核查。官方入口依据：[技能文档](https://free-plat-test.qcloudcdn.com/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)。本包格式符合SKILL.md目录结构；本次未在WorkBuddy客户端完成导入与触发验收，不将格式检查称为客户端实测。

DeepSeek Harness：项目作用域放到 `.dsh/skills/rh-video-replica/` 或 `.agents/skills/rh-video-replica/`，确保该目录下直接有SKILL.md。目录发现规则来自 [DeepSeek官方源码文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.zh.md)。实际版本的插件与目录加载仍须在目标会话核查；不需要为了本技能修改其他会话、模型或授权配置。

Codex：放在 `~/.codex/skills/rh-video-replica/`，新会话可发现。未安装依赖时先运行 requirements.txt 安装，再做 doctor 检查。外部API需要由用户在本地配置自己的凭据。

示例任务：
“使用 rh-video-replica，把本地 ref.mp4 的镜头结构改为 product.png 的商品短片，保持15秒9:16；卖点仅使用我提供的资料，输出参考证据、分镜、成片、费用和验收记录。”

技能要求宿主能够读本地图片、执行Python、保存文件；仅有聊天而没有工具权限的宿主不能完成自动视频交付。当前不声称已通过商店上架审核。
