#!/usr/bin/env python3
"""Explicit, local-only Feishu setup. Default/--doctor never reads credentials.

--configure reads App ID/Secret from the user's terminal, without echo, and
saves an unpaired private file. --pair explicitly connects the reviewed official
SDK, receives only a one-use private-chat pairing phrase, and saves one owner
only after confirmation in this terminal. Neither operation sends messages,
reads project artifacts, creates an application, or starts the workflow engine.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import getpass
import importlib.metadata
import importlib.util
import json
import logging
import multiprocessing
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tempfile
import time
from typing import Any, Callable
import warnings


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SDK_VERSION = "1.7.5"
MAX_FILE_BYTES = 65536
CONFIRMATION = "确认绑定"
SOURCES = {
    "console": "https://open.feishu.cn/app?lang=zh-CN",
    "enterprise_prerequisite": "https://open.feishu.cn/document/home/introduction-to-custom-app-development/self-built-application-development-process",
    "bot": "https://open.feishu.cn/document/uAjLw4CM/ugTN1YjL4UTN24CO1UjN/trouble-shooting/how-to-enable-bot-ability",
    "long_connection": "https://open.feishu.cn/document/ukTMukTMukTM/uYDNxYjL2QTM24iN0EjN/event-subscription-configure-",
    "receive_event": "https://open.feishu.cn/document/server-docs/im-v1/message/events/receive",
    "availability": "https://open.feishu.cn/document/home/introduction-to-scope-and-authorization/availability",
    "sdk": "https://github.com/larksuite/oapi-sdk-python",
}


class SetupError(RuntimeError):
    """Fixed diagnostics only; never interpolate credentials or SDK responses."""


def setup_report() -> dict[str, Any]:
    return {
        "mode": "offline-setup-report", "network_used": False,
        "credentials_read": False, "installed_anything": False,
        "live_tested": False, "sdk": {"name": "lark-oapi", "reviewed_version": SDK_VERSION,
            "present": importlib.util.find_spec("lark_oapi") is not None},
        "sources": SOURCES,
        "minimum_tenant_scopes": ["im:message:send_as_bot", "im:message.p2p_msg:readonly", "im:resource"],
        "steps": [
            "先成为飞书企业/团队用户；本机个人自用选择自己的组织。无需为此先付费升级。",
            "打开 console，创建企业自建应用；添加应用能力→机器人；权限管理仅开通列出的三项应用身份权限。",
            "在凭证与基础信息取得 App ID/Secret，自己在终端执行 --configure；不要把密钥发到聊天、命令参数或 Git。",
            "显式执行 --pair 并保持终端运行；在事件与回调→事件配置选择长连接（本地连接在线才能保存），添加接收消息 v2.0：im.message.receive_v1。",
            "应用发布→版本管理与发布→创建版本，可用范围只选择自己，由用户自行发布并完成租户审核；自用不打开对外共享。",
            "用本人账号向机器人私聊发送本机显示的一次性配对口令，再回本机输入确认绑定。设置程序不发消息、不读素材、不启动制作。",
            "配对完成后，bridge 使用显式 --run --channel feishu --feishu-credentials 路径；还需明确已有项目、状态库和素材目录。",
        ],
        "boundaries": ["配置文件必须在 Skill/Git 和共享临时目录之外；父目录0700，文件0600，属主为本人，不接受符号链接。",
            "审核图片和文件上传飞书需另行授权；飞书接通不授权向生成供应商上传素材、扣费或发布。",
            "电脑及桥接进程须在线；长连接无需公网端口。当前审核使用完整文本指令。"],
    }


def _path(value: str | Path) -> Path:
    raw = os.path.expanduser(str(value))
    candidate = Path(raw)
    if not raw or not candidate.is_absolute() or ".." in candidate.parts or any(ord(c) < 32 for c in raw):
        raise SetupError("请选择明确的绝对私有文件路径，不使用父目录跳转。")
    candidate = Path("/" + str(candidate).lstrip("/"))
    forbidden = (PACKAGE_ROOT, Path("/tmp").resolve(), Path("/var/tmp").resolve(),
                 Path("/dev/shm"), Path(tempfile.gettempdir()).resolve())
    if any(candidate.is_relative_to(root) for root in forbidden):
        raise SetupError("凭据必须保存在 Skill、Git 仓库和共享临时目录之外。")
    return candidate


@contextmanager
def _parent(value: str | Path, *, create: bool = False):
    """Walk with dir_fd/O_NOFOLLOW; hold the checked parent through all I/O."""
    path = _path(value)
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise SetupError("本机不支持此凭据入口所需的安全文件操作。")
    descriptor = None
    def reject_project_ancestor(directory: int) -> None:
        for marker in (".git", "SKILL.md"):
            try:
                os.stat(marker, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise SetupError("凭据不能保存在任何 Skill 目录或 Git 仓库内。")
    try:
        descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        reject_project_ancestor(descriptor)
        for component in path.parent.parts[1:]:
            try:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(component, 0o700, dir_fd=descriptor)
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            reject_project_ancestor(descriptor)
        info = os.fstat(descriptor)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise SetupError("凭据父目录必须属于本人且权限严格为0700。")
        yield path, descriptor
    except SetupError:
        raise
    except OSError:
        raise SetupError("私有路径不可用；请检查符号链接、属主、目录权限和文件是否存在。") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_at(path: Path, parent: int) -> dict[str, Any]:
    try:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                    or not 0 < info.st_size <= MAX_FILE_BYTES):
                raise SetupError("凭据须为本人拥有的0600小型普通文件，不接受链接。")
            raw = stream.read(MAX_FILE_BYTES + 1)
            if len(raw.encode("utf-8")) > MAX_FILE_BYTES:
                raise SetupError("私有凭据超过支持大小。")
            value = json.loads(raw)
    except SetupError:
        raise
    except (OSError, ValueError, UnicodeError):
        raise SetupError("明确指定的私有凭据无法安全读取。") from None
    if not isinstance(value, dict):
        raise SetupError("私有凭据格式无效。")
    return value


def read_private_json(value: str | Path) -> dict[str, Any]:
    with _parent(value) as (path, parent):
        return _read_at(path, parent)


def _write_at(path: Path, parent: int, data: dict[str, Any], *, replace: bool = False) -> None:
    encoded = (json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()
    if len(encoded) > MAX_FILE_BYTES:
        raise SetupError("凭据超过支持大小。")
    temporary = ".hc-feishu-" + secrets.token_hex(16)
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            _read_at(path, parent)  # A new insecure target must not be overwritten.
            os.replace(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent)
        else:
            os.link(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        os.fsync(parent)
    except SetupError:
        raise
    except OSError:
        raise SetupError("私有凭据未能安全保存；已有文件不会被隐式覆盖。") from None
    finally:
        try:
            os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError:
            pass


@contextmanager
def _locked(value: str | Path, *, create: bool = False):
    with _parent(value, create=create) as (path, parent):
        name = path.name + ".lock"
        try:
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        except OSError:
            raise SetupError("该凭据已有设置进程或遗留锁；请在本机核实后再继续。") from None
        try:
            os.close(descriptor)
            yield path, parent
        finally:
            os.unlink(name, dir_fd=parent)


def _identifier(value: Any, prefix: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9_-]{1,150}", value):
        raise SetupError("应用或配对标识格式无效。")
    return value


def _validate(data: dict[str, Any], *, require_paired: bool = False) -> dict[str, Any]:
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1 or data.get("provider") != "feishu":
        raise SetupError("此文件不是支持的飞书凭据。")
    _identifier(data.get("app_id"), "cli_")
    secret = data.get("app_secret")
    if not isinstance(secret, str) or not 0 < len(secret) <= 16384 or any(c.isspace() or ord(c) < 32 for c in secret):
        raise SetupError("应用凭据不完整或格式无效。")
    if data.get("state") not in {"configured", "paired"}:
        raise SetupError("凭据配对状态无效。")
    if data["state"] == "paired":
        owner, chat = _identifier(data.get("owner_open_id"), "ou_"), _identifier(data.get("owner_chat_id"), "oc_")
        if data.get("recipient") != chat or data.get("allowed_chats") != [chat] or data.get("approvers") != [owner]:
            raise SetupError("本人配对与单人白名单不一致。")
    elif require_paired:
        raise SetupError("请先在本机完成 --pair，未绑定凭据不能启动桥接。")
    elif any(key in data for key in ("owner_open_id", "owner_chat_id", "recipient", "allowed_chats", "approvers")):
        raise SetupError("未配对文件不能包含部分审批人或会话绑定。")
    return data


def load_feishu_environment(value: str | Path) -> dict[str, str]:
    """Explicit file only; the bridge calls this exclusively after --run."""
    data = _validate(read_private_json(value), require_paired=True)
    return {"HC_FEISHU_APP_ID": data["app_id"], "HC_FEISHU_APP_SECRET": data["app_secret"],
            "HC_FEISHU_RECIPIENT": data["owner_chat_id"], "HC_FEISHU_ALLOWED_CHATS": data["owner_chat_id"],
            "HC_FEISHU_APPROVERS": data["owner_open_id"]}


def pairing_candidate(payload: Any, app_id: str, phrase: str) -> dict[str, str] | None:
    try:
        header, event = payload["header"], payload["event"]
        sender, message = event["sender"], event["message"]
        if (header.get("app_id") != app_id or header.get("event_type") != "im.message.receive_v1"
                or sender.get("sender_type") != "user" or message.get("chat_type") != "p2p"
                or message.get("message_type") != "text" or json.loads(message["content"]).get("text") != phrase):
            return None
        return {"open_id": _identifier(sender["sender_id"]["open_id"], "ou_"),
                "chat_id": _identifier(message["chat_id"], "oc_")}
    except (KeyError, TypeError, ValueError, AttributeError, SetupError):
        return None


def _sdk_worker(connection, sdk_loader: Callable | None = None) -> None:
    """Isolated process: suppress SDK logs, send only status and matched IDs."""
    previous_logging = logging.root.manager.disable
    try:
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            logging.disable(logging.CRITICAL)
            credentials, phrase = connection.recv()
            if sdk_loader is None:
                import lark_oapi as sdk
            else:
                sdk = sdk_loader()
            found = False
            unmatched_reported = False

            def receive(event):
                nonlocal found, unmatched_reported
                if found:
                    return
                try:
                    candidate = pairing_candidate(json.loads(sdk.JSON.marshal(event)), credentials["app_id"], phrase)
                    if candidate:
                        found = True
                        connection.send({"status": "candidate", **candidate})
                    elif not unmatched_reported:
                        unmatched_reported = True
                        connection.send({"status": "message_not_matched"})
                except BaseException:
                    if not unmatched_reported:
                        unmatched_reported = True
                        connection.send({"status": "message_not_matched"})

            handler = sdk.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(receive).build()

            # The reviewed 1.7.5 start() may stay alive after its receive task
            # fails. Observe its actual lifecycle, not the worker's liveness.
            # These control outcomes must never share a diagnostic rate limit.
            class ObservedClient(sdk.ws.Client):
                async def _connect(self):
                    await super()._connect()
                    connection.send({"status": "connected" if self._conn is not None else "connection_failed"})

                async def _disconnect(self):
                    # SDK lock/socket cleanup can itself block. Report the
                    # closing transition before awaiting it, so a live worker
                    # cannot mask a connection that is already being closed.
                    connection.send({"status": "disconnecting"})
                    try:
                        return await super()._disconnect()
                    finally:
                        connection.send({"status": "disconnected"})

                async def _receive_message_loop(self):
                    try:
                        return await super()._receive_message_loop()
                    finally:
                        connection.send({"status": "receive_stopped"})

            client = ObservedClient(credentials["app_id"], credentials["app_secret"], event_handler=handler,
                                    log_level=sdk.LogLevel.ERROR, auto_reconnect=False)
            connection.send({"status": "connecting"})
            client.start()
            connection.send({"status": "listener_stopped"})
    except BaseException:
        try:
            connection.send({"status": "failed"})
        except BaseException:
            pass
    finally:
        try:
            logging.disable(previous_logging)
            connection.close()
        except BaseException:
            pass


def collect_pair(credentials: dict[str, Any], phrase: str, timeout: float,
                 progress: Callable[[str], None]) -> dict[str, str] | None:
    try:
        if importlib.metadata.version("lark-oapi") != SDK_VERSION:
            raise SetupError("此设置入口仅验证过 lark-oapi 1.7.5；不会自动安装或升级。")
    except importlib.metadata.PackageNotFoundError:
        raise SetupError("本机缺少官方 lark-oapi 1.7.5；本程序不会自动安装。") from None
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_sdk_worker, args=(child,), daemon=True)
    try:
        process.start()
        child.close()
        parent.send(({"app_id": credentials["app_id"], "app_secret": credentials["app_secret"]}, phrase))
        deadline = time.monotonic() + timeout
        connected = False
        shown = set()
        while time.monotonic() < deadline:
            if parent.poll(min(0.25, max(0, deadline - time.monotonic()))):
                message = parent.recv()
                status = message.get("status") if isinstance(message, dict) else None
                if status == "candidate":
                    if not connected:
                        raise SetupError("尚未确认官方长连接已建立；本次配对未保存。")
                    return {"open_id": _identifier(message.get("open_id"), "ou_"),
                            "chat_id": _identifier(message.get("chat_id"), "oc_")}
                if status in {"failed", "connection_failed", "listener_stopped"}:
                    raise SetupError("官方长连接未能保持运行；请核对自己的应用凭据、网络和控制台配置。")
                if status in {"disconnecting", "disconnected", "receive_stopped"}:
                    if not connected:
                        raise SetupError("官方长连接未能建立；本次配对未保存，请核对应用凭据、网络和控制台配置。")
                    raise SetupError("官方长连接已中断或正在关闭；本次配对未保存，请重新启动配对后使用新口令。")
                if status not in {"connecting", "connected", "message_not_matched"}:
                    raise SetupError("配对监听返回了不支持的状态；本次配对未保存。")
                if status == "connected":
                    connected = True
                if status not in shown:
                    shown.add(status)
                    progress({"connecting": "正在尝试建立飞书连接，尚未确认连通。",
                              "connected": "飞书连接已建立。现在发送本次完整口令；机器人不会自动回复，以此终端提示为准。",
                              "message_not_matched": "已收到消息，但未匹配本次私聊口令。请仅发送口令完整一行，不附加空格或换行。"}[status])
            elif not process.is_alive():
                raise SetupError("设置监听已退出；未保存任何新的审批绑定。")
        return None
    except (EOFError, OSError):
        raise SetupError("设置监听中断；未保存任何新的审批绑定。") from None
    finally:
        parent.close()
        child.close()
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=3)
            if process.is_alive():
                process.kill()
                process.join(timeout=3)


def configure(value: str | Path, *, secret_reader: Callable[[str], str]) -> dict[str, Any]:
    with _locked(value, create=True) as (path, parent):
        try:
            os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise SetupError("凭据文件已存在；使用 --pair，或为另一个应用选择新文件。")
        data = {"schema_version": 1, "provider": "feishu", "state": "configured",
                "app_id": secret_reader("App ID（不回显）："),
                "app_secret": secret_reader("App Secret（不回显）："), "created_at": int(time.time())}
        _validate(data)
        _write_at(path, parent, data)
    return {"status": "configured_not_paired", "credentials_file": str(path), "network_used": False,
            "credentials_printed": False, "message": "应用凭据已私有保存；尚未绑定审批人，请显式执行 --pair。"}


def _confirmation_reason(reader: Callable[[str], str], prompt: str) -> str:
    """Classify only the observed read result; never record its contents.

    A timed reader must raise TimeoutError to report a timeout. An arbitrary
    reader returning an empty string does not prove how an earlier run ended.
    KeyboardInterrupt/SystemExit retain their existing cancellation path.
    """
    try:
        value = reader(prompt)
    except TimeoutError:
        return "wait_timeout"
    except EOFError:
        return "eof"
    except Exception:
        return "read_failed"
    if type(value) is not str:
        return "read_failed"
    if value == CONFIRMATION:
        return "exact_confirmed"
    return "empty_line" if value == "" else "nonmatching_input"


def pair(value: str | Path, *, timeout: float = 300, rebind: bool = False,
         listener: Callable = collect_pair, confirm_reader: Callable[[str], str] = input,
         progress: Callable[[str], None] = print) -> dict[str, Any]:
    if not 1 <= timeout <= 900:
        raise SetupError("配对监听时间必须为1至900秒。")
    with _locked(value) as (path, parent):
        data = _validate(_read_at(path, parent))
        if data["state"] == "paired" and not rebind:
            raise SetupError("此应用已绑定本人；重新绑定必须显式传 --rebind。")
        phrase = "硬核导演配对-" + secrets.token_hex(16)
        progress("本次一次性配对口令（请等连接成功后，仅用本人账号向机器人私聊发送）：\n" + phrase)
        progress("保持此终端运行，完成控制台长连接、事件订阅与仅自己可用的版本发布；本程序不代为发布。")
        candidate = listener(data, phrase, timeout, progress)
        if candidate is None:
            return {"status": "pairing_timed_out", "network_used": True, "binding_saved": False}
        owner, chat = _identifier(candidate.get("open_id"), "ou_"), _identifier(candidate.get("chat_id"), "oc_")
        progress("已收到并逐字匹配私聊口令，接收监听已结束。请确认是自己刚发送的消息。")
        reason = _confirmation_reason(confirm_reader, "确认是本人刚发送的私聊后，输入“确认绑定”保存；其他输入取消：")
        if reason != "exact_confirmed":
            progress({"wait_timeout": "确认等待超时；未保存绑定。", "eof": "确认输入已结束；未保存绑定。",
                      "empty_line": "没有收到确认文字；未保存绑定。", "nonmatching_input": "确认文字不完全匹配；未保存绑定。",
                      "read_failed": "无法读取确认输入；未保存绑定。"}[reason])
            return {"status": "pairing_cancelled", "network_used": True, "binding_saved": False,
                    "confirmation_reason": reason}
        if _read_at(path, parent) != data:
            raise SetupError("凭据在配对期间发生变化；本次绑定未写入。")
        updated = dict(data, state="paired", owner_open_id=owner, owner_chat_id=chat,
                       recipient=chat, allowed_chats=[chat], approvers=[owner], paired_at=int(time.time()))
        _validate(updated, require_paired=True)
        _write_at(path, parent, updated, replace=True)
    return {"status": "paired", "credentials_file": str(path), "network_used": True,
            "binding_saved": True, "credentials_printed": False,
            "confirmation_reason": "exact_confirmed",
            "message": "只保存本人私聊与单人白名单；尚未发送消息、上传素材或启动工作流。"}


def _terminal_secret(prompt: str) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            return getpass.getpass(prompt)
        except getpass.GetPassWarning:
            raise SetupError("无法关闭终端回显；请在自己的交互终端重试。") from None


def main(argv: list[str] | None = None, *, secret_reader: Callable = _terminal_secret,
         confirm_reader: Callable = input, listener: Callable = collect_pair) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--doctor", action="store_true")
    mode.add_argument("--configure", action="store_true", help="Explicitly read App ID/Secret in your local terminal; no network")
    mode.add_argument("--pair", action="store_true", help="Explicitly enable bounded official SDK private-chat pairing; no outgoing messages")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--rebind", action="store_true", help="Deliberately replace an existing owner after local confirmation")
    args = parser.parse_args(argv)
    if args.doctor or not (args.configure or args.pair):
        print(json.dumps(setup_report(), ensure_ascii=False, indent=2))
        return 0
    if not args.credentials_file:
        parser.error("--configure/--pair requires an explicit --credentials-file")
    if args.rebind and not args.pair:
        parser.error("--rebind requires --pair")
    try:
        if not sys.stdin.isatty():
            raise SetupError("请由用户在本机交互终端执行设置；不要通过聊天、管道或命令参数输入凭据。")
        if args.configure:
            result = configure(args.credentials_file, secret_reader=secret_reader)
        else:
            result = pair(args.credentials_file, timeout=args.timeout, rebind=args.rebind,
                          listener=listener, confirm_reader=confirm_reader)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] in {"configured_not_paired", "paired"} else 1
    except (KeyboardInterrupt, EOFError):
        print(json.dumps({"status": "cancelled", "binding_saved": False,
                          "message": "设置已中断；未保存新的审批绑定。"}, ensure_ascii=False))
        return 1
    except SetupError as error:
        print(json.dumps({"status": "blocked", "message": str(error)}, ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps({"status": "blocked", "message": "设置失败；请在本机核对配置。未输出凭据或原始SDK错误。"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
