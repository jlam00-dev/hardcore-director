# 硬核导演3.0账号接入与运行手册

本手册适用于3.0.0。先按使用手册确认实际版本与安装目录。每节提供可以复制给Agent的指令，终端命令供Agent或希望自行操作的用户核对。[使用手册](user-guide.md)

本机Agent通过即梦画布CLI推进获准的制作任务，微信和飞书作为同一工作流的审核通道。实际运行前读取本机 `--help`、版本及实时合同，页面操作以官方现场为准。本版使用macOS或支持POSIX文件权限与锁的环境，原生Windows尚未验证。

## 先准备三个位置

请Agent分别记录：**Skill实际目录、私有凭据目录、本次作品目录**。后两者在Skill和Git仓库之外，不能放公共临时目录。示例变量只是一套新项目位置，可换成你自己的绝对路径：

```bash
HC_SKILL="/你实际解压或安装的位置/hardcore-director"
HC_PRIVATE="$HOME/.config/hardcore-director"
HC_RUN="$HOME/.local/state/hardcore-director/my-first-film"
HC_PYTHON="python3"
```

路径中有空格时保留双引号。换一个终端窗口后，需要重新设置变量。凭据父目录必须属于本人，权限0700；凭据文件由向导写为0600。Agent应先核对路径，避免覆盖已有配置。项目数据库、素材、报价和运行记录留在作品目录；**不要把App Secret、微信token或登录文件发进聊天、贴进命令参数、提交Git或打进Skill安装包。**

## 第一步：只读检查环境

对Agent说：

```text
请检查我实际使用的硬核导演版本与Python环境，运行本包的离线doctor。
我要接即梦＋飞书。请列出缺的依赖和官方安装入口，暂不安装、不登录、不发消息、不启动生成。
```

检查命令：

```bash
"$HC_PYTHON" --version
"$HC_PYTHON" "$HC_SKILL/scripts/validate_package.py"
"$HC_PYTHON" "$HC_SKILL/scripts/workflow_login.py" dreamina --doctor
"$HC_PYTHON" "$HC_SKILL/scripts/feishu_setup.py" --doctor
"$HC_PYTHON" "$HC_SKILL/scripts/workflow_bridge.py" --channel feishu --doctor
```

上述doctor只说明本机依赖和设置步骤，不读取凭据，不证明已经登录或消息可收发。核心脚本需Python 3.10及以上；创作交接与核心状态机使用Python标准库。飞书另需 `lark-oapi`，微信媒体另需 `cryptography`，真实视频检查和合成需可执行的 `ffmpeg`、`ffprobe`。

飞书向导审阅的SDK版本是 **lark-oapi 1.7.5**，不等同于自动追随最新SDK。若依赖缺失，可在用户选择安装后使用独立虚拟环境，放在Skill和作品素材之外；例如：

```bash
python3 -m venv "$HOME/.local/share/hardcore-director/venv"
HC_PYTHON="$HOME/.local/share/hardcore-director/venv/bin/python"
"$HC_PYTHON" -m pip install "lark-oapi==1.7.5"
```

只接飞书不必为微信安装媒体依赖。已有专用环境时直接复用，不重复建环境。ffmpeg和官方CLI由Agent按你的系统给出官方安装方式；本包不会自动替你安装。

## 第二步：接通即梦画布CLI

对Agent说：

```text
请带我安装或检查即梦“画布CLI”，不要把通用创作CLI当成同一个程序。
使用官方安装页，先核对系统和现有版本。登录由我自己确认；已有正确登录就复用。
登录后请核对账号、个人或团队空间和专用画布，再读取可用图像/视频模型及参数。暂不生成。
```

本工作流调用 **`dreamina-canvas`**，请安装“全能画布CLI”并在该程序完成授权。通用 `dreamina` CLI 有独立的命令和登录。实际会员资格与额度以你的官方账号响应为准。[即梦官方安装页](https://jimeng.jianying.com/ai-tool/install?from_page=banner)

安装时优先由Agent打开官方页面，按当前系统执行页面上的“全能画布CLI”命令；不复制来历不明的脚本。随后核对：

```bash
dreamina-canvas version
dreamina-canvas schema
dreamina-canvas auth --help
dreamina-canvas --profile default auth status
```

这里只把 `default` 作为示例profile。如果你已有专用profile，所有登录、核验和配置都沿用同一个名字。需要登录时执行：

```bash
dreamina-canvas --profile default auth login
```

打开该命令返回的官方授权页面，用自己的账号完成登录确认。Agent按当前帮助等待同一次授权，再用 `auth account` 核对账号身份。**浏览器已登录或页面已打开，都不能替代CLI授权成功；不默认退出账号或加 `--force`。**

接着由Agent按实时命令列出你的画布，选中或新建本次专用画布，给你画布链接。多个空间／画布时由你选择，不能默认使用第一项。读取图像与视频模型目录后，Agent保存本次执行器配置：官方CLI路径、profile、画布ID、图像/视频模型的规范名、模式和当前参数。配置中不放即梦token。

**接通的判据：** 官方CLI可用、身份核对成功、目标画布明确、所选模型和输入模式可用。这一步没有生成媒体。

## 第三步：接通飞书本人审核（推荐）

飞书长连接只需电脑能访问互联网，不需要公网域名或内网穿透；官方说明及“本地客户端在线后才能保存订阅方式”的要求见 [飞书长连接文档](https://open.feishu.cn/document/ukTMukTMukTM/uYDNxYjL2QTM24iN0EjN/event-subscription-configure-)。

对Agent说：

```text
请按硬核导演的feishu_setup向导，逐屏带我创建仅自己可用的飞书审核机器人。
一次告诉我当前页面要做什么。App ID和Secret让我在本机交互终端输入，不要让我发到聊天。
请保持配对窗口可见，把可以公开给我的一次性配对口令单独发成一行。
```

### 3.1 创建自己的应用

1. 用自己的飞书账号进入 [开放平台](https://open.feishu.cn/app?lang=zh-CN)，切到自己的组织／团队，创建**企业自建应用**。如果没有组织，先完成飞书组织／团队创建；无需为此先购买付费升级。
2. 添加应用能力“机器人”。在“权限管理”选择**应用身份**权限，只申请本人私聊与媒体收发所需的三项：`im:message:send_as_bot`、`im:message.p2p_msg:readonly`、`im:resource`。不顺带申请通讯录或所有群消息。
3. 在“凭证与基础信息”找到App ID、App Secret。留在你自己的屏幕上，不发到聊天。

### 3.2 在自己的终端保存凭据

由Agent打开可交互的本机终端，运行：

```bash
"$HC_PYTHON" "$HC_SKILL/scripts/feishu_setup.py" --configure \
  --credentials-file "$HC_PRIVATE/feishu.json"
```

按提示粘贴App ID并回车，再粘贴App Secret并回车。输入不回显是正常现象。保存成功时文件仍是“未配对”状态，不能直接拿去启动审核。旧文件已存在时先核对，不覆盖或把Secret写成命令参数。

### 3.3 开启接收事件并内部启用

先运行配对监听，保持该终端打开：

```bash
"$HC_PYTHON" "$HC_SKILL/scripts/feishu_setup.py" --pair \
  --credentials-file "$HC_PRIVATE/feishu.json"
```

等待本机实际连接建立，再到开放平台的“事件与回调→事件配置”：

1. 编辑“订阅方式”，选择**使用长连接接收事件**并保存。
2. 添加 **接收消息v2.0：`im.message.receive_v1`**。见 [官方接收消息事件](https://open.feishu.cn/document/server-docs/im-v1/message/events/receive)。
3. 到“版本管理与发布”创建内部版本，更新说明可填“本人分镜与视频审核”。**可用范围只选自己**，不启用对外共享。
4. 由你完成申请发布和组织需要的审核，看到该内部版本已启用。这里启用的是你自己的飞书机器人，不是对外发布硬核导演Skill。

配对超时就按向导重新开始一次，不保留两个监听窗口。飞书同应用多个长连接客户端会分流事件；同时运行旧诊断、配对和正式桥接，可能让口令被另一个进程收到。

### 3.4 绑定本人私聊

切到同一飞书组织，打开自己创建的机器人。若搜索不到，可让Agent用你的App ID生成机器人打开链接，不使用别人的示例App ID。

把当前配对终端显示的完整一次性口令发到该机器人**私聊**。终端显示已收到口令后，回终端输入 **`确认绑定`** 并回车。只有终端明确报告保存配对成功，才绑定完成。机器人在配对阶段不主动回信，不要仅因聊天里没回复就判断失败。

此向导保存唯一审批人的稳定ID和唯一私聊会话。一次性口令只用于配对，日常审核使用“同意／拒绝”。换人或换会话时使用向导的重新绑定流程，并核对新请求。

## 可选：改用微信本人审核

本包按 [腾讯官方微信机器人协议](https://github.com/Tencent/openclaw-weixin/blob/874637a0dbc24050f72d1385add4fc6170a2d726/docs/protocol_zh_CN.md)接入私聊，扫码方式可参照 [腾讯官方说明](https://github.com/Tencent/openclaw-weixin/blob/874637a0dbc24050f72d1385add4fc6170a2d726/README.zh_CN.md)。**本包不要求安装OpenClaw**，也不提供个人号外挂。官方服务、客户端和账号资格可能限制可用性；不能承诺每个微信号都能接入。

对Agent说：

```text
我要改用微信审核。请先检查本包微信doctor，说明媒体依赖和官方账号可用性。
由我扫描官方二维码。扫码成功后请继续核对本人稳定ID和审核白名单，不要把扫码成功直接当成审核绑定完成。
先做收信、回信和0费用媒体审核测试，不生成视频。
```

检查后，由用户明确开始扫码：

```bash
"$HC_PYTHON" "$HC_SKILL/scripts/workflow_login.py" wechat --begin \
  --credentials-file "$HC_PRIVATE/wechat.json" \
  --challenge-file "$HC_PRIVATE/wechat-challenge.json"
```

在微信里扫描官方返回的二维码或授权页面并确认，然后等待同一份授权：

```bash
"$HC_PYTHON" "$HC_SKILL/scripts/workflow_login.py" wechat --wait \
  --credentials-file "$HC_PRIVATE/wechat.json" \
  --challenge-file "$HC_PRIVATE/wechat-challenge.json"
```

`pending` 表示仍在等待，`connected` 才表示取得登录凭据。需要手机数字验证时，让Agent按当前 `--help` 使用标准输入入口，不把验证码写进命令参数。二维码过期后才明确重启该扫码申请；不连续申请多张二维码。

**当前还有一步需要Agent辅助：** 扫码文件只为桥接器加载机器人身份与token，不会自动配置审核人。Agent必须从已授权的官方登录／私聊事件中核对本人的稳定ID，设置本进程的 `HC_WECHAT_RECIPIENT`、`HC_WECHAT_ALLOWED_CHATS`、`HC_WECHAT_APPROVERS`。白名单环境变量是逗号分隔的稳定ID文本；本人私聊只填写已核实的单一ID，不加JSON方括号。不能填微信昵称、手机号或猜出来的ID，也不能把白名单设为空或通配所有人。凭据不得在这一步打印。没有可靠ID时停在待配置，优先使用飞书向导。

桥接启动后，先给刚绑定的机器人发一条私聊，建立可回信上下文。重启或上下文过期时可能需要再发一次。当前微信适配器只开放本人私聊，不把它扩展成群聊审核。

## 第四步：从方案进入真实工作流

对Agent说：

```text
账号和审核人已配置。请把已检查的创作交接导入一个新的本地项目，暂不生成。
展示项目编号、当前方案、即梦画布、准确账号、图像/视频模型、审核接收人和上传素材范围。
先验证0费用审核，再分别向我申请生图和生视频预算。真实运行中保存任务身份，出错只恢复同一次任务。
```

以下是Agent需要完成的连接点：

1. 用 `creative_handoff.py` 检查共享创作包，导出**新路径**的零预算草稿。导出不批准任何生成。
2. 用 `director_workflow.py init` 建立独立项目，再用 `plan --file` 导入。用于真实即梦的项目模式、图像/视频provider与执行器配置必须明确，不能把模拟示例JSON改个标题就当作真实片。
3. 配置文件是含 `providers` 对象的JSON。即梦条目名是 `dreamina-canvas`，可包含 `executable`、`profile`、`project_id` 以及 `image`、`video` 参数块；模型参数以现场目录为准。`project_id`在这里指即梦**画布ID**，不是本地工作流项目号。由Agent读取实时模型与素材要求生成配置，不让新用户猜字段。
4. 把核对过的账号、上传范围、阶段与累计预算绑定到当前项目修订和素材，再生成手机审核请求。默认零预算、无生成范围的草稿不会自行变成付费请求。
5. 明确允许向飞书／微信发送本项目的分镜和视频后，启动对应通道。工作流数据库和审批数据库必须分开；每个审批库只保留一个协调进程。

飞书桥接启动模板如下，前提是这些文件和项目已经由Agent建立、核对；不要直接复制占位值运行：

```bash
"$HC_PYTHON" "$HC_SKILL/scripts/workflow_bridge.py" \
  --channel feishu --run \
  --engine-db "$HC_RUN/workflows.sqlite3" \
  --approval-db "$HC_RUN/approvals.sqlite3" \
  --artifact-root "$HC_RUN/artifacts" \
  --project-id "本地工作流项目号" \
  --feishu-credentials "$HC_PRIVATE/feishu.json" \
  --config "$HC_RUN/providers.json" \
  --generation-provider dreamina-canvas
```

该模板启用消息监听与审核处理，**未启用自动推进调度，也不会主动发送待审事件**；待审消息在Engine推进时发送。Agent做0费用审核测试时，需先确认此项目无生成范围、无有效生成批准，再让Engine发送对应请求。当你明确允许继续本项目的已批准任务时，才在同一命令加 `--resume-authorized`；此参数仍不批准内容、上传或费用。不要同时启动两个版本的命令。

微信使用 `--channel wechat` 和 `--wechat-credentials`，并需先配置上节说明的本人稳定ID与白名单。不要同时传飞书与微信凭据文件。

### 取报价和批准费用有什么区别

即梦报价是官方CLI对具体已保存节点的当前估价，不能把旧片价格、余额或总秒数相乘当成确定报价。图生视频还需要实际分镜图，生图之前的文字转视频估价不能冒充最终图生视频报价。

**本包 `director_workflow.py` 没有 `quote-only` 子命令。** 如需只报价，由Agent在用户授权范围内保存专用、不运行的草稿，再用实时CLI的报价命令；不得启动调度或用 `tick` 假装只查询价格。待用户看清价格、预算上限和范围后再进入获准阶段。报价过期、涨价、换模型或重做增加次数时重新核对。

读完3.0发来的有效请求后，在同一机器人私聊回复 **`同意`** 或 **`拒绝`**。有多项待审、内容变更或刚处理过上一项时，先按提示回复编号。机器人会重新展示选定请求的内容、账号与费用，再等这两个字。收到“已记录，等待工作流核验”表示决定已入队，实际执行状态以本地工作流为准。遇到旧版消息，请Agent重发新版请求。

**内容审核、允许上传、允许生图、允许生视频是不同决定。** 审图时0费用同意不会给视频生成授权。合成如需重编码统一规格，另有独立的0费用本地处理审核。只有当前本人、当前机器人、当前会话和有效请求的回复才可受理；引用旧消息、过期或无法可靠确认消息时间时会暂停并提示重新选择，不猜测你要批哪一项。

## 第五步：合成、终审与结束

分镜逐镜审批通过并获准视频预算后，工作流逐镜生成视频。全部视频就绪后，它会检查时长、画幅、帧率和音轨，按镜号顺序合成并回传成片待终审。默认拼接保留原时序，遇到不兼容规格就暂停。可选统一规格会保留原片，另存副本，需你看清影响后独立批准。若想合成前逐条看视频，请在原Agent会话要求分阶段处理，并由Agent停在合成前组织看片。

成片回传后，请实际打开并播放，再按该版本的审核提示回复“同意”或“拒绝”；需要选择时先回复编号。保存原项目号、作品目录、各镜头和最终片路径，之后续作可从这里恢复。最终内容通过不等于对外发布，本工作流不会自动发平台。

## 遇到问题时

| 看到的情况 | 应该怎么做 |
| --- | --- |
| 找不到Skill或仍显示2.x | 核对实际解析目录，确认新包完整安装；新开会话重新发现Skill，不混读两份目录 |
| `dreamina-canvas` 找不到 | 检查官方安装结果和PATH；安装了 `dreamina` 不代表画布CLI已安装 |
| 浏览器能打开即梦，CLI仍要求登录 | 在同一系统用户、同一profile完成官方CLI授权，再核对账号，不复制浏览器Cookie |
| CLI提示账号、空间或权限变化 | 停止继续提交，恢复原账号／空间；明确更换时重新规划、核对报价和审批 |
| 飞书长连接方式保存失败 | 保持配对程序在线，确认实际连接建立；查网络、App ID/Secret和组织，不通过放开权限碰运气 |
| 飞书机器人找不到 | 核对组织、机器人能力、仅本人可用范围及内部版本已启用；从本应用App ID对应的链接打开 |
| 配对口令发了但终端没收到 | 核对同一个机器人、本人私聊和当前完整口令；确认事件已添加且生效，关闭同应用其他监听。先看终端，配对向导不会主动回信 |
| 飞书已收口令但仍未绑定 | 回当前配对终端输入 `确认绑定`；看到配对保存成功才算完成 |
| 微信二维码过期 | 明确重启一次扫码申请；未过期的同一申请继续wait，不循环申请新码 |
| 微信扫码成功但不能启动审核 | 继续核对本人稳定ID和三项审核设置；登录成功不等于审核人已绑定 |
| 微信无回信 | 先给正确机器人发一条私聊刷新上下文，再核对唯一桥接进程、账号和白名单；不通过反复扫码重置所有状态 |
| 文本能收，图片或视频打不开 | 检查媒体依赖、权限、文件格式与实际送达；不能把文字通知当成媒体已交付 |
| 手机审批被拒绝或没继续 | 读回执：多项时先选编号；内容变更或过期时重新核对。确认本人、同机器人、同会话；旧版消息让Agent重发。已入队但没继续时查本地状态与预算，不反复回复同意 |
| `coordinator_busy` | 已有协调器占用审批库，先找到原进程；不要删除锁文件或让两个进程抢同一项目 |
| 合成暂停 | 保留原片，查看受控原因；由Agent给出保留分片、获准统一规格或重做的选择 |
| 超时、进程退出或电脑休眠 | 读取原任务和操作ID，先查询远端结果；不要重建项目、删数据库或换ID重复生成 |

恢复时先让Agent使用**原数据库、原供应商配置、原素材目录和原项目号**查看状态：

```bash
"$HC_PYTHON" "$HC_SKILL/scripts/director_workflow.py" \
  --db "$HC_RUN/workflows.sqlite3" \
  --config "$HC_RUN/providers.json" \
  --artifacts "$HC_RUN/artifacts" \
  status "原本地工作流项目号"
```

真实项目不能省略原 `--config`，否则仅加载模拟执行器，可能无法正确判断原审批与阶段。状态读取会按配置查询当前官方账号与空间，属于使用原profile的只读核对，不是离线doctor。需要 `resume` 时，也沿用这些全局参数，并核对原操作ID和明确选择恢复；它不是重新开始按钮。重启桥接仍使用原来的项目、两份数据库、素材目录和配置。审批过期或内容变化时重新审，不补造过去的同意。

## MiniMax Design目前怎么用

MiniMax Design走官方桌面应用与本机MCP，不存在本包可承诺的同名CLI扫码命令。可以在你自己的应用里登录、选专用项目，再由Agent列能力与准备可审阅请求。即梦的账号和积分不会与它共用。

3.0的MiniMax Design适配提供能力检查、受限请求准备和另行授权的纯文字写入。由于账号核验、可靠报价与硬费用上限、媒体提交幂等保障仍未具备，**自动付费生成保持关闭**。`execute` 在余额充足时可能直接提交付费任务，询价应使用能明确保持未提交状态的入口。
