# AI提示词:构图法则转提示词

> 将经典构图法则转化为平台化AI视频提示词，适用于 Seedance / Vidu / Kling / 海螺

---

## 核心原理

**构图 = 视觉元素的组织与安排**

| 维度 | 说明 |
|------|------|
| 主体 | 被拍摄对象（人物/物体/场景焦点） |
| 空间 | 正空间（主体）+ 负空间（留白） |
| 线条 | 引导视线、构建透视 |
| 形状 | 几何/有机、三角/圆形 |
| 比例 | 三分法、黄金分割、框架比例 |

---

## 构图法则参数表

### 1. 黄金分割 (Golden Ratio)

| 参数 | 数值 | AI提示词关键词 |
|------|------|---------------|
| 分割比例 | 1:1.618 | golden ratio, golden section |
| 螺旋位置 | 中心向外旋 | fibonacci spiral, golden spiral |
| 画面占比 | 主体38.2% | off-center, asymmetric balance |

**AI提示词模板：**
```
[主体] positioned at golden ratio point, golden spiral leading to [焦点],
fibonacci composition, [氛围色调]
```

### 2. 三分法则 (Rule of Thirds)

| 参数 | 数值 | AI提示词关键词 |
|------|------|---------------|
| 网格 | 3×3均分 | rule of thirds, thirds grid |
| 交叉点 | 4个兴趣点 | intersection point, power point |
| 地平线 | 上1/3或下1/3 | horizon at upper third, sky dominant |

**AI提示词模板：**
```
[主体] placed at left/right intersection point of thirds,
horizon aligned to upper/lower third, rule of thirds composition,
[光影氛围]
```

### 3. 前景遮挡 (Repoussoir/Framing)

| 参数 | 说明 | AI提示词关键词 |
|------|------|---------------|
| 遮挡比例 | 15-30%画面 | foreground obstruction, partial frame |
| 虚化程度 | 浅景深 | shallow DoF, bokeh foreground |
| 框架元素 | 门窗/树枝/人影 | natural frame, doorway, archway |

**AI提示词模板：**
```
[主体] viewed through [框架元素], foreground partially obscuring [主体],
shallow depth of field, repoussoir composition, leading eye inward,
[色调氛围]
```

### 4. 负空间 (Negative Space)

| 参数 | 说明 | AI提示词关键词 |
|------|------|---------------|
| 留白比例 | 40-60% | vast negative space, minimalist |
| 平衡方式 | 偏心放置 | off-center subject, breathing room |
| 情感暗示 | 孤独/自由/紧张 | isolated figure, lonely atmosphere |

**AI提示词模板：**
```
[主体] isolated in vast [颜色/纹理] negative space,
minimalist composition, [情感氛围], [比例]
```

### 5. 对角线构图 (Diagonal Composition)

| 参数 | 说明 | AI提示词关键词 |
|------|------|---------------|
| 角度范围 | 30-60度 | diagonal lines, dynamic angle |
| 汇聚效果 | 消失点导向 | converging lines, vanishing point |
| 张力感 | 动态/不安 | tension lines, dynamic movement |

**AI提示词模板：**
```
[主体] positioned along diagonal axis, converging lines toward [消失点],
dynamic composition, [角度] degree angle, [光影]
```

### 6. 三角构图 (Triangular Composition)

| 参数 | 说明 | AI提示词关键词 |
|------|------|---------------|
| 形状类型 | 正三角/倒三角 | triangular arrangement, pyramid |
| 稳定性 | 正三角=稳固 | stable pyramid, grounded composition |
| 张力感 | 倒三角=危险 | inverted triangle, unstable balance |

**AI提示词模板：**
```
[主体群] arranged in [正三角/倒三角] formation,
pyramid composition, [数量] figures, [稳定/动态] mood
```

### 7. S型/C型曲线 (S-Curve)

| 参数 | 说明 | AI提示词关键词 |
|------|------|---------------|
| 曲线类型 | S形/ C形/ Z形 | S-curve, serpentine path, C-curve |
| 引导效果 | 视线沿曲线移动 | flowing composition, winding path |
| 应用场景 | 河流/道路/人体 | river winding through, winding road |

**AI提示词模板：**
```
[场景元素] forming [S/C/Z]-curve composition,
serpentine arrangement, [引导主体], [光影]
```

### 8. 对称与平衡 (Symmetry)

| 参数 | 说明 | AI提示词关键词 |
|------|------|---------------|
| 对称类型 | 水平/垂直/径向 | bilateral symmetry, mirror composition |
| 平衡方式 | 正式/非正式 | formal balance, symmetrical axis |
| 打破方式 | 微偏移+色彩对比 | subtle asymmetry, weighted balance |

**AI提示词模板：**
```
[主体] centered on vertical axis, perfect bilateral symmetry,
formal composition, [建筑/水面/倒影] environment
```

---

## 白梦客构图配方

### 通用线构图（故事短片/情绪片）

| 元素 | 配方 | AI提示词 |
|------|------|----------|
| 前景 | 70%场景使用 | foreground obstruction, natural frame, branches silhouette |
| 负空间 | 60%+留白 | vast negative space, minimalist composition |
| 地平线 | 下1/3 | horizon at lower third, sky dominant |
| 主体位置 | 左侧1/3交点 | left third intersection point |

**示例提示词：**
```
Solitary figure standing at left third intersection,
vast negative space to the right, horizon at lower third,
foreground tree branch silhouette, shallow DoF,
earth tones with pale cyan, side-backlighting, smoke scattering,
King Hu inspired composition, 2.35:1 Cinemascope
```

### 高定线构图（高端品牌广告）

| 元素 | 配方 | AI提示词 |
|------|------|----------|
| 负空间 | 60%+负空间 | 60% negative space, extreme minimalism |
| 地平线 | 极低/极高 | horizon at extreme edge |
| 主体比例 | 极小 | tiny subject, vast environment |
| 对称 | 正式对称为主 | perfect symmetry, formal balance |

**示例提示词：**
```
Single figure at center, 70% negative space,
horizon line at extreme bottom edge,
minimalist composition, Apple aesthetic,
natural light source, monochrome palette,
16mm film grain, slight overexposure
```

---

## 融合配方转提示词方法

### 步骤

1. **确定主体位置** → 三分法/黄金分割/偏心
2. **选择空间处理** → 负空间比例 + 框架元素
3. **添加线条引导** → 对角线/S曲线/汇聚线
4. **匹配色调氛围** → 色彩空间 + 光影质感
5. **指定比例格式** → 16:9 / 2.35:1 / 1:1

### 组合示例：胡金铨+王家卫

```
[主体] at golden ratio point, S-curve river leading to [焦点],
foreground bamboo obstruction, 40% negative space,
earth tones, pale cyan fog, side-backlighting,
long take, slow tracking shot, King Hu + Wong Kar-wai fusion,
2.35:1 Cinemascope, Kodak Ektachrome 1970s palette
```

---

## 构图提示词清单

### 正向提示词（Positive Prompts）

| 构图类型 | 关键词串 |
|----------|----------|
| 三分法 | rule of thirds, intersection point, power point |
| 黄金分割 | golden ratio, fibonacci spiral, golden section |
| 前景遮挡 | foreground obstruction, natural frame, bokeh foreground |
| 负空间 | negative space, minimalist, isolated figure, breathing room |
| 对角线 | diagonal composition, converging lines, dynamic angle |
| 三角构图 | triangular arrangement, pyramid composition |
| S曲线 | S-curve, serpentine path, flowing composition |
| 对称平衡 | bilateral symmetry, perfect mirror, formal balance |

### 反向提示词（Negative Prompts）

| 要避免 | 关键词 |
|--------|--------|
| 中心构图 | centered subject, symmetrical center, perfectly centered |
| 分割画面 | horizon dividing frame in half, equal halves |
| 拥挤构图 | cluttered frame, busy composition, too many elements |
| 平均分布 | evenly spaced elements, equal distribution |
| 直线分割 | straight dividing line, rigid grid |

---

## 平台适配

| 平台 | 构图提示词特点 |
|------|---------------|
| **Seedance** | 支持完整构图术语，可结合镜头运动 |
| **Vidu** | 中文友好，构图描述需简洁 |
| **Kling** | 擅长前景虚化，适合遮挡构图 |
| **海螺** | 对角线/曲线效果稳定 |

---

## 参考来源

- Wikipedia: Composition (visual arts) — 经典构图法则
- Wikipedia: Framing (visual arts) — 框架与前景遮挡
- Wikipedia: Axial cut — 轴向剪辑与景别变换
- 白梦客美学系统 — 通用线/高定线配方
