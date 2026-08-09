---
name: stylized-color-grading
description: |
  风格化调色：将经典调色风格转化为AI视频提示词。
  触发词：「调色」「风格化调色」「Teal-Orange」「Film-Noir」「Cyberpunk」「Bleach-Bypass」「王家卫色调」「北野武色调」「情绪调色」

  核心功能：
  1. 12种经典调色风格的HEX色值参数
  2. AI视频提示词模板（Seedance/Vidu/Kling）
  3. 调色师决策流程（七情×风格线×导演融合）
  4. 导演风格融合变体（王家卫/北野武/胡金铨/李安）

  协同：colorist agent、emotional-color-grading wiki、tint-to-prompt skill
---

# 风格化调色

> 版本: v1.0 | 更新: 2026-04-20 | 适用: Seedance/Vidu/Kling

## TL;DR

```
情绪类型 → 选择调色风格 → 融合导演风格 → 输出平台化AI提示词
```

---

## 一、十二大风格化调色

| 风格 | 主色 | 饱和度 | 对比度 | 核心关键词 | 适用场景 |
|------|------|--------|--------|-----------|---------|
| **Teal-Orange** | 影#1C3A3A/光#D4845A | +20% | +30% | 商业大片、现代都市 | 广告/科幻 |
| **Bleach-Bypass** | 影#1A1F2A/光#D8DDE8 | -50% | +50% | 战争、苍凉、压迫 | 纪实/战争 |
| **Film-Noir** | 影#0A0A10/光#E8E0D0 | -75% | +65% | 悬疑、宿命、百叶窗 | 侦探/黑色电影 |
| **Cyberpunk** | 底#0D0D1A/霓#00D4FF | +50% | +30% | 未来、霓虹、雨夜倒影 | 科幻/赛博朋克 |
| **Vintage-Warm-70s** | 影#3D2B1F/光#D4A574 | -15% | ±0 | 怀旧、褪色、粗颗粒 | 复古/记忆 |
| **Cross-Process** | 影绿#1A3020/光橙#E8C070 | +35% | +45% | 前卫、色彩移位、实验 | 实验艺术 |
| **Desaturated-Cool** | 影#1A1E24/光#D2D8E0 | -45% | +20% | 高端、极简、克制 | 高定品牌广告 |
| **Neon-Noir** | 底#0A0F1A/霓#C9A86C | 局部+90% | +50% | 都市孤独、王家卫式 | 情感短片 |
| **Muted-Green** | 影#1E2420/光#B0C4A8 | -30% | +5% | 欧洲文艺、北欧内省 | 文艺片 |
| **Bronze-Sepia** | 影#1A0F0A/光#D4B090 | -48% | +15% | 历史、档案、铁版照片 | 历史/纪录片 |
| **Magic-Hour** | 暖光#F7931E/蓝影#2D1B5A | +30% | +20% | 神圣、命运、史诗 | 史诗/命运 |
| **白梦客通用线** | 大地#6B5344+苍青#2D4A5A | -20%~30% | 变量 | 东方情绪短片 | 情感/武侠 |
| **白梦客高定线** | 黑白#1a1a2e+金#b8860b | -50%~70% | 变量 | 高端品牌广告 | 广告 |

---

## 二、核心色值库

### 暖色系

| 颜色名 | HEX | HSB | 用途 |
|--------|-----|-----|------|
| 血红 | #E63946 | H0° S74% B90% | 愤怒、爆发点缀 |
| 琥珀 | #C9A86C | H38° S47% B79% | 霓虹/怀旧主色 |
| 深金 | #B8860B | H42° S100% B72% | 高定线克制点缀 |
| 暖驼 | #B8926A | H30° S40% B72% | 大地色高光 |
| 深驼褐 | #6B5344 | H25° S38% B42% | 大地色主基调 |
| 魔幻金 | #F7931E | H36° S100% B100% | Magic Hour |

### 冷色系

| 颜色名 | HEX | HSB | 用途 |
|--------|-----|-----|------|
| 墨蓝灰 | #2D323C | H220° S15% B24% | 北野武主基调 |
| 苍青 | #2D4A5A | H200° S45% B35% | 东方冷调 |
| 铁蓝 | #5F738C | H205° S35% B55% | 雨夜天空 |
| 冷白 | #D2D8E0 | H210° S8% B88% | 高定线高光 |
| 深钢蓝 | #1A1E24 | H210° S25% B14% | 极简冷调 |
| 墨蓝黑 | #0A0A10 | H240° S90% B6% | Film Noir深影 |
| 蓝紫暗 | #2D1B5A | H260° S70% B35% | Magic Hour阴影 |

### 霓虹色

| 颜色名 | HEX | HSB | 用途 |
|--------|-----|-----|------|
| 霓虹青 | #00D4FF | H190° S100% B100% | Cyberpunk主色 |
| 霓虹品红 | #FF00DD | H305° S100% B100% | 赛博/王家卫点缀 |
| 电紫 | #8B00FF | H270° S100% B100% | 未来感光晕 |
| 霓虹橙 | #FF6B00 | H25° S100% B100% | 警示/招牌 |

---

## 三、AI视频提示词模板

### 1. Teal-Orange（商业大片感）

```
【Seedance】
青灰阴影#1C3A3A与暖橙高光#D4845A撞色，
饱和度+20%，对比度+30%，
侧光打亮主体，霓虹城市背景，
35mm胶片颗粒，商业大片质感，
--ar 2.35:1 --style raw --model_version 4.6 --v 7

【Kling/Runway】
cinematic commercial, teal #1C3A3A shadows vs orange #D4845A highlights
saturation +20%, contrast +30%, side lighting
urban neon background, 35mm film grain
negative: desaturated, muted tones, flat lighting

【Vidu Q3】
cinematic style, teal orange color grade
shadow #1C3A3A, highlight #D4845A
saturation +20%, contrast +30%, side lighting
35mm film grain, commercial quality
--style realistic --ar 2.35:1 --duration 8s
```

### 2. Bleach-Bypass（战争/苍凉压迫）

```
【Seedance】
灰白阴影#1A1F2A与冷白高光#D8DDE8，
饱和度-50%，对比度+50%，
高光硬调，无色彩偏色，
16mm粗颗粒，重压抑感，
--ar 2.35:1 --style raw --model_version 4.6 --v 7

【Kling/Runway】
bleach bypass, grey #1A1F2A shadows vs cold white #D8DDE8 highlights
saturation -50%, contrast +50%, hard highlight
no color cast, 16mm gritty grain
oppressive atmosphere, war torn
negative: vivid colors, soft contrast, color grading

【Vidu Q3】
cinematic style, bleach bypass look
shadow #1A1F2A, highlight #D8DDE8
desaturation 50%, high contrast 50%
hard lighting, gritty 16mm grain
oppressive mood, --style realistic --ar 2.35:1 --duration 8s
```

### 3. Film-Noir（悬疑/宿命/百叶窗阴影）

```
【Seedance】
深黑阴影#0A0A10与暖白高光#E8E0D0，
饱和度-75%，对比度+65%，
百叶窗光切割，单一硬光源，
35mm高对比颗粒，黑色电影质感，
--ar 2.35:1 --style raw --model_version 4.6 --v 7

【Kling/Runway】
film noir, black #0A0A10 shadows vs warm white #E8E0D0 highlights
saturation -75%, contrast +65%, venetian blind light cuts
single hard light source, 35mm high contrast grain
fate, suspense, detective atmosphere
negative: color, soft lighting, cheerful mood

【Vidu Q3】
noir cinematic style, high contrast B&W
shadow #0A0A10, highlight #E8E0D0
desaturation 75%, contrast +65%
venetian blind lighting, dramatic shadows
--style realistic --ar 2.35:1 --duration 8s
```

### 4. Cyberpunk（未来/科技/霓虹雨夜）

```
【Seedance】
深蓝黑底#0D0D1A与霓虹青#00D4FF对比，
饱和度+50%，对比度+30%，
湿街道倒影，霓虹招牌光晕，
蓝紫霓虹点缀，赛博朋克质感，
--ar 16:9 --style raw --model_version 4.6 --v 7

【Kling/Runway】
cyberpunk, dark blue #0D0D1A base vs neon cyan #00D4FF
saturation +50%, contrast +30%, wet street reflections
neon signs glow, purple accent, blue neon
future tech atmosphere, rain, reflections
negative: natural daylight, soft lighting, muted colors

【Vidu Q3】
cyberpunk aesthetic, neon cyan #00D4FF vs dark #0D0D1A
saturation +50%, contrast +30%
wet reflections, neon signs, futuristic
--style anime --ar 16:9 --duration 8s
```

### 5. Vintage-Warm-70s（怀旧/褪色/粗颗粒）

```
【Seedance】
深褐阴影#3D2B1F与暖金高光#D4A574，
饱和度-15%，对比度±0，
褪色感，暖调颗粒，70年代质感，
轻微过曝边缘，胶片模拟，
--ar 2.35:1 --style raw --model_version 4.6 --v 7

【Kling/Runway】
vintage 70s, dark brown #3D2B1F shadows vs warm gold #D4A574 highlights
saturation -15%, contrast ±0, faded look
warm tone, retro feel, 70s aesthetic
slight overexposure, film grain, nostalgic
negative: sharp digital, cool tones, modern

【Vidu Q3】
vintage cinematic, warm faded tones
shadow #3D2B1F, highlight #D4A574
saturation -15%, retro warm grade
70s film grain, nostalgic mood
--style realistic --ar 2.35:1 --duration 8s
```

### 6. Cross-Process（前卫/色彩移位/实验）

```
【Seedance】
深绿阴影#1A3020与暖橙高光#E8C070，
饱和度+35%，对比度+45%，
色彩移位，不自然色调，
实验影像感，饱和偏色，
--ar 16:9 --style raw --model_version 4.6 --v 7

【Kling/Runway】
cross process, green #1A3020 shadows vs orange #E8C070 highlights
saturation +35%, contrast +45%, color shift
unnatural tones, experimental film look
bold color manipulation, avant-garde
negative: natural colors, subtle grading, realistic
```

### 7. Desaturated-Cool（高端/极简/克制）— 高定线基础

```
【Seedance】
深钢蓝阴影#1A1E24与冷白高光#D2D8E0，
饱和度-45%，对比度+20%，
极简空间，单一光源，
克制冷调，高端产品质感，
--ar 16:9 --style raw --model_version 4.6 --v 7

【Kling/Runway】
desaturated cool, steel blue #1A1E24 shadows vs cold white #D2D8E0 highlights
saturation -45%, contrast +20%, minimalist space
single light source, restrained cool tone
luxury minimal, high-end product aesthetic
negative: warm tones, vibrant colors, cluttered

【Vidu Q3】
luxury minimal, desaturated cool tones
shadow #1A1E24, highlight #D2D8E0
desaturation 45%, contrast +20%
minimal space, single light, elegant restraint
--style realistic --ar 16:9 --duration 8s
```

### 8. Neon-Noir（都市孤独/王家卫式）— 通用线基础

```
【Seedance】
深蓝黑底#0A0F1A与琥珀霓虹#C9A86C，
局部饱和度+90%，对比度+50%，
雨夜霓虹，湿街道倒影，
王家卫都市孤独美学，
--ar 2.35:1 --style raw --model_version 4.6 --v 7

【Kling/Runway】
neon noir, dark blue #0A0F1A base vs amber #C9A86C neon
local saturation +90%, contrast +50%, rain night neon
wet street reflections, Wong Kar-wai urban solitude
handheld, step-printing, melancholic
negative: daylight, uniform lighting, cheerful
```

### 9. Muted-Green（欧洲文艺/北欧内省）

```
【Seedance】
深绿阴影#1E2420与灰绿高光#B0C4A8，
饱和度-30%，对比度+5%，
自然光散射，北欧内省氛围，
柔和过渡，文艺感，
--ar 16:9 --style raw --model_version 4.6 --v 7

【Kling/Runway】
muted green, dark green #1E2420 shadows vs grey green #B0C4A8 highlights
saturation -30%, contrast +5%, natural diffused light
Nordic introspection, soft transitions
art house, European cinema feel
negative: high saturation, harsh colors, dramatic
```

### 10. Bronze-Sepia（历史/档案/铁版照片）

```
【Seedance】
深棕阴影#1A0F0A与古铜高光#D4B090，
饱和度-48%，对比度+15%，
铁版照片质感，古铜色调，
档案记录感，历史厚重，
--ar 4:5 --style raw --model_version 4.6 --v 7

【Kling/Runway】
bronze sepia, dark brown #1A0F0A shadows vs bronze #D4B090 highlights
saturation -48%, contrast +15%, iron plate photo aesthetic
historical archive, bronze tone, period feel
negative: modern colors, digital sharpness, vibrant
```

### 11. Magic-Hour（神圣/命运/史诗）

```
【Seedance】
暖金高光#F7931E与蓝紫阴影#2D1B5A，
饱和度+30%，对比度+20%，
黄金时刻光照，逆光神圣感，
命运史诗感，蓝紫冷调阴影，
--ar 2.35:1 --style raw --model_version 4.6 --v 7

【Kling/Runway】
magic hour, golden orange #F7931E highlights vs blue purple #2D1B5A shadows
saturation +30%, contrast +20%, golden hour backlight
sacred light, destiny, epic atmosphere
blue purple cool shadows, holy moment
negative: flat lighting, grey day, muted
```

### 12. 白梦客通用线（东方情绪短片）

```
【Seedance】
大地色#6B5344主调偏苍青#2D4A5A，琥珀霓虹#C9A86C点缀，饱和红#E63946不超过10%，
饱和度-20%~30%，对比度变量，
侧逆光+烟雾散射70%+霓虹漫射30%，
前景遮挡+极简留白+负空间呼吸，
长镜头留白70%+抽帧慢动作20%+硬切断刀10%，
Kodak Ektachrome 1970s，35mm胶片颗粒，2.35:1电影宽屏，
--ar 2.35:1 --style raw --model_version 4.6 --v 7

【Kling/Runway】
King Hu + Wong Kar-wai + Takeshi Kitano fusion, East Asian cinematic
earth tones #6B5344 50%, pale cyan #2D4A5A 20%, amber neon #C9A86C 20%
saturated red accent #E63946 <10%, saturation -20%~30%
side-backlight 70% + neon diffusion 30%
foreground obstruction, minimalist negative space
long take 70% + slow motion 20% + hard cut 10%
Kodak Ektachrome 1970s, 35mm film grain, cinematic 2.35:1
negative: bright neon, oversaturated, modern CGI

【Vidu Q3】
cinematic East Asian aesthetic, earth tones palette
earth tones #6B5344 50%, pale cyan #2D4A5A 20%
amber neon #C9A86C 20%, red accent #E63946 <10%
side-backlight, smoke scattering, long take atmosphere
negative space, film grain, melancholic
--style realistic --ar 2.35:1 --duration 8s
```

---

## 四、导演风格融合变体

### 王家卫变体（都市孤独+怀旧错失）

叠加元素：
- **色调**：琥珀橙+品红点缀+阴郁蓝绿阴影
- **质感**：Kodak Vision3 500T，过曝1/3档，颗粒感
- **光影**：霓虹漫射，湿街道水洼反射
- **运镜**：手持轻微晃动，抽帧慢动作0.25x

```
【Seedance】
王家卫风格，雨夜香港，
青蓝#2A4B5C阴影，琥珀#C9A86C高光，霓虹品红#D4527A点缀，
低饱和20%-40%，褪色感，
青蓝阴影+琥珀暖光撞色，霓虹溢出色差偏移3px，
湿街道水洼反射，抽帧慢动作0.25x，手持轻微晃动，
胶片颗粒20%，过曝轮廓，
--ar 2.35:1 --v 7 --s 600 --chaos 35
```

### 北野武变体（冷峻暴力+极致静默）

叠加元素：
- **色调**：墨蓝灰#2D323C为主，蓝灰冷调
- **质感**：T-Max高对比颗粒，极端对比1:8
- **光影**：单一硬光源，几何阴影切割
- **构图**：负空间60%+，两人各占画面边缘25%

```
【Seedance】
北野武风格，冷峻暴力，
墨蓝灰#2D323C为主，饱和度20%-35%，蓝灰冷调，
极端对比1:8，纯黑阴影，
几何阴影切割，单光源，负空间60%，
两人各占画面边缘25%，中间湿柏油路，
15秒无运动静默，突然切断黑屏5秒，
35mm T-Max高对比颗粒，
--ar 2.35:1 --style raw --model_version 4.6 --v 7
```

### 胡金铨变体（禅意武侠+留白禅定）

叠加元素：
- **色调**：苔藓绿#3D5240+土褐#8B6B4A+烟灰#8A8A8A
- **质感**：Kodak Ektachrome，2.35:1 Cinemascope
- **光影**：侧逆光135°±15°，晨雾散射
- **构图**：负空间70%+，前景竹干遮挡25%+

```
【Seedance】
胡金铨禅意武侠，竹林对峙，
大地色#6B5344偏苍青#2D4A5A，饱和度30%-45%，明度35%-50%，
侧逆光135°±15°，冷白散射5500K-6500K，烟雾，
对比度75%-90%，负空间70%，前景竹干遮挡25%，
固定长镜头15秒+，深景深，
35mm Kodachrome颗粒，胶片质感，
--ar 2.35:1 --style raw --model_version 4.6 --v 7
```

### 李安变体（情感内省+东方意境）

叠加元素：
- **色调**：暖金#D4A574主调+克制蓝#4A6670辅色
- **质感**：自然窗光，深焦，钨丝室内光
- **光影**：暖调，Magic Hour时刻
- **情绪**：隐忍，文化压力暗示，未说出

```
【Seedance】
李安情感内省，家庭张力，
Magic Hour金#D4A574主调，克制蓝#4A6670辅色，
暖调，钨丝室内光，自然窗光深焦，
负空间50%，缓慢推镜8秒，微表情，
无音乐仅环境音，文化压力暗示，
饱和红#E63946点缀≤10%情绪爆发，
--ar 16:9 --style raw --model_version 4.6 --v 7
```

---

## 五、调色师决策流程

```
Step 1: 分析情绪类型
七情（哀/喜/怒/惧/爱/恶/欲）→ 确定调色方向

Step 2: 判断美学线
商业广告 → 高定线（黑白40%+大地灰20%+冷白20%+克制金20%）
故事短片/情绪短片 → 通用线（大地色50%+苍青20%+琥珀霓虹20%+饱和红10%）

Step 3: 选择风格化调色基础
商业大片感 → Teal-Orange
战争/苍凉 → Bleach-Bypass
悬疑/宿命 → Film-Noir
未来/科技 → Cyberpunk
怀旧/记忆 → Vintage-Warm-70s
前卫/实验 → Cross-Process
高端/极简 → Desaturated-Cool（高定线基础）
都市孤独 → Neon-Noir（通用线基础）
北欧/内省 → Muted-Green
历史/档案 → Bronze-Sepia
神圣/宏大 → Magic-Hour
东方情绪 → 白梦客通用线

Step 4: 融合导演风格
王家卫 → 加入琥珀霓虹+过曝+抽帧
北野武 → 加入墨蓝灰+极端对比+静默
胡金铨 → 加入大地色+侧逆光+负空间
李安 → 加入暖金+自然散射+隐忍

Step 5: 输出平台化提示词
Seedance → 中文逗号分隔，时间戳分段
Kling → 英文，negative显式
Vidu → 风格词前置，--style realistic/anime
```

---

## 六、平台参数速查

| 参数类型 | Seedance | Kling/可灵 | Runway | Vidu Q3 |
|---------|----------|-----------|--------|---------|
| **分辨率** | --ar 16:9/9:16/2.35:1 | --ar 16:9 | 1920x1080 | --ar 16:9/9:16/1:1 |
| **模型版本** | --model_version 4.6 | - | Gen-3 | --model v3 |
| **时长** | 隐含 | --duration | - | --duration 4s/8s |
| **风格控制** | 直接描述 | --stylize | style strength | --style |
| **负向词** | 独立段落 | negative: | 独立段落 | 不推荐 |
| **胶片颗粒** | "胶片颗粒+X%" | "film grain" | "grain" | "film grain" |
| **推荐语言** | 中文优先 | 英文优先 | 英文 | 英文 |

---

## 七、负向提示词基础库

```
所有风格通用：
不要任何文字/字幕/水印/logo
不要直接情绪标签（悲伤的、快乐的）
不要抽象概念（自由、希望、梦想）
不要未量化变化（灯光变亮、速度变快）

暖调专项：不要冷蓝, 不要青绿, 不要蓝天
冷调专项：不要暖橙, 不要日落, 不要金色
复古专项：不要数字感, 不要现代锐利, 不要鲜艳饱和
极简专项：不要高饱和, 不要杂乱, 不要暖光
黑白专项：不要彩色, 不要均匀打光, 不要明亮
霓虹专项：不要自然日光, 不要均匀布光
```

---

## 八、质量检查清单

生成提示词后检查：

```
□ 色调描述具体化（色相/饱和度/明度三要素）
□ 色值比例明确（主色+辅助色+点缀色）
□ 导演风格融合正确
□ 光影与色调匹配（冷调→冷光源，暖调→暖光源）
□ 质感参数完整（胶片型号/颗粒/曝光）
□ 平台格式正确（Seedance中文/Vidu中英/Kling英文）
□ 无抽象情绪词（用色彩参数替代）
□ 构图色彩分布说明（负空间颜色/主体颜色占比）
□ 负向提示词完整
```

---

## 九、相关文档

- [[skills/tint-to-prompt]] — 色调转AI提示词（色彩理论+导演配方）
- [[wiki/aesthetic/emotional-color-grading]] — 情绪调色（七情×调色参数）
- [[agents/colorist]] — 调色师Agent
- [[skills/prompt-matrix]] — 广告提示词矩阵系统

---

> 版本: v1.0 | 更新: 2026-04-20
> 白梦客 AI创作团队
