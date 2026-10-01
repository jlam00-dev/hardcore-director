# v2.2 本地升级记录

审阅日期：2026-10-01。基于 v2.1 固定提交 `b450d8367aeb46db135c0134636fadcfb617b96c` 完成独立候选验收，随后由用户明确授权发布至现有 GitHub 仓库。固定发行标识为 `v2.2.0`；SkillHub 平台发布不在本次授权范围内。

## 变更口径

45 项旧模块全部保留；4 项能力内容升级（中文润色、实拍剪辑、Seedance 2.5、影视配乐）；2 项现有路由随新门禁调整（模型路由器、分镜交付包）；新增2项按需能力，合计47项。没有把上游仓库的脚本、音频、截图、套餐或运行时批量装入本包。

| 组件 | 原固定来源 → 本次审阅固定来源 | 处理 |
| --- | --- | --- |
| humanizer-zh | b4b4fe5c9bc4f14f1be0614f8c2c234161734a6e → f4518a8eab97b8bfebc66a89d34320a89bef6930 | 同步新快照：保留事实、确定程度与作者声音；完整 MIT 许可 |
| video-editing | db7f2a6fd5b013d56ec0ba0cfc547ba77baddbce → 928c1dea72f5c330442fc1f595563398b8f389f7 | 吸收项目 checkpoint、原生保存/重开与导出听验；保留本地授权边界，外部 Fusion 例子使用固定链接 |
| ai-music-generator | 9f94c51ae727426c31cc49f7d45ceb68c7f95cc5 → 3b292b08776796f593d7abf816c19a9ff652733d | 官方 v6/v6-wild/mini、Variety、Max、Voices；平台设置与音乐正文分离 |
| seedance-2.5-prompt-tool | OSide 201061da4e91600aa9bfb6d860b9fe469b369f4b → 28bff386ffe706a8f030ad39393759b11598fd7c | Higgsfield web/API/CLI 分开；1080p、码率、首尾帧计数、素材保真、前后延长与声音边界 |

Suno 与 OSide 的内容依赖也加入 `additional_upstreams`，避免入口未改但模型规则已改时漏报。主 Seedance Square-Zero 来源未变。Higgsfield 公开 API 页的内嵌 Input Schema 已核实 resolution 三档和 bitrate_mode 两档；公开 API 默认码率 high，CLI 快照 standard。首尾帧和四模式只属第三方 CLI 记录，没有嫁接到该公开 T2V API。

## 新增能力取舍

- `product-promo-shotcraft`：上游10,121星（本次审阅）、Apache-2.0；固定仓库 `5ddbf521038b0a7accfb6dc1e0a9eb29c67277ab`。只接入10条真正能表达产品功能的镜头词典与验收条件；实际卡和实施例子按需读取。部分上游音频出处待核，全部排除。没有执行其 Node、Remotion、工作台或脚本。
- `storyboard-quality-gates`：shuohao 上游4,020星（本次审阅）、Apache-2.0，固定仓库 `ef4ac0c313c7eeb1f918db5f0f0eb319745900bc`。吸收节拍归属、时长、引用和对白容量思想，独立实现 Python 标准库校验器。新合同不兼容上游 JSON；15秒、2–5秒、3人等短剧预算没有写成通用限制。上游实际没有状态连续性代码，本包新增声明级首尾状态校验。
- AI Presenter 保持观察：GitHub 信号较强，但安装样本少且涉及人脸/声音上传与外部付费服务。没有集成。
- Video TalkCraft、Anything2Explainer 等未明确许可或重复能力候选未集成；ClawHub/SkillHub 本轮没有额外候选通过全部门槛。

## 暂留的上游信号

`higgsfield-explainer` 和 `remotion-production` 的入口变化主要为版本号，不作为功能升级盲同步；Wan 网站 `1.0.91→1.0.95` 仅是网页构建变化。本版保留其旧固定来源，在线检查仍会报告 review_available，方便后续单独审阅。

## 脚本与包装

- 更新检查改为公开 HTTP 查询 ClawHub，校验命名空间作者；不调用 `npx` 或安装 CLI。
- 次来源失败保留主来源证据；组件最多8线程并行（默认4），输出检查时间。
- GitHub 优先使用现有 `GITHUB_TOKEN` 或已登录的 `gh` 进行只读查询，避免新增内容依赖超过匿名限流；没有配置时保留公开 HTTP 回退，不启动登录。
- 包体校验按当前清单计数，不固定45；历史36→45与新增2项可核算。
- SkillHub 包从 `VERSION` 读取版本；本地候选支持 `--draft`，正式包装仍拒绝脏工作树/遗漏未跟踪文件。`.md` 保存许可证，避开曾拒绝的无扩展名文件。
- 解压实测后修复 SkillHub 安装包的校验器：没有无扩展名 VERSION 时，从平台 frontmatter 与清单交叉校验版本；标准包仍验证 VERSION。

## 验收范围

独立前向验收以20秒16:9软件宣传片实际建立5镜台账，造坏样本检查帧空档、节拍覆盖、素材引用、状态和对白。发现严格模式 JSON 与退出码不一致后已修复；补充非空节拍与项目画幅/总帧数期望检查。brief三项功能是否真实表达仍须人审，不靠JSON自洽代替。

本地包体、清单哈希、链接、可移植性、单元测试、分镜示例与负例、在线来源和实际压缩包内容必须通过，才同步本机入口。机器门禁只证明声明，actual_asset_files、visual_continuity、prompt_to_dialogue_match 与 rendered_or_generated_media 明确为未检查。没有调用付费生成、登录平台、上传素材或验证生成成功率。

最终验收记录见 [validation-v2.2.md](validation-v2.2.md)。
