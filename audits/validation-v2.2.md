# v2.2 验收记录

2026-10-01 发布前验收通过。固定发行标识为 `v2.2.0`；该结果不构成生成效果或实际产品素材的验收结论。

| 检查 | 实际结果 |
| --- | --- |
| 包体 | `python3 scripts/validate_package.py` 通过：frontmatter、链接、47项清单、SHA256、可移植性 |
| 单元测试 | `python3 -m unittest discover -s tests -q`：32项通过；发布时补充兼容包图片固定到当前版本的测试 |
| 官方 Skill 校验 | 官方 `quick_validate.py` 输出 `Skill is valid!`；仅在临时目录配置 PyYAML 6.0.3，未修改全局 Python |
| 分镜示例 | 16:9、300帧示例通过，无估算警告；实际素材与音画列为 not_checked |
| 独立行为验收 | 20秒16:9、5镜、600帧软件宣传片计划通过；截图缺失明确披露，未声称实测功能 |
| 独立负例 | 3份坏台账全部被拒；额外画幅、空节拍、期望帧数、strict语速例均准确拒绝 |
| 在线全量扫描 | 47项，26项来源可追踪、21项本地完整性；local_issues=0、updates=0、reviews=3、errors=0；检查时间 2026-10-01T12:49:56Z |
| 压缩包预检 | Codex 与 SkillHub 均通过 ZIP 完整性；实际解压后包体校验通过47项 |
| 差异 | `git diff --check` 通过；以下记录为发布前技术验收，发行状态以 GitHub Release/Tag 为准 |

在线扫描的3项保留信号为 Higgsfield explainer、Remotion 与 Wan 网页构建。它们没有被误标为已升级；详见 [升级审阅](upgrade-review-v2.2.md)。

打包前实测发现 SkillHub 包移除无扩展名 VERSION 后，旧校验器不能运行；已修复为识别 SkillHub 专用 frontmatter，并读取其声明版本与清单交叉核对，补充回归测试。标准 Codex 包仍从 VERSION 校验。

机器门禁只证明声明及已传入的项目规格。功能语义、素材文件、实际镜头连续性、提示词对白保真、最终生成/渲染和响度还须在制作阶段看验；没有付费生成、平台登录或素材上传。
