---
name: legacy-filmmaking-v1
description: 为旧版 filmmaking 调用提供 v2.1 兼容路由，把历史的一体化请求转交给当前按制作阶段拆分的模块；不进入默认调用。
metadata:
  implementation: hardcore-director-original
  version: "2.1.0"
  status: compatibility-only
---

# 旧版 Filmmaking 兼容路由

本文件只处理旧命令或旧项目仍引用 `filmmaking` 的情况。它不保存旧版方法正文，也不作为新的创作入口。新的请求应从主 `SKILL.md` 识别制作阶段，再按需读取一个主模块、一个平台适配器和最多两个专项增强。

## 兼容映射

| 旧请求意图 | v2.1 主路由 |
| --- | --- |
| 故事、剧本、短剧 | `screenwriter`、`shanyin-screenwriting` 或短剧三模块之一 |
| 角色、场景、空间 | `character-design`、`ai-scene-design`、`composition-to-prompt` |
| 分镜与连续性 | `screenwriter` + `integrations/storyboard-package` |
| AI 视频提示词 | `prompt-tools/model-router` + 唯一目标模型适配器 |
| 表演、动作、运镜 | `seedance-perform-v5-single` 或当前平台适配器的表演段 |
| 色彩、调色、节奏 | `tint-to-prompt`、`stylized-color-grading`、`rhythm-to-prompt` 中最多两个 |
| 声音与配乐 | `sound-design-to-prompt`、`ai-music-generator` |
| 拉片与反推 | `video-analysis` 或 `video-reverse-engineer` |
| 素材剪辑与确定性渲染 | `video-editing` 或 `integrations/remotion-production` |
| 短视频发布 | `short-video-script`、`short-video-hook-lab`、抖音专项模块 |

## 迁移规则

1. 保留用户原始交付目标、素材、时长、画幅和平台，不沿用旧路由的隐含默认值。
2. 先判断当前最靠近交付物的阶段；没有通过当前门禁时，不提前堆叠后续模块。
3. 旧请求只说“调用 filmmaking”时，按普通硬核导演请求处理，并说明已进入 v2.1 兼容路由。
4. 旧项目明确依赖某个历史字段时，只在本次输出中做字段映射，不把该字段升级成全局规则。
5. 外部 API、上传、付费、安装和发布仍需单独授权；旧命令不构成授权。

## 兼容验收

- 输出仍能完成旧请求的核心目标；
- 没有一次性加载全部影视模块；
- 新模型请求进入 Seedance 2.5、Wan 3.0 或 MiniMax H3 对应工具；
- 时长、连续性、素材职责和声音关系经过当前质量门禁；
- 不再引用旧版私有路径、作者信息或不可核实的历史正文。

本文件为硬核导演 v2.1 的原创兼容层，仅用于平滑迁移旧调用。
