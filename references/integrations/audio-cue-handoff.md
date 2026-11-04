# 声音cue交接

用于多镜短片、广告和有明确声音叙事的项目。它把 [声音设计](../sound-design-to-prompt.md) 和 [AI配乐](../ai-music-generator.md) 的结果，接到同一份分镜、平台提示词和剪辑交接中。字段和检查入口以 [创作协作合同](creative-collaboration.md) 为准，不另建第二套计划。

## 输入与输出

读入已锁的 `project/script/direction/storyboard`：声音限制、逐字对白、人物关系、镜头起止状态和绝对帧区间。先问声音承担什么叙事动作，再决定环境音、对白、Foley、音乐或有意的静默；项目禁止BGM时，配乐模块也必须保留这个限制。

写入 `audio={source_hash,cues}`。每条cue包含稳定 `id`、所属 `shot_ids/beat_ids`、`kind`、`placement`、绝对 `start_frame/end_frame`、`bridge`、声音意图、可选 `dialogue_id/source_asset_id`、`source_kind`、`evidence_status` 和 `rights_note`。

- 台词cue继承剧本原句ID和分镜窗口，每句恰好一条；不改人、不改词、不凭空加旁白。
- 环境、Foley和音乐写出它对当前画面的作用、与对白的前景关系、进入和退出依据；无需用固定分贝、统一LUFS或固定静默次数代替判断。
- 同一声音跨镜延续时，完整列出覆盖镜头并声明bridge。不得为了每镜独立而把一段跨镜声音切碎。
- 原生声音、用户素材、许可库和拟生成声音分开标来源；无素材时保持planned。`reported` 只表示调用方报告了来源和hash，不表示本工具测量或听过。
- 素材许可不明时，把待核实事项写入 `rights_note`，不能把“可下载”或仓库许可当成所有声音、真人音色和平台产物的商用许可。

## 谁消费这些cue

模型内生成的cue，进入 `prompts.shots[].cue_ids`，并逐条填写 `cue_bindings[{cue_id,text}]`。平台化短句必须实际出现在对应 `video_prompt`，不能只在元数据里挂名；允许翻译，但语义忠实与模型音频模式仍需人工核对。使用外部声音参考时，它必须是调用方允许的provided素材，并附在每个消费镜头的references中。

后期cue进入对应 `editorial.events[].cue_ids`。配乐模块消费音乐cue生成配乐简报，声音提示词模块消费环境/Foley/空间cue，再交给明确选择的后期路径。生成时点、后期同步点和实际测量值不能混写；尚未生成时不填假“实测秒数”。

## 失败退回

| 问题 | 回到哪里 |
| --- | --- |
| 对白原文、人物或情节不明确 | 编剧；保留原文问题，不擅自补话 |
| 声音动机、视听前景冲突 | 导演与声音设计 |
| cue越界、跨镜未声明、下游没有消费 | audio或对应prompts/editorial段 |
| 换素材使同步依据失效 | 仅重测受影响cue及下游；保留其他已接受项 |
| 没有真实音频或还没听验 | 保持planned/pending，交出待听队列，不能报PASS |

## 来源与执行边界

原创中文适配参考 [spot-audio-assembly](https://github.com/konradre/video-production-skills/blob/cd92701fd52fbfa668f2247687b32d0f85506fda/skills/spot-audio-assembly/SKILL.md) 的来源追踪、同步锚点、逐层交接与成片实测方法；源仓库最近维护可核实，但只有仓库级7星，不宣称单模块热门或显著升星。固定快照 `cd92701fd52fbfa668f2247687b32d0f85506fda`；该SKILL最近内容提交为 `14e4f24b9d3a959470588e934982caa70287f66f`。保留 [MIT许可](../support/licenses/video-production-skills-MIT.md)。

这里没有复制上游执行器、命令或授权规则：不默认使用其AceDataCloud/Suno、ElevenLabs、转写、声音克隆或重试；不采用其拒绝台词改用克隆配音的做法，也不继承“所有VO不与SFX重叠”“字幕统一无标点”等项目惯例。录音、上传、生成、克隆、混音或母带处理都不是本方法包的动作。
