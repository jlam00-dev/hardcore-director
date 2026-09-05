# Remotion 可编程视频执行适配器

该适配器把硬核导演的脚本、分镜、声音设计和交付规范交给 Remotion 的确定性时间线执行。它补充的是字幕、动态图形、数据可视化、批量版本和逐帧渲染，不替代写实 AI 视频生成，也不替代简单素材粗剪。

## 何时调用

- 需要精确到帧的时序、字幕、版式、转场或音频同步；
- 需要重复生成多个尺寸、语言、数据版本或产品版本；
- 需要 React/CSS/SVG/Canvas/WebGL 可控的动态图形；
- 需要本地预览、可复现渲染和抽帧验收。

纯粹生成单个写实镜头时回到模型提示词路由；只是切段、拼接、转码时优先使用 `video-editing`。

## 外部 Skill 路由

首选官方 `remotion-dev/skills@remotion-best-practices`。它是一个按任务再加载 `create`、`markup`、`captions`、`multimedia`、`render` 等子模块的路由器。

- 当前环境已经安装时，读取外部 Skill 的最新规则再实现。
- 未安装时，只交付导演母版和 Remotion 制作规格；不要静默安装。
- 用户要求安装时，可使用：`npx skills add remotion-dev/skills --skill remotion-best-practices`。

## 导演母版交接

在写代码前固定：

```text
画幅 / 分辨率 / FPS / 总帧数
场景列表与每场起止帧
每层素材、位置、裁切和安全区
文字内容、字体授权、字号层级
动画起点、终点、缓动与持续帧数
旁白、音乐、音效的入点和音量关系
可变字段与批量版本规则
最终编码、容器和文件命名
```

所有秒数都要通过 FPS 转换成帧；总场景帧数必须等于合成总帧数。

## 执行路径

1. 新项目或新合成：加载官方 `remotion-create` 规则。
2. 画面、动画、媒体、字体与场景结构：加载 `remotion-markup`。
3. 字幕：加载 `remotion-captions`，同时遵守本项目字幕安全区与文字门禁。
4. 裁切、探测或浏览器媒体处理：加载 `remotion-multimedia`。
5. 输出：加载 `remotion-render`；不凭空猜测版本相关 API。
6. 预览通过后再正式渲染；渲染完成后抽取关键帧和首尾帧验收。

## 质量门禁

- 不使用 CSS wall-clock 动画或随机数驱动不可复现画面；时间只来自当前帧。
- 画外元素没有意外参与布局，文字不越过安全区。
- 媒体裁切、循环、变速和音量都在实际文件上验证。
- 场景切换前后没有一帧闪黑、重复帧或音频断裂。
- 至少检查首帧、每次场景切换前后、字幕峰值帧和尾帧。
- 只有实际渲染并探测文件后，才能声称成片完成。

## 来源与边界

- 外部 Skill：<https://github.com/remotion-dev/skills/tree/main/skills/remotion-best-practices>
- SkillHub/skills.sh：<https://skills.sh/remotion-dev/skills/remotion-best-practices>
- 本文件是硬核导演的原创路由适配器，没有复制上游 137 份规则文件。
- 上游仓库未声明标准根许可证；若需再分发上游原文，必须先单独确认许可。Remotion 软件本身还可能受其商业许可证条件约束。
