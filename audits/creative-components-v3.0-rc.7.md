# 创作组件全覆盖审阅与协作升级 · 3.0.0-rc.7

审阅日期：2026-11-03。基线为冻结的rc.6清单：47项原有组件，加1项既有远程制作模块，共48项。本页逐项覆盖这48项；本轮新增能力另按主清单登记，不把内部脚本或镜头配方数当作Skill数。

## 覆盖与实际改动

初次在线检查遍历48项：27项有公开来源、21项本机/原创来源；本地完整性问题0，3项可更新信号、5项来源审阅信号、1项来源错误。初次退出2，不能改写成零错误。后续通过作者限定官方API、公开页面和正文哈希核对，确定短视频脚本原作者为rascal6666，并修复查询owner传递。

初次审阅的21项本机/原创来源中，16项与已安装同名入口逐字节一致；3项差异只有本包已做的作者绝对路径可移植化；2项是本包原创兼容层，不预期存在同名独立安装。此结论仅证明初扫本机一致性，不宣称有公开版本或已是全网最新。独立创作前向审阅随后发现旧通用方法与当前模型/锁定需求冲突，rc.7对角色设计、视频提示词和声音提示词另补了明确兼容边界；未同步改写已安装的原独立Skill。

本组实际更新6个原组件的内容或边界适配：CellCog通用入口、外部创作、外部视频、Remotion、产品镜头词典、分镜门禁；另修复1个检查源身份，不算创作内容升级。未改原工作流生成、审批或合成运行代码；检查器变更按主清单重新计算完整性哈希。

## 基线48项逐项去向

最终装配在保留基线48项的基础上新增4个创作方法适配和1个原创协作层，主清单共53项。下面基线表仍逐项列原48项，不把许可证、脚本、Schema或同仓库不同参考文件另算Skill。

版本缩写只为排版，固定来源链接包含完整提交。source_watch变化经方法审阅后适配，不拿上游整文件覆盖本包合同。

| 基线组件 | 基线固定版本 | 处理状态 | 协作交接 | 固定来源与许可 |
| --- | --- | --- | --- | --- |
| ai-music-generator | adapter:2.2.0/Suno-v6-reviewed | 配置的公开路径/版本未见变化；保留 | 节拍/视听约束 → 声音cue或节奏/色彩意图 → 提示词/后期 | [固定源](https://github.com/bitwize-music-studio/claude-ai-music-skills/blob/3b292b08776796f593d7abf816c19a9ff652733d/skills/suno-engineer/SKILL.md)；package-original; upstream CC0-1.0 |
| ai-scene-design | local-unversioned | 本机同名入口逐字节一致；保留 | 剧本/连续性锚点 → 人物/场景依据 → 调度/分镜 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| ang-lee-perspective | local-unversioned | 本机同名入口逐字节一致；保留 | 故事与视觉方向 → 可观察导演选择 → 分镜/提示词 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| cellcog | 2.0.21 | 有界原创适配升级：2.0.21 → 依据2.0.26；显式档位/无可靠额度上限不提交；不接雇员、浏览器或co-work | 服务选择/稿件范围/费用边界 → 外部结果 → 本地创作或终审 | [固定源](https://clawhub.ai/cellcog/skills/cellcog)；MIT-0 |
| character-design | 5.0 | 初扫本机一致；rc.7按原模块可选开关设置watermark:false，保留文档归属，区分文字方案与完整角色资产门禁 | 身份/外观不变量 → 共享锁定状态；剧情暂态 → 导演逐镜状态 | 本机来源、无公开版本；原MIT与作者署名保留，本包兼容修订另记 |
| composition-to-prompt | local-unversioned | 本机同名入口逐字节一致；保留 | 剧本节拍/视觉依据/画幅时长 → 镜头职责/状态/引用 → 提示词/制作计划 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| douyin-safety-rewriter | adapter:local | 配置的公开路径/版本未见变化；保留 | Brief/事实/平台 → 可审脚本/文案 → 分镜或用户发布 | [固定源](https://github.com/CCCpan/chinese-sensitive-words-mcp/blob/c7abcbf7fce7b2cb522dd4e66e4a2ebd054338c2/README.md)；package adapter; upstream MIT |
| douyin-script | local-unversioned | 本机同名入口逐字节一致；保留 | Brief/事实/平台 → 可审脚本/文案 → 分镜或用户发布 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| douyin-viral-planner | adapter:local | 配置的公开路径/版本未见变化；保留 | Brief/事实/平台 → 可审脚本/文案 → 分镜或用户发布 | [固定源](https://github.com/yaojingang/yao-open-prompts/blob/c7758f7076484e0ee0be393cbe4a138bc4beeab6/prompts/06-ai-content/douyin-viral-planner.md)；package adapter; upstream MIT |
| drama-creator | git:d53e7c305643 | 配置的公开路径/版本未见变化；保留 | Brief/事实/格式 → 结构/场次/节拍 → 导演/分镜 | [固定源](https://github.com/VanGong1999/screen-creative-skills/blob/d53e7c305643bbc6f9c23e1e0f0b647d66ba3594/category/creation/drama-creator/SKILL.md)；MIT |
| drama-evaluator | git:d53e7c305643 | 配置的公开路径/版本未见变化；保留 | Brief/事实/格式 → 结构/场次/节拍 → 导演/分镜 | [固定源](https://github.com/VanGong1999/screen-creative-skills/blob/d53e7c305643bbc6f9c23e1e0f0b647d66ba3594/category/evaluation/drama-evaluator/SKILL.md)；MIT |
| drama-planner | git:d53e7c305643 | 配置的公开路径/版本未见变化；保留 | Brief/事实/格式 → 结构/场次/节拍 → 导演/分镜 | [固定源](https://github.com/VanGong1999/screen-creative-skills/blob/d53e7c305643bbc6f9c23e1e0f0b647d66ba3594/category/creation/drama-planner/SKILL.md)；MIT |
| humanizer-zh | git:f4518a8eab97 | 配置的公开路径/版本未见变化；保留 | Brief/事实/平台 → 可审脚本/文案 → 分镜或用户发布 | [固定源](https://github.com/op7418/Humanizer-zh/blob/f4518a8eab97b8bfebc66a89d34320a89bef6930/SKILL.md)；MIT |
| higgsfield-explainer | adapter:3.0.0-rc.1/upstream:0.14.0 | 配置的公开路径/版本未见变化；保留 | 锁定文案/时间线/素材 → 预览/工程 → 后期与终审 | [固定源](https://github.com/higgsfield-ai/skills/blob/eac5c12137e47a157a8a3c11865fd9bc02e4ec13/higgsfield-video-explainer/SKILL.md)；package-original; upstream MIT |
| remotion-production | adapter:3.0.0-rc.1/upstream:4.0.539 | 原创适配更新：路由4.0.539 → 4.0.540观察；许可导航/共享交接，未复制上游代码 | 锁定文案/时间线/素材 → 预览/工程 → 后期与终审 | [固定源](https://github.com/remotion-dev/skills/blob/30d4553ecd46fbc5212fd0ff006ae43af522158b/skills/remotion-best-practices/SKILL.md)；package-original; upstream license unverified |
| storyboard-package | adapter:2.2.0 | 原配置来源未变；本包增加导演到关键帧、真实REF与PLAN、世界空间及实测take交接 | 导演处理/视觉依据 → 分镜状态/真实参考 → 平台提示词和剪辑计划 | Agentara基线保留，另参考Zenstory与video-take-review；固定路径及MIT许可见主清单 |
| jackyshen-gen-short-video-script | git:e4794d7ba683 | 配置的公开路径/版本未见变化；保留 | Brief/事实/平台 → 可审脚本/文案 → 分镜或用户发布 | [固定源](https://github.com/mebusw/awesome-jackyshen-skills/blob/e4794d7ba683fb7ffcdae0c8e1657be47aa0f816/skills/jackyshen-gen-short-video-script/SKILL.md)；MIT |
| king-hu-perspective | local-unversioned | 仅作者绝对路径已可移植化；保留本包版 | 故事与视觉方向 → 可观察导演选择 → 分镜/提示词 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| legacy-filmmaking-v1 | 2.1.0 | 原创兼容层；无独立同名入口属预期 | 明确旧入口 → 当前方法路由；不要求同名独立安装 | 本机/原创，无公开版本源；MIT; original compatibility layer |
| miyazaki-perspective | local-unversioned | 本机同名入口逐字节一致；保留 | 故事与视觉方向 → 可观察导演选择 → 分镜/提示词 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| minimax-h3-prompt-tool | git:35491cdba2ad | 配置的公开路径/版本未见变化；保留 | 分镜/参考职责/实时模式 → 参数与prompt → 生成请求预览 | [固定源](https://github.com/MiniMax-AI/MiniMax-H3/blob/35491cdba2adfe62a510f725e8619f8e58783ea2/skills/h3-prompt-writing/references/base-en.txt)；package-original; upstream license unverified |
| model-prompt-router | adapter:2.2.0 | 原配置来源未变；本包接入共享摘要、对白及cue投影，不更新模型能力声明 | 当前分镜/声音cue/参考职责 → 一个目标平台的prompt → 生成请求预览 | [原固定源](https://github.com/Square-Zero-Labs/video-prompting-skill/blob/15e4b3cefa83a1e7e80d3447908e104a64461173/video-prompting/SKILL.md)；Apache-2.0与本包原创交接 |
| seedance-2.5-prompt-tool | adapter:2.2.0 | 审阅无语义变化：MODE-PLAYBOOKS 54a18665a4c9 → e5db5d970fa6，仅新增目录，不改模式/提示词 | 分镜/参考职责/实时模式 → 参数与prompt → 生成请求预览 | [固定源](https://github.com/Square-Zero-Labs/video-prompting-skill/blob/e596f57274c47540d0d215fea9afe361079f2354/video-prompting/references/models/seedance2-5/prompting.md)；package-original; adapted sources Apache-2.0 and MIT |
| wan-3.0-prompt-tool | 2.1.0 | 能力变化未证实：官方前端1.0.91 → 1.0.95，仅构建信号，未取得可读模型发布说明 | 分镜/参考职责/实时模式 → 参数与prompt → 生成请求预览 | [固定源](https://create.wan.video/explore)；package-original |
| rhythm-to-prompt | local-unversioned | 本机同名入口逐字节一致；保留 | 节拍/视听约束 → 声音cue或节奏/色彩意图 → 提示词/后期 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| screenwriter | 2.1.0 | 配置的公开路径/版本未见变化；保留 | 分镜/参考职责/实时模式 → 参数与prompt → 生成请求预览 | [固定源](https://github.com/macrochen/seedance-screenwriter-skills/blob/a9ab4db14be0c3ac7b84a55bac10c9df4aa504ef/.claude/skills/screenwriter/SKILL.md)；package-original; upstream license unverified |
| seedance-perform-v5-single | 2.1.0 | 原创兼容层；无独立同名入口属预期 | 明确旧入口 → 当前方法路由；不要求同名独立安装 | 本机/原创，无公开版本源；MIT; original compatibility adapter |
| shanyin-screenwriting | 1.0.0 | 本机同名入口逐字节一致；保留 | Brief/事实/格式 → 结构/场次/节拍 → 导演/分镜 | 本机/原创，无公开版本源；MIT; local attribution |
| short-drama-writer | 2.3.6 | 配置的公开路径/版本未见变化；保留 | Brief/事实/平台 → 可审脚本/文案 → 分镜或用户发布 | [固定源](https://clawhub.ai/ckchzh/skills/short-drama-writer)；MIT-0 |
| short-video-hook-lab | 2.1.0 | 配置的公开路径/版本未见变化；保留 | Brief/事实/平台 → 可审脚本/文案 → 分镜或用户发布 | [固定源](https://clawhub.ai/skills/short-video-hook-lab)；package-original; old snapshot excluded due license conflict |
| short-video-script | 1.0.1 | 源身份消歧：同为1.0.1，正文SHA相同；@rascal6666和?owner=；不计内容升级 | Brief/事实/平台 → 可审脚本/文案 → 分镜或用户发布 | [固定源](https://clawhub.ai/rascal6666/skills/short-video-script)；MIT-0 |
| sound-design-to-prompt | 1.0 | 初扫本机一致；rc.7将旧泛称平台音频表/比例标为历史经验，具名模型合同与用户无BGM约束优先 | 当前分镜/cue → 实际prompt声音短句或后期cue → 平台/EDL | 本机/原创，无公开版本；MIT及本包兼容修订 |
| creative-writing-cellcog | 1.0.15 | 快照+边界升级：1.0.15 → 1.0.17；flash显式参数纠错，外部草稿回本地审阅 | 服务选择/稿件范围/费用边界 → 外部结果 → 本地创作或终审 | [固定源](https://clawhub.ai/cellcog/skills/creative-writing-cellcog)；MIT-0 |
| story-master | 2.1.0 | 配置的公开路径/版本未见变化；保留 | Brief/事实/格式 → 结构/场次/节拍 → 导演/分镜 | [固定源](https://clawhub.ai/skills/story-master)；package-original; old snapshot excluded due missing license |
| style-fusion | 1.0 | 本机同名入口逐字节一致；保留 | 故事与视觉方向 → 可观察导演选择 → 分镜/提示词 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| stylized-color-grading | 1.0 | 本机同名入口逐字节一致；保留 | 节拍/视听约束 → 声音cue或节奏/色彩意图 → 提示词/后期 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| takeshi-kitano-perspective | local-unversioned | 本机同名入口逐字节一致；保留 | 故事与视觉方向 → 可观察导演选择 → 分镜/提示词 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| tarkovsky-perspective | local-unversioned | 本机同名入口逐字节一致；保留 | 故事与视觉方向 → 可观察导演选择 → 分镜/提示词 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| tint-to-prompt | 1.0 | 本机同名入口逐字节一致；保留 | 节拍/视听约束 → 声音cue或节奏/色彩意图 → 提示词/后期 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| video-analysis | local-unversioned | 本机同名入口逐字节一致；保留 | 获准源片/分析范围 → 时间码事实与解释 → 导演/分镜/参考职责 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| video-editing | git:928c1dea72f5 | 配置的公开路径/版本未见变化；保留 | 锁定文案/时间线/素材 → 预览/工程 → 后期与终审 | [固定源](https://github.com/affaan-m/ECC/blob/928c1dea72f5c330442fc1f595563398b8f389f7/skills/video-editing/SKILL.md)；MIT |
| video-generation-cellcog | 1.0.18 | 快照+边界升级：1.0.18 → 1.0.19；flash显式参数纠错，不默认重跑max | 服务选择/稿件范围/费用边界 → 外部结果 → 本地创作或终审 | [固定源](https://clawhub.ai/cellcog/skills/video-generation-cellcog)；MIT-0 |
| video-prompt-writer | local-unversioned | 初扫差异仅路径可移植化；rc.7增加旧15秒/强制密度/必改灯光规则的适用边界，不覆盖当前平台或锁定brief | 当前分镜/逐字对白/cue → 唯一平台表达 → 生成草稿 | 本机/原创，无公开版本；MIT及本包兼容修订 |
| video-reverse-engineer | local-unversioned | 仅作者绝对路径已可移植化；保留本包版 | 获准源片/分析范围 → 时间码事实与解释 → 导演/分镜/参考职责 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| wong-kar-wai-perspective | local-unversioned | 本机同名入口逐字节一致；保留 | 故事与视觉方向 → 可观察导演选择 → 分镜/提示词 | 本机/原创，无公开版本源；MIT; publisher-confirmed authorship 2026-09-05 |
| product-promo-shotcraft | adapter:2.2.0/10-shot-recipes | 方法适配升级：SKILL路径5f047c7cfe10 → 1266a3ec4831；动作阶段/可读停留/声音交接；9现行+1历史配方 | 剧本节拍/视觉依据/画幅时长 → 镜头职责/状态/引用 → 提示词/制作计划 | [固定源](https://github.com/Vincentwei1021/video-shotcraft/blob/5f047c7cfe10d6616fe59160a750fcfaea510b2e/SKILL.md)；Apache-2.0; adapted and attributed |
| storyboard-quality-gates | adapter:2.2.0/contract:1 | 方法适配升级：06f25952fe8d → 1084e66bc606；单一画幅+Zenstory分镜方法；JSON v1和校验器保留 | 剧本节拍/视觉依据/画幅时长 → 镜头职责/状态/引用 → 提示词/制作计划 | [固定源](https://github.com/eternityspring/shuohao-skills/blob/06f25952fe8d359065245194427bd1fc5f7b34d8/skills/novel-storyboard/SKILL.md)；package-original; upstream concepts Apache-2.0 |
| remote-production-workflow | 3.0.0-rc.6 | 既有执行代码保留；配置来源未见路径变化 | 获准计划/素材/范围 → 任务/媒体/审批回执 → 执行器与终审 | [固定源](https://github.com/Tencent/openclaw-weixin/blob/b1779c43ec19e02cd770d927c4caad7ea3e13611/docs/protocol_zh_CN.md)；MIT original implementation; optional official SDKs and service terms remain separate |


## 实质变化与合同边界

- 产品镜头词典吸收预备→主动作→可读结果、追踪焦点、落定余波与声音来源交接。源卡30fps帧号先换为秒，再映射项目FPS并回算总长；不照搬品牌文案、假UI、音频下载或自动发布。上游由157卡缩为124卡，ai-stream-response已删除，本包留为明确历史兼容来源，固定旧提交54ec8c39967deabca25d38ca928d89f286d12e99，不将其继续当现行依赖。
- 分镜方法以项目aspect_ratio为单一来源，贯通分镜、关键帧、模型参数和报告；保留本包JSON v1及既有合法画幅。追加真实场景/节拍覆盖、世界空间锚点、首帧不偷跑终点、同一可见主体清单与修订身份的方法检查，不声称旧校验器已自动检查这些导演语义。
- CellCog通用入口改成依据2.0.26的短原创边界适配，不整版复制SDK手册。当前源观察缺省core；显式chat_tier，无法核实费用上限则停在本地方案；未接入雇用、浏览器、co-work或客服外发。两个小组件完整同步1.0.17/1.0.19并加调用边界，只属flash参数纠错，不冒称新增编剧算法。任何外部结果仍回本地复核，不默认重跑max。
- Remotion上游4.0.540本次仅增加许可参考入口；本包增加共享创作/声音交接并保持先预览。仓库API未返回标准根许可证，未复制上游代码；软件自身许可另按用户实际主体核对。
- Seedance额外源仅目录变化，不改变模式和prompt；Wan前端版本变化不是模型能力证据。两项来源审阅与实际创作更新分开记录。

## 来源、可信信号与服务影响

| 来源 | 本次可核实信号 | 许可与接入边界 |
| --- | --- | --- |
| [Video ShotCraft](https://github.com/Vincentwei1021/video-shotcraft) | 16136星；实际方法更新、共享SFX移除及配方退役 | Apache-2.0。Freesound预览搜索源说明无需API key；本包仅吸收选材/许可/文件种类与署名方法，未下载、未试听。原始文件与发布服务按实际入口另核许可/账号；不接自动发布 |
| [shuohao-skills](https://github.com/eternityspring/shuohao-skills) | 5889星；aspectRatio贯通seed/出图/报告 | Apache-2.0。只吸收方法，不采用固定15秒/H3方言，也不缩窄全包画幅 |
| [drama-skills](https://github.com/zenstory-ai/drama-skills/tree/d8a9a9b5f5fa0e46dc2644d55879d1c984ff70e6) | storyboard路径最后提交17dbb47865fcca836913e23d47a66cf298a0a2a2；场次视觉/覆盖参考c9f46c6aef614dfb3a4d5aaeae809f06c1dc070f | MIT，Copyright (c) 2026 drama-skills contributors；见[许可](../references/support/licenses/drama-skills-MIT.md)。不继承目录/标点格式、默认英语、Seedance2.0槽位或生产权限 |
| [Remotion官方Skill](https://github.com/remotion-dev/skills) | 6076星；4.0.540许可路由 | 根许可证未核实，继续原创适配。实际软件许可查[官方说明](https://www.remotion.dev/docs/license.md)，无自动安装或购买 |
| [Seedance模式参考](https://github.com/OSideMedia/higgsfield-ai-prompt-skill) | 841星；本次只有目录变化 | MIT；本包已有其他来源Apache-2.0/MIT分别保留 |
| [CellCog](https://clawhub.ai/cellcog/skills/cellcog) / [外部创作](https://clawhub.ai/cellcog/skills/creative-writing-cellcog) / [外部视频](https://clawhub.ai/cellcog/skills/video-generation-cellcog) | 分别535/264/302安装，8/19/25星；2.0.26/1.0.17/1.0.19 | 官方文档MIT-0；远端任务需要用户账号/key，credits不可预测。没有安装、连接、雇用、上传或付费联调，SDK/MCP出现不等于范围或额度授权 |
| [短视频脚本原作者页](https://clawhub.ai/rascal6666/skills/short-video-script) | 1.0.1，132安装/6星；与本包正文SHA完全一致 | MIT-0。正文SHA为6cd21325f29bacc6c5fe0981b4c15ea447d955a645f72f0f7761809ce02be8cf；petehuax同名1.0.0内容不同，未切换作者 |

上述数字为本次观察，不是显著升星的时间序列证明。未重查热度的保留项只按固定来源/内容一致性判断，不编造安装量或公开新版本。

## 串成同一创作流程

[创作协作合同](../references/integrations/creative-collaboration.md) 是唯一共享交接：Brief/事实 → 剧本与节拍 → 导演选择/视觉依据 → 同ID分镜 → [声音cue](../references/integrations/audio-cue-handoff.md) → 平台参数与prompt → [叙事剪辑计划](../references/integrations/narrative-edit-handoff.md) → 零预算待审执行草稿。真实生成后再用实际素材窗口补后期交接、人工终审。模块只输出自己阶段的成果，已接受上游由原阶段修订；文字交接不会扩大生成、上传、收费或发布许可。

画幅/FPS/总帧数从项目传到底，场次、节拍、人物/道具及镜号可追溯。图片提示词项和挂图计划不冒充真实文件；真实文件也不自动授权上传。上游内容变化会使依赖它的阶段摘要过期；保留未受影响的镜号、内容与素材，复核受影响部分后再更新阶段交接，不要求全部重生成。

## 新增的4个方法模块与1个协作层

| 新模块 | 上一步输入 → 本阶段输出 → 下一位消费者 | 采用来源与当次可信信号 |
| --- | --- | --- |
| screenplay-diagnosis | 当前剧本/节拍/对白 → 有证据的最小改单 → 原编剧修订、导演处理 | [sw-scene-craft](https://github.com/jtydhr88/screenwriting-skills/blob/ffb70c3cd154a599d5e020351debb5d8a7636118/plugins/screenwriting/skills/sw-scene-craft/SKILL.md)，仓库1933星；[单项399次安装](https://skills.sh/jtydhr88/screenwriting-skills/sw-scene-craft)，9月实质更新；MIT与NOTICE分开保留，不复制书籍/译本引文 |
| director-blocking-coverage | 锁定剧本/角色 → 站位、视线、表演、覆盖与端点状态 → 分镜 | [DirectorSKILL](https://github.com/wuwangzhang1216/DirectorSKILL/tree/c65ae0d14457053efb1e354c7e7f7e120d97fad1)，仓库307星、[单项120安装](https://skills.sh/wuwangzhang1216/directorskill/cinematic-director)；另吸收[表演时序](https://github.com/kangarooking/director-skills/tree/301e6e72199f28b8ea82cd48ff06ab9ae49d0ee5)（仓库257星、单项22安装），并入同一导演模块，均MIT |
| audio-cue-handoff | 当前分镜/逐字对白/声音禁用项 → cue ID、时窗、来源与平台化短句 → 视频prompt或后期 | [video-production-skills](https://github.com/konradre/video-production-skills/tree/cd92701fd52fbfa668f2247687b32d0f85506fda)，9月建立、10月实质维护、仓库仅7星；MIT，按交接缺口选择，不宣传高星；不继承外部付费或声音克隆流程 |
| narrative-edit-handoff | 节拍/镜号/声音cue/实际take窗口或待测声明 → 有来源的剪辑计划 → 原剪辑/Remotion/剪映路径 | 同一MIT来源的独立后期交接能力；没有实际素材窗口时保持计划，不提供自动变速、循环、混音或渲染权限 |
| creative-collaboration | 各阶段共享项目包 → 来源/ID/状态/对白/声音投影检查 → 既有Engine格式的零预算草稿 | 本包原创；编译器、Schema、示例与分镜校验脚本纳入完整性追踪；不调用模型或媒体服务 |

星标为来源仓库当次总量，安装量为上游具体Skill，不是本包新适配器的安装量；没有历史星标快照，不声称显著升星。共用一个来源的声音与剪辑模块分别负责生成前意图及生成后素材交接，不把同仓库15项全部导入。

## 检索覆盖与未采用项

检索覆盖GitHub、腾讯SkillHub、skills.sh与ClawHub。GitHub为有限相关性检索；SkillHub对“分镜、编剧、导演、screenwriting、storyboard”各读取下载排序首12条，并深查候选，不宣称遍历整个平台。skills.sh单项页面已用匿名HTTPS核对；ClawHub用于源身份、版本及明确许可核对。

- SkillHub的 `novel-to-storyboard` 只有4月首发能被证明，11月目录更新时间不能当作近90天能力更新；未采用。
- `novel-to-drama` 有8月运镜更新，但读取的22文件与Skill未给出清楚许可证；未复制入包。
- `screenwriting-master` 同时写MIT和禁止商用限制，且与既有山音模块重叠；未采用。
- ClawHub `script-to-storyboard` 官方卡为MIT-0，但仅拆表，未补足本包连续性/调度缺口；目录更新时间口径亦不一致，未作为新能力导入。
- 其他仅词汇重叠、近期维护不符合、许可待核实或需要另行安装执行器的项目，保留筛选记录，不凭数量加入。

## 当前整体检查

独立导演前向使用中还发现：通用提示词旧15秒上限与Seedance 2.5适配器不一致，强制每段动作/环境/灯光变化不适合用户已锁的静止表达；旧声音泛表不能判断当前具名模型音频；角色资料的完整三视图门禁不适用于只有文字的方案。前向案例按入口优先级正确保留锁定需求，根再给这3份旧方法增加兼容边界，保留原文及作者归属，不冒称它们收到公开上游更新。

源码全量293项测试通过（5.849秒、0跳过），独立HOME及Python socket guard观测网络尝试0。包校验、官方Skill快速校验、差异检查和离线53项完整性通过。最终在线检查覆盖53项（31公开来源、22本机/原创），本地问题、可更新、待审阅及来源错误均为0；该结果只针对本清单配置来源及本次观察时点。

40秒四镜自创示例已实际检查、导出并导入现有Engine，`tick`仍停在方案审核，0操作、预算0/UNAPPROVED。改剧本后5段交接过期、拒绝导出。独立代码审查发现并修复导出失败可能删除并发文件的问题，单文件staging写入同步后独占发布的两项失败复现已通过。

独立导演Agent另以新的32秒四镜需求完整串测，未复制自带示例：左手信封、右手黑伞、先挡雨后说唯一对白、无BGM等锁定项传到分镜、实际声音短句、提示词与剪辑计划；最终packet-v2检查及导出无issues/warnings。导入独占Engine、重新导入到revision2并tick后仍为plan_review，4镜均未批准、0操作、预算0/UNAPPROVED。

该案例在机器首次通过后，导演Agent复核发现剧本“抬眼”与分镜“向下看”语义矛盾，按最早上游退回script，只改冲突语句，保留v1，逐段复核并更新5段依赖后导出v2。这展示了协作回退的实际用法，也证明机器摘要不理解叙事语义。此处“导演复核”由独立Agent执行，不是用户真人创作接受。

本次导入兼容的是原有先分镜图后视频流程，不证明纯T2V跳过生图/审图直通；EDL与后期雨底仍为计划，没有真实素材窗口、混音或渲染。真实画面、表演、平台语法/运行和听感未测。完整证据与装包后复验以最终候选验收收据记录，不据此声称真实媒体生成或商业成片验收。

## 本组验证与未覆盖部分

更新检查器专项17项通过、0跳过，覆盖限定作者消歧、保持裸slug行为、不猜选冲突作者及既有owner mismatch拒绝。真实只读owner限定查询已返回1.0.1。完整包检查与新共享合同的独立行为验证由主协调器另行完成，不在本页提前宣称。

本组未安装CLI/SDK、未登录、未读取key、未外发稿件/媒体、未消费生成额度、未构建或发布安装包。新增导演语义仍需创作者看验；文档更新不等于真实画面提升，脚本通过不等于模型生成、手机联调或用户终审通过。
