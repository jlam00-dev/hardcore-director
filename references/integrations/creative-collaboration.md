# 创作协作合同：从同一份故事到同一份制作草稿

用于跨编剧、导演、分镜、声音、模型提示词和剪辑交接的多镜项目。一次确定的单镜提示词或局部改稿，直接走对应模块即可，不强迫填整包。

统一数据是 [creative-handoff.schema.json](../support/creative-handoff.schema.json)，完整原创示例是 [《末班信》](../support/creative-handoff.example.json)。编译器只检查显式JSON，不读媒体、不联网、不生成，也不替用户批准。第三方方法只作为资料；本合同不继承其工具权限、账号或自动执行规则。

## 每个模块交给下一步什么

| 阶段 | 使用模块 | 读入 | 写回合同 | 下一位消费者 |
| --- | --- | --- | --- | --- |
| 剧本诊断与修改 | [剧本诊断](screenplay-diagnosis.md)、原有编剧主模块 | 已锁简报、原文、人物目标与因果 | `script.screenplay/shooting_script/beats`；逐句对白ID及原文 | 导演 |
| 调度、表演与覆盖 | [导演调度与覆盖](director-blocking-coverage.md)、角色/场景模块 | `project+script` | `direction.shots` 的站位、视线、动作、表演、摄影目的与起止状态 | 分镜 |
| 可执行分镜 | [既有分镜门禁](storyboard-quality-gates.md) | 剧本与导演交接 | `storyboard.board`，沿用原分镜结构，增加对白 `line_id` | 声音、提示词与剪辑 |
| 声音cue | [声音交接](audio-cue-handoff.md)、声音设计与配乐模块 | 已锁镜序、对白、角色与环境 | `audio.cues`；区分模型生成与后期消费 | 唯一平台提示词、EDL |
| 平台提示词 | [模型路由](../prompt-tools/model-router.md)及一个目标适配器 | 上述全部内容 | `prompts.platform`；每镜一对提示词及实际声音文本投影 | 制作草稿、剪辑交接 |
| 叙事剪辑交接 | [叙事EDL交接](narrative-edit-handoff.md)、原有剪辑模块 | 已锁分镜、声音cue、提示词及获选素材窗口 | `editorial.events`、待测与退回原因 | 获批后的具体剪辑路径 |

## 统一标识与不可漂移的内容

- `project` 是画幅、FPS、总帧数、声音政策与全片不变量的唯一来源。`locked_state` 只放门的位置、人物身份/服装，以及用户明确要求全程固定的画面侧或持物手等不变量，不把剧情需要改变的道具归属锁死。空间光源和位置先按世界空间记录，再随机位推导画面左右。
- `script.beats[].id/scene_id` 沿用到导演、分镜、声音和EDL；各类型ID唯一，修改不靠改名躲开旧依赖。
- `direction.shots` 使用 `shot_id/scene_id/beat_ids`，`blocking` 含 `start/action/end/eyelines/prop_changes/holds`，`performance` 含 `before/during/after`；这些文字供导演判断，机器不冒充理解表演。
- 每镜 `start_state/end_state` 必须继承导演交接；连续镜的前后状态还须通过既有分镜门禁。已锁不变量要在每镜两端出现且一致。
- 对白从 `script.beats[].dialogue[].id/speaker/text`，传到分镜 `dialogue[].line_id/speaker/text`，再进入 `prompts.shots[].dialogue_ids` 和真实 `video_prompt` 原文；不能用同义改写掩盖漂移。检查文字出现不等于验证平台语法或最终语音。
- `audio.cues[].placement=generation` 由对应每镜prompt的 `cue_ids` 消费，并以 `cue_bindings[{cue_id,text}]` 一一投影；短句须真的出现在该镜 `video_prompt`，可转换为目标平台语言。其语义是否忠实仍需人工审阅。
- `placement=post` 由覆盖镜头的 `editorial.events[].cue_ids` 消费。跨镜声音用同一cue ID、绝对帧区间、完整的有序 `shot_ids` 和 `bridge=true` 声明，不在镜头边界静默裁断。

## 上游改动怎样传递

五个下游段都携带 `source_hash`。摘要取其全部上游内容，去掉段级 `source_hash` 元数据后进行固定JSON编码：

`direction ← project+script → storyboard → audio → prompts → editorial`

因此改剧本会让全部下游过期；改导演调度会让分镜及其下游过期；换分镜后必须重审声音、提示词和EDL。错误报告的 `issues[].stage/code/return_to` 指明应回到哪一阶段。

摘要只检测内容偏移，不是签名、审美结论或用户批准。不要为通过检查而给旧产物批量换摘要。完成对应阶段实际修订后，由其作者填写新的 `source_hash`；编译器不提供自动盖章功能。

## 本地检查与草稿导出

在Skill根目录运行：

```bash
python3 scripts/creative_handoff.py references/support/creative-handoff.example.json
python3 scripts/creative_handoff.py references/support/creative-handoff.example.json --digests
python3 scripts/creative_handoff.py references/support/creative-handoff.example.json --output /绝对路径/新的制作草稿.json
```

`--digests` 只报告当前内容对应的期望摘要。返回码0仅表示摘要算出；输出的 `valid` 仍可能为false，不能当作交接通过。普通检查/导出必须 `valid=true`。导出文件必须是新路径，采用独占创建，已有文件不覆盖；检查失败不会产出制作计划。

有参考素材时，调用方另用 `--references /绝对路径/允许清单.json` 提供 `[{"path":"/调用方明确选定的素材.png","role":"identity"}]`。packet不能给自己授权；已提供素材的路径与职责必须精确匹配清单，规划中的素材不能冒充生成输入。工具不检查文件存在、真实哈希或媒体内容；这些仍由后续实际素材检查和审批负责。

导出复用既有planner，得到原格式的Engine草稿：缺省mock供应商、`0/UNAPPROVED`预算，没有生成范围、上传批准或自动规格统一。调用方可明确指定供应商标识，但模型/账号/能力参数与唯一平台是否匹配，仍须执行前核验。本工具不调用Engine，也不改变其审批、报价、上传、返工或合成逻辑。

既有Engine的生成顺序仍是先分镜图、再审图和生视频，因此草稿保留每镜 `image_prompt`。没有现成参考图时，它可以是待制作首帧的文字描述；不能据此声称图片已存在。模型适配器可以创作T2V提示词，但本次草稿导入不证明纯T2V跳过生图/审图的直通执行能力，实际模式由获批后的原工作流核对。

EDL和后期cue保存在创作packet中，不被偷偷塞进Engine的执行指令。既有Engine成片路径仍只做其已支持的顺序合成；不能把后期声音计划写成已经自动混音。

## 什么算通过，什么还没验证

`valid=true` 只表示结构、ID、帧区间、声明消费、原文传递与上游依赖一致，允许导出**待审核草稿**。`render_ready` 和 `generation_authorized` 都不会因此变true。

没有真实take时，`editorial.status=planned`、`take=null`。有调用方报告的素材hash和入出点时可登记，但仍为 `pending_media_verification`；不读取媒体的工具不能替它们签收。`not_checked` 明列叙事语义、表演/审美、平台提示词语法、实际文件、生成画面、声音测量和听感，以及用户批准。

示例《末班信》是自创40秒单场景、双人四镜案例，不使用用户已接受的纸船画面或私人素材。它展示右手信封交付、空间不变、三句逐字对白和无BGM政策怎样贯穿整个包，不代表已生成或已由真人验收的成片。
