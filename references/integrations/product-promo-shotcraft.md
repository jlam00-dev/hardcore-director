# 产品与软件宣传片镜头词典

用于展示真实产品、软件界面、功能操作和前后效果。先读取用户的产品素材和表达目标，再选 1–3 个能传达该功能的镜头；需要渲染时衔接 [Remotion 适配器](remotion-production.md)，需要生成模型时进入 [模型路由器](../prompt-tools/model-router.md)。

本模块改编自 [Video ShotCraft](https://github.com/Vincentwei1021/video-shotcraft/tree/1266a3ec4831289c4d893d42dd5102723658039a)，保留镜头技法，重新整理成硬核导演的导演母版。固定审阅快照 `1266a3ec4831289c4d893d42dd5102723658039a`，审阅于 2026-11-03。Apache-2.0，Copyright 2026 Wei Yihao；[完整许可](../support/licenses/video-shotcraft-Apache-2.0.md)。未复制模板截图、音频、原片、Gallery 媒体或 Node/Remotion 执行工程。上游当前说明为124张卡，本包仍只选用下列10个镜头职责，其中1个保留为历史兼容来源，不把内部配方数量计为新增Skill。

## 先选镜头功能

| 卡名与固定来源 | 适合表达 | 起始 → 终止状态 | 实施时先检查 |
| --- | --- | --- | --- |
| [spotlight-hero-card](https://github.com/Vincentwei1021/video-shotcraft/blob/1266a3ec4831289c4d893d42dd5102723658039a/references/shots/opening/spotlight-hero-card.md) | 核心对象登场 | 全页 → 寻光锁定 → 推进、悬浮 → 归位定格 | 聚焦后主体全幅可读；光源、投影与同一机位一致；收尾由光呼吸而非相机漂移 |
| [crane-rise-reveal](https://github.com/Vincentwei1021/video-shotcraft/blob/1266a3ec4831289c4d893d42dd5102723658039a/references/shots/opening/crane-rise-reveal.md) | 从细节展示整体规模 | 可读的数据行 → 小幅预备 → 连续拉升后退 → 整体与状态余波 | 原卡约5.5秒；先让观众认出追踪行，再揭全局；一条运动进度控制机位和缩放，落定保留阅读时间 |
| [product-card-progressive-assemble](https://github.com/Vincentwei1021/video-shotcraft/blob/1266a3ec4831289c4d893d42dd5102723658039a/references/shots/ui-entrance/product-card-progressive-assemble.md) | 自动填表、商品结构化 | 填充光标 → 图/标题/字段到位 → 真实业务状态改变 → 完整卡片 | 原卡约5.7秒；视线跟随当前字段，不能同时塞进更多动作或演示不存在的能力 |
| [page-waterfall-wall](https://github.com/Vincentwei1021/video-shotcraft/blob/1266a3ec4831289c4d893d42dd5102723658039a/references/shots/ui-entrance/page-waterfall-wall.md) | 页面与模板数量 | 多列切片墙 → 差速反向流动 → 交棒到可读信息镜头 | 画面展示体量，文字细读放后镜；缩放后仍须按实际输出检查文字，不把实现技巧当清晰度保证 |
| [integration-hub-map](https://github.com/Vincentwei1021/video-shotcraft/blob/1266a3ec4831289c4d893d42dd5102723658039a/references/shots/ui-entrance/integration-hub-map.md) | 接入关系、版本焕新 | 旧页翻面 → 图标到位 → 连线接通 → 脉冲输送 | 产品是否支持所画连接；同时/依次接通要与真实语义一致；本卡未发现创作正文变化 |
| [type-and-filter](https://github.com/Vincentwei1021/video-shotcraft/blob/1266a3ec4831289c4d893d42dd5102723658039a/references/shots/interaction/type-and-filter.md) | 搜索到详情的操作因果 | 特写看清输入 → 呼吸位拉全景 → 筛选收敛 → 点击详情 | 输入可读后再看筛选结果；指针屏幕尺寸稳定，按实际字数分配时间 |
| [ai-stream-response，历史兼容](https://github.com/Vincentwei1021/video-shotcraft/blob/54ec8c39967deabca25d38ca928d89f286d12e99/references/shots/interaction/ai-stream-response.md) | AI 输出、证据、完成态 | 空面板 → 摘要落定 → 证据逐行出现 → 完成定格 | 上游2026-10已删除此卡；保留此前技法兼容，不称当前卡或已实战验证，不伪造处理速度 |
| [before-after-slider-scrub](https://github.com/Vincentwei1021/video-shotcraft/blob/1266a3ec4831289c4d893d42dd5102723658039a/references/shots/data/before-after-slider-scrub.md) | 同一输入的优化效果 | 静置与小幅预备 → 分割杆移动 → 暂停/慢扫 → after 定格 | 同机位、同输入和实际结果；预备动作服务对比，不能遮掉处理前状态 |
| [shot-transitions：焦点交接](https://github.com/Vincentwei1021/video-shotcraft/blob/1266a3ec4831289c4d893d42dd5102723658039a/references/shots/transition/shot-transitions.md) | 同一长页两个区块衔接 | A 清晰 → A 失焦、B 入场收焦 → B 清晰 | 按当前具体式核对，不沿用旧Gallery编号；相邻镜头分配转场预算，保持可观看对象 |
| [ui-strip-away-outro](https://github.com/Vincentwei1021/video-shotcraft/blob/1266a3ec4831289c4d893d42dd5102723658039a/references/shots/outro/ui-strip-away-outro.md) | 发布、完成、品牌落版 | 终结性操作 → 外围退场 → 按钮居中 → 字标停留 | 原卡约4.8秒，字标留至少1秒可读；按钮持续可见，普通保存不演成整个产品结束 |

原卡常见预算约2.5–6秒，不是固定平台限制。先把配方帧换回秒，再按项目FPS换成台账帧数：例如 `150帧@30fps = 5秒 = 120帧@24fps`。不能整帧表示时回分镜调整并复核总帧数，不能在提示词或渲染阶段偷改总长；相邻镜头的转场只计一次。读取卡片后仍须按真实素材检查节奏与可读性，不能照搬示例品牌、文案和假UI。

## 交付给下一阶段

每镜只记录：

```text
镜号 / 卡名 / 叙事功能
真实产品素材与批准版本
起始页面状态 → 操作或运动 → 终止页面状态
主视觉对象、运镜触发点、运动路径、停止点
时长、FPS、输入/动作时间、阅读停留、转场所占帧
准确文字、必须保真的界面结构、允许重组的布局
声音动作与最终编码要求
```

以上字段沿 [创作协作合同](creative-collaboration.md) 的现有场次/镜头身份交接，不另建格式。每镜说明“预备、主动作、可读结果”各占多少时间；选卡不能替换已确认的戏剧职责。形成镜头表后读取 [分镜机器门禁](storyboard-quality-gates.md)，再交给生成或渲染路径。精确还原某卡时才读取固定来源的具体卡与官方 TSX；链接不是已经安装或验证过的执行依赖。

声音交接到 [声音交接单](audio-cue-handoff.md)：记录镜号、对应动作/材质、目标时长、攻击与尾音、用户禁用项及许可要求。提示词阶段只接声音意图；后期阶段才接已核对的真实文件、入点、修改记录和署名。来源许可、元数据和波形不能代替实际试听。

## 实际验收

- 截图是目标产品且清晰，敏感数据已按用户要求处理；界面文字能读完。
- 点击、筛选、填入、状态变化体现真实功能和因果；不存在的产品能力不能靠动画补齐。
- 动画由时间线驱动；需要定格阅读时元素完全停止。
- 转场帧计入相邻镜头或总合成，不能凭空增加或重复计算。
- 本地镜头计划与 JSON 校验不使用外部 API、登录、付款或素材上传；真正渲染按 Remotion 软件许可执行。

## 来源与素材说明

镜头研究参考公开产品影片，公开观看不等于拥有复刻或素材授权。此包只参考技法、独立实施，不携带原品牌画面。更多出处见固定快照的 [shots/ATTRIBUTION.md](https://github.com/Vincentwei1021/video-shotcraft/blob/1266a3ec4831289c4d893d42dd5102723658039a/references/shots/ATTRIBUTION.md)。

上游已移除共享SFX库，改为Freesound选材及逐素材许可记录。可吸收“先写具体声源、再核许可/文件种类/修改与署名”的方法；本包未复制其搜索、下载、自动发布、音频或Node工程。默认不运行这些执行路径。用户要求外部选音时再核对实际服务与范围；CC0、CC BY、署名义务和下载种类逐素材确认，MP3预览不能称原始无损音源。保留上游发布适配器为外部参考，不将其接入本包默认调用链。
