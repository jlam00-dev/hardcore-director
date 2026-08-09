---
name: tint-to-prompt
description: |
  将色彩理论、情绪色调、导演美学配方转化为AI视频平台可执行的提示词。
  核心功能：输入色调描述（色相/情绪/风格）→ 输出结构化AI提示词（含参数、色值、平台适配）

  触发词：
  - 核心触发：「色调转提示词」「色彩参数」「色值生成」「颜色配方」
  - 进阶触发：「橙蓝撞色」「单色系」「低饱和灰」「高饱和撞色」「黑白灰」
  - 情绪触发：「冷调孤独」「暖调怀旧」「压抑暗调」「明亮活力」「复古色调」
  - 导演触发：「王家卫色调」「北野武色调」「胡金铨色调」「李安色调」「侯孝贤色调」
  - 场景触发：「雨夜霓虹」「晨雾山林」「海边日落」「极简空间」「废墟」
  - 方法触发：「色彩心理学」「色相环」「互补色」「邻近色」「饱和度」「明度」
---

# AI提示词：色调风格转提示词

> 版本：v1.0 | 更新：2026-04-20 | 适用：Seedance/Vidu/海螺/Kling

## TL;DR

```
色调输入（色彩描述/情绪/导演风格）→ 分析色彩维度 → 匹配白梦客配方 → 输出平台化提示词
```

## 启动检查点

激活后先确认：
1. **输入类型**：情绪色调描述 / 导演风格名称 / 具体色值 / 参考图片
2. **目标平台**：Seedance / Vidu / 海螺 / Kling
3. **应用场景**：视频生成 / 图像生成 / 风格迁移

> 三项确认后再转换，避免方向偏差。

---

## 一、色彩理论基础

### 1.1 色彩三要素

| 要素 | 定义 | AI提示词表达 |
|------|------|-------------|
| **色相 (Hue)** | 颜色的基本相貌，如红、橙、黄、绿、蓝、紫 | 琥珀色、青灰色、墨蓝色 |
| **饱和度 (Saturation)** | 颜色的纯度/鲜艳程度 | 高饱和、低饱和、灰调、褪色 |
| **明度 (Lightness/Value)** | 颜色的明暗程度 | 亮调、暗调、中间调、过曝、欠曝 |

### 1.2 色相关系

| 关系 | 视觉感受 | AI提示词表达 |
|------|---------|-------------|
| **互补色** | 强烈对比、冲突、张力 | 红vs绿、蓝vs橙、紫vs黄 |
| **邻近色** | 和谐、统一、渐进 | 黄+橙+红、蓝+紫+青 |
| **分裂互补** | 既有对比又不冲突 | 主色+互补色的邻近色 |
| **三角对立** | 活泼、平衡 | 120度色相分布 |
| **单色系** | 统一、克制、沉静 | 同一色相的不同明度/饱和度 |

### 1.3 色调情感映射

| 色调 | 情绪关键词 | 视觉特征 | AI提示词关键词 |
|------|-----------|---------|---------------|
| **暖色调** | 温暖、怀旧、亲密、舒适 | 黄/橙/红主导，高明度 | warm amber, golden hour, orange glow |
| **冷色调** | 孤独、疏离、理性、压抑 | 蓝/青/紫主导，低明度 | cold blue, teal shadow, icy atmosphere |
| **中性色** | 平静、克制、真实 | 灰/棕/米色为主 | neutral gray, earthy tone, muted |
| **高饱和** | 活力、激情、戏剧性 | 鲜艳纯色 | high saturation, vivid color, bold |
| **低饱和** | 忧郁、内敛、高级感 | 灰蒙蒙的 | desaturated, muted, matte finish |
| **高对比** | 戏剧性、冲突、紧张 | 明暗分明 | high contrast, chiaroscuro, dramatic |
| **低对比** | 柔和、梦幻、模糊 | 明暗接近 | soft contrast, diffused, hazy |

---

## 二、白梦客色调配方库

### 2.1 通用线色调（故事/情绪/概念短片）

```
融合：胡金铨 + 王家卫 + 北野武 + 李安
```

| 色调名称 | 配方比例 | 色值参考 | AI提示词关键词 |
|---------|---------|---------|---------------|
| **大地色基调** | 50% | #6B5B4F, #8B7355, #A67C52, #C4A77D | earth tones, ochre, warm brown, sand |
| **苍青点缀** | 20% | #5B8A8A, #6B9B9B, #8FBFBF, #A3C4C4 | pale cyan, teal shadow, muted blue-green |
| **琥珀霓虹** | 20% | #D4A574, #E8B87D, #FF9E4A, #FFD93D | amber neon, warm orange, golden glow |
| **饱和红点缀** | 10% | #C73E3A, #D64545, #E85D5D | saturated red, crimson accent |

### 2.2 高定线色调（高端品牌广告）

```
融合：Apple + Chanel/Dior + 北野武 + 李安
```

| 色调名称 | 配方比例 | 色值参考 | AI提示词关键词 |
|---------|---------|---------|---------------|
| **黑白灰** | 40% | #1A1A1A, #2D2D2D, #4A4A4A, #808080 | black and white, charcoal, gunmetal |
| **大地灰** | 20% | #6B6B6B, #8B8B8B, #A3A3A3, #BEBEBE | earth gray, warm gray, greige |
| **冷白** | 20% | #F5F5F5, #FAFAFA, #FFFFFF, #E8E8E8 | cold white, stark white, clean white |
| **克制金/铜** | 20% | #B8860B, #DAA520, #CD7F32, #A0522D | muted gold, restrained copper, antique bronze |

### 2.3 导演色调速查

| 导演 | 主色调 | 辅助色 | 质感特征 | AI提示词关键词 |
|------|-------|-------|---------|---------------|
| **王家卫** | 琥珀橙#E8A862, 阴郁蓝绿#2D5A4A | 深青#1A3A3A, 暖黄#D4A574 | 过曝、高饱和、暖调 | amber neon, soft focus, Kodak Vision3 500T, overexposed |
| **北野武** | 墨蓝#1A2A3A, 碳灰#3D4D5D | 冷白#E8E8E8, 深灰#2D2D2D | 低对比、自然光、高冷 | cold blue-grey, desaturated, natural light, shallow depth |
| **胡金铨** | 苔藓绿#3D5240, 土褐#8B6B4A | 烟灰#8A8A8A, 暖白#E8DCC8 | 侧逆光、烟雾、胶片感 | earth tone green, incense smoke, side-backlighting, Kodak Ektachrome |
| **李安** | 大地棕#8B6B4A, 暖灰#A89B8B | 暗青#4A5A5A, 暖黄#D4B896 | 暖调自然光、散射、怀旧 | warm earth tones, natural diffused light, nostalgic, lean into memory |
| **侯孝贤** | 青灰#7A8B8B, 土黄#B8A080 | 暗棕#6B5B4A, 雾白#D8D8D0 | 长镜头、自然光、沉默 | cyan-grey, long take stillness, natural light, silent observation |
| **宫崎骏** | 天空蓝#87CEEB, 草绿#7CB342 | 云白#F5F5F5, 暖橙#FFB74D | 高饱和、干净光线、童话感 | vibrant blue sky, lush green, soft clouds, fairy tale aesthetic |
| **贾樟柯** | 土黄#C4A870, 灰蓝#6B7B8B | 暗红#8B4B4B, 煤灰#3D3D3D | 低饱和、纪实感、现实主义 | desaturated yellow-grey, muted blue-grey, documentary realism |

---

## 三、色彩转提示词核心公式

### 3.1 五层提示词结构

```
【主体层】人物/物体/场景描述
【光影层】光源类型 + 方向 + 质感
【色调层】色相 + 饱和度 + 明度 + 撞色关系
【构图层】色彩分布 + 负空间 + 前景遮挡
【质感层】胶片/数字 + 颗粒 + 曝光参数
```

### 3.2 色调转换矩阵

| 输入色调 | 转换策略 | 输出关键词示例 |
|---------|---------|---------------|
| 「暖调」 | 明度↑ + 色温偏暖 + 高光溢出 | warm amber, golden hour, soft highlight |
| 「冷调」 | 明度↓ + 色温偏冷 + 阴影偏青 | cold blue, teal shadow, desaturated |
| 「高饱和撞色」 | 互补色并列 + 对比度↑ | high saturation, complementary contrast, vivid |
| 「低饱和灰调」 | 饱和度↓ + 中间调为主 | desaturated, muted, matte, grey-scale |
| 「黑白」 | 饱和度=0 + 高对比 | black and white, high contrast, B&W |
| 「复古」 | 饱和度↓ + 暖调 + 颗粒 | vintage, warm tone, film grain, nostalgic |
| 「赛博朋克」 | 高饱和 + 霓虹色 + 深色背景 | neon purple-cyan, wet reflection, cyberpunk |
| 「电影感」 | 中间调 + 胶片质感 + 负空间 | cinematic, film grain, anamorphic, moody |

---

## 四、具体色调场景转换模板

### 4.1 雨夜霓虹（王家卫风格）

```
【输入】
色调：冷调 + 霓虹撞色 + 高饱和
情绪：疏离、怀旧、都市孤独
风格：香港1990s

【转换】
主色调：琥珀橙 #E8A862 (60%) + 阴郁蓝绿 #2D5A4A (40%)
光源：单一暖黄路灯 + 霓虹漫射
质感：Kodak Vision3 500T, 过曝1/3档, 轻微颗粒

【AI提示词输出】
neon-lit wet street at night, amber orange vs deep teal shadows
low-key lighting, single warm amber streetlight, rain reflections
high saturation, Kodak Vision3 500T film, nostalgic color grading
handheld slightly unstable, melancholic urban solitude
--ar 16:9 --style raw --v 7 --s 500
```

### 4.2 晨雾山林（胡金铨风格）

```
【输入】
色调：大地色 + 苍青 + 低饱和
情绪：禅定、冥想、孤独修行
风格：1970s武侠

【转换】
主色调：苔藓绿 #3D5240 (50%) + 土褐 #8B6B4A (30%) + 烟灰 #8A8A8A (20%)
光源：侧逆光 + 晨雾散射
质感：Kodak Ektachrome, 2.35:1 Cinemascope

【AI提示词输出】
King Hu style, 1970s Kodak Ektachrome earth tones
bamboo grove at dawn, morning mist rolling through
earth tone green + pale cyan sky + warm white
side-backlighting, smoke scattering, mist diffusion
foreground bamboo stalks as frame obstruction 60%
negative space 70%, figure small in frame
minimalist composition, classical Chinese landscape
meditative atmosphere, martial arts as spiritual practice
--ar 2.35:1 --style raw --v 7 --s 650
```

### 4.3 极简空间（高定线）

```
【输入】
色调：黑白灰 + 冷白 + 克制金
情绪：克制、高级、精致
风格：Chanel/Dior品牌

【转换】
主色调：炭灰 #2D2D2D (40%) + 冷白 #F5F5F5 (40%) + 暗金 #B8860B (20%)
光源：自然光50% + 单一致光源30%
质感：16mm胶片, 过曝1/3档, 轻颗粒

【AI提示词输出】
high-end fashion editorial, Chanel meets Kitano
black and white 40% + earth grey 20% + cold white 20% + muted gold 20%
minimalist product or model in stark white studio
single directional light source, dramatic shadow
60%+ negative space, extreme simplicity
16mm film grain, slight overexposure +1/3 stop
long take stillness, no quick cuts
silence as luxury, restraint as elegance
--ar 4:5 --style raw --v 7 --s 400
```

### 4.4 海边黄昏（北野武风格）

```
【输入】
色调：冷蓝 + 碳灰 + 低对比
情绪：压抑、暴力后的平静、虚无
风格：北野武《坐头市》

【转换】
主色调：墨蓝 #1A2A3A (50%) + 碳灰 #3D4D5D (30%) + 冷白 #E8E8E8 (20%)
光源：自然光（阴天）+ 低反差
质感：高度饱和抑制, 真实感

【AI提示词输出】
Takeshi Kitano style, Hana-bi inspired
extreme minimalist composition, vast negative space
quiet seaside at dusk, single figure on rocky shore
cold blue-grey tones, desaturated, shallow depth
natural ambient light, overcast sky
figure small against enormous sea and sky
stillness after violence, existential solitude
no movement, time frozen
--ar 16:9 --style raw --v 7 --s 400
```

### 4.5 老宅怀旧（李安风格）

```
【输入】
色调：暖调 + 大地色 + 褪色感
情绪：家庭、情感压抑、含蓄
风格：李安家庭三部曲

【转换】
主色调：土褐 #8B6B4A (40%) + 暖灰 #A89B8B (30%) + 暗青 #4A5A5A (30%)
光源：暖黄自然光 + 散射
质感：怀旧色调, 低饱和, 柔和

【AI提示词输出】
Ang Lee family drama aesthetic, warm earth tones
old Chinese house interior, kitchen courtyard, overcast day
ochre 40% + warm grey 30% + muted teal 30%
warm diffused natural light, nostalgic color grading
tender melancholy, emotional restraint, subtle tension
lean into memory, soft focus, gentle pace
--ar 16:9 --style raw --v 7 --s 450
```

---

## 五、色值精确参数表

### 5.1 白梦客标准色板

| 色名 | Hex | RGB | 使用场景 | AI提示词 |
|------|-----|-----|---------|---------|
| 苔藓绿 | #3D5240 | 61,82,64 | 山林、竹林 | moss green, earth tone green |
| 土褐 | #8B6B4A | 139,107,74 | 寺庙、土地、老宅 | ochre, warm brown, earth |
| 烟灰 | #8A8A8A | 138,138,138 | 烟雾、晨雾 | smoke grey, mist, atmospheric haze |
| 苍青 | #5B8A8A | 91,138,138 | 天空、水面、阴影 | pale cyan, teal shadow |
| 暗赭 | #6B4A3A | 107,74,58 | 屋顶、门框、古建筑 | dark ochre, burnt sienna |
| 暖白 | #E8DCC8 | 232,220,200 | 阳光、宣纸、温暖光 | warm white, parchment, soft light |
| 墨黑 | #1A1A1A | 26,26,26 | 夜色、墨迹、深色 | ink black, deep charcoal |
| 琥珀橙 | #E8A862 | 232,168,98 | 霓虹、路灯、怀旧 | amber, warm orange, golden glow |
| 阴郁蓝绿 | #2D5A4A | 45,90,74 | 王家卫阴影 | deep teal, muted blue-green |
| 墨蓝 | #1A2A3A | 26,42,58 | 北野武冷调 | dark blue, charcoal blue |
| 碳灰 | #3D4D5D | 61,77,93 | 北野武灰调 | carbon grey, cool grey |
| 冷白 | #F5F5F5 | 245,245,245 | 高定线冷调 | cold white, stark white |
| 暗金 | #B8860B | 184,134,11 | 高定线金色 | muted gold, antique bronze |
| 饱和红 | #C73E3A | 199,62,58 | 强调色 | saturated red, crimson accent |
| 琥珀霓虹 | #FF9E4A | 255,158,74 | 霓虹灯 | amber neon, warm orange neon |

### 5.2 饱和度/明度参数

| 效果 | 饱和度 | 明度 | AI提示词 |
|------|-------|------|---------|
| 过曝效果 | -20% | +30% | overexposed, bleached, washed out |
| 欠曝效果 | +10% | -40% | underexposed, deep shadows, crushed blacks |
| 高饱和 | +40% | 中等 | high saturation, vivid, bold colors |
| 低饱和 | -50% | 中等 | desaturated, muted, matte |
| 褪色 | -30% | +20% | faded, vintage, worn |
| 黑白 | 0% | 调整 | black and white, B&W, grayscale |

### 5.3 色彩对比度参数

| 对比度 | 色差ΔE | AI提示词 |
|--------|-------|---------|
| 高对比 | >30 | high contrast, dramatic, chiaroscuro |
| 中对比 | 15-30 | balanced contrast, cinematic |
| 低对比 | <15 | soft contrast, diffused, hazy, flat |

---

## 六、平台化输出格式

### 6.1 Seedance（中文）

```
[色调描述] + [光影] + [构图] + [质感]

示例：
琥珀橙与深青撞色，侧逆光打出发丝光，60%负空间，
胶片颗粒，轻过曝，电影感
```

### 6.2 Vidu（中英混合）

```
[风格词] + [色调参数] + [质感描述]

示例：
Wong Kar-wai cinematic style
amber orange 60% + deep teal 40%, overexposed 1/3 stop
soft focus, light film grain, neon reflections
```

### 6.3 海螺（图像转视频）

```
主色调：[色相描述]
光影：[光源+方向]
动态预期：[色调变化]

示例：
主色调：琥珀橙为主，冷蓝为辅
光影：暖黄路灯从左侧打来，霓虹从右侧漫射
动态预期：色调随人物移动产生冷暖变化
```

### 6.4 Kling（英文参数）

```
--style cinematic
--color-tone warm amber 60%, cold blue 40%
--saturation high
--contrast high
--texture 35mm film grain
```

---

## 七、情绪色调逆向转换

### 7.1 从情绪反推色调

| 情绪 | 色调解法 | AI提示词生成 |
|------|---------|-------------|
| 「孤独」 | 低明度 + 冷调 + 负空间 | cold blue-grey, isolated figure, vast negative space |
| 「温暖」 | 高明度 + 暖调 + 柔光 | warm amber, golden hour, soft diffused light |
| 「紧张」 | 高对比 + 冷调 + 硬光 | high contrast, cold blue, hard shadows |
| 「平静」 | 低对比 + 中性色 + 散射光 | soft contrast, neutral grey, diffused light |
| 「怀旧」 | 低饱和 + 暖调 + 颗粒 | desaturated, warm tone, film grain, nostalgic |
| 「活力」 | 高饱和 + 暖调 + 高明度 | high saturation, vivid color, bright, energetic |
| 「压抑」 | 低明度 + 冷调 + 窄色域 | dark, desaturated, cold blue, confined space |
| 「神秘」 | 低明度 + 中性色 + 戏剧光 | dark atmosphere, neutral tones, dramatic lighting |

### 7.2 色调冲突检测

当输入包含冲突色调时，提供调和方案：

| 冲突 | 检测词 | 调和方案 |
|------|-------|---------|
| 暖+冷 | 「冷调但温暖」「蓝配橙」 | 选择主导色，另一色降饱和度作为辅助 |
| 高饱和+低饱和 | 「鲜艳但低调」 | 主体用低饱和，焦点元素用高饱和撞色 |
| 高对比+低对比 | 「戏剧但柔和」 | 降低对比度，用色调变化代替明暗对比 |

---

## 八、质量检查清单

生成提示词后检查：

```
□ 色调描述具体化（不只是"好看"，要有色相/饱和度/明度）
□ 色值比例明确（主色60%+辅助30%+点缀10%）
□ 光影与色调匹配（冷调→冷光源，暖调→暖光源）
□ 质感参数完整（胶片型号/颗粒/曝光）
□ 平台格式正确（Seedance中文/Vidu中英/Kling英文）
□ 无抽象情绪词（用色彩参数替代"孤独感""温暖感"）
□ 构图色彩分布说明（留白区域颜色/主体颜色占比）
```

---

## 九、场景类型快速索引

| 场景 | 推荐色调 | 配方 | AI提示词关键词 |
|------|---------|------|---------------|
| 雨夜街道 | 王家卫 | 琥珀60%+深青40% | neon-lit wet street, amber vs teal |
| 山林竹海 | 胡金铨 | 大地绿50%+苍青30%+烟灰20% | bamboo grove, earth tones, mist |
| 极简空间 | 高定线 | 黑白灰40%+冷白40%+暗金20% | minimalist, black and white, negative space |
| 海边日落 | 北野武+李安 | 墨蓝50%+碳灰30%+暖橙20% | seaside dusk, cold blue-grey, golden accents |
| 废墟探索 | 贾樟柯 | 土黄40%+灰蓝40%+暗红20% | ruins, desaturated yellow-grey, documentary |
| 复古唱片店 | 王家卫 | 琥珀50%+深青30%+暖白20% | vintage record shop, amber neon, nostalgic |

---

> 本Skill由白梦客 AI创作团队创建
> 版本：v1.0 | 更新：2026-04-20
> 核心参考：白梦客知识库·东方美学体系 + color theory (Wikipedia)
