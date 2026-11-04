#!/usr/bin/env python3
"""Optional user-run login wizard. Default/--doctor is completely offline.

Only `wechat --begin` requests a QR authorization challenge. `--wait` polls
that same private challenge; it never starts or refreshes a login implicitly.
No OpenClaw configuration is searched, no messages are sent, and no account is
created by this tool. The user scans and confirms in the official WeChat flow.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import getpass
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import tempfile
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request
import uuid


SOURCE_COMMIT = "874637a0dbc24050f72d1385add4fc6170a2d726"
SOURCE = "https://github.com/Tencent/openclaw-weixin/blob/" + SOURCE_COMMIT + "/docs/protocol_zh_CN.md"
API_BASE = "https://ilinkai.weixin.qq.com"
CLIENT_VERSION = str((2 << 16) | (4 << 8) | 10)
CHALLENGE_TTL = 300
MAX_FILE_BYTES = 65536
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_NAMES = ["HC_WECHAT_BOT_TOKEN", "HC_WECHAT_BOT_ID", "HC_WECHAT_RECIPIENT",
                     "HC_WECHAT_ALLOWED_CHATS", "HC_WECHAT_APPROVERS"]


class LoginError(RuntimeError):
    """Messages are fixed diagnostics, never provider responses or secret values."""


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def private_path(value: str | Path, *, create_parent: bool = False) -> Path:
    raw = str(value)
    if not raw or any(ord(char) < 32 for char in raw):
        raise LoginError("Choose an explicit private absolute file path.")
    candidate = Path(os.path.abspath(os.path.expanduser(raw)))
    if not Path(os.path.expanduser(raw)).is_absolute():
        raise LoginError("Credential and challenge paths must be absolute.")
    # Inspect before resolving so symlinked folders cannot bypass repository/tmp checks.
    for entry in [candidate, *candidate.parents]:
        if entry.is_symlink():
            raise LoginError("Symlinked credential or challenge paths are not allowed.")
    resolved = candidate.resolve()
    forbidden = [PACKAGE_ROOT, Path("/tmp").resolve(), Path("/var/tmp").resolve(),
                 Path("/dev/shm"), Path(tempfile.gettempdir()).resolve()]
    if any(_inside(resolved, root) for root in forbidden):
        raise LoginError("Do not store login material inside a repository or shared temporary directory.")
    if any((parent / ".git").exists() for parent in candidate.parents):
        raise LoginError("Do not store login material inside a repository.")
    if create_parent:
        missing = []
        cursor = candidate.parent
        while not cursor.exists():
            missing.append(cursor)
            cursor = cursor.parent
        for directory in reversed(missing):
            directory.mkdir(mode=0o700)
    parent = candidate.parent
    if not parent.is_dir():
        raise LoginError("The explicit private parent directory does not exist.")
    info = parent.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o022:
        raise LoginError("Use a directory owned by you that is not writable by other users.")
    return candidate


def read_private_json(value: str | Path) -> dict:
    path = private_path(value)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > MAX_FILE_BYTES:
                raise LoginError("Login files must be small regular files owned by you with mode 0600.")
            result = json.load(stream)
    except LoginError:
        raise
    except (OSError, ValueError, TypeError):
        raise LoginError("The explicitly selected private login file could not be read.") from None
    if not isinstance(result, dict):
        raise LoginError("The private login file has an invalid format.")
    return result


def _write_private(path: Path, data: dict, *, replace: bool = False) -> None:
    path = private_path(path, create_parent=True)
    encoded = (json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()
    if len(encoded) > MAX_FILE_BYTES:
        raise LoginError("Login material exceeds the supported size.")
    if path.exists():
        read_private_json(path)  # Refuse insecure files even when replacement was explicit.
        if not replace:
            raise LoginError("The private file already exists; replacement requires an explicit choice.")
    fd, temporary_name = tempfile.mkstemp(prefix=".hc-login-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            # Link is exclusive and atomic; never silently replace another process's file.
            os.link(temporary, path)
    except OSError:
        raise LoginError("The private login file could not be saved safely.") from None
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _lock(path: Path):
    lock = path.with_name(path.name + ".lock")
    private_path(lock, create_parent=True)
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except OSError:
        raise LoginError("This challenge is already in use; do not run two login commands at once. Review a stale lock locally after an interrupted process.") from None
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def _secret(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 16384 or "\r" in value or "\n" in value:
        raise LoginError("The official confirmation response is missing valid credentials.")
    return value


def load_wechat_credentials(value: str | Path) -> dict:
    """Only call after a user explicitly selected this file (bridge: --run)."""
    data = read_private_json(value)
    if data.get("schema_version") != 1 or data.get("provider") != "wechat" or data.get("api_base") != API_BASE:
        raise LoginError("Unsupported WeChat credential file or API region.")
    return {"schema_version": 1, "provider": "wechat", "bot_token": _secret(data.get("bot_token")),
            "ilink_bot_id": _secret(data.get("ilink_bot_id")), "api_base": API_BASE,
            "ilink_user_id": data.get("ilink_user_id"), "created_at": data.get("created_at")}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http(method: str, url: str, headers: dict, body: bytes | None, timeout: float):
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.build_opener(_NoRedirect()).open(req, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read(MAX_FILE_BYTES + 1)
    except Exception:
        # HTTP exceptions may contain full challenge URLs; never print them.
        raise LoginError("The official login endpoint could not be reached; the existing challenge was retained.") from None


def _qr_url(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 8192:
        return None
    try:
        parsed = urllib.parse.urlsplit(value)
        host = parsed.hostname or ""
        valid = parsed.scheme == "https" and not parsed.username and not parsed.password and parsed.port in (None, 443)
    except ValueError:
        return None
    if not valid:
        return None
    if host != "weixin.qq.com" and not host.endswith(".weixin.qq.com"):
        return None
    return value


class WeChatLogin:
    def __init__(self, *, request_fn: Callable = _http, clock: Callable = time.time, sleep: Callable = time.sleep):
        self.request = request_fn
        self.clock, self.sleep = clock, sleep
        self.timer = time.monotonic if clock is time.time else clock

    def _fetch(self, method: str, endpoint: str, *, body: dict | None = None, timeout: float = 15) -> dict:
        headers = {"iLink-App-Id": "bot", "iLink-App-ClientVersion": CLIENT_VERSION}
        encoded = None
        if method == "POST":
            headers.update({"Content-Type": "application/json", "AuthorizationType": "ilink_bot_token",
                            "X-WECHAT-UIN": base64.b64encode(str(secrets.randbits(32)).encode()).decode()})
            encoded = json.dumps(body or {}, separators=(",", ":")).encode()
        try:
            status, _, raw = self.request(method, API_BASE + endpoint, headers, encoded, timeout)
            if status != 200 or len(raw) > MAX_FILE_BYTES:
                raise LoginError("The official login endpoint returned an unsuccessful response.")
            value = json.loads(raw)
        except LoginError:
            raise
        except Exception:
            raise LoginError("The official login response was invalid; no credentials were logged.") from None
        if not isinstance(value, dict) or value.get("ret", 0) != 0 or value.get("errcode", 0) != 0:
            raise LoginError("The official login endpoint rejected this request.")
        return value

    @staticmethod
    def _paths(credentials_file: str | Path, challenge_file: str | Path | None):
        credentials = private_path(credentials_file, create_parent=True)
        challenge = private_path(challenge_file or credentials.with_name(credentials.name + ".challenge.json"), create_parent=True)
        if challenge == credentials:
            raise LoginError("Use different files for the pending challenge and final credentials.")
        return credentials, challenge

    @staticmethod
    def _public(challenge: dict, path: Path, status: str, **extra) -> dict:
        return {"status": status, "challenge_file": str(path), "qrcode_url": _qr_url(challenge.get("qrcode_url")),
                "network_used": extra.pop("network_used", False), "token_printed": False, **extra}

    def begin(self, credentials_file: str | Path, *, challenge_file: str | Path | None = None,
              restart: bool = False, replace_credentials: bool = False) -> dict:
        credentials, challenge_path = self._paths(credentials_file, challenge_file)
        with _lock(challenge_path):
            if credentials.exists() and not replace_credentials:
                # Do not initiate another account binding just to discover an existing file.
                read_private_json(credentials)
                raise LoginError("Credentials already exist. Use the explicit file with the bridge, or deliberately choose --replace-credentials for a new login.")
            if challenge_path.exists():
                previous = read_private_json(challenge_path)
                if previous.get("schema_version") != 1 or previous.get("provider") != "wechat" or previous.get("credentials_file") != str(credentials):
                    raise LoginError("This challenge belongs to a different explicit credential destination.")
                age = self.clock() - previous.get("started_at", 0)
                if not restart and previous.get("status") not in {"expired", "verify_code_blocked", "confirmed"} and 0 <= age < CHALLENGE_TTL:
                    if previous.get("qrcode"):
                        return self._public(previous, challenge_path, "awaiting_scan", reused_challenge=True)
                    return self._public(previous, challenge_path, "unknown", message="The earlier begin outcome is unknown. Wait for expiry or explicitly choose --restart-challenge.")
            challenge = {"schema_version": 1, "provider": "wechat", "challenge_id": str(uuid.uuid4()),
                         "status": "requesting", "started_at": self.clock(), "credentials_file": str(credentials),
                         "replace_credentials": bool(replace_credentials), "api_base": API_BASE}
            # Record intent before the non-idempotent QR request. A lost response is not retried.
            _write_private(challenge_path, challenge, replace=challenge_path.exists())
            try:
                response = self._fetch("POST", "/ilink/bot/get_bot_qrcode?bot_type=3", body={"local_token_list": []})
                challenge["qrcode"] = _secret(response.get("qrcode"))
                challenge["qrcode_url"] = _qr_url(response.get("qrcode_img_content")) or _qr_url(response.get("qrcode"))
                challenge["status"] = "waiting"
                _write_private(challenge_path, challenge, replace=True)
            except Exception:
                challenge["status"] = "unknown"
                _write_private(challenge_path, challenge, replace=True)
                return self._public(challenge, challenge_path, "unknown", network_used=True,
                    message="No new challenge will be requested automatically. Inspect this login or explicitly restart it.")
            return self._public(challenge, challenge_path, "awaiting_scan", network_used=True,
                qr_image_generated=False, message="用自己的微信扫描官方授权入口并确认。未生成替代二维码；若没有图像资源，使用返回的官方URL。" if challenge["qrcode_url"] else
                "官方响应没有可验证的扫码URL；未编造二维码。请使用官方客户端，或显式重新发起。")

    def wait(self, credentials_file: str | Path, *, challenge_file: str | Path | None = None,
             timeout: float = 180, interval: float = 1, verify_code: str | None = None) -> dict:
        if not 0 < timeout <= CHALLENGE_TTL or not 0.25 <= interval <= 10:
            raise LoginError("Use a timeout in 0..300 seconds and a polling interval in 0.25..10 seconds.")
        if verify_code is not None and (not verify_code.isdigit() or len(verify_code) > 64):
            raise LoginError("Read only the digits displayed by the official WeChat confirmation screen.")
        credentials, challenge_path = self._paths(credentials_file, challenge_file)
        with _lock(challenge_path):
            challenge = read_private_json(challenge_path)
            if challenge.get("schema_version") != 1 or challenge.get("provider") != "wechat" or challenge.get("credentials_file") != str(credentials) or challenge.get("api_base") != API_BASE:
                raise LoginError("This is not the same authorized login challenge and destination.")
            if challenge.get("status") == "confirmed":
                return self._public(challenge, challenge_path, "credentials_already_saved", credentials_file=str(credentials))
            if challenge.get("status") in {"expired", "verify_code_blocked"}:
                return self._public(challenge, challenge_path, challenge["status"], message="此challenge已停止；需要新登录时请显式--begin。")
            if challenge.get("status") in {"unknown", "requesting"} and not challenge.get("qrcode"):
                return self._public(challenge, challenge_path, "unknown", message="此前begin响应未知，无法凭空恢复二维码；不会自动重发，需要用户显式选择--begin --restart-challenge。")
            started = challenge.get("started_at")
            if not isinstance(started, (int, float)) or not 0 <= self.clock() - started < CHALLENGE_TTL:
                return self._public(challenge, challenge_path, "expired", message="二维码已过期；--wait不会自动新建。需要重新登录时显式使用--begin。")
            qrcode = _secret(challenge.get("qrcode"))
            deadline = self.timer() + min(timeout, CHALLENGE_TTL - (self.clock() - started))
            network_used, errors = False, 0
            while self.timer() < deadline:
                query = {"qrcode": qrcode}
                if verify_code:
                    query["verify_code"] = verify_code
                try:
                    network_used = True
                    response = self._fetch("GET", "/ilink/bot/get_qrcode_status?" + urllib.parse.urlencode(query), timeout=min(35, max(0.1, deadline - self.timer())))
                    errors = 0
                except LoginError:
                    errors += 1
                    if errors >= 3:
                        return self._public(challenge, challenge_path, "pending_network", network_used=True,
                            message="轮询暂时失败；同一challenge已保留，稍后继续--wait，不重复创建。")
                    self.sleep(min(interval, max(0, deadline - self.timer())))
                    continue
                status = response.get("status")
                if status == "confirmed":
                    api_base = str(response.get("baseurl") or API_BASE).rstrip("/")
                    if api_base != API_BASE:
                        raise LoginError("This login requires an unsupported API region. Use the official client; credentials were not saved.")
                    result = {"schema_version": 1, "provider": "wechat", "bot_token": _secret(response.get("bot_token")),
                              "ilink_bot_id": _secret(response.get("ilink_bot_id")), "api_base": API_BASE,
                              "created_at": self.clock()}
                    if response.get("ilink_user_id"):
                        result["ilink_user_id"] = _secret(response["ilink_user_id"])
                    _write_private(credentials, result, replace=challenge.get("replace_credentials") is True)
                    # Do not retain the expired authorization material in the recovery record.
                    completed = {key: challenge[key] for key in ("schema_version", "provider", "challenge_id", "started_at", "credentials_file", "api_base")}
                    completed.update(status="confirmed", completed_at=self.clock())
                    _write_private(challenge_path, completed, replace=True)
                    return self._public(completed, challenge_path, "connected", network_used=True,
                        credentials_file=str(credentials), environment_names=ENVIRONMENT_NAMES,
                        bridge_option="--wechat-credentials", message="凭据仅保存到指定的0600私有文件；桥接需用户显式--run。请先给Bot发一条私聊，再配置自己的接收人和审批allowlist。")
                if status in {"expired", "verify_code_blocked"}:
                    challenge["status"] = status
                    _write_private(challenge_path, challenge, replace=True)
                    return self._public(challenge, challenge_path, status, network_used=True, message="当前扫码已停止；不会自动刷新或重新登录。")
                if status == "need_verifycode":
                    return self._public(challenge, challenge_path, "needs_verification", network_used=True,
                        message="微信需要数字验证。继续同一--wait并使用--verify-code-stdin输入手机显示的数字；验证码不会存盘或打印。")
                if status == "binded_redirect":
                    return self._public(challenge, challenge_path, "already_bound_no_credentials_issued", network_used=True,
                        message="官方报告已经绑定，但未签发新凭据。本工具不会搜索或读取OpenClaw的其他配置。")
                if status == "scaned_but_redirect":
                    if response.get("redirect_host") != urllib.parse.urlsplit(API_BASE).hostname:
                        return self._public(challenge, challenge_path, "unsupported_region", network_used=True,
                            message="官方要求另一个区域端点；当前桥接未支持，停止且不向未知域名发送challenge。")
                elif status not in {"wait", "scaned"}:
                    return self._public(challenge, challenge_path, "unknown", network_used=True, message="未识别的官方状态；保留同一challenge并停止。")
                self.sleep(min(interval, max(0, deadline - self.timer())))
            return self._public(challenge, challenge_path, "pending", network_used=network_used,
                message="本次等待已结束；仍可在有效期内继续同一--wait，不会自动创建新二维码。")


def doctor(provider: str = "wechat") -> dict:
    common = {"status": "offline_doctor", "provider": provider, "network_used": False,
              "login_performed": False, "credentials_read": False, "installed_anything": False}
    if provider == "wechat":
        return {**common, "source_commit": SOURCE_COMMIT, "source": SOURCE,
                "openclaw_required": False, "environment_names": ENVIRONMENT_NAMES,
                "private_file_example": "~/.config/hardcore-director/wechat.json",
                "commands": ["python3 scripts/workflow_login.py wechat --begin --credentials-file <absolute-private-file>",
                             "python3 scripts/workflow_login.py wechat --wait --credentials-file <same-private-file>",
                             "python3 scripts/workflow_bridge.py --channel wechat --run --wechat-credentials <same-private-file> <explicit-workflow-options>"],
                "notes": ["用自己的微信扫描官方返回的授权URL并确认；不自动安装OpenClaw或接管其他账号。",
                          "凭据文件0600，新建父目录0700；禁止仓库、共享临时目录和symlink。",
                          "begin的未知响应不会自动重试；wait只查询同一个challenge，过期后由用户明确重新begin。",
                          "--verify-code-stdin仅在手机要求数字验证时使用；不会打印或持久化验证码。"]}
    if provider == "dreamina":
        return {**common, "official_entry": "dreamina-canvas auth login", "note": "由用户另行执行官方登录；此doctor不检查或改变当前登录。"}
    return {**common, "official_entry": "MiniMax Design 官方桌面应用的内置账号登录",
            "note": "MCP使用Design官方应用的登录会话；本工具不导出凭据、不启动应用、不选择已有项目。"}


def main(argv: list[str] | None = None, *, request_fn: Callable = _http, clock: Callable = time.time,
         sleep: Callable = time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", nargs="?", default="wechat", choices=("wechat", "dreamina", "minimax-design"))
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--doctor", action="store_true")
    action.add_argument("--begin", action="store_true", help="Explicitly request one official WeChat QR challenge")
    action.add_argument("--wait", action="store_true", help="Bounded polling of the same private challenge")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--challenge-file", type=Path)
    parser.add_argument("--restart-challenge", action="store_true")
    parser.add_argument("--replace-credentials", action="store_true")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--verify-code-stdin", action="store_true", help="Read the official verification digits from stdin, never argv")
    args = parser.parse_args(argv)
    if args.doctor or not (args.begin or args.wait):
        print(json.dumps(doctor(args.provider), ensure_ascii=False, indent=2))
        return 0
    if args.provider != "wechat" or args.credentials_file is None:
        parser.error("WeChat --begin/--wait requires an explicit absolute --credentials-file")
    if args.restart_challenge and not args.begin or args.replace_credentials and not args.begin:
        parser.error("replacement flags are only valid with explicit --begin")
    try:
        login = WeChatLogin(request_fn=request_fn, clock=clock, sleep=sleep)
        if args.begin:
            result = login.begin(args.credentials_file, challenge_file=args.challenge_file,
                                 restart=args.restart_challenge, replace_credentials=args.replace_credentials)
        else:
            code = None
            if args.verify_code_stdin:
                code = getpass.getpass("输入手机微信显示的数字（不会保存）：") if sys.stdin.isatty() else sys.stdin.readline().strip()
            result = login.wait(args.credentials_file, challenge_file=args.challenge_file, timeout=args.timeout,
                                interval=args.interval, verify_code=code)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in {"awaiting_scan", "connected", "credentials_already_saved", "pending", "needs_verification"} else 1
    except LoginError as exc:
        print(json.dumps({"status": "blocked", "message": str(exc), "token_printed": False}, ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps({"status": "blocked", "message": "登录流程已停止；未打印凭据。请检查私有文件与官方网络入口。", "token_printed": False}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
