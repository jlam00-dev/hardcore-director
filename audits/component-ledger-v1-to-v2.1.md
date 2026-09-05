# 旧版 36 项组件对账（v1 → v2.1）

审计日期：2026-09-05。

## 结论

旧版所称“36 个 Skill”实际是 `references/` 下的 36 份顶层能力模块：34 份来自当时本机的独立 Skill，2 份是硬核导演内部汇总文件。它不是“36 个都能在注册表查询版本”的依赖清单。

本次逐项对账后：

- 36/36 均已找到去向，没有 25 项被删除或忘记；
- 15 项具有可识别的公开来源或注册表，可自动监控上游；
- 其中 6 项在 v2.1 实际升级或重写，9 项核对后保留并加入来源追踪；
- 19 项是本机原创、用户/团队署名或无版本化上游的模块，只能做哈希与可移植性检查，不能声称“已是网上最新版”；
- 2 项是包内汇总模块，不是外部 Skill，不存在单独升级版本。

此外，v2.1 在这 36 项之外新增 9 份顶层能力模块：`cellcog`、`video-generation-cellcog`、模型路由器、Seedance 2.5、Wan 3.0、MiniMax H3、分镜交付包、Remotion 制作适配器、Higgsfield 解释视频适配器。当前顶层能力模块总数为 45。

## 36 项逐项账本

| # | v1 模块 | 来源类别 | v2.1 处理 | 自动更新状态 |
| ---: | --- | --- | --- | --- |
| 1 | `ai-music-generator` | CC0 上游改编 | 已按 Bitwize Music 最新 Suno V5/V5.5、分轨与母带逻辑重构，删除真实艺人提示词与僵化响度结论 | 追踪 GitHub 指定路径 |
| 2 | `ai-scene-design` | 本机知识库整合 | 保留；修复与主路由的调用关系 | 无版本上游；仅校验包内哈希 |
| 3 | `ang-lee-perspective` | 本机导演研究模块 | 保留 | 无版本上游；仅校验包内哈希 |
| 4 | `character-design` | 白梦客署名模块 | 保留 | 无版本上游；仅校验包内哈希 |
| 5 | `composition-to-prompt` | 本机原创/整合 | 保留 | 无版本上游；仅校验包内哈希 |
| 6 | `douyin-safety-rewriter` | 基于公开项目改编 | 保留本地适配，增加来源路径监控；平台规则实际使用时仍需实时核对 | 追踪 GitHub 指定路径 |
| 7 | `douyin-script` | 本地化创作 | 保留；平台规则实际使用时实时核对 | 无版本上游；仅校验包内哈希 |
| 8 | `douyin-viral-planner` | 基于公开提示词改编 | 保留本地精简适配，增加来源路径监控 | 追踪 GitHub 指定路径 |
| 9 | `drama-creator` | GitHub Skill 快照 | 上游无新内容；保留并补齐嵌套参考 | 追踪 GitHub 指定路径 |
| 10 | `drama-evaluator` | GitHub Skill 快照 | 上游无新内容；保留并补齐嵌套参考 | 追踪 GitHub 指定路径 |
| 11 | `drama-planner` | GitHub Skill 快照 | 上游无新内容；保留并补齐嵌套参考 | 追踪 GitHub 指定路径 |
| 12 | `humanizer-zh` | MIT GitHub Skill | 上游 Skill 正文无新提交；保留 | 追踪 GitHub 指定路径 |
| 13 | `jackyshen-gen-short-video-script` | MIT GitHub Skill | 上游无新内容；保留 | 追踪 GitHub 指定路径 |
| 14 | `king-hu-perspective` | 本机导演研究模块 | 保留；只修复包内路由/链接 | 无版本上游；仅校验包内哈希 |
| 15 | `legacy-filmmaking-v1` | 包内历史汇总 | 保留为追溯档案，不进入默认调用 | 内部模块；不查外部版本 |
| 16 | `miyazaki-perspective` | 本机导演研究模块 | 保留 | 无版本上游；仅校验包内哈希 |
| 17 | `rhythm-to-prompt` | 白梦客知识模块 | 保留 | 无版本上游；仅校验包内哈希 |
| 18 | `screenwriter` | 原 GitHub 快照无明确许可证 | 已重写为本包原创“故事到分镜”模块，并删除原上游嵌套快照 | 只监控上游信号，不自动覆盖原创实现 |
| 19 | `seedance-perform-v5-single` | 包内组合模块 | 保留为旧版单段 Seedance 路径；2.5 请求不再默认调用 | 内部模块；不查外部版本 |
| 20 | `shanyin-screenwriting` | 山音署名 MIT 模块 | 保留 | 无公开版本上游；仅校验包内哈希 |
| 21 | `short-drama-writer` | ClawHub Skill | 2.3.5 → 2.3.6，并修复不可解析的 frontmatter | 追踪 ClawHub 版本 |
| 22 | `short-video-hook-lab` | 注册页与正文许可证冲突 | 已重写为本包原创钩子实验室，不继续复制非商业文本 | 只监控上游信号，不自动覆盖原创实现 |
| 23 | `short-video-script` | ClawHub Skill | 1.0.1 已是当前版本；保留 | 追踪 ClawHub 版本 |
| 24 | `sound-design-to-prompt` | 白梦客知识模块 | 保留 | 无版本上游；仅校验包内哈希 |
| 25 | `story-cog` | ClawHub Skill | 1.0.1 → `creative-writing-cellcog` 1.0.15 | 追踪 ClawHub 版本 |
| 26 | `story-master` | 原 ClawHub 快照无许可证且绑定固定远程接口 | 已重写为本地连续性管道，默认不联网 | 只监控上游信号，不自动覆盖原创实现 |
| 27 | `style-fusion` | 白梦客知识模块 | 保留 | 无版本上游；仅校验包内哈希 |
| 28 | `stylized-color-grading` | 白梦客知识模块 | 保留 | 无版本上游；仅校验包内哈希 |
| 29 | `takeshi-kitano-perspective` | 本机导演研究模块 | 保留 | 无版本上游；仅校验包内哈希 |
| 30 | `tarkovsky-perspective` | 本机导演研究模块 | 保留 | 无版本上游；仅校验包内哈希 |
| 31 | `tint-to-prompt` | 白梦客知识模块 | 保留 | 无版本上游；仅校验包内哈希 |
| 32 | `video-analysis` | 白梦客本机流程 | 保留 | 无版本上游；仅校验包内哈希 |
| 33 | `video-editing` | MIT GitHub Skill | 上游指定路径无新提交；保留 | 追踪 GitHub 指定路径 |
| 34 | `video-prompt-writer` | 白梦客知识模块 | 保留并调整到新模型路由之下 | 无版本上游；仅校验包内哈希 |
| 35 | `video-reverse-engineer` | 白梦客本机流程 | 保留并修复私有绝对路径 | 无版本上游；仅校验包内哈希 |
| 36 | `wong-kar-wai-perspective` | 本机导演研究模块 | 保留 | 无版本上游；仅校验包内哈希 |

## “为什么不是 36 个都升级”

升级成立至少需要一个可验证的上游版本或提交。21 项没有独立、版本化的公开上游，其中 19 项是本机知识模块，2 项是包内汇总；给它们强行编一个“最新版本”反而是假更新。v2.1 对这些模块采取三种维护方式：固定包内哈希、检查引用和可移植性、在主路由变化时做兼容性复核。

对 15 项有来源的旧组件，脚本必须继续区分：

- `current`：上游信号未变化；
- `update_available`：上游版本或指定路径提交变化；
- `source_watch`：本包为原创改写，只提醒审阅上游，不自动覆盖；
- `error`：注册表、网络或来源检查失败。

## 发布口径

对外不要再说“2.1 把 36 个 Skill 全部升级”。准确表述为：

> v2.1 完成旧版 36 项全量对账：6 项升级或重写，9 项核对后纳入上游追踪，21 项本机/内部模块纳入完整性检查；同时新增 9 个顶层能力模块，形成 45 模块的按阶段路由。
