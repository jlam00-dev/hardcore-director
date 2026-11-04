#!/usr/bin/env python3
"""Opt-in local coordinator for user-owned Feishu/Weixin review channels.

Default invocation and --doctor only print setup instructions; they do not read
credential files, log in, install dependencies, or contact a platform. --run
explicitly enables delivery/listening for the chosen existing project IDs.
--resume-authorized additionally enables the local engine scheduler. Network
callbacks only enqueue approvals; all engine calls happen on the owner thread.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import errno
import importlib.util
import json
import os
from pathlib import Path
import stat
import threading
import time
from typing import Any

from hc_workflow.channels import ApprovalBroker, ChannelError, ConfigurationError, create_channel


class CoordinatorBusy(ChannelError):
    """Another local coordinator owns this private approval queue."""


SOURCES = {
    "feishu_sdk": "https://github.com/larksuite/oapi-sdk-python/tree/0d9749a4728446a0ffa2e8374b37b5e1ce1cfd9c",
    "feishu_console": "https://open.feishu.cn/app",
    "wechat_protocol": "https://github.com/Tencent/openclaw-weixin/blob/874637a0dbc24050f72d1385add4fc6170a2d726/docs/protocol_zh_CN.md",
    "wechat_setup": "https://github.com/Tencent/openclaw-weixin/blob/874637a0dbc24050f72d1385add4fc6170a2d726/README.zh_CN.md",
    "wechat_license": "https://github.com/Tencent/openclaw-weixin/blob/874637a0dbc24050f72d1385add4fc6170a2d726/LICENSE",
}


def setup_report(provider: str) -> dict[str, Any]:
    common = {
        "mode": "offline-setup-report", "network_used": False, "installed_anything": False,
        "approvals": "exact stage + project + revision + one-use nonce + scope/budget digests; expiry and sender/chat allowlists; separate SQLite queue",
        "live_tested": False, "sources": SOURCES,
        "required_local_choices": ["existing workflow database and project IDs", "authorized artifact directory",
                                   "separate private approval database", "explicit generation scope and stage budget in the plan"],
    }
    if provider == "feishu":
        return dict(common, provider=provider,
            optional_dependency={"name": "lark-oapi", "present": importlib.util.find_spec("lark_oapi") is not None,
                                 "reviewed_reference_version": "1.7.5", "license": "MIT",
                                 "user_install_command": "python3 -m pip install lark-oapi"},
            required_environment=["HC_FEISHU_APP_ID", "HC_FEISHU_APP_SECRET", "HC_FEISHU_RECIPIENT", "HC_FEISHU_ALLOWED_CHATS", "HC_FEISHU_APPROVERS"],
            setup_steps=["在飞书开放平台创建自己的企业自建应用并启用机器人。按 references/support/remote-setup-guide.md 使用 feishu_setup.py 在本机保存凭据、配对本人私聊。",
                         "先启动配对监听，再在开放平台保存长连接订阅、添加 im.message.receive_v1 并启用仅本人可用的内部版本。",
                         "从本人私聊发送一次性配对口令，在配对终端输入确认绑定。正式运行时传入私有凭据文件，或配置等价的稳定 ID 与白名单。",
                         "对新版有效审核请求回复同意或拒绝；多项待审先按提示选编号并核对内容与费用。",
                         "保持电脑和桥接进程运行；无需公网回调地址。先完成离线检查，再由用户明确运行 --run；--resume-authorized 才启动本地已有授权任务的调度。"],
            capabilities={"inbound_approval": True, "transport": "official SDK WebSocket message events", "card_actions": False, "image_delivery": True, "file_delivery": True})
    if provider == "wechat":
        return dict(common, provider=provider, protocol_reference_version="2.4.10", source_license="MIT (Tencent LICENSE text; GitHub metadata says Other)",
            optional_dependency={"name": "cryptography", "present": importlib.util.find_spec("cryptography") is not None,
                                 "purpose": "Tencent documented AES-128-ECB/PKCS#7 media encryption; missing dependency blocks image review",
                                 "user_install_command": "python3 -m pip install cryptography"},
            required_environment=["HC_WECHAT_BOT_TOKEN", "HC_WECHAT_BOT_ID", "HC_WECHAT_RECIPIENT", "HC_WECHAT_ALLOWED_CHATS", "HC_WECHAT_APPROVERS"],
            optional_environment=["HC_WECHAT_CONTEXT_TOKEN (memory only; otherwise send the bot a private message first)"],
            setup_steps=["微信已有 Tencent 官方 openclaw-weixin/iLink 双向 Bot 通道，不使用个人号外挂或逆向私有协议。",
                         "本包提供按官方公开协议实现的 workflow_login.py 扫码向导；先阅读该脚本 --help，再由用户主动执行 begin/wait。不会自动安装 OpenClaw、创建账号或启动扫码。",
                         "用户用自己的微信扫码并确认授权，向导仅将凭据保存到用户明确指定、Skill/Git之外的私有0600文件，不在stdout显示token。",
                         "运行bridge时明确传 --run --wechat-credentials <该私有文件>；只在用户启用运行后读取并临时注入本进程环境，绝不自动搜索插件目录。也可自行设置环境变量。",
                         "可选官方OpenClaw入口（本包运行不要求安装）：Tencent README中的插件安装与openclaw channels login --channel openclaw-weixin流程。",
                         "配置自己的私聊 peer ID 为 recipient、allowed_chats 和 approvers。群聊未在本适配器开放。先给 Bot 发一条私聊，以取得内存中的 context_token。",
                         "媒体上传遵循官方 getuploadurl、AES 加密和 CDN 引用；出站链接只能去文档列出的 HTTPS CDN，不把 Bot token 传给 CDN。",
                         "本次doctor仅作离线检查；版本随附的真实联调记录见audits/workflow-v3.0.md，自己的服务端契约、账号可用性和额度仍需现场确认。保持电脑/进程运行，--run 后才联网，--resume-authorized 才启用本地调度。"],
            capabilities={"inbound_approval": True, "transport": "published official iLink private-chat long poll", "card_actions": False,
                          "image_delivery": importlib.util.find_spec("cryptography") is not None,
                          "file_delivery": importlib.util.find_spec("cryptography") is not None})
    raise ConfigurationError("unsupported channel")


def _read_wechat_credentials(path: Path) -> dict[str, str]:
    """Explicit user-selected file only. Caller invokes exclusively after --run."""
    source_root = Path(__file__).resolve().parents[1]
    if path.is_symlink():
        raise ConfigurationError("credentials file must not be a symbolic link")
    path = path.resolve(strict=True)
    metadata = path.stat()
    if path.is_relative_to(source_root) or not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ConfigurationError("credentials require a private 0600 regular file outside the Skill")
    if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
        raise ConfigurationError("credentials must be owned by the current user")
    if not 0 < metadata.st_size <= 65536:
        raise ConfigurationError("invalid credential file size")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise ConfigurationError("invalid credential file JSON") from None
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1 or data.get("provider") != "wechat":
        raise ConfigurationError("unsupported credential file schema")
    if data.get("api_base") != "https://ilinkai.weixin.qq.com":
        raise ConfigurationError("credential API host is not supported by this audited protocol adapter")
    values = {}
    for key, environment_name in (("bot_token", "HC_WECHAT_BOT_TOKEN"), ("ilink_bot_id", "HC_WECHAT_BOT_ID")):
        value = data.get(key)
        if not isinstance(value, str) or not 0 < len(value) <= 16384 or any(char.isspace() for char in value):
            raise ConfigurationError("credential file is missing a valid bot identity/token")
        values[environment_name] = value
    return values


def _read_provider_config(path: Path) -> dict[str, dict[str, Any]]:
    """Only an explicitly selected config, called after --run; never log it."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        raise ConfigurationError("provider configuration could not be read as JSON") from None
    if not isinstance(value, dict) or not isinstance(value.get("providers"), dict):
        raise ConfigurationError("provider configuration requires a providers object")
    providers = value["providers"]
    if any(not isinstance(name, str) or not isinstance(settings, dict) for name, settings in providers.items()):
        raise ConfigurationError("each configured provider requires a settings object")
    return providers


class WorkflowBridge:
    """Owner-thread coordinator. Its channel can be passed to Engine(channel=...)."""

    def __init__(self, engine: Any, channel: Any, project_ids: list[str], *, resume_authorized: bool = False,
                 clock=time.time):
        if not project_ids or any(not isinstance(item, str) or not item for item in project_ids):
            raise ConfigurationError("bridge requires explicitly scoped existing project IDs")
        self.engine, self.channel = engine, channel
        self.project_ids = frozenset(project_ids)
        self.resume_authorized, self.clock = resume_authorized, clock
        self._owner = threading.get_ident()
        self._coordinator_depth = 0
        self.stop_event = threading.Event()
        self._listener_failed = threading.Event()

    def run_once(self) -> dict[str, Any]:
        if threading.get_ident() != self._owner:
            raise ChannelError("only the local coordinator thread may consume approvals")
        with self._coordinator_guard():
            return self._run_once_locked()

    @contextmanager
    def _coordinator_guard(self):
        if threading.get_ident() != self._owner:
            raise ChannelError("only the local coordinator thread may own the queue lock")
        if self._coordinator_depth:
            self._coordinator_depth += 1
            try:
                yield
            finally:
                self._coordinator_depth -= 1
            return
        try:
            import fcntl
        except ImportError:
            raise ConfigurationError("this bridge requires local POSIX file locking") from None
        database = Path(self.channel.broker.path)
        if database.is_symlink():
            raise ConfigurationError("approval database must not be a symbolic link")
        lock_path = database.resolve(strict=True).with_name(database.name + ".coordinator.lock")
        if not hasattr(os, "O_NOFOLLOW"):
            raise ConfigurationError("safe coordinator file locking is unavailable")
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0), 0o600)
        except OSError:
            raise ConfigurationError("cannot safely open the private coordinator lock") from None
        acquired = False
        try:
            metadata = os.fstat(descriptor)
            if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
                    or metadata.st_uid != os.getuid() or metadata.st_nlink != 1 or metadata.st_size != 0):
                raise ConfigurationError("coordinator lock must be an empty private regular file owned by this user")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                if error.errno in {errno.EACCES, errno.EAGAIN}:
                    raise CoordinatorBusy("another coordinator holds the approval queue; this process did not take over") from None
                raise ConfigurationError("cannot acquire the private coordinator lock") from None
            acquired = True
            self._coordinator_depth = 1
            self.channel.broker.recover_claimed(self.project_ids)
            yield
        finally:
            self._coordinator_depth = 0
            try:
                if acquired:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _run_once_locked(self) -> dict[str, Any]:
        if not self._coordinator_depth:
            raise ChannelError("approval consumption requires the coordinator lock")
        results = []
        for item in self.channel.broker.drain(project_ids=self.project_ids):
            applied = False
            outcome_known = False
            try:
                if item["project_id"] not in self.project_ids or item["expires_at"] <= self.clock():
                    raise ChannelError("approval is outside this bridge scope or expired")
                if not item.get("binding_hash"):
                    raise ChannelError("remote approval requires a complete content binding hash")
                actor = f"{item['channel']}:{item['sender_id']}"
                arguments = {"stage": item["stage"], "actor": actor, "shot_ids": item["shot_ids"] or None,
                             "expected_revision": item["revision"], "expected_binding_hash": item["binding_hash"]}
                if item["decision"] == "approve":
                    self.engine.approve(item["project_id"], **arguments, budget=item["budget"],
                        live_scope=item["live_scope"], expires_at=item["expires_at"],
                        ttl_seconds=min(3600, item["expires_at"] - self.clock()))
                else:
                    self.engine.reject(item["project_id"], **arguments, reason="human rejected the bound channel review")
                applied = True
                outcome_known = True
            except Exception:
                # Core rechecks revision, complete hashes, scope, budgets and expiry.
                # No arbitrary engine/provider exceptions or channel secrets logged.
                outcome_known = True
            finally:
                # Ctrl-C/SystemExit/process interruption is not an explicit
                # rejection. Retain claimed when the apply result is unknown.
                if outcome_known:
                    self.channel.broker.acknowledge(item["queue_id"], applied=applied)
            results.append({"project_id": item["project_id"], "decision": item["decision"], "applied": applied})
        statuses = []
        if self.resume_authorized:
            for project_id in sorted(self.project_ids):
                try:
                    status = self.engine.tick(project_id)
                    statuses.append({"project_id": project_id, "status": status.get("status", "unknown")})
                except Exception:
                    statuses.append({"project_id": project_id, "status": "blocked_check_local_workflow"})
        return {"decisions": results, "scheduler_enabled": self.resume_authorized, "projects": statuses}

    def run(self, *, interval: float = 2.0) -> None:
        if not 0.5 <= interval <= 60:
            raise ConfigurationError("bridge interval must be between 0.5 and 60 seconds")
        with self._coordinator_guard():
            self._run_locked(interval=interval)

    def _run_locked(self, *, interval: float) -> None:
        def listen():
            try:
                self.channel.listen(self.stop_event)
            except Exception:
                self._listener_failed.set()
        listener = threading.Thread(target=listen, name="hc-review-channel", daemon=True)
        listener.start()
        try:
            while not self.stop_event.is_set():
                if self._listener_failed.is_set():
                    raise ChannelError("review listener stopped; coordinator paused without automatically reconnecting a new account")
                self.run_once()
                self.stop_event.wait(interval)
        finally:
            self.stop_event.set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", choices=("feishu", "wechat"), required=True)
    parser.add_argument("--doctor", action="store_true", help="Offline setup report, no credentials/network")
    parser.add_argument("--run", action="store_true", help="Explicitly enable channel message delivery and receiving")
    parser.add_argument("--engine-db", type=Path)
    parser.add_argument("--config", type=Path, help="Explicit provider configuration JSON (providers map), read only after --run")
    parser.add_argument("--approval-db", type=Path)
    parser.add_argument("--wechat-credentials", type=Path, help="Explicit user-owned 0600 QR credential file, read only after --run")
    parser.add_argument("--feishu-credentials", type=Path, help="Explicit user-owned 0600 paired Feishu file from feishu_setup.py, read only after --run")
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--project-id", action="append", default=[])
    parser.add_argument("--generation-provider", action="append", choices=("mock", "dreamina-canvas", "minimax-design"))
    parser.add_argument("--resume-authorized", action="store_true", help="Run local scheduler; existing per-stage spending/upload authorization remains mandatory")
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--retry-notification", help="Local-only reset of one unknown notification after checking prior delivery")
    parser.add_argument("--confirm-resend", action="store_true", help="Explicitly allow this reviewed notification to be sent again")
    args = parser.parse_args(argv)
    if args.wechat_credentials and args.feishu_credentials:
        parser.error("select only one channel credential file")
    if args.wechat_credentials and args.channel != "wechat" or args.feishu_credentials and args.channel != "feishu":
        parser.error("credential file does not match the selected channel")
    if args.retry_notification:
        if not args.confirm_resend or not args.approval_db or not args.approval_db.is_file():
            parser.error("retry requires an existing --approval-db and explicit --confirm-resend")
        broker = ApprovalBroker(args.approval_db)
        try:
            allowed = broker.allow_notification_retry(args.channel, args.retry_notification)
        finally:
            broker.close()
        print(json.dumps({"retry_enabled": allowed, "network_used": False,
                          "note": "next explicitly running bridge may resend; already confirmed deliveries are not reset"}))
        return 0 if allowed else 1
    if args.doctor or not args.run:
        print(json.dumps(setup_report(args.channel), ensure_ascii=False, indent=2))
        return 0
    if not args.engine_db or not args.approval_db or not args.artifact_root or not args.project_id:
        parser.error("--run requires --engine-db, --approval-db, --artifact-root and --project-id")
    if not args.engine_db.is_file():
        parser.error("select an existing user-authorized workflow database")
    if args.engine_db.resolve() == args.approval_db.resolve():
        parser.error("approval database must be separate from workflow state")
    channel = None
    engine = None
    original_environment: dict[str, str | None] = {}
    try:
        if args.wechat_credentials:
            if args.channel != "wechat":
                raise ConfigurationError("WeChat credentials cannot configure another provider")
            for key, value in _read_wechat_credentials(args.wechat_credentials).items():
                original_environment[key] = os.environ.get(key)
                os.environ[key] = value
        if args.feishu_credentials:
            from feishu_setup import load_feishu_environment
            for key, value in load_feishu_environment(args.feishu_credentials).items():
                original_environment[key] = os.environ.get(key)
                os.environ[key] = value
        from hc_workflow.engine import Engine
        from hc_workflow.providers import get_provider
        provider_config = _read_provider_config(args.config) if args.config else {}
        selected = args.generation_provider or ["mock"]
        if args.config and any(name != "mock" and name not in provider_config for name in selected):
            raise ConfigurationError("selected generation provider is missing from the explicit configuration")
        providers = {name: get_provider(name, provider_config.get(name, {})) for name in selected}
        channel = create_channel(args.channel, artifact_root=args.artifact_root, approval_db=args.approval_db)
        engine = Engine(args.engine_db, providers=providers, channel=channel, artifact_dir=args.artifact_root)
        for project_id in args.project_id:
            engine.status(project_id)  # Fail before networking for unknown projects.
        bridge = WorkflowBridge(engine, channel, args.project_id, resume_authorized=args.resume_authorized)
        bridge.run(interval=args.interval)
    except KeyboardInterrupt:
        return 0
    except CoordinatorBusy:
        print(json.dumps({"status": "blocked", "reason": "coordinator_busy", "message": "另一协调器正在处理此审批库；本进程未接管。"}, ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps({"status": "blocked", "message": "桥接未启动或已暂停。请按 --doctor 核对自己的依赖、凭据、allowlist及本地工作流；未自动安装或重发未知消息。"}, ensure_ascii=False))
        return 1
    finally:
        if engine is not None:
            engine.close()
        if channel is not None:
            channel.broker.close()
        for key, previous in original_environment.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
