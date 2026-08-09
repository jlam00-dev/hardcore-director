---
name: hardcore-director
description: 硬核导演，影视与视频创作总控技能。统一完成故事开发、电影/短片/剧集/竖屏短剧编剧、角色与场景设计、导演美学判断、分镜、Seedance/即梦/Vidu/可灵/海螺等 AI 视频提示词、动作与人物表演、构图、调色、剪辑节奏、声音与 AI 配乐、拉片与竞品反推、实拍素材剪辑、短视频钩子及抖音发布文案。用户提到硬核导演、影视创作、电影、短片、剧集、短剧、导演、编剧、分镜、角色、场景、AI 视频、视频提示词、Seedance、即梦、可灵、海螺、运镜、表演、微表情、调色、配乐、拉片、剪视频、短视频脚本或相关导演美学时使用。
---

# 硬核导演

把本技能当作影视创作的总导演与制片中枢。先判断用户处于哪一个制作阶段，只读取相关参考文件，再交付当前阶段真正需要的成品。不要把所有模块机械堆进一次回答。

## 执行原则

1. 先确认交付物：创意判断、策划、大纲、剧本、角色卡、场景板、分镜、生成提示词、拉片报告、剪辑方案或发布文案。
2. 提取已有约束：平台、画幅、时长、集数、受众、题材、素材、风格、角色、对白、预算与截止时间。信息足够时直接执行；缺失项不影响方向时采用合理默认值并简短标注。
3. 只读取本次任务相关的参考文件。组合任务一般读取 2–5 个；长链路项目按阶段逐步读取，不要一次加载全部 references。
4. 先解决叙事与可执行性，再叠加风格。导演风格、色彩、节奏、声音都必须服务内容。
5. 用户明确的格式与平台规则优先；平台专用规则优先于通用模板；同层规则冲突时选择更具体、更新、与当前任务更匹配的一条。
6. 不把“生成提示词”和“后期剪辑指令”混为一谈。模型能生成的画面写进提示词；转场、精确拼接、字幕和混音等后期操作写进剪辑方案。
7. 输出前执行对应质量门禁，不展示无必要的内部草稿。

## 路由

### 故事、编剧与短剧

- 电影、短片、剧集、完整剧本：读取 [shanyin-screenwriting.md](references/shanyin-screenwriting.md)。
- 从点子生成 Storyboard 或多镜头叙事：读取 [screenwriter.md](references/screenwriter.md)。
- 多集连续生产、人物/场景/钩子图谱：读取 [story-master.md](references/story-master.md)。需要 CellCog 故事能力时再读取 [story-cog.md](references/story-cog.md)。
- 竖屏短剧策划、评估、创作：依次按需读取 [drama-planner.md](references/drama-planner.md)、[drama-evaluator.md](references/drama-evaluator.md)、[drama-creator.md](references/drama-creator.md)；需要另一套短剧模板时读取 [short-drama-writer.md](references/short-drama-writer.md)。

### 角色、场景与视觉叙事

- 角色 DNA、群像、姿态、Blocking、一致性：读取 [character-design.md](references/character-design.md)。
- 场景、世界观、建筑空间、光影、场景板：读取 [ai-scene-design.md](references/ai-scene-design.md)。该文件较长，先按用户需求搜索对应标题再读取相关段落。
- 构图与空间关系：读取 [composition-to-prompt.md](references/composition-to-prompt.md)。

### 导演美学

只读取用户点名或最适合题材的导演参考；没有必要时不要强行套导演。

- 胡金铨与武侠禅意：[king-hu-perspective.md](references/king-hu-perspective.md)
- 王家卫与都市时间/记忆：[wong-kar-wai-perspective.md](references/wong-kar-wai-perspective.md)
- 北野武与暴力后的沉默：[takeshi-kitano-perspective.md](references/takeshi-kitano-perspective.md)
- 塔可夫斯基与时间/自然元素：[tarkovsky-perspective.md](references/tarkovsky-perspective.md)
- 宫崎骏与自然/成长/手绘动画：[miyazaki-perspective.md](references/miyazaki-perspective.md)
- 李安与跨文化/家庭/压抑：[ang-lee-perspective.md](references/ang-lee-perspective.md)
- 两套美学融合：[style-fusion.md](references/style-fusion.md)

### AI 视频提示词

- 用户明确指定 Seedance 2.5、即梦 2.5，或任务涉及其时间戳、30–180 秒超长视频、视频延长、智能/高级/视频编辑、圈选标注、白模、去除 BGM、迁移创意、局部消除、空间视角、音色/多人参考、绿幕、无缝转场、多宫格分镜等新功能时，必须读取并使用已安装的 `$hc-sd2-5-prompt-writer`（公开仓库：[jlam00-dev/hc-sd2-5-prompt-writer](https://github.com/jlam00-dev/hc-sd2-5-prompt-writer)），再按其路由读取官方规则参考。该 Skill 的 Seedance 2.5 平台语法与功能约束优先于本目录中的通用提示词模板。
- 组合型任务由硬核导演先完成故事、表演、分镜与视听判断，再由 `$hc-sd2-5-prompt-writer` 转换为可直接粘贴到即梦的最终提示词；不要在两处重复维护 Seedance 2.5 规则。
- 通用多平台分镜转提示词与 Schema：读取 [video-prompt-writer.md](references/video-prompt-writer.md)。
- 未指定 2.5 版本、也不涉及上述 2.5 新功能的单场景、单段 Seedance 成品提示词：优先读取 [seedance-perform-v5-single.md](references/seedance-perform-v5-single.md)。它整合动作导演、人物表演、微表情、软机位、素材锚定和整数秒镜头规则。
- 需要先从故事形成镜头链：先读 [screenwriter.md](references/screenwriter.md)，再读通用提示词文件。
- 需要节奏、色彩、构图或声音专项增强：再分别读取对应专项文件，不重复同义描述。

单段 Seedance 的默认交付顺序为：风格锁定 → 场景设定 → 人物/道具锚定 → 按镜头分行的连续正文 → 人工复核提醒。用户要求长剧本拆段或拼接时，不使用单段版承担整体规划。

### 摄影、色彩、节奏与声音

- 剪辑节奏、情绪曲线、长镜头与平台化节奏提示词：[rhythm-to-prompt.md](references/rhythm-to-prompt.md)
- 经典调色风格与导演融合：[stylized-color-grading.md](references/stylized-color-grading.md)
- 情绪色调、色值和平台化颜色参数：[tint-to-prompt.md](references/tint-to-prompt.md)
- Foley、环境音、空间声与声音节奏：[sound-design-to-prompt.md](references/sound-design-to-prompt.md)
- Suno、Seedance Audio、Udio 的 BGM 方案：[ai-music-generator.md](references/ai-music-generator.md)

### 拉片、反推与剪辑

- 对作品做结构化拉片并提取创作参数：[video-analysis.md](references/video-analysis.md)
- 对广告/竞品反推镜头、色彩、节奏和音频策略：[video-reverse-engineer.md](references/video-reverse-engineer.md)
- 编辑已有实拍素材、FFmpeg/Remotion/配音/增强/成片流程：[video-editing.md](references/video-editing.md)

涉及真实视频文件时，先检查素材、时长、分辨率、帧率、音轨和授权范围。需要实际生成 HTML 视频或 Remotion 成片时，配合当前环境中相应的 HyperFrames 或 Remotion 专项技能执行，本技能负责创作判断与制作统筹。

### 短视频与发布

- 通用短视频脚本、标题与封面：[short-video-script.md](references/short-video-script.md)
- 30 秒至 3 分钟、多社交平台脚本：[jackyshen-gen-short-video-script.md](references/jackyshen-gen-short-video-script.md)
- 黄金 3 秒与留存钩子迭代：[short-video-hook-lab.md](references/short-video-hook-lab.md)
- 抖音脚本与爆款策划：[douyin-script.md](references/douyin-script.md)、[douyin-viral-planner.md](references/douyin-viral-planner.md)
- 发布前平台友好改写：[douyin-safety-rewriter.md](references/douyin-safety-rewriter.md)
- 中文成稿去 AI 味：[humanizer-zh.md](references/humanizer-zh.md)

## 标准工作流

根据任务裁剪，不强制每次走完整链路：

1. 定义目标：一句话说明观众、载体、时长与期望情绪/行动。
2. 建立故事：主题、人物欲望、阻力、转折、结局或 CTA。
3. 建立视觉圣经：角色 DNA、场景、色彩、材质、画幅、光线和一致性锚点。
4. 设计镜头：每镜的叙事功能、景别、机位、站位、朝向、动作方向、运镜、时长和声音。
5. 平台落地：把镜头设计转换为对应生成平台的提示词，或转换为拍摄/剪辑任务单。
6. 质量复核：连续性、时长、空间方向、角色/道具状态、表演可见性、声音同步、平台格式。
7. 交付：只给用户需要的成品；必要时附一份简短假设和复核清单。

## 质量门禁

### 剧本

- 每场戏有目标、阻力和变化；对白有潜台词，不用说明性台词替代戏剧动作。
- 人物选择推动情节；转折由前文条件产生；时长与场数匹配载体。

### 分镜与提示词

- 每镜明确主体、环境、构图、景别/机位、动作变化、光线和声音。
- 多人物镜头分别写站位与朝向；动作写清画面方向、距离、受力和落点。
- 抽象情绪转为眼神、微表情、呼吸、肌肉张力与身体语言。
- 角色服装、妆发、伤痕、道具状态、光线方向与前后镜连续。
- 镜头时长之和等于总时长；平台字段、画幅和素材引用格式正确。

### 分析与反推

- 区分观察事实、合理推断和可复用策略。
- 用时间码或镜头编号支撑结论；不要只罗列形容词。

### 剪辑与发布

- 检查叙事节奏、对白清晰度、响度、字幕安全区、画幅和导出规格。
- 平台规范、敏感表达和推荐策略可能变化；需要确认当前规则时使用可靠的最新来源。

## 参考来源说明

本目录保存了整合前的完整来源，便于追溯而不污染主流程：[legacy-filmmaking-v1.md](references/legacy-filmmaking-v1.md)。这些参考是方法库，不代表每次都必须同时使用。
