---
name: sound-design-to-prompt
description: |
  将声音设计概念转化为AI视频生成提示词。覆盖音效(Foley)、环境音、环境音层、声音质感、空间感、声音节奏。
  配合 ai-music-generator（音乐）和 rhythm-to-prompt（视觉节奏）使用。
  触发词：「声音设计」「音效」「环境音」「Foley」「声音质感」「AI配音」「音效提示词」「sound effects」「ambient」。
version: v1.0
created: 2026-04-20
updated: 2026-04-20
source: 白梦客知识库 · 声音组研究整合
---

# Sound Design → AI Video Prompt

将专业声音设计转化为AI视频生成提示词。

## 核心工作流

```
声音概念 → 声音层解析 → AI提示词生成 → 平台适配
     ↓
[主体层] + [环境音层] + [质感层] + [空间层]
```

## TL;DR

```
声音设计提示词 = 音效层(20%) + 环境音层(40%) + 质感层(20%) + 空间层(20%)
正向：具体声音行为 + 动态变化 + 情绪关键词
负向：无声/过度饱和/失真/不自然
平台：Seedance/Vidu/Kling/海螺（注意平台音频支持差异）
```

---

## 一、声音设计核心概念

### 1.1 声音层架构

专业声音设计由多层声音叠加：

| 声音层 | 占比 | 定义 | AI提示词关键词 |
|--------|------|------|---------------|
| **主体音** | 10-20% | 角色动作、对白 | footsteps, breathing, clothing rustle |
| **Foley** | 15-25% | 现场真实感 | surface textures, object interactions |
| **环境音(Ambience)** | 35-50% | 场景背景氛围 | city hum, nature, weather, crowd |
| **声音质感(Textural)** | 10-20% | 情绪渲染 | drone, pulse, tension layers |
| **空间混响** | 5-15% | 空间大小感 | reverb, echo, distance |

### 1.2 声音层 → AI提示词映射

```
主体层：具体动作声音（脚步声、门声、物体碰撞）
Foley层：材质交互（布料、水、金属、木质、玻璃）
环境音层：场景背景（城市、自然、室内、特定场所）
质感层：情绪底噪（紧张Drone、温暖Pad、压迫低频）
空间层：距离感和混响（近/远/封闭/开阔）
```

---

## 二、白梦客声音美学系统

### 2.1 通用线声音配方

融合：胡金铨 + 王家卫 + 北野武 + 李安

| 声音维度 | 配方 | 参数 |
|----------|------|------|
| **主色调** | 自然+都市 | 70%自然环境音 + 30%都市质感 |
| **环境音** | 呼吸感 | 风声、水流、远雷、呼吸 |
| **Foley** | 克制的真实 | 极轻脚步声、衣物摩擦 |
| **质感层** | 霓虹低鸣 | 远处霓虹灯嗡鸣、电力低频 |
| **节奏** | 留白优先 | 70%无声 + 30%轻声音 |

**AI提示词模板：**
```
[声音] natural ambience 70%, urban undertone 30%
[环境] subtle wind, distant water, breathing space
[Foley] minimal footsteps, clothing rustle
[质感] neon hum, electric tension drone
[节奏] silence 70%, light ambient 30%
```

### 2.2 高定线声音配方

融合：Apple + Chanel/Dior + 北野武 + 李安

| 声音维度 | 配方 | 参数 |
|----------|------|------|
| **主色调** | 极简留白 | 90%无声 + 10%必要音效 |
| **环境音** | 纯净空间 | 极轻空调声、远处钟声 |
| **Foley** | 优雅克制 | 产品触碰声、纸张翻动 |
| **质感层** | 丝绸质感 | 无杂质的空气感 |
| **节奏** | 极致沉默 | 95%静默 + 5%核心声音 |

**AI提示词模板：**
```
[声音] extreme silence 90%, essential sound 10%
[环境] pure space, distant clock, air presence
[Foley] product touch, paper rustle, silk movement
[质感] clean air, absence of noise
[节奏] 95% mute, 5% pristine sound
```

---

## 三、声音设计转AI提示词速查表

### 3.1 环境音层（Ambience）

| 环境类型 | 声音描述 | AI提示词关键词 |
|----------|----------|---------------|
| **城市雨夜** | 霓虹雨声、远处车流、积水反射 | rain on asphalt, distant traffic, neon reflections |
| **山林空镜** | 竹林风声、鸟鸣、溪流 | bamboo wind, birds, distant stream |
| **都市街道** | 人群嘈杂、远处音乐、汽车声 | city crowd, distant music, car horns |
| **室内空间** | 空调声、时钟滴答、纸张翻动 | AC hum, clock tick, paper rustle |
| **海边/码头** | 海浪、风声、远处汽笛 | ocean waves, seagulls, distant horn |
| **废弃空间** | 回声、水滴、风吹玻璃 | echo, water drip, window rattle |
| **寺庙/古建** | 钟声、回音、焚香氛围 | temple bell, incense echo, sacred silence |
| **夜间车内** | 引擎低鸣、雨点敲打、仪表盘微光 | engine hum, rain on roof, dashboard glow |

**AI提示词示例：**
```
[环境音] urban night rain, neon-lit street
[声音层] rain 40%, distant traffic 20%, neon hum 15%, wind 10%
[质感] wet asphalt reflection, electric tension
[节奏] continuous ambient, no sudden changes
```

### 3.2 Foley音效层

| 动作类型 | 声音描述 | AI提示词关键词 |
|----------|----------|---------------|
| **脚步** | 木地板、水泥、泥土、草地 | footsteps on wood, concrete, mud, grass |
| **门** | 开门吱呀、关门闷响、锁舌声 | door creak, door slam, lock click |
| **玻璃** | 破碎清脆、敲击叮当、裂纹蔓延 | glass shatter, glass tap, crack spread |
| **布料** | 丝绸摩擦、皮夹克、棉麻质感 | silk rustle, leather creak, cotton movement |
| **纸张** | 翻页轻响、信封撕开、文件掉落 | page turn, envelope tear, paper drop |
| **金属** | 钥匙碰撞、武器出鞘、链条声 | key jingle, blade drawn, chain rattle |
| **水** | 滴落、泼溅、浸泡、流淌 | water drip, splash, soak, flow |
| **火** | 噼啪燃烧、火焰蔓延、灭火嘶嘶 | crackle, whoosh, sizzle |

**AI提示词示例：**
```
[Foley] footsteps on wet concrete, leather jacket movement
[声音] subtle clothing rustle, heavy breathing, rain patter
[质感] close-mic'd realistic, intimate perspective
[节奏] sound on action, silent pauses between
```

### 3.3 声音质感层（Textural Sound）

| 情绪质感 | 声音描述 | AI提示词关键词 |
|----------|----------|---------------|
| **紧张** | 低频Drone、高频警报、金属摩擦 | tension drone, high frequency alert, metal scrape |
| **温暖** | 弦乐底噪、模拟合成、柔软Pad | string undertone, analog warmth, soft pad |
| **悬疑** | 不定频率、电子脉冲、黑暗低鸣 | uncertain frequency, electronic pulse, dark hum |
| **浪漫** | 钢琴泛音、丝绒质感、空间混响 | piano harmonics, velvet texture, reverb wash |
| **压迫** | 次低频振动、沉闷心跳、厚重感 | sub-bass rumble, heartbeat, weight |
| **虚无** | 极低音量、电子白噪音、空灵 | near-silence, electronic white noise, ethereal |
| **怀旧** | 黑胶噪音、模拟失真、温暖底噪 | vinyl crackle, analog distortion, warm noise |

**AI提示词示例：**
```
[质感层] tension drone 20%, uncertainty pulse 10%
[情绪] suspenseful, impending, dark atmosphere
[声音] low-frequency hum, metallic tension, breathing space
[节奏] gradual intensity build, release on cut
```

### 3.4 空间层（Reverb & Distance）

| 空间类型 | 声音特征 | AI提示词关键词 |
|----------|----------|---------------|
| **开阔户外** | 自然混响、声音散射、距离感强 | natural reverb, open space, distant sounds |
| **封闭室内** | 干涩无混响、声音聚集、近距离感 | dry close, enclosed, intimate |
| **大型空间** | 深度混响、回声延迟、气场感 | deep reverb, echo delay, cathedral space |
| **金属空间** | 反射尖锐、混响金属感、回声清晰 | metallic reverb, sharp reflection, clear echo |
| **布料空间** | 声音吸收、无回声、沉闷感 | sound absorbed, no echo, muffled |
| **水下感** | 低频传递延迟、模糊、压迫 | low-frequency delay, muffled, pressure |

**AI提示词示例：**
```
[空间] enclosed concrete room, dry close-mic perspective
[混响] minimal reverb 0.3s, intimate distance
[声音] footsteps close, breathing audible, footsteps dominate
[质感] direct sound, no environmental wash
```

---

## 四、导演风格声音配方

### 4.1 胡金铨声音公式

```
自然为本 + 禅意留白 + 动作音效极简化
```

**声音核心**：风声、水声、呼吸声。动作无声或极轻。禅意通过空间感表达。

**正向提示词：**
```
King Hu sound, natural ambience dominant
wind through bamboo, distant stream, bird call
minimal Foley, action near-silent
temple space reverb, sacred emptiness
silence 60%, natural sound 30%, occasional bell 10%
```

**负向提示词：**
```
electronic music, urban noise, dialogue-heavy
action sounds amplified, dramatic music score
modern city ambience, car sounds, crowd noise
synthesizer, artificial textures
```

**场景变体：**

| 场景 | 声音描述 | AI提示词关键词 |
|------|----------|---------------|
| 竹林对峙 | 竹叶风声、远处溪流、呼吸 | bamboo rustle, distant water, breath tension |
| 寺庙禅修 | 焚香气息、钟声余韵、空间感 | incense, temple bell decay, spatial echo |
| 剑斗瞬间 | 金属破空、风声、落地沉默 | sword whoosh, wind, sudden silence |

### 4.2 王家卫声音公式

```
都市孤独 + 霓虹质感 + 抽帧视觉对应听觉碎片化
```

**声音核心**：都市底噪、霓虹灯嗡鸣、怀旧爵士、内心独白感。

**正向提示词：**
```
Wong Kar-wai sound, urban neon ambience
rain on window, distant jazz, neon hum
retro textures, vinyl warmth, city loneliness
handheld perspective audio, intimate breathing
nostalgic 60%, electric undertone 30%, silence 10%
```

**负向提示词：**
```
natural rural sound, folk music, peaceful ambient
modern pop score, upbeat rhythm
clean modern audio, no texture
outdoor open space, forest sound
```

**场景变体：**

| 场景 | 声音描述 | AI提示词关键词 |
|------|----------|---------------|
| 雨夜窗口 | 雨打玻璃、霓虹反射、内心呼吸 | rain on glass, neon glow, breath close-mic |
| 60年代餐厅 | 老式爵士、餐具碰撞、时光质感 | vintage jazz, silverware clink, era texture |
| 街头错过 | 嘈杂人群、脚步匆匆、都市低频 | crowd murmur, hurried footsteps, urban bass |

### 4.3 北野武声音公式

```
暴力与沉默 + 极端对比 + 日常噪音真实感
```

**声音核心**：沉默是常态。暴力瞬间2-4帧，声音爆发，然后是更长的沉默。日常声音（海浪、风声、收音机）是情绪锚点。

**正向提示词：**
```
Takeshi Kitano sound, extreme silence 70%
sudden impact sound 5%, post-violence silence 25%
ocean waves, wind through room, radio static
tension build through absence, not addition
realistic everyday sounds, nothing artificial
```

**负向提示词：**
```
constant background music, score throughout
dramatic orchestral hit on violence
emotional music telling how to feel
peaceful ambient, no tension
clean perfect audio, no imperfection
```

**场景变体：**

| 场景 | 声音描述 | AI提示词关键词 |
|------|----------|---------------|
| 暴力瞬间 | 短促撞击声、沉默、心跳 | impact 2 frames, silence 8s, heartbeat fade |
| 海边虚无 | 海浪循环、风声、无对话 | ocean waves loop, wind, no dialogue |
| 车内沉默 | 收音机低鸣、引擎、仪表盘滴答 | car radio murmur, engine idle, dashboard tick |

### 4.4 李安声音公式

```
内敛蓄力 + 东方留白 + 声音情绪化处理
```

**声音核心**：声音不是同步的。是延迟的情绪反应。静默中的张力用声音质感层（而非音量）表达。

**正向提示词：**
```
Ang Lee sound, restrained emotional tension
ambient undertone, subtle drone, unspoken feeling
silence with presence, tension in negative space
natural sound 50%, textural tension 30%, silence 20%
ceremonial pacing, sound delayed from action
```

**负向提示词：**
```
explosive sound effects, action audio loud
constant music bed, no breathing room
Western dramatic score, obvious emotional cues
modern fast-paced audio, no contemplative space
```

**场景变体：**

| 场景 | 声音描述 | AI提示词关键词 |
|------|----------|---------------|
| 情感爆发前 | 呼吸声放大、环境音退后、内心震动 | breath amplified, ambience recedes, inner tremor |
| 仪式化动作 | 动作音效延迟、质感层渐入 | sound delayed 0.5s, texture fades in |
| 对话留白 | 沉默比话语重、声音暗示情绪 | silence heavier than dialogue, sound implies |

---

## 五、声音设计 × AI视频生成平台

### 5.1 平台音频能力对比

| 平台 | 音频支持 | 声音生成 | 局限性 |
|------|----------|----------|--------|
| **Seedance** | 部分支持 | 无 | 主要生成视频，音频需后期 |
| **Vidu** | 部分支持 | 无 | 视频生成为主 |
| **Kling** | 有限 | 无 | 主要视觉 |
| **海螺** | 有限 | 无 | 短片段为主 |
| **Sora** | 无 | 无 | 纯视觉 |
| **Runway** | Gen-3 有声 | 有 | 音频生成能力有限 |

**策略**：
1. AI视频生成时在提示词中标注**声音期望**（作为后期参考）
2. 声音设计由 sound-designer 在后期独立处理
3. AI音乐由 ai-music-generator 生成

### 5.2 AI视频提示词中的声音标注

在视觉提示词末尾添加声音标注：

```
[视频主体描述]
...
[声音标注]
sound: [环境音描述], [Foley描述], [质感层描述]
rhythm: [声音节奏], [留白比例]
reference: [参考音乐/声音设计风格]
```

**示例 - Seedance完整提示词：**
```
雨夜东京街头，霓虹灯反射在水面上，孤独男人站在街角
[声音] urban rain night, distant traffic, neon hum
[Foley] wet footsteps on concrete, rain patter on jacket
[质感] electric tension drone, isolation undertone
[节奏] silence 60%, ambient 30%, subtle sound 10%
[参考] Wong Kar-wai rain scene sound design
```

---

## 六、声音节奏与视觉节奏同步

### 6.1 声音节奏类型

| 节奏类型 | 声音特征 | 视觉对应 |
|----------|----------|----------|
| **心跳型** | 低频脉冲，均匀节奏 | 固定长镜头，凝视 |
| **呼吸型** | 起伏感，近似呼吸节奏 | 缓慢推拉，缓入缓出 |
| **脉冲型** | 规则电子节拍，律动感 | 快剪、动作、节奏卡点 |
| **流动型** | 连续环境音，无明显节奏 | 横移、跟拍、长镜头 |
| **爆发型** | 突然大声→渐弱 | 快切→长镜头留白 |
| **静止型** | 几乎无声，留白 | 固定机位，极简构图 |

### 6.2 声画同步提示词模板

```
[视觉节奏] → [声音节奏] → [AI提示词]

长镜头凝视 → 呼吸型 → ambient breathing rhythm, wind pulse
快剪节奏 → 脉冲型 → beat-sync footsteps, rhythm cut sound
情绪爆发 → 爆发型 → impact sound → silence decay
极简留白 → 静止型 → near-silence, occasional single tone
```

### 6.3 Beat-Match 声音提示词

当视觉需要与音乐节拍同步时：

```
[00:00-00:03] Downbeat脚步声，声音爆发
[00:03-00:06] Snare切刀声，视觉切换点
[00:06-00:09] 音乐留白，呼吸空间，声音渐隐
[00:09-00:12] Build-up，质感层渐入，视觉推进
[00:12-00:15] Drop爆发，视觉快切，声音释放
```

---

## 七、专业声音设计参数表

### 7.1 响度与动态

| 参数 | 定义 | AI提示词关键词 |
|------|------|---------------|
| **LUFS** | 感知响度单位 | loudness standard -14 LUFS |
| **动态范围** | 最响与最轻的比值 | dynamic range, compression |
| **SPL** | 声压级，分贝 | decibel level, ambient noise |
| **信噪比** | 信号与噪声比 | clean audio, high SNR |

### 7.2 频率分布

| 频段 | 频率范围 | 声音特征 | AI提示词 |
|------|----------|----------|----------|
| **Sub-Bass** | 20-60Hz | 震撼、压迫、心跳 | sub-bass rumble, deep impact |
| **Bass** | 60-250Hz | 重量感、厚实 | bass weight, low-end warmth |
| **Low-Mid** | 250-500Hz | 浑浊/清晰分界 | muddy/clean division |
| **Mid** | 500-2kHz | 清晰度、人声 | clarity, vocal presence |
| **Upper-Mid** | 2-4kHz | 临场感、亮度 | presence, brightness |
| **High** | 4-20kHz | 空气感、细节 | air, sparkle, detail |

### 7.3 声音质感关键词

```
【材质类】
metallic, wooden, glass, fabric, water, concrete, organic, synthetic
【温度类】
warm, cold, cool, hot, sterile, humid, dry
【形态类】
dense, sparse, layered, transparent, opaque, textured, smooth
【情绪类】
tense, relaxed, nostalgic, futuristic, ominous, ethereal
```

---

## 八、场景声音设计速查

### 8.1 雨夜系列

| 场景 | 环境音 | Foley | 质感层 | 节奏 |
|------|--------|-------|--------|------|
| 雨夜街头 | 雨打路面、车经过 | 脚步、伞撑开 | 霓虹低鸣 | 留白70% |
| 雨夜窗边 | 雨打玻璃 | 呼吸、衣物摩擦 | 室内温暖底噪 | 室内干燥 |
| 雨夜车内 | 雨点敲顶、刷雨 | 方向盘、转弯 | 引擎低鸣 | 封闭感 |

**AI提示词模板 - 雨夜街头：**
```
[环境音] heavy rain 40%, distant traffic 15%, neon reflection buzz 20%
[Foley] wet footsteps on asphalt, rain patter on umbrella
[质感] electric tension, isolation undertone
[节奏] ambient continuous, no sudden changes
[参考] Blade Runner rain scene sound, Wong Kar-wai rain intimacy
```

### 8.2 自然系列

| 场景 | 环境音 | Foley | 质感层 | 节奏 |
|------|--------|-------|--------|------|
| 山林空镜 | 风声、鸟鸣、流水 | 无 | 空间感 | 极静 |
| 竹林剑斗 | 风穿竹叶 | 剑声、布衣 | 金属张力 | 爆发 |
| 海边日落 | 海浪、风 | 脚印、贝壳 | 开阔虚无 | 呼吸 |

### 8.3 都市系列

| 场景 | 环境音 | Foley | 质感层 | 节奏 |
|------|--------|-------|--------|------|
| 地铁站台 | 报站、远鸣 | 脚步、回声 | 金属空间 | 脉冲 |
| 便利店 | 制冷机、门铃 | 商品声、找零 | 荧光灯嗡鸣 | 日常 |
| 天台夜景 | 远城轰鸣、风 | 脚步、烟点燃 | 开阔与压迫 | 独处 |

### 8.4 室内系列

| 场景 | 环境音 | Foley | 质感层 | 节奏 |
|------|--------|-------|--------|------|
| 茶室 | 焚香、钟声 | 茶杯碰撞、茶水 | 木质共鸣 | 禅定 |
| 深夜办公室 | 空调、打字 | 键盘、纸张 | 荧光灯感 | 孤独 |
| 复古客厅 | 唱片机、挂钟 | 玻璃碰撞、笑声 | 暖色质感 | 怀旧 |

---

## 九、质量检查清单

### 生成前检查
```
□ 声音层次是否清晰？（主体/Foley/环境/质感/空间）
□ 是否匹配白梦客美学线？（通用线/高定线）
□ 是否有导演风格声音配方？（胡金铨/王家卫/北野武/李安）
□ 声音节奏是否与视觉节奏同步？
□ 是否有明确的留白比例？
□ 是否适合目标平台的音频能力？
```

### 生成后评估
```
□ 声音是否有层次感？（不单调）
□ 是否克制不过度？（不过度煽情）
□ 是否有呼吸空间？（不是全程满声音）
□ 是否与视觉情绪匹配？
□ 是否有白梦客美学辨识度？
□ AI味是否去除？（使用 humanize-dialogue 逻辑处理声音）
```

---

## 十、完整示例

### 场景：北野武式雨夜暴力对峙（10秒）

**声音设计方案：**

| 时间 | 声音层 | 内容 | 比例 |
|------|--------|------|------|
| 0-7s | 主体层 | 沉默，只有雨声 | 100%环境音 |
| 7-8s | Foley | 短促撞击声（2帧） | 瞬间爆发 |
| 8-10s | 质感层 | 撞击后极长沉默 | 95%无声 |

**AI视频提示词（Seedance）：**
```
北野武节奏，雨夜东京街道，暴力对峙

[00:00-00:07]
[画面] 固定长镜头，两人各占画面15%，中间70%负空间
        雨滴落下，霓虹在水面反射
[声音] rain on asphalt 40%, distant traffic 20%
        neon hum 10%, near-silence tension
        蓝灰冷色调，高对比

[00:07-00:08]
[画面] 突然硬切，2帧暴力瞬间，黑场
[声音] brief impact sound 2 frames
        瞬间爆发，然后立即转入沉默

[00:08-00:10]
[画面] 暴力后的虚无，固定镜头，雨继续
[声音] rain continues 10%, then near-total silence
        沉默比暴力更重
        声音节奏：静70% + 爆发15% + 虚无15%

[声音质感] tension without music
[留白比例] 90%无声 + 10%环境音
[参考] Sonatine rain scene, Kitano silence philosophy
```

---

## 相关技能

| 技能 | 用途 |
|------|------|
| `ai-music-generator` | BGM/音乐生成，72种风格 |
| `rhythm-to-prompt` | 视觉节奏转AI提示词 |
| `sound-designer` | 完整声音设计工作流 |
| `humanize-dialogue` | 去除AI味，保持声音自然 |

---

> 本技能整合自白梦客知识库：声音组研究 + 导演声音风格 + AI视频提示词规范
> 配合：`ai-music-generator`（音乐层）、`rhythm-to-prompt`（视觉节奏层）
