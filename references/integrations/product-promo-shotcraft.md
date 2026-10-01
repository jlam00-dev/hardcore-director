# 产品与软件宣传片镜头词典

用于展示真实产品、软件界面、功能操作和前后效果。先读取用户的产品素材和表达目标，再选 1–3 个能传达该功能的镜头；需要渲染时衔接 [Remotion 适配器](remotion-production.md)，需要生成模型时进入 [模型路由器](../prompt-tools/model-router.md)。

本模块改编自 [Video ShotCraft](https://github.com/Vincentwei1021/video-shotcraft/tree/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab)，保留镜头技法，重新整理成硬核导演的导演母版。固定仓库快照 `5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab`，审阅于 2026-10-01。Apache-2.0，Copyright 2026 Wei Yihao；[完整许可](../support/licenses/video-shotcraft-Apache-2.0.md)。未复制模板截图、音频、原片、Gallery 媒体或 Node/Remotion 执行工程。

## 先选镜头功能

| 卡名与固定来源 | 适合表达 | 起始 → 终止状态 | 实施时先检查 |
| --- | --- | --- | --- |
| [spotlight-hero-card](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/opening/spotlight-hero-card.md) | 核心对象登场 | 全页正视 → 聚光锁定单卡 → 侧向推进、悬浮 → 归位定格 | 截图放大后的清晰度、单一视觉焦点、收尾停止漂移 |
| [crane-rise-reveal](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/opening/crane-rise-reveal.md) | 从细节展示整体规模 | 数据行特写 → 相机升起后退 → 完整 dashboard | 动画只在该行进入可见区时触发；终点留阅读时间 |
| [product-card-progressive-assemble](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/ui-entrance/product-card-progressive-assemble.md) | 自动填表、商品结构化 | 空卡 → 图片/标题/字段依次到位 → 真实业务状态改变 → 完整卡片 | 中文长度、字段落位、高亮跟随；只有产品真实支持的状态才演示 |
| [page-waterfall-wall](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/ui-entrance/page-waterfall-wall.md) | 页面与模板数量 | 多列切片墙 → 差速反向流动 → 交棒到可读信息镜头 | 素材去重、速度差；该镜头展示体量，长文字放到后续镜头 |
| [integration-hub-map](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/ui-entrance/integration-hub-map.md) | 接入关系、版本焕新 | 旧页翻面 → 图标到位 → 连线接通 → 脉冲输送 | 产品是否支持所画连接；同时/依次接通要与真实语义一致 |
| [type-and-filter](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/interaction/type-and-filter.md) | 搜索到详情的操作因果 | 空搜索框 → 输入、停顿 → 筛选 → 目标回槽位 → 点击详情 | 占位字重影、目标真实位置；按实际字数分配输入时间 |
| [ai-stream-response](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/interaction/ai-stream-response.md) | AI 输出、证据、完成态 | 空面板 → 摘要落定 → 证据逐行出现 → 完成定格 | 读完摘要再展示证据；不伪造处理速度。上游此卡尚未实战验证 |
| [before-after-slider-scrub](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/data/before-after-slider-scrub.md) | 同一输入的优化效果 | 同布局两版叠放 → 分割杆快移 → 暂停、慢扫 → after 定格 | 同机位、同输入和实际结果；杆与揭示边界必须一致 |
| [shot-transitions：C 式焦点交接](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/transition/shot-transitions.md) | 同一长页两个区块衔接 | A 清晰 → A 失焦、B 错开入场收焦 → B 清晰 | 相邻镜头分配转场预算；同时全屏模糊会失去观看对象。Gallery key 为 shot-transitions-5 |
| [ui-strip-away-outro](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/outro/ui-strip-away-outro.md) | 发布、完成、品牌落版 | 完整编辑器 → 终结性操作 → 外围退场 → 按钮居中 → 字标 | 核心按钮持续可见；普通保存操作不应演成产品整个结束 |

原卡常见预算约 2.5–6 秒，不是固定平台限制。具体帧数、缩放、倾角与缓动要在读取对应卡后按项目 FPS 换算；例如原卡的“配方帧 / 60”不能直接当成 30fps 工程帧。

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

形成镜头表后读取 [分镜机器门禁](storyboard-quality-gates.md)，再交给生成或渲染路径。精确还原某卡时才读取固定来源的具体卡与官方 TSX；链接不是已经安装或验证过的执行依赖。

## 实际验收

- 截图是目标产品且清晰，敏感数据已按用户要求处理；界面文字能读完。
- 点击、筛选、填入、状态变化体现真实功能和因果；不存在的产品能力不能靠动画补齐。
- 动画由时间线驱动；需要定格阅读时元素完全停止。
- 转场帧计入相邻镜头或总合成，不能凭空增加或重复计算。
- 本地镜头计划与 JSON 校验不使用外部 API、登录、付款或素材上传；真正渲染按 Remotion 软件许可执行。

## 来源与素材说明

镜头研究参考公开产品影片，公开观看不等于拥有复刻或素材授权。此包只参考技法、独立实施，不携带原品牌画面。更多出处见固定快照的 [shots/ATTRIBUTION.md](https://github.com/Vincentwei1021/video-shotcraft/blob/5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab/references/shots/ATTRIBUTION.md)。上游部分音频出处待核，因此本模块完全排除其音频库。
