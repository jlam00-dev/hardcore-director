# 分镜机器门禁

对多镜头分镜和批量提示词使用；简单单镜头无需先写 JSON。吸收 [novel-storyboard 2.0.0](https://github.com/eternityspring/shuohao-skills/tree/ef4ac0c313c7eeb1f918db5f0f0eb319745900bc/skills/novel-storyboard) 的节拍归属、对白容量和引用检查思想；本地脚本与 JSON 合同为独立实现，不兼容上游 board JSON，也不复制其模型方言或固定 15 秒预算。

固定仓库快照 `ef4ac0c313c7eeb1f918db5f0f0eb319745900bc`，2026-10-01 审阅。Apache-2.0，Copyright 2026 烁皓；[完整许可](../support/licenses/shuohao-Apache-2.0.md)与 [NOTICE](../support/licenses/shuohao-NOTICE.md)。真实上游结构见 [schema.md](https://github.com/eternityspring/shuohao-skills/blob/ef4ac0c313c7eeb1f918db5f0f0eb319745900bc/skills/novel-storyboard/references/schema.md)。

## 什么时候运行

在 [分镜交付包](storyboard-package.md) 生成镜头台账后、交给 [模型适配器](../prompt-tools/model-router.md) 或 [Remotion](remotion-production.md) 前运行。存在剧本时，先人工核对 JSON beats 与获准剧本逐项对应，不能只根据镜头反造节拍再宣称已覆盖原作。

```bash
python3 scripts/validate_storyboard.py path/to/storyboard.json --json
```

脚本只读输入，使用 Python 标准库；不下载依赖、不上传素材、不调用生成服务。错误返回 1，通过返回 0。`--strict` 把对白时长估算警告也视为失败；正式对白已有录音时优先填写实测帧数。

用户已定画幅/时长时，同时传入 `--expected-aspect-ratio 16:9 --expected-total-frames 600`（例：20秒、30fps），防止 JSON 自己写错规格却内部自洽。`--strict` 下 JSON 的 `valid` 与退出码一致；`structurally_valid` 单列声明结构是否过关。

## 本包 JSON 合同 v1

完整示例：[storyboard-example.json](../support/storyboard-example.json)。时序全部使用绝对整数帧，30fps 的一秒是 30 帧；所有区间为左闭右开 `[start_frame,end_frame)`。

| 字段 | 约定 |
| --- | --- |
| `schema_version` / `aspect_ratio` / `fps` / `total_frames` | 版本为 1，画幅为正整数比，FPS 和总帧数为正整数 |
| `beats` | 非空的叙事播放顺序节拍对象 `{id}`；每拍唯一归属一镜。倒叙按实际讲述顺序声明 |
| `assets` | 唯一素材对象 `{id, path?, approved_version?}`；不是已上传素材列表 |
| `limits.max_shot_frames` | 可选项目/模型模式上限，由当前适配器和实际入口确定，不内置 15 秒 |
| `limits.speech_units_per_second` | 可调对白估算预算，默认 4.5，非官方模型限制或实际语速保证 |
| `shots` | 按播放顺序排列；每镜有唯一 `id`、`scene_id`、`purpose`、起止帧、`beat_ids` 和首尾状态 |
| `references` | 每镜 `{asset_id, role, exclude}`；同素材在同镜只有一个主职责，并写不应迁移属性 |
| `start_state` / `end_state` | 非空对象；用稳定键跟踪身份、左右手、道具、数量、空间或产品 UI 状态 |
| `transition` | 默认 `continuous`；时空跳转用 `time_jump`/`scene_change` 和 `transition_reason`，换场还须换 `scene_id` |
| `dialogue` | 每句 `{speaker,text,start_frame,end_frame,audio_duration_frames?}`；绝对帧窗口必须在本镜内 |

参考职责枚举：`identity`、`product`、`space`、`start_frame`、`end_frame`、`motion`、`camera`、`style`、`voice`、`music`。素材数量及这些职责在目标服务中能否使用，由模型适配器再次检查，枚举只是本包生产合同。

## 能检查与仍需看验的内容

脚本可以阻止：时间空档/重叠、总帧数不符、超出配置镜头时长、节拍缺漏/重复/顺序错乱、未知素材引用、同镜素材职责重复、连续镜首尾声明不一致、无剧情理由的重置、对白窗口越界、同一说话人窗口重叠、实测音频装不下。

对白没有实测音频时，按汉字数和拉丁/数字词数估算，超预算报告 warning。快慢语速、停顿、表演和其他语言仍须实际听验，不能拿估算通过证明音画同步。

脚本检查的是声明。素材文件存在、角色相似度、实际画面连续性、prompt 中台词逐字对应、生成和渲染效果会在 JSON 输出 `not_checked` 中明确列出，需在对应阶段实际检查。状态字段漏记的信息不能靠机器发现。

H3 固定字段和逐镜对白对齐由 [H3 适配器](../prompt-tools/minimax-h3.md) 负责；Seedance/Wan 的语法由各自适配器负责。这里的门禁不替换平台规则或导演验收。
