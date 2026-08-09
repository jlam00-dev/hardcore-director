# 硬核导演（Hardcore Director）

面向 Codex / Agent 工作流的影视与视频创作总控 Skill。

它把故事开发、编剧、角色与场景设计、导演美学、分镜、AI 视频提示词、表演、构图、调色、节奏、声音、拉片、剪辑与短视频发布统一到一套路由中；按制作阶段读取所需参考，避免一次性堆叠全部方法。

## 能力范围

- 电影、短片、剧集与竖屏短剧
- 角色 DNA、场景设计、构图与视觉连续性
- 分镜及多平台 AI 视频提示词
- 导演美学、调色、节奏、声音与 AI 配乐
- 拉片、竞品反推、实拍素材剪辑
- 短视频钩子、脚本与发布文案

## 安装

```bash
git clone https://github.com/jlam00-dev/hardcore-director.git ~/.codex/skills/hardcore-director
```

安装后可在任务中直接调用：

```text
使用 $hardcore-director，把这个故事做成可执行的分镜和 AI 视频提示词。
```

## 可选依赖

Seedance 2.5 / 即梦 2.5 的新功能与平台专用语法由独立 Skill 维护：

- [hc-sd2-5-prompt-writer](https://github.com/jlam00-dev/hc-sd2-5-prompt-writer)

## 目录

```text
hardcore-director/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    └── *.md
```

主入口与路由位于 `SKILL.md`，完整方法参考保存在 `references/`。
