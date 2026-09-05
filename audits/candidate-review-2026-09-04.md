# 视频制作 Skill 候选审计（2026-09-04，2026-09-05 补充复核）

目标是补能力，不是堆目录。入选标准：近期有实质更新、GitHub 星标或 SkillHub 评分/安装量有可信信号、许可证或使用边界清楚、能补上现有调用链缺口。

## 已集成

| 来源 | 候选 | 当前信号 | 集成方式 | 原因 |
| --- | --- | ---: | --- | --- |
| GitHub | `MiniMax-AI/MiniMax-H3` 官方 `h3-prompt-writing` | 8,008 stars；2026-08 新增/更新 | 根据官方结构重写 H3 适配器，不整包复制 | 第一方、固定输出 Schema、补齐 T2VA/I2VA/FL2VA/L2VA/Ref2VA |
| GitHub | `Square-Zero-Labs/video-prompting-skill` | 164 stars；2026-08-24 更新 | 吸收“主路由 + 模型适配器 + 参数外置”的架构 | 许可证 Apache-2.0，解决跨模型重复和路由混乱 |
| GitHub | `OSideMedia/higgsfield-ai-prompt-skill` | 487 stars；2026-08-23 更新 | 只吸收素材职责/排除项、阶段终态、按主要任务拆镜 | 许可证 MIT；不引入其 Higgsfield 参数和未经独立验证的经验规则 |
| GitHub | `agentara/skills` 的 `video-storyboard` | 仓库 455 stars；Skill 2026-05 | 改造成“独立帧优先、总览板可选”的分镜交付门禁 | 许可证 MIT；保留连续性与时间核算，去掉固定网格的普适假设 |
| SkillHub | `@cellcog/video-generation-cellcog` | 24 stars、9,496 downloads、299 installs；v1.0.18 | 作为明确授权后的可选外部执行器 | SkillHub 中同类评分最高的一档；MIT-0；需要 API key、上传和额度，因此不进入默认路径 |
| SkillHub / GitHub | `video-editing`（`affaan-m/ECC`） | GitHub 247,953 stars；SkillHub 高热度 | 保留已集成后期模块并补充上游追踪 | 能力成熟，避免再接入重复的 FFmpeg/Remotion 指南 |
| SkillHub / GitHub | `remotion-dev/skills@remotion-best-practices` | skills.sh 约 502k installs；仓库 4,487 stars；v4.0.520；2026-09-01 更新 | 新增原创 `remotion-production` 路由适配器，不复制上游 137 份规则文件 | 补齐可编程视频、字幕、批量版本、预览与确定性渲染；与生成模型提示词不重叠 |
| SkillHub / GitHub | `higgsfield-ai/skills@higgsfield-video-explainer` | skills.sh 约 60k installs；仓库 865 stars；v0.12.0；2026-07 更新 | 新增原创 `higgsfield-explainer` 适配器；外部执行需授权 | 补齐非写实旁白解释视频的十秒分块生产；MIT，能力边界清楚 |

## 已更新的组成 Skill

| 组成 Skill | 原包状态 | v2.1 内状态 |
| --- | --- | --- |
| `short-drama-writer` | 2.3.5 | 2.3.6 |
| `creative-writing-cellcog`（旧路由名 `story-cog`） | 1.0.1 | 1.0.15 |
| `cellcog`（传递依赖） | 1.0.21 | 2.0.21 |
| `video-generation-cellcog` | 未集成 | 1.0.18，可选执行器 |

这些更新只进入隔离版，没有覆盖 `~/.agents/skills` 或 `~/.codex/skills` 的现役版本。

## 未进入默认调用链

| 候选 | 信号 | 决定 |
| --- | --- | --- |
| SkillHub `@pruna-ai/video-prompting` | 0 stars、0 installs，虽有近期更新 | 不集成；缺少使用反馈 |
| SkillHub `@permew/wan-3-0-prime-reference-to-video` | 0 stars、0 installs，刚发布 | 不集成；过新且强绑定 RunComfy |
| SkillHub `@omerflo/video-production` | 1 star、56 installs | 不集成；Veo/API 专用且与现有制作流程重叠 |
| `skills-101/superpowers@ai-video-generation` / RunComfy 同源技能 | skills.sh 安装量很高 | 不集成；强绑定外部模型路由与付费生成，且与现有三模型路由、CellCog 执行器高度重叠 |
| `prime-skills/runcomfy-agent-skills@video-edit` | 安装量很高，但独立能力强绑定付费服务 | 不集成；仅作为外部工具候选 |
| `coreyhaines31/marketingskills@video` | skills.sh 约 63k installs；仓库约 46.9k stars；MIT | 暂不新增独立模块；其营销视频与剪辑语法和现有反推、短视频链路重叠，列入月度观察 |
| `elementsix/elementsix-skills@seedance-storyboard` | 826 installs；仓库 307 stars；MIT | 不集成；仍以 Seedance 2.0 规则为主，与本包 2.5 + storyboard-package 重叠 |
| `fal-ai-community/skills` | 234 stars | 不集成；根许可证未识别且 API 强绑定 |
| `refly-ai/refly-skills` | 202 stars | 不集成；许可证未识别且工作流依赖平台 |
| `modelscope/ms-agent` | 4,375 stars | 不集成；未找到与本任务直接对应的分镜/视频制作 Skill |

## 风险说明

- 星标属于仓库或注册页信号，不等于单个 Skill 的质量保证。
- 平台能力、参数和价格会变；提示词工具只锁创作结构，当前参数应在实际生成前复查。
- MiniMax 官方仓库未识别到根许可证，因此本包没有复制其整套文件，只保留必要字段名、互操作格式和原创中文说明。
- 外部执行器可能上传素材并消耗额度，必须先获得用户对素材范围、服务商和成本的明确授权。
- Remotion Skill 仓库未声明标准根许可证，因此本包只提供原创路由并链接外部 Skill，不再分发它的规则正文。
