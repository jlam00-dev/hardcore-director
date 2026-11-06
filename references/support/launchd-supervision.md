# macOS 可选后台运行

当飞书或微信已经在前台通过收发测试时，可以让当前 macOS 用户的 `launchd` 托管桥接器。关闭终端后，已登录会话中的作业仍可运行。真实启用前，先确认审核对象、允许发送的素材、现有项目及其费用批准。指南中的作业由你手动加载。

## 1. 准备

- 保留已通过前台测试的同一个 Python、Skill、工作流库、审批库、素材目录与项目号。工作流库和审批库使用不同的绝对路径。先关闭该审批库上的手工桥接器，托管期间也由一个进程推进该项目。
- 准备一个本人拥有的 `0700` 私有目录保存 plist 和日志，先建好两个 `0600` 日志文件。凭据 JSON 留在独立的 `0600` 私有文件里，plist 只记录路径。日志仅供本机排查。
- 确认登录用户能从后台读取这些路径。给即梦配置填已验证的 CLI 绝对路径，用明确的 `PATH` 让后台找到 `ffmpeg`、`ffprobe`。后台进程不会加载交互 shell 的配置。

## 2. 保存并启动

以下以飞书为例。替换所有 `/ABS/…` 占位路径和本地项目号，再保存为私有目录中的 `hardcore-director.plist`。对这个项目明确启用已获批准任务的调度时保留 `--resume-authorized`，只监听审核时删去这一项。启用调度仍按项目内现有的阶段、上传和预算批准推进。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>local.hardcore-director.bridge</string>
  <key>ProgramArguments</key>
  <array>
    <string>/ABS/venv/bin/python3</string>
    <string>-B</string>
    <string>/ABS/hardcore-director/scripts/workflow_bridge.py</string>
    <string>--channel</string><string>feishu</string>
    <string>--run</string>
    <string>--resume-authorized</string>
    <string>--engine-db</string><string>/ABS/workflow/workflows.sqlite3</string>
    <string>--approval-db</string><string>/ABS/workflow/approvals.sqlite3</string>
    <string>--artifact-root</string><string>/ABS/workflow/artifacts</string>
    <string>--project-id</string><string>LOCAL_PROJECT_ID</string>
    <string>--feishu-credentials</string><string>/ABS/private/feishu.json</string>
    <string>--config</string><string>/ABS/workflow/providers.json</string>
    <string>--generation-provider</string><string>dreamina-canvas</string>
  </array>
  <key>WorkingDirectory</key><string>/ABS/workflow</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/ABS/ffmpeg-bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>StandardOutPath</key><string>/ABS/private/logs/bridge.out.log</string>
  <key>StandardErrorPath</key><string>/ABS/private/logs/bridge.err.log</string>
</dict>
</plist>
```

使用微信时，按[账号接入与运行指南](remote-setup-guide.md)换成 `--channel wechat` 与 `--wechat-credentials`，并由 Agent 从私有配置将已经核实的收件人、会话与审批人设置到桥接器进程。请先在同一用户的后台启动环境核对这些变量。两个通道只选其一。

在当前已登录的用户终端运行。启动后用 `print` 核对作业状态，再用一次已获许可的零费用审核验证实际收发。

```bash
HC_PLIST="/ABS/private/hardcore-director.plist"
HC_GUI="gui/$(id -u)"
HC_SERVICE="$HC_GUI/local.hardcore-director.bridge"
/usr/bin/plutil -lint "$HC_PLIST" &&
  /bin/launchctl bootstrap "$HC_GUI" "$HC_PLIST" &&
  /bin/launchctl print "$HC_SERVICE"
```

## 3. 停机和恢复

计划停机前先在本机查看当前状态，尽量等正在执行的外部操作有回执后再停。用以下命令卸载作业，避免 `KeepAlive` 再拉起它：

```bash
/bin/launchctl bootout "gui/$(id -u)/local.hardcore-director.bridge"
```

作业反复退出时先停机，再核对本机日志、凭据、网络、后台路径和是否有另一桥接器。修正后用同一个 plist 和同一个工作流库重新启动，既有审批、项目和操作记录可继续核对。看到结果不明的生成操作时，先查询原任务状态。微信重启后可能需要从已绑定的本人私聊发一条消息恢复回信上下文。

使用独立临时作业、模拟供应商及审核通道完成了本机强制终止测试。新进程读取原数据库，继续查询并取回同一模拟操作的结果。真实账号仍要现场核验。电脑需要保持唤醒、联网且当前用户保持登录。此手动加载方式在注销或重启后需要重新启动作业。
