<p align="center">
  <img src="./assets/hardcore-director-hero-v2.png" alt="硬核导演 — 影视与 AI 视频创作总控 Skill" width="100%" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Codex-Skill-111111?style=for-the-badge" alt="Codex Skill" />
  <img src="https://img.shields.io/badge/Version-2.2.0-4A7A5B?style=for-the-badge" alt="Version 2.2.0" />
  <img src="https://img.shields.io/badge/License-MIT-3D6B8E?style=for-the-badge" alt="MIT License" />
  <img src="https://img.shields.io/badge/Language-中文-D74A3A?style=for-the-badge" alt="中文" />
  <img src="https://img.shields.io/badge/Workflow-Film%20Production-30363D?style=for-the-badge" alt="Film Production" />
</p>

<h1 align="center">硬核导演 · Hardcore Director</h1>

<p align="center">
  面向 Codex / Agent 工作流的影视与 AI 视频创作总控 Skill。<br />
  从故事、人物与分镜，到生成提示词、声音、剪辑与发布，统一成一条可执行的制作链路。
</p>

---

<p align="center">
  <img src="./assets/detail-story-to-delivery.png" alt="从故事到交付 — 完整影视制作链路" width="100%" />
</p>

## 它不是“提示词大全”

`hardcore-director` 先判断你正处于哪个制作阶段，再读取当前真正需要的方法模块。

它解决的不是“再写一段更华丽的描述”，而是三个更具体的问题：

- **故事能不能成立**：人物有欲望，场景有阻力，转折由行动产生。
- **画面能不能执行**：主体、站位、动作方向、机位、光线、声音都能落到镜头。
- **成片能不能交付**：时长、连续性、平台格式、字幕、响度与发布表达都有复核门禁。

> 先解决叙事与可执行性，再叠加风格。

<p align="center">
  <img src="./assets/detail-command-center.png" alt="八大能力，一个中枢" width="100%" />
</p>

## 能力版图

| 制作阶段 | 可以交付什么 |
| --- | --- |
| 故事开发 | 高概念、梗概、人物弧光、世界观、长短片与多集结构 |
| 编剧与短剧 | 完整剧本、竖屏短剧、冲突升级、钩子、反转与爽点 |
| 角色与场景 | 角色 DNA、造型锚点、场景板、Blocking、空间与连续性 |
| 导演与分镜 | 景别、机位、构图、运镜、表演、微表情、镜头时长与声音 |
| AI 视频 | Seedance / 即梦 / Vidu / 可灵 / 海螺等平台的可执行提示词 |
| 视听风格 | 导演美学、色彩、调色、节奏、环境音、Foley 与 AI 配乐 |
| 分析与后期 | 拉片、竞品反推、实拍素材剪辑、字幕、混音与导出规格 |
| 内容发布 | 短视频脚本、黄金三秒、标题、封面建议与平台友好改写 |

## 工作方式

```text
你的想法 / 素材 / 剧本
        ↓
识别制作阶段与硬约束
        ↓
按需路由 2–5 个方法模块
        ↓
故事与视觉可执行性判断
        ↓
分镜 / 提示词 / 剪辑任务单
        ↓
连续性、时长、声音与平台复核
        ↓
可直接进入制作的交付物
```

它不会在一次回答里机械加载全部参考，而是按任务裁剪：一个主模块、一个平台适配器、最多两个专项增强。编剧先处理戏剧动作，分镜再处理空间与连续性，平台生成最后转换成对应语法。

旧版曾把 `references/` 下的 36 份顶层能力快照简称为“36 个 Skill”。准确口径是：其中 34 份对应当时的本机 Skill，另有 2 份是内部汇总模块；并非 36 份都有公开版本号或可查询上游。v2.1 已建立逐项账本，不再把“模块数”和“可自动更新依赖数”混算。

## v2.2 升级

v2.2.0 通过固定 GitHub Tag/Release 发行；v2.1.0 保留为历史版本。

v2.2 更新中文成稿润色与实拍剪辑规则，审阅并升级 Seedance 2.5 和 Suno v6 配乐适配器；新增 10 条产品/软件宣传片镜头词典、平台无关的分镜 JSON 门禁。顶层能力模块由 45 项变为 47 项。分镜脚本能检查时间、节拍、引用与状态声明，实际画面和音画仍须看验。

更新检查直接使用公开 HTTP 接口，不再临时下载 ClawHub CLI；清单还会追踪模型规则和镜头配方的内容依赖。具体来源、取舍与验收见 [v2.2 升级记录](audits/upgrade-review-v2.2.md)。

### v2.1 历史升级

- Seedance 2.5、Wan 3.0、MiniMax H3 三个独立提示词工具；
- 按“制作阶段 → 主模块 → 平台适配器 → 专项增强”重写调用路径；
- MiniMax H3 官方 T2VA / I2VA / FL2VA / L2VA / Ref2VA 固定 Schema；
- 独立分镜帧优先的交付包与连续性台账，多宫格改为按需选项；
- 更新 `short-drama-writer`、`creative-writing-cellcog`、传递依赖 `cellcog`，并按最新上游重构影视配乐适配器；
- 接入 SkillHub 高评分的 `video-generation-cellcog` 作为明确授权后的可选外部执行器；
- 接入高热度的官方 Remotion Skill 路由，补齐可编程视频、字幕、批量版本与确定性渲染；
- 接入 Higgsfield 非写实旁白解释视频路径，保留登录、上传和额度授权门禁；
- 为旧版 36 项建立全量状态账本；依赖清单、只读更新检查、包体校验、候选审计和第三方来源说明不再只覆盖 11 项。

## 安装与发布

v2.2.0 的固定发行源是 [GitHub Release](https://github.com/jlam00-dev/hardcore-director/releases/tag/v2.2.0) 与 `v2.2.0` Tag。Codex 完整包与 SkillHub 兼容包均可从 Release 下载；提供兼容包不等于已发布到 SkillHub 平台。本次发行范围为 GitHub。不要把持续变化的 `main` 当作固定版本。仓库原创部分采用 MIT；第三方快照和改编内容继续遵守各自许可证与来源说明。

安装后可直接点名调用：

```text
使用 $hardcore-director，把这个故事改成 90 秒竖屏短剧。
```

```text
使用 $hardcore-director，把这份剧本拆成可拍摄的分镜表。
```

```text
使用 $hardcore-director，把这组参考图变成角色稳定、动作连续的 AI 视频提示词。
```

```text
使用 $hardcore-director，拉片分析这个广告，并给出可复用的镜头、色彩和声音策略。
```

## 标准制作链路

1. **定义目标** — 观众、载体、时长、画幅和期望情绪。
2. **建立故事** — 人物欲望、阻力、转折、结局或 CTA。
3. **建立视觉圣经** — 角色、场景、色彩、材质、光线与一致性锚点。
4. **设计镜头** — 景别、机位、站位、动作方向、运镜、时长与声音。
5. **平台落地** — 转成生成提示词、拍摄单或剪辑任务单。
6. **质量复核** — 连续性、总时长、状态变化、声音同步与平台格式。
7. **交付成品** — 只输出当前阶段真正需要使用的版本。

<p align="center">
  <img src="./assets/detail-quality-gate.png" alt="先过门禁，再交付" width="100%" />
</p>

## 质量门禁

- 每场戏必须有目标、阻力和变化；对白不能替代戏剧动作。
- 抽象情绪必须转成眼神、呼吸、肌肉张力与身体动作。
- 多人物镜头必须写清站位、朝向、距离、受力与落点。
- 服装、妆发、伤痕、道具与光线方向必须保持前后连续。
- 镜头时长之和必须等于总时长，平台字段与画幅必须正确。
- 分析结论必须有时间码或镜头编号支撑，并区分观察与推断。

## 模型提示词路由

| 模型 | 处理重点 |
| --- | --- |
| Seedance 2.5 / 即梦 2.5 | 30 秒内叙事、多素材职责、长镜头、编辑、延长和终止状态 |
| Wan 3.0 | Omni 多模态参考、首尾帧路径、参考生视频、编辑与音画联合结构 |
| MiniMax H3 | 官方固定字段、关键帧对齐、全参考保留分析、严格音画时间线 |

三者先共用一份“导演母版”，再只加载一个目标模型的适配器。需要即梦界面最新专用语法时，可进一步调用 [`hc-sd2-5-prompt-writer`](https://github.com/jlam00-dev/hc-sd2-5-prompt-writer)。

Wan 3.0 的公开官方页面尚未给出一套固定字段规范，因此 v2.1 明确把它标成“本 Skill 制作模板”，不会把自定义标题冒充官方语法。

## 外部执行器边界

CellCog 长视频生产和 Higgsfield 解释视频只在用户明确接受对应服务商、素材上传、API key/登录和额度消耗后使用。Remotion 只在需要可编程、确定性视频时进入执行路径。默认只完成本地的创作、分镜、提示词与验收设计，不自动安装外部 Skill、不自动上传素材、不自动消费额度、不自动发布。

## 目录结构

```text
hardcore-director/
├── README.md
├── SKILL.md                  # 主入口、任务路由与质量门禁
├── VERSION                   # 2.2.0
├── agents/
│   └── openai.yaml           # Skill 展示信息
├── assets/
│   ├── hardcore-director-hero-v2.png
│   ├── detail-story-to-delivery.png
│   ├── detail-command-center.png
│   └── detail-quality-gate.png
├── audits/                   # GitHub / SkillHub 候选审计
├── manifests/                # 依赖版本、哈希与上游追踪
├── scripts/                  # 包体验证与只读更新检查
├── tests/                    # 更新检查脚本测试
└── references/
    ├── prompt-tools/         # SD2.5 / Wan 3.0 / MiniMax H3
    ├── integrations/         # 分镜交付等新集成
    ├── support/              # 原先缺失的嵌套参考
    └── *.md                  # 编剧、导演、视听、后期与发布方法库
```

## 维护检查

```bash
python3 scripts/validate_package.py
python3 -m unittest discover -s tests -v
python3 scripts/validate_storyboard.py references/support/storyboard-example.json --json
python3 scripts/check_updates.py --offline
python3 scripts/check_updates.py
```

`check_updates.py` 对所有顶层能力模块做哈希检查，并对存在公开上游的项目查询版本或提交；本机原创/内部模块明确标为不可自动升级，而不是从统计中消失。查询 GitHub、ClawHub 与平台页面时只读取公开信息，不安装 CLI。返回码：`0` 当前无异常，`1` 有本地漂移或发现更新，`2` 上游检查失败。某个次来源失败时仍保留已查到的主来源变化证据。

本地未提交的候选版可运行 `python3 scripts/build_skillhub_package.py --draft --output <新文件.zip>` 生成审阅包；默认正式包装仍要求工作树干净。包内版本从 `VERSION` 读取，并排除 SkillHub 已拒绝的 `.gitignore`、`LICENSE`、`VERSION` 无扩展名文件。许可证正文保存在 `.md` 文件中。

加 `--format codex` 生成完整 Codex 包，保留图片与标准许可证文件；两种包都有 `hardcore-director/` 根目录。构建已有同名文件时停止，不覆盖原包。

旧版 36 项的去向见 [`component-ledger-v1-to-v2.1.md`](./audits/component-ledger-v1-to-v2.1.md)，来源与许可证边界见 [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md)，发布门槛关闭记录见 [`publication-gate-v2.1.md`](./audits/publication-gate-v2.1.md)。

## 设计原则

- 叙事先于风格，行动先于解释。
- 平台规则优先于通用模板。
- 生成内容与后期操作分开描述。
- 风格、色彩、节奏与声音必须服务内容。
- 不把内部草稿当成交付物。

---

<p align="center">
  <strong>从一个想法，到一条能拍、能生成、能交付的片子。</strong>
</p>
