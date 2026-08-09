---
name: style-fusion
description: 输入两个风格代码，自动融合B×A矩阵参数，输出平台化提示词
version: v1.0
date: 2026-04-11
inputs: b_code (B1-B5), a_code (A1-A4), platform, duration
outputs: JSON Schema + 平台化提示词
---

# Style Fusion — B×A 风格融合提示词生成器

## 功能

接收两个风格代码，自动从 B×A 矩阵查询/融合参数，输出针对 Seedance / Vidu / 海螺 / MidJourney 优化的视频提示词。

## 输入参数

| 参数 | 必填 | 选项 | 说明 |
|------|------|------|------|
| `b_code` | 是 | B1-B5 | B系列风格代码 |
| `a_code` | 是 | A1-A4 | A系列风格代码 |
| `platform` | 否 | seedance / vidu / hairui / mj / all | 目标平台，默认 all |
| `duration` | 否 | 5 / 10 / 15 / 30 | 视频时长(秒)，默认 15 |

## B系列风格

| 代码 | 风格 | 定位 |
|------|------|------|
| B1 | 超现实 + 色域绘画 + 生物形态 | 通用线·生物形态抽象 |
| B2 | 赛博朋克 + 故障艺术 + 欧普艺术 | 数字视觉·感知扭曲 |
| B3 | 梦核 + 蒸汽波 + 超现实 | 复古未来·数字怀旧 |
| B4 | 极简 + 装饰艺术 + 新古典 | 高定线·克制奢华 |
| B5 | 怪核 + 童核 + 苍白核 | 失落童心·可爱恐怖 |

## A系列风格

| 代码 | 风格 | 融合核心 |
|------|------|----------|
| A1 | 胡金铨 × Hollywood Golden Age | 禅意静谧 × 戏剧张力 |
| A2 | 王家卫 × French New Wave | 记忆碎片 × 存在自由 |
| A3 | 北野武 × German Expressionism | 沉默暴力 × 阴影戏剧化 |
| A4 | 李安 × Western Modernism | 东方克制 × 视觉诗意 |

## 融合矩阵

|  | A1 胡金铨×Hollywood | A2 王家卫×French NW | A3 北野武×German Exp | A4 李安×Western Mod |
|--|---------------------|---------------------|---------------------|---------------------|
| **B1** 超现实 | B1×A1 | B1×A2 | B1×A3 | B1×A4 |
| **B2** 赛博 | B2×A1 | B2×A2 | B2×A3 | B2×A4 |
| **B3** 梦核 | B3×A1 | B3×A2 | B3×A3 | B3×A4 |
| **B4** 高定 | B4×A1 | B4×A2 | B4×A3 | B4×A4 |
| **B5** 童心 | B5×A1 | B5×A2 | B5×A3 | B5×A4 |

## 使用方式

### CLI（推荐）

```bash
python3 ~/.Codex/skills/style-fusion/fusion.py B2 A3 --platform seedance
python3 ~/.Codex/skills/style-fusion/fusion.py B4 A1 --platform all
python3 ~/.Codex/skills/style-fusion/fusion.py B5 A2 --platform mj
```

### Python API

```python
import sys
sys.path.insert(0, "~/.Codex/skills/style-fusion")
from fusion import StyleFusion

engine = StyleFusion()
fusion = engine.get_fusion("B2", "A3")
schema = engine.to_schema(fusion, "我的融合项目")
print(engine.to_seedance(schema))
```

## 输出示例

```
============================================================
  STYLE FUSION: B2×A3
  融合核心: 表现主义阴影码头——压抑暴力泄漏为故障
  来源: exact
============================================================

--- SEEDANCE 提示词 ---
白梦客[数字视觉·感知扭曲]，表现主义阴影码头——压抑暴力泄漏为故障。

[核心场景]: Takeshi Kitano × German Expressionism × Cyberpunk glitch...
色调：北野武蓝灰40%，德表高对比黑白30%，赛博冷蓝/电紫20%
光影：German Expressionist chiaroscuro, theatrical shadow, digital interference
构图：extreme minimalist, deep noir shadows
质感：Op Art geometric patterns emerging from shadows
节奏：violence has happened, silence as aftermath

参考：北野武, German Expressionism
格式：16:9，475风格值

--- MIDJOURNEY PROMPT ---
Takeshi Kitano × German Expressionism × Cyberpunk glitch... --ar 16:9 --s 450-500
```

## 融合逻辑

| 情况 | 策略 | 说明 |
|------|------|------|
| 矩阵已有组合 (20个) | exact lookup | 返回预定义融合，含 sample prompts |
| 非矩阵组合 | interpolation | B 60% + A 40% 加权融合 |

## 质量检查清单

生成后逐项确认：

```
□ 色调有主色+辅色+点缀色
□ 光影包含方向+氛围
□ 构图包含比例数字（70%、60%等）
□ 节奏包含时间分布
□ 质感包含机型+颗粒参数
□ 无情绪标签（紧张/愤怒/悲伤）
□ 无因果逻辑词（因为/所以/为了）
□ 无抽象概念（希望/梦想/自由）
□ 无文字/字幕/LOGO
□ 无未量化变化（变亮/变大/变快）
```

## 文件结构

```
~/.Codex/skills/style-fusion/
├── SKILL.md              # 本文件
├── fusion.py            # 融合引擎 + CLI
└── style-database.json  # B×A 矩阵数据（20个融合）
```
