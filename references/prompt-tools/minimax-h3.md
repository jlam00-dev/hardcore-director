# MiniMax H3 提示词工具

本工具按 MiniMax 官方 H3 Prompt Writing Skill 与官方指南组织输出。H3 提示词正文用英文；对白、歌词和画面文字保留原语言。不要翻译或改写用户给定的台词。

官方资料：

- https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing
- https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md
- https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md

## 选择模式

- **T2VA**：纯文字生成完整音画时间线。
- **I2VA**：Picture 1 是 0.00 秒首帧，从它向前发展。
- **FL2VA**：Picture 1 是首帧，Picture 2 是尾帧，写连续到达路径。
- **L2VA**：Picture 1 是尾帧，反推合理开场并在结尾落到它。
- **Ref2VA**：图片、视频、主体或音频承担复用、编辑、延长、结构或声音关系。

## 基础模式固定结构

T2VA 直接输出三个字段：

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

I2VA 在三个字段前增加以下一行和一个空行：

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

FL2VA：

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
```

L2VA：

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```

将 `N` 换成真实尾镜编号，将 `S.SS` 换成两位小数的有效时长。第一镜不写时间；后续镜头写成 `[Shot 2] At 00:03.500, ...`，时间严格递增且位于总时长内。

## Ref2VA 固定结构

按以下顺序输出，不增删字段：

```text
subject_definitions:
...

summary:
...

retention_analysis:
...

detailed_description:
...

overall_soundscape:
...

non_diegetic_music:
...
```

标签规则：

- `<Subject N>`：从素材抽象出的可复用人物、物体、环境、服装、动作、表演或风格；
- `<Picture N>`：实际首帧、关键帧、尾帧或分镜构图锚点；
- `<Video N>`：被编辑/延长的源视频，或整段镜头运动、剪辑和时间结构；
- `<Audio N>`：被复制或参考的音频信号。

可见素材在 `retention_analysis` 中只用：`fully_preserved`、`partially_preserved`、`attribute_transfer`、`weak_reference`。音频只用：`fully_copy`、`partially_copy`、`reference`、`weak_reference`。

## 音画规则

- 发声者按首次发声顺序使用稳定 ID `(S1)`、`(S2)`；静默角色不编号。
- 台词格式：`<d>[Language] 用户原文</d>`；旁白写 `says in an off-screen voiceover`，并说明画面内对应人物嘴唇保持闭合。
- `overall_soundscape` 用 1–4 句英文概括环境声、动作声和非语言人声；不重复对白、演唱和剧情内音乐。
- `non_diegetic_music` 用 1–3 句英文写观众听见、角色听不见的配乐；无配乐写 `N/A`。
- 完全静音时两个声音字段都写 `N/A`，且其他字段不得再出现任何声音事件。

## 镜头和关键帧

- 镜头运动写成自然动作，必要时同时说明类型、幅度和速度；
- I2VA：首帧锚定 → 动作开始 → 连续发展 → 结果/反应；
- FL2VA：优先单镜头，写出缩小首尾差异的中间状态；
- L2VA：合理前态 → 明确动作路径 → 最后逐项收敛到尾帧；
- 切镜只用于引入新的主体、空间、状态、视点或时间信息，轻微角度变化用运镜完成。

## 最终检查

- 字段名、顺序、空行、标签和时间格式完全一致；
- 除官方对齐句和镜头时间外，模型名、分辨率、画幅、API 参数不写进正文；
- 每个独立标签有且只有一个定义、一个保留分析条目，并在真正生效的镜头中出现；
- 台词、歌词和画面文字保持原语言与原文；
- 参考表演与目标身份分开映射，多人说话归属不交换；
- 总时长不超过 H3 官方当前支持的 4–15 秒范围，参数变更时先查官方最新资料。
