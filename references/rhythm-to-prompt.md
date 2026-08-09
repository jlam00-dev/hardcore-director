---
name: rhythm-to-prompt
description: |
  将剪辑节奏概念转化为AI视频可执行的提示词。覆盖快/正常/慢剪节奏、情绪曲线、导演风格节奏公式、长镜头分段策略。
  支持白梦客两条线的节奏参数（通用线/高定线），并提供平台化输出（Seedance/Vidu/Kling/海螺）。
  触发词：「节奏剪辑」「转提示词」「节奏公式」「快剪」「慢剪」「长镜头」「抽帧」「硬切」「留白」「情绪曲线」「节奏参数」。
---

# AI提示词:节奏剪辑转提示词

## TL;DR
```
剪辑节奏 → 节奏参数 → AI视频提示词
支持：快剪/正常剪/慢剪 + 导演风格节奏 + 情绪曲线
平台：Seedance / Vidu / Kling / 海螺
```

## 启动检查点

激活后先确认：
1. **剪辑类型**：快剪(1-3s/镜) / 正常剪(3-8s/镜) / 慢剪(8s+/镜) / 混合？
2. **风格线**：通用线 or 高定线？
3. **导演风格**：北野武 / 胡金铨 / 王家卫 / 李安 / 融合？
4. **目标平台**：Seedance / Vidu / Kling / 海螺？

> 四项确认后再选择节奏公式和输出模板。

---

## 一、节奏剪辑核心概念

### 1.1 三种基本剪辑节奏

| 类型 | 镜头时长 | 适用场景 | 情绪特征 |
|------|---------|---------|---------|
| **快剪** | 1-3秒/镜 | 追逐/动作/紧张升级/广告 | 高张力、肾上腺素、节奏感 |
| **正常剪** | 3-8秒/镜 | 叙事/对话/情感/品牌片 | 自然流畅、叙事清晰 |
| **慢剪** | 8秒+/镜 | 情绪/留白/仪式/高定广告 | 凝视、内省、诗意 |

### 1.2 情绪节奏曲线

```
蓄力型(先慢后快)：[0-30%]平稳 → [30-60%]微变 → [60-90%]加速 → [90-100%]爆发
爆发型(先静后惊)：[0-20%]沉默 → [20-40%]暗涌 → [40-70%]骤变 → [70-100%]释放
平推型(持续压迫)：[0-100%]均匀递增
消退型(渐行渐远)：[0-30%]高潮 → [30-70%]缓降 → [70-100%]余韵
```

### 1.3 分镜衔接类型

| 衔接 | 适用场景 | 视觉特征 |
|------|---------|---------|
| **硬切** | 情绪突变、下一个独立冲击 | 无过渡，直接跳切 |
| **叠化** | 情绪延续、时间流逝 | 淡入淡出，模糊过渡 |
| **续接** | 同一动作的连续 | 上一镜结尾=下一镜开头 |
| **跳切** | 时间压缩、回忆、强调 | 同场景同镜头突然剪 |
| **匹配切** | 动作呼应、视觉对仗 | 方向/形状/运动匹配 |

---

## 二、白梦客节奏配方

### 2.1 通用线节奏（故事/情绪/概念短片）

融合：胡金铨 + 王家卫 + 北野武 + 李安

| 节奏类型 | 比例 | 参数 |
|---------|------|------|
| **长镜头留白** | 70% | 10-30秒/镜，固定镜头或缓慢推拉 |
| **抽帧慢动作** | 20% | 抽掉1/3帧，24帧→16帧效果 |
| **硬切断刀** | 10% | 2-4帧暴力瞬间，干净利落 |

**AI提示词模板：**
```
[节奏] long take 70%, slow-motion step-printing 20%, hard cut 10%
[时长] 10-30s per shot
[运动] minimal camera movement, static hold, occasional slow push
[质感] film grain 0.2-0.3, slight under-exposure
```

### 2.2 高定线节奏（高端品牌广告）

融合：Apple + Chanel/Dior + 北野武 + 李安

| 节奏类型 | 比例 | 参数 |
|---------|------|------|
| **长镜头凝视** | 60% | 15-45秒/镜，固定凝视 |
| **静默留白** | 30% | 无对话、无音乐、纯环境音 |
| **偶尔快切** | 10% | 3-5秒/镜，打破沉默 |

**AI提示词模板：**
```
[节奏] long take gaze 60%, silence 30%, occasional quick cut 10%
[时长] 15-45s per shot, fixed camera
[运动] no camera movement, subject may move slowly
[质感] 16mm/35mm film, overexposed 1/3 stop, light grain
```

---

## 三、导演风格节奏公式

### 3.1 北野武节奏公式

```
静70% + 突然爆15% + 虚无15%
```

**核心**：漫才的"铺梗→炸梗"逻辑。长镜头蓄力，暴力瞬间2-4帧硬切，暴力后更长的沉默。

**AI提示词模板：**
```
北野武节奏, Beat Takeshi rhythm
static long take 10-30s → sudden cut 2-4 frames → post-violence silence 8-10s
blue-grey #2D323C, high contrast 1:8
no music, ambient sound only, hard cut
negative space 60%, fixed camera
```

**场景变体：**

| 场景 | 时长 | 节奏描述 | AI提示词关键词 |
|------|------|---------|---------------|
| 雨夜对峙 | 10-15s | 10秒固定蓄力→突然硬切黑场 | fixed camera 12s, sudden cut to black, no music |
| 海边虚无 | 15-25s | 远景固定，低云压海，沉默为主 | static camera 20s, grey-blue ocean, no dialogue |
| 暴力蓄力 | 8-12s | 高对比沉默，突然硬切 | high contrast 1:8, sudden silence, tension |
| 汽车内沉默 | 12-20s | 仪表盘微光，烟头，雨中沉默 | dashboard glow, cigarette, rain silence |

### 3.2 胡金铨节奏公式

```
慢70% + 禅定15% + 动作15%
```

**核心**：对峙(长)→爆发(短)→沉淀(长)。武侠不是"打"，是"动"，动是禅。

**AI提示词模板：**
```
胡金铨节奏, King Hu rhythm
slow tension 8s → brief action 2s → stillness 3s
earth tones, side-backlight 45°, morning mist
minimalist composition, foreground obstruction 60%
natural light, no music or minimal ambient
```

**场景变体：**

| 场景 | 时长 | 节奏描述 | AI提示词关键词 |
|------|------|---------|---------------|
| 竹林对峙 | 15-25s | 竹叶飘落，对峙蓄力，突然出剑 | bamboo forest, tension, slow breathing, sudden blade |
| 山林空镜 | 20-40s | 雾气流动，无人物，纯自然 | misty mountain, no figure, natural breathing rhythm |
| 寺庙静默 | 15-30s | 钟声回荡，空间感，禅意 | temple courtyard, incense smoke, spatial tension |

### 3.3 王家卫节奏公式

```
抽帧慢动作 + 时间碎片化
```

**核心**：每秒抽掉几帧，动作"断断续续"，观众与角色保持"距离"。

**AI提示词模板：**
```
王家卫节奏, Wong Kar-wai rhythm
step-printing, frames skipped for stutter effect
slow-motion at 0.5x speed, fragmented time
neon amber, low exposure, handheld slight shake
overexposed highlights, memory color grade
```

**场景变体：**

| 场景 | 时长 | 节奏描述 | AI提示词关键词 |
|------|------|---------|---------------|
| 街头错过 | 8-15s | 抽帧跟拍，人群穿越，慢动作 | step-printing, crowd passing, slow-motion 0.5x |
| 窗口孤独 | 10-20s | 固定镜头，雨夜，霓虹反射 | rain-soaked street, neon reflections, fixed camera 15s |
| 回忆过曝 | 5-10s | 过曝处理，色调失真，时间感 | overexposed, desaturated, memory texture |

### 3.4 李安节奏公式

```
内敛蓄力 + 仪式化动作
```

**核心**：东方内敛，动作是仪式不是功能。静默中的张力，爆发后的余韵。

**AI提示词模板：**
```
李安节奏, Ang Lee rhythm
restrained tension, slow build 70%
ceremonial action, brief release 20%
lingering aftermath, silence 10%
natural light, subtle color temperature shift
long take with gradual emotional escalation
```

---

## 四、节奏剪辑转AI提示词速查表

### 4.1 快剪节奏（1-3秒/镜）

**使用场景**：追逐、动作、紧张升级、广告片段、节奏卡点

**AI提示词参数：**
```
[节奏] fast cut, 1-3s per shot
[运动] handheld or quick pan, high energy
[声音] music beat sync, rhythm-driven
[转场] hard cut, jump cut
```

**正向提示词：**
```
fast-paced editing, quick cuts 1-3s, handheld camera
high energy, action sequence, music beat sync
sudden cut, dynamic movement, momentum
```

**负向提示词：**
```
slow motion, long take, static camera
soft lighting, romantic atmosphere, quiet
fixed frame, no movement, peaceful
```

**平台化输出示例（Seedance）：**
```
[00:00-00:03] 快切镜头A，手持跟拍，运动模糊，节奏感强
[00:03-00:06] 快切镜头B，低角度仰拍，主体占画面60%
[00:06-00:09] 硬切黑场，1秒静帧，然后切换
节奏：快剪1-3s/镜，手持晃动，音乐卡点
```

### 4.2 正常剪节奏（3-8秒/镜）

**使用场景**：叙事、对话、情感推进、品牌故事

**AI提示词参数：**
```
[节奏] normal cut, 3-8s per shot
[运动] slow push or static, cinematic
[声音] ambient + dialogue, natural rhythm
[转场] cross-dissolve or hard cut
```

**正向提示词：**
```
cinematic pacing, 3-8s per shot, slow push
natural dialogue rhythm, ambient sound
balanced composition, film grain
```

**负向提示词：**
```
rapid cut, jittery camera, fast-paced
chaotic, loud music, action overload
overly stylized, saturated colors
```

**平台化输出示例（Vidu）：**
```
Wong Kar-wai cinematic, normal pacing
[0-4s] establish space, slow dolly forward
[4-8s] mid-shot dialogue, static camera
earth tones, side-light, film grain texture
```

### 4.3 慢剪节奏（8秒+/镜）

**使用场景**：情绪、留白、仪式感、高定广告、诗意时刻

**AI提示词参数：**
```
[节奏] slow cut, 8s+ per shot, long take
[运动] static or very slow drift, meditative
[声音] silence or minimal ambient, no music
[转场] dissolve or no cut (hold)
```

**正向提示词：**
```
long take 10-30s, static camera, minimalist
silence, negative space, meditative rhythm
overexposed 1/3 stop, light grain, stillness
no camera movement, natural breathing pace
```

**负向提示词：**
```
fast cut, handheld shake, quick pace
loud music, dialogue-heavy, busy frame
bright saturated colors, action sequence
camera movement, zoom, pan, tilt
```

**平台化输出示例（Kling）：**
```
--duration 45
--motion MINIMAL (fixed camera)
--pace SLOW (8-15s per shot)
--silence 70%
negative space 60%, long take
earth grey + cold white palette
ambient: rain, 20%
```

---

## 五、情绪曲线转提示词

### 5.1 蓄力型曲线

```
[0-30%] 平稳建立 → [30-60%] 微变积累 → [60-90%] 加速 → [90-100%] 爆发
```

**AI提示词模板：**
```
[情绪曲线] 蓄力型: 平静 → 暗涌 → 加速 → 爆发
[节奏] 前30% slow static → 中段 gradually increase → 后10% sudden release
[视觉] 色调从冷→暖，光从弱→强，主体从静止→剧烈运动
```

**示例（5秒蓄力爆发）：**
```
[0-1.5s] 静止建立，固定镜头，环境音低沉
[1.5-3s] 微变，暗处有动静，色调开始转暖
[3-4.5s] 加速，主体开始动作，运动模糊出现
[4.5-5s] 爆发，色彩饱和，亮度骤升
```

### 5.2 爆发型曲线

```
[0-20%] 沉默 → [20-40%] 暗涌 → [40-70%] 骤变 → [70-100%] 释放
```

**AI提示词模板：**
```
[情绪曲线] 爆发型: 沉默 → 暗涌 → 骤变 → 释放
[节奏] 前20% near-silence → 中段 building tension → 后30% sudden release
[视觉] 纯黑→微光→对比爆发→余韵
```

**示例（北野武式爆发）：**
```
[0-2s] 沉默，纯黑，只有呼吸声
[2-4s] 暗涌，光源微亮，色调转蓝灰
[4-7s] 骤变，高对比，主体动作
[7-10s] 释放，然后是比爆发更长的沉默
```

### 5.3 消退型曲线

```
[0-30%] 高潮 → [30-70%] 缓降 → [70-100%] 余韵
```

**AI提示词模板：**
```
[情绪曲线] 消退型: 高潮 → 缓降 → 余韵
[节奏] 前30% peak → 中段 gradual decay → 后30% lingering silence
[视觉] 亮度/饱和度逐渐降低，运动逐渐静止
```

---

## 六、长镜头分段生成策略

超过15秒的镜头建议分段生成，每段5-8秒为宜。

### 6.1 分段原则

```
原始需求：20秒完整镜头
分段策略：
  分镜01：0-5s（建立场景+引入）
  分镜02：5-10s（主体动作）
  分镜03：10-15s（高潮/冲突）
  分镜04：15-20s（收尾/落位）
```

### 6.2 分段衔接规则

| 衔接方式 | 分镜01结尾 | 分镜02开头 | 效果 |
|---------|-----------|-----------|------|
| **续接** | 手抬起 | 手到达顶点 | 动作连续 |
| **叠化** | 火焰燃烧 | 火焰更大 | 时间流逝 |
| **硬切** | 爆炸瞬间 | 平静场景 | 情绪独立 |

### 6.3 保持一致性的技巧

```
每段使用相同STYLE参数：
STYLE: 北野武 + ARRI Alexa Mini LF + F002质感

每段首尾留承接点：
分镜01结尾：蓝焰喷涌 → 分镜02开头：蓝焰吞没车身

时序标记在每段提示词开头：
[00:00-00:05] / [00:05-00:10] / [00:10-00:15]
```

---

## 七、平台化输出模板

### 7.1 Seedance（即梦）

```json
{
  "output": {
    "platform": "seedance",
    "language": "中文",
    "format": "timestamp_segmented"
  }
}
```

**模板：**
```
[节奏类型]，[风格线]，[导演风格]，
[00:00-00:05] [分镜1描述，含节奏参数]
[00:05-00:10] [分镜2描述，含节奏参数]
...
[节奏公式] long take X%, slow-motion X%, hard cut X%
[时长] Xs per shot, total Ys
```

### 7.2 Vidu

```json
{
  "output": {
    "platform": "vidu",
    "language": "中英混合",
    "format": "structured"
  }
}
```

**模板：**
```
[导演风格] cinematic, [节奏类型] pacing
[0-4s] slow push, static camera, earth tones
[4-8s] mid-shot dialogue, natural light
[节奏公式] long take 60%, silence 30%, quick cut 10%
```

### 7.3 Kling（可灵）

```json
{
  "output": {
    "platform": "kling",
    "language": "英文为主",
    "format": "params"
  }
}
```

**模板：**
```
[场景描述], [导演风格] rhythm
--pace SLOW (10-15s per shot)
--motion MINIMAL (fixed camera)
--rhythm long_take 70%, slow_motion 20%, hard_cut 10%
--silence 60%, ambient 30%, music 10%
earth tones 50%, teal 20%, amber neon 20%
--style cinematic --texture 35mm grain
```

### 7.4 海螺

```json
{
  "output": {
    "platform": "hairui",
    "language": "中文",
    "format": "dynamic_description"
  }
}
```

**模板：**
```
[场景]，动态预期：
节奏：长镜头留白70%，缓慢推近，凝视
运动：主体缓慢移动，呼吸感，无剧烈动作
时长：10-15s
氛围：沉默为主，环境音极简，留白
```

---

## 八、实用场景速查

| 场景 | 推荐节奏 | 导演风格 | AI提示词核心 |
|------|---------|---------|------------|
| **雨夜对峙** | 正常→爆发 | 北野武 | fixed 15s → hard cut → silence 10s |
| **追逐动作** | 快剪 | 北野武+王家卫 | fast cuts 1-2s, handheld, step-printing |
| **情感告白** | 慢剪 | 李安+王家卫 | long take 20s, slow push, silence |
| **品牌高定** | 极慢剪 | 胡金铨+北野武 | static 30s+, negative space 60%, minimal |
| **都市孤独** | 正常+抽帧 | 王家卫 | step-printing, neon, low exposure |
| **武侠动作** | 正常剪+爆发 | 胡金铨 | slow tension → brief action → stillness |
| **诗意留白** | 极慢剪 | 胡金铨+塔可夫斯基 | static 40s+, no cut, natural elements |

---

## 九、质量检查清单

**生成前检查：**
```
□ 节奏类型是否匹配场景？（快剪≠慢剪场景）
□ 导演风格节奏公式是否正确？（北野武≠王家卫）
□ 时长是否符合平台限制？（Seedance≤15s单次）
□ 衔接方式是否适合情绪？（硬切≠叠化）
□ 长镜头是否分段？（超过15s建议分段）
□ 声音策略是否匹配画面节奏？（上升加layer，高峰留白）
```

**生成后评估：**
```
□ 节奏是否符合预期？（快剪不拖沓，慢剪不急躁）
□ 情绪曲线是否完整？（有蓄力，有爆发，有余韵）
□ 导演风格是否明确？（北野武的沉默，胡金铨的禅意）
□ 衔接是否流畅？（无跳帧，无断裂）
□ 是否有塑料拼贴感？（节奏自然，无人工痕迹）
```

---

## 十、案例：节奏剪辑转提示词完整示例

### 场景：北野武式雨夜对峙（10秒）

**Step 1: 确定节奏参数**
- 类型：爆发型（沉默蓄力→突然爆发→更长沉默）
- 导演风格：北野武
- 节奏公式：静70% + 突然爆15% + 虚无15%

**Step 2: 生成AI提示词**

```
Seedance平台：
北野武节奏，雨夜东京街道，爆发型情绪曲线

[00:00-00:07] 固定长镜头蓄力，两人在街道两端对立，各占画面15%，
             中间70%为负空间。雨滴落下，霓虹灯在水面反射。
             蓝灰色调#2D323C，高对比1:8，无音乐，只有雨声。
             香烟微光在黑暗中明灭。

[00:07-00:08] 突然硬切。一人倒下，另一人静止。
             2帧暴力瞬间，黑场。

[00:08-00:10] 暴力后的虚无。更长的沉默。
             固定镜头，雨继续下，霓虹继续亮，
             但人物已不再动。静默比暴力更重。

节奏：静70%(7s) + 突然爆15%(1s) + 虚无15%(2s)
色调：蓝灰#2D323C，冷白#C8CDD7，饱和度极低
构图：负空间60%+，主体各占15%
声音：无音乐，雨声+沉默
```

---

> 本技能整合自白梦客知识库：导演节奏公式 + 情绪曲线理论 + 平台化输出规范
> 相关技能：`video-prompt-writer`（完整提示词结构）、`video-prompt-schema`（Schema格式）、导演视角技能组
