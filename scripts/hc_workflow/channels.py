"""Opt-in review channels. No SDK, account, credential file, or network at import.

Feishu: official lark-oapi WebSocket MESSAGE events; cards display instructions,
not approval buttons. Current official ws/client.py drops CARD frames, so we do
not promise button callbacks. Weixin: independently implement Tencent's published
iLink private-chat protocol, not a reverse-engineered personal-account protocol.
Neither adapter executes a workflow from a network callback.

Sources reviewed 2026-11-01 (implementation is original, no SDK code vendored):
https://github.com/larksuite/oapi-sdk-python
https://open.feishu.cn/document/server-docs/im-v1/image/create
https://open.feishu.cn/document/server-docs/im-v1/file/create
https://open.feishu.cn/document/server-docs/im-v1/message/create
https://github.com/Tencent/openclaw-weixin/blob/main/docs/protocol_zh_CN.md
https://github.com/Tencent/openclaw-weixin/blob/main/README.zh_CN.md

Secrets come exclusively from explicit environment variables. iLink context
tokens stay in transport memory, never in the workflow or approval database.
The separate approval database stores only nonce digests and nonsecret bindings.
Live platform delivery has NOT been tested by this package's offline tests.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
import logging
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from typing import Any, Callable, Mapping
import urllib.error
import urllib.parse
import urllib.request
import uuid


class ChannelError(RuntimeError):
    """Safe diagnostics: never include response bodies or credentials."""


class ConfigurationError(ChannelError):
    pass


class CursorStorageError(ChannelError):
    """Fatal polling failure: never advance past an unpersisted message batch."""


_STAGE_LABELS = {"plan": "方案审核", "storyboard": "分镜图审核", "composition": "本地规格处理审批", "final": "终片验收"}
_CURRENCY_LABELS = {"CNY": "人民币", "DREAMINA_CREDITS": "即梦积分"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()[:32]


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,159}", value):
        raise ConfigurationError(f"invalid {label}")
    return value


def _allowlist(value: str, label: str) -> frozenset[str]:
    items = frozenset(part.strip() for part in value.split(",") if part.strip())
    if not items:
        raise ConfigurationError(f"{label} must explicitly list allowed IDs")
    for item in items:
        _identifier(item, label)
    return items


def _binding(stage: str, revision: int, scope: Mapping[str, Any] | None,
             budget: Mapping[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if stage not in {"plan", "storyboard", "composition", "final"} or type(revision) is not int or revision < 1:
        raise ConfigurationError("invalid approval stage or revision")
    scope = dict(scope or {"stages": [], "allow_uploads": False})
    budget = dict(budget or {"amount": "0", "currency": "CNY"})
    allowed_scope = {"stages", "provider", "account", "allow_uploads", "revision", "plan_hash", "asset_hash"}
    if stage == "composition":
        allowed_scope.add("composition")
    if set(scope) - allowed_scope or set(budget) != {"amount", "currency"}:
        raise ConfigurationError("approval scope/budget has unsupported fields")
    stages = scope.get("stages")
    if not isinstance(stages, list) or any(item not in {"image", "video"} for item in stages):
        raise ConfigurationError("scope stages must explicitly list image/video, or be empty")
    if len(stages) != len(set(stages)) or type(scope.get("allow_uploads")) is not bool:
        raise ConfigurationError("invalid scope stages or upload authorization")
    if stages:
        expected = {"plan": ["image"], "storyboard": ["video"], "composition": [], "final": []}[stage]
        if stages != expected or scope.get("revision") != revision:
            raise ConfigurationError("scope stage/revision does not match this review")
        for field in ("provider", "account", "plan_hash", "asset_hash"):
            _identifier(scope.get(field), f"scope.{field}")
    if "revision" in scope and type(scope["revision"]) is not int:
        raise ConfigurationError("scope revision must be an integer")
    if not isinstance(budget.get("amount"), str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,31}", str(budget.get("currency", ""))):
        raise ConfigurationError("budget requires a decimal string and explicit currency/credit unit")
    try:
        amount = Decimal(budget["amount"])
        if not amount.is_finite() or amount < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ConfigurationError("budget must be a finite nonnegative amount") from None
    if stage == "composition":
        if (set(scope) != {"stages", "allow_uploads", "revision", "plan_hash", "asset_hash", "composition"}
                or stages != [] or scope["allow_uploads"] is not False or amount != 0
                or scope.get("revision") != revision):
            raise ConfigurationError("local processing requires exact zero-cost scope without generation or uploads")
        for field in ("plan_hash", "asset_hash"):
            if not isinstance(scope.get(field), str) or not re.fullmatch(r"[a-f0-9]{64}", scope[field]):
                raise ConfigurationError("local processing requires exact content hashes")
        details = scope["composition"]
        if (not isinstance(details, dict) or set(details) != {"mode", "fps", "aspect_ratio", "shots"}
                or details["mode"] != "normalize_cfr" or type(details["fps"]) is not int or not 1 <= details["fps"] <= 120
                or not isinstance(details["aspect_ratio"], str)
                or not re.fullmatch(r"[1-9][0-9]{0,3}:[1-9][0-9]{0,3}", details["aspect_ratio"])
                or not isinstance(details["shots"], list) or not 1 <= len(details["shots"]) <= 48):
            raise ConfigurationError("invalid local processing specification")
        seen = set()
        for shot in details["shots"]:
            if not isinstance(shot, dict) or set(shot) != {"shot_id", "sha256", "duration_seconds"}:
                raise ConfigurationError("invalid local processing input")
            sid = _identifier(shot["shot_id"], "local processing shot")
            if sid in seen or not isinstance(shot["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", shot["sha256"]):
                raise ConfigurationError("invalid local processing input identity")
            seen.add(sid)
            if (type(shot["duration_seconds"]) not in (int, float) or not math.isfinite(shot["duration_seconds"])
                    or not 0 < shot["duration_seconds"] <= 180):
                raise ConfigurationError("invalid local processing input duration")
    _json(scope)
    return scope, budget


@dataclass(frozen=True)
class ChannelCapabilities:
    provider: str
    transport: str
    inbound_approval: bool
    image_delivery: bool
    file_delivery: bool
    card_actions: bool = False
    live_verified: bool = False


@dataclass(frozen=True)
class ApprovalChallenge:
    challenge_id: str
    job_id: str
    revision: int
    stage: str
    expires_at: float
    approve_command: str
    reject_command: str
    scope: dict[str, Any]
    budget: dict[str, Any]
    binding_hash: str = ""
    shot_ids: tuple[str, ...] = ()

    def message(self) -> str:
        stage = _STAGE_LABELS[self.stage]
        stages = self.scope.get("stages", [])
        actions = "、".join({"image": "生成本次分镜图", "video": "按本次分镜生成视频"}[item] for item in stages)
        authorization = actions if actions else "仅记录本次审核结论；不授权任何模型生成或扣费"
        processing = ""
        if self.stage == "composition":
            details = self.scope["composition"]
            shots = "；".join(f"{s['shot_id']}：{s['duration_seconds']}秒，原片{s['sha256'][:12]}" for s in details["shots"])
            authorization = "仅按下面规格从本次绑定原片制作并顺序拼接新副本；不授权模型生成或扣费"
            processing = (f"本地处理目标：{details['fps']}帧/秒，{details['aspect_ratio']}画幅；{shots}。\n"
                          "输出H.264 CRF18/yuv420p；帧率统一可能复制或丢弃帧，按每镜获批时长裁尾，最多裁去2个目标帧的尾部余量；不足则暂停，不补画面或静音。\n"
                          "有音轨时仅在全部源片采样率和声道一致时一次AAC编码，保持原采样率与声道；全部无音轨时保持无音轨，混合情况暂停。\n"
                          "保留原片，不缩放或裁画幅、不加配乐、不上传；输出仍需终片验收。\n")
        uploads = ("允许仅向上述供应商上传本次绑定版本、上述镜号对应的提示词和参考素材；不包含其他文件"
                   if self.scope.get("allow_uploads") else "不允许向生成供应商上传提示词或参考素材")
        currency = self.budget["currency"]
        unit = {"CNY": "CNY（人民币）", "DREAMINA_CREDITS": "DREAMINA_CREDITS（即梦积分）"}.get(currency, currency)
        expiry = datetime.fromtimestamp(self.expires_at, timezone.utc).astimezone().isoformat(sep=" ", timespec="seconds")
        provider = "本机FFmpeg" if self.stage == "composition" else (self.scope.get("provider") or "未指定（本次无模型生成授权）")
        account = "不涉及生成账号" if self.stage == "composition" else (self.scope.get("account") or "未指定")
        return (f"审核项目：{self.job_id}\n"
                f"修订：{self.revision}；阶段：{stage}\n"
                f"镜号：{'、'.join(self.shot_ids) if self.shot_ids else '当前修订全部镜头'}\n"
                f"供应商：{provider}\n"
                f"本次绑定账号标识：{account}\n"
                f"同意将允许：{authorization}\n"
                f"{processing}"
                f"素材上传范围：{uploads}\n"
                f"本阶段累计上限：{self.budget['amount']} {unit}，包含已花费、已提交及结果未知任务的预留；不是每镜额度。\n"
                f"到期时间：{expiry}；只对本次修订和当前素材有效，修改后需重新审核。\n"
                "请直接回复“同意”或“拒绝”。多项待审或请求有变化时，机器人会先请你回复编号选清楚。\n"
                "只处理本次绑定的请求；回复“审核”可重新查看待审项。")


class ApprovalBroker:
    """Durable one-use approvals; this database must be separate from job state.

    Queue acceptance is atomic with nonce consumption and event deduplication.
    Restarting invalidates no issued challenge and cannot replay a consumed one.
    No shell command, arbitrary instruction, auth/context token, or complete SDK
    response is persisted. A separate Bot-digest table holds opaque sync cursors.
    """

    def __init__(self, path: str | Path, *, clock: Callable[[], float] = time.time):
        self.path = Path(path)
        if self.path.is_symlink():
            raise ConfigurationError("approval database must not be a symbolic link")
        if not self.path.parent.is_dir():
            raise ConfigurationError("approval database parent directory must already exist")
        self._clock = clock
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), timeout=10, isolation_level=None, check_same_thread=False)
        os.chmod(self.path, 0o600)
        self._db.row_factory = sqlite3.Row
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS challenges (
                id TEXT PRIMARY KEY, nonce_hash TEXT NOT NULL UNIQUE, channel TEXT NOT NULL,
                job_id TEXT NOT NULL, revision INTEGER NOT NULL, stage TEXT NOT NULL,
                chat_id TEXT NOT NULL, senders TEXT NOT NULL, expires REAL NOT NULL,
                scope TEXT NOT NULL, budget TEXT NOT NULL, scope_hash TEXT NOT NULL,
                budget_hash TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS accepted_events (
                channel TEXT NOT NULL, event_id TEXT NOT NULL, PRIMARY KEY(channel,event_id));
            CREATE TABLE IF NOT EXISTS approval_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT, challenge_id TEXT NOT NULL,
                payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued');
            CREATE TABLE IF NOT EXISTS notifications (
                channel TEXT NOT NULL, event_id TEXT NOT NULL, state TEXT NOT NULL,
                PRIMARY KEY(channel,event_id));
            CREATE TABLE IF NOT EXISTS wechat_cursors (
                bot_hash TEXT PRIMARY KEY, cursor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS short_reviews (
                challenge_id TEXT PRIMARY KEY, instance TEXT NOT NULL,
                delivered REAL NOT NULL, message_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS short_contexts (
                channel TEXT NOT NULL, instance TEXT NOT NULL, chat_id TEXT NOT NULL,
                sender_id TEXT NOT NULL, state TEXT NOT NULL, focus_id TEXT NOT NULL,
                snapshot TEXT NOT NULL, generation TEXT NOT NULL, ready_at REAL NOT NULL,
                message_id TEXT NOT NULL,
                PRIMARY KEY(channel,instance,chat_id,sender_id));
            CREATE TABLE IF NOT EXISTS short_events (
                channel TEXT NOT NULL, instance TEXT NOT NULL, event_id TEXT NOT NULL,
                PRIMARY KEY(channel,instance,event_id));
            CREATE TABLE IF NOT EXISTS short_messages (
                channel TEXT NOT NULL, instance TEXT NOT NULL, message_id TEXT NOT NULL,
                challenge_id TEXT NOT NULL,
                PRIMARY KEY(channel,instance,message_id));
        """)
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(challenges)")}
        for name, definition in (("binding_hash", "TEXT NOT NULL DEFAULT ''"), ("shot_ids", "TEXT NOT NULL DEFAULT '[]'")):
            if name not in columns:
                self._db.execute(f"ALTER TABLE challenges ADD COLUMN {name} {definition}")

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def load_wechat_cursor(self, bot_id: str) -> str:
        """Private channel state, keyed by Bot digest; no context/token storage."""
        partition = hashlib.sha256(_identifier(bot_id, "bot_id").encode()).hexdigest()
        try:
            with self._lock:
                row = self._db.execute("SELECT cursor FROM wechat_cursors WHERE bot_hash=?", (partition,)).fetchone()
        except sqlite3.Error:
            raise CursorStorageError("WeChat cursor storage is unavailable; polling cannot start") from None
        if row is None:
            return ""
        if not isinstance(row["cursor"], str):
            raise CursorStorageError("WeChat cursor storage is invalid; polling cannot start")
        return row["cursor"]

    def save_wechat_cursor(self, bot_id: str, cursor: str) -> None:
        if not isinstance(cursor, str) or not cursor:
            raise CursorStorageError("refusing to replace the saved WeChat cursor with an empty value")
        partition = hashlib.sha256(_identifier(bot_id, "bot_id").encode()).hexdigest()
        try:
            with self._lock:
                self._db.execute("INSERT INTO wechat_cursors(bot_hash,cursor) VALUES(?,?) ON CONFLICT(bot_hash) DO UPDATE SET cursor=excluded.cursor", (partition, cursor))
        except sqlite3.Error:
            raise CursorStorageError("WeChat cursor storage failed; listener stopped without advancing the cursor") from None

    def issue(self, *, channel: str, job_id: str, revision: int, stage: str,
              chat_id: str, allowed_sender_ids: set[str] | frozenset[str],
              live_scope: Mapping[str, Any] | None = None, budget: Mapping[str, Any] | None = None,
              ttl_seconds: float = 900, expires_at: float | None = None,
              binding_hash: str | None = None, shot_ids: list[str] | None = None) -> ApprovalChallenge:
        for value, label in ((channel, "channel"), (job_id, "job_id"), (chat_id, "chat_id")):
            _identifier(value, label)
        if not allowed_sender_ids:
            raise ConfigurationError("review requires explicit approvers")
        for sender in allowed_sender_ids:
            _identifier(sender, "approver")
        scope, cap = _binding(stage, revision, live_scope, budget)
        if binding_hash is not None and (not isinstance(binding_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", binding_hash)):
            raise ConfigurationError("invalid content binding hash")
        if shot_ids is not None and (not isinstance(shot_ids, list) or not shot_ids):
            raise ConfigurationError("shot_ids must be a nonempty list when provided")
        for shot_id in shot_ids or []:
            _identifier(shot_id, "shot_id")
        now = self._clock()
        if type(ttl_seconds) not in (int, float) or not math.isfinite(ttl_seconds) or not 1 <= ttl_seconds <= 3600:
            raise ConfigurationError("approval TTL must be between 1 and 3600 seconds")
        if expires_at is not None and (type(expires_at) not in (int, float) or not math.isfinite(expires_at)):
            raise ConfigurationError("invalid approval expiry")
        expiry = min(now + ttl_seconds, expires_at) if expires_at is not None else now + ttl_seconds
        if not math.isfinite(expiry) or expiry <= now:
            raise ConfigurationError("approval is already expired")
        nonce, ident = secrets.token_urlsafe(32), uuid.uuid4().hex
        scope_hash, budget_hash = _digest(scope), _digest(cap)
        prefix = f"{stage} {job_id} {revision} {nonce} scope={scope_hash} budget={budget_hash}"
        challenge = ApprovalChallenge(ident, job_id, revision, stage, expiry,
                                      f"/hc approve {prefix}", f"/hc reject {prefix}", scope, cap,
                                      binding_hash or "", tuple(shot_ids or []))
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                selected = set(shot_ids or [])
                senders_json = _json(sorted(allowed_sender_ids))
                previous = self._db.execute("SELECT id,revision,binding_hash,shot_ids,chat_id,senders FROM challenges WHERE channel=? AND job_id=? AND stage=? AND status IN ('pending','accepted')",
                                            (channel, job_id, stage)).fetchall()
                for old in previous:
                    stored_selected = json.loads(old["shot_ids"])
                    if not isinstance(stored_selected, list):
                        raise ConfigurationError("stored challenge has invalid shot scope")
                    for shot_id in stored_selected:
                        _identifier(shot_id, "stored shot_id")
                    old_selected = set(stored_selected)
                    independent = (bool(binding_hash) and old["binding_hash"] == binding_hash
                                   and old["revision"] == revision and old["chat_id"] == chat_id
                                   and old["senders"] == senders_json and bool(selected) and bool(old_selected)
                                   and selected.isdisjoint(old_selected))
                    if not independent:
                        self._db.execute("UPDATE challenges SET status='superseded' WHERE id=?", (old["id"],))
                self._db.execute("INSERT INTO challenges(id,nonce_hash,channel,job_id,revision,stage,chat_id,senders,expires,scope,budget,scope_hash,budget_hash,status,binding_hash,shot_ids) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    ident, hashlib.sha256(nonce.encode()).hexdigest(), channel, job_id, revision, stage,
                    chat_id, senders_json, expiry, _json(scope), _json(cap), scope_hash, budget_hash,
                    "pending", binding_hash or "", _json(shot_ids or [])))
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        return challenge

    def cancel(self, challenge_id: str) -> None:
        with self._lock:
            self._db.execute("UPDATE challenges SET status='cancelled' WHERE id=? AND status='pending'", (challenge_id,))

    @staticmethod
    def _short_key(channel: str, instance: str, chat_id: str, sender_id: str) -> tuple[str, str, str, str]:
        for value, name in ((channel, "channel"), (chat_id, "chat_id"), (sender_id, "sender_id")):
            _identifier(value, name)
        if not isinstance(instance, str) or not re.fullmatch(r"[a-f0-9]{64}", instance):
            raise ConfigurationError("short replies require an explicit bot/app instance digest")
        return channel, instance, chat_id, sender_id

    def _short_candidates(self, key: tuple[str, str, str, str]) -> list[sqlite3.Row]:
        channel, instance, chat, sender = key
        rows = self._db.execute(
            "SELECT c.*,s.delivered,s.message_id FROM challenges c JOIN short_reviews s ON s.challenge_id=c.id "
            "WHERE c.channel=? AND s.instance=? AND c.chat_id=? AND c.status='pending' AND c.expires>? "
            "ORDER BY s.delivered,c.id", (channel, instance, chat, self._clock())).fetchall()
        return [row for row in rows if sender in json.loads(row["senders"])]

    def _short_context(self, key: tuple[str, str, str, str]) -> sqlite3.Row | None:
        return self._db.execute(
            "SELECT * FROM short_contexts WHERE channel=? AND instance=? AND chat_id=? AND sender_id=?", key).fetchone()

    def _set_short_context(self, key: tuple[str, str, str, str], *, state: str,
                           focus: str = "", snapshot: list[str] | None = None,
                           generation: str = "", ready_at: float = 0, message_id: str = "") -> None:
        self._db.execute("INSERT INTO short_contexts VALUES (?,?,?,?,?,?,?,?,?,?) "
                         "ON CONFLICT(channel,instance,chat_id,sender_id) DO UPDATE SET "
                         "state=excluded.state,focus_id=excluded.focus_id,snapshot=excluded.snapshot,"
                         "generation=excluded.generation,ready_at=excluded.ready_at,message_id=excluded.message_id",
                         (*key, state, focus, _json(snapshot or []), generation, ready_at, message_id))

    @staticmethod
    def _row_message(row: sqlite3.Row) -> str:
        return ApprovalChallenge(row["id"], row["job_id"], row["revision"], row["stage"], row["expires"], "", "",
                                 json.loads(row["scope"]), json.loads(row["budget"]), row["binding_hash"],
                                 tuple(json.loads(row["shot_ids"]))).message()

    def mark_review_delivered(self, challenge_id: str, *, instance: str, message_id: str = "") -> None:
        """Activate short replies only after this new-style explanation was sent.

        Legacy rows have no short_reviews entry and remain nonce-only. A receipt
        lost before this call cannot silently enable a two-character approval.
        """
        if not isinstance(message_id, str) or len(message_id) > 256:
            raise ConfigurationError("invalid review delivery identity")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute("SELECT * FROM challenges WHERE id=?", (challenge_id,)).fetchone()
                if row is None or row["status"] != "pending" or row["expires"] <= self._clock():
                    raise ConfigurationError("delivered review is no longer current")
                if self._db.execute("SELECT 1 FROM short_reviews WHERE challenge_id=?", (challenge_id,)).fetchone():
                    raise ConfigurationError("review delivery is already recorded")
                now = self._clock()
                self._db.execute("INSERT INTO short_reviews VALUES (?,?,?,?)", (challenge_id, instance, now, message_id))
                if message_id:
                    self._db.execute("INSERT INTO short_messages VALUES (?,?,?,?)",
                                     (row["channel"], instance, message_id, challenge_id))
                for sender in json.loads(row["senders"]):
                    key = self._short_key(row["channel"], instance, row["chat_id"], sender)
                    prior = self._short_context(key)
                    candidates = self._short_candidates(key)
                    # Never move a spent or previously shown focus to a new
                    # request on the strength of a repeated bare "同意".
                    # Old schema rows cannot be attributed to a particular
                    # bot/app. A delayed/repeated bare reply to that history
                    # must not approve the first new-style paid request.
                    legacy_rows = self._db.execute(
                        "SELECT c.senders FROM challenges c LEFT JOIN short_reviews s ON s.challenge_id=c.id "
                        "WHERE c.channel=? AND c.chat_id=? AND c.id<>? AND s.challenge_id IS NULL",
                        (row["channel"], row["chat_id"], challenge_id)).fetchall()
                    legacy_history = any(sender in json.loads(old["senders"]) for old in legacy_rows)
                    first = prior is None and len(candidates) == 1 and not legacy_history
                    self._set_short_context(key, state="focus" if first else "needs_choice",
                                            focus=challenge_id if first else "",
                                            snapshot=[item["id"] for item in candidates], ready_at=now,
                                            message_id=message_id if first else "")
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def _prepare_short_menu(self, key: tuple[str, str, str, str], rows: list[sqlite3.Row]) -> dict[str, Any]:
        if not rows:
            self._set_short_context(key, state="stale")
            return {"accepted": False, "reason": "no_current_review",
                    "reply": "没有可处理的有效审核，可能已处理、过期或内容已更新。请等待新的审核请求。"}
        generation = uuid.uuid4().hex
        self._set_short_context(key, state="menu_sending", snapshot=[row["id"] for row in rows], generation=generation)
        labels = []
        for index, row in enumerate(rows, 1):
            budget = json.loads(row["budget"])
            shots = "、".join(json.loads(row["shot_ids"])) or "本次全部镜头"
            stage = _STAGE_LABELS[row["stage"]]
            currency = _CURRENCY_LABELS.get(budget["currency"], budget["currency"])
            labels.append(f"{index}. {row['job_id']}｜修订{row['revision']}｜{stage}｜镜号：{shots}｜上限{budget['amount']} {currency}")
        return {"accepted": False, "reason": "selection_required",
                "reply": "请先选清楚本次审核项，回复下面的编号。选择编号不会批准生成或扣费：\n" + "\n".join(labels),
                "presentation": {"key": key, "generation": generation, "state": "menu"}}

    def confirm_text_delivery(self, presentation: dict[str, Any], *, message_id: str = "") -> None:
        """A menu/selected scope becomes usable only after its API send succeeds."""
        key = self._short_key(*presentation["key"])
        if not isinstance(message_id, str) or len(message_id) > 256:
            raise ConfigurationError("invalid clarification delivery identity")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._short_context(key)
                candidates = self._short_candidates(key)
                current = [item["id"] for item in candidates]
                if (row is None or row["generation"] != presentation["generation"]
                        or json.loads(row["snapshot"]) != current
                        or row["state"] not in {"menu_sending", "focus_sending"}):
                    raise ConfigurationError("clarification changed while sending; no short approval enabled")
                state = presentation["state"]
                if state not in {"menu", "focus"}:
                    raise ConfigurationError("invalid clarification state")
                self._set_short_context(key, state=state, focus=row["focus_id"], snapshot=current,
                                        generation=row["generation"], ready_at=self._clock(), message_id=message_id)
                if message_id and state == "focus":
                    self._db.execute("INSERT INTO short_messages VALUES (?,?,?,?)",
                                     (key[0], key[1], message_id, row["focus_id"]))
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def accept_text(self, *, channel: str, event_id: str, sender_id: str,
                    chat_id: str, text: str, instance: str | None = None,
                    created_at: float | None = None, quoted_message_id: str | None = None,
                    unverified_reference: bool = False) -> dict[str, Any]:
        if not isinstance(text, str):
            return {"accepted": False, "reason": "invalid_command"}
        if text.startswith("/hc "):
            return self.accept(channel=channel, event_id=event_id, sender_id=sender_id,
                               chat_id=chat_id, command=text)
        # Ignore only outer whitespace, never extract an approval from prose,
        # mixed lines, or multiple choices in one message.
        text = text.strip()
        recognized = text in {"同意", "拒绝", "审核"} or re.fullmatch(r"[1-9][0-9]{0,2}", text) is not None
        if not isinstance(event_id, str) or not event_id or len(event_id) > 256:
            return {"accepted": False, "reason": "missing_event_id"}
        key = self._short_key(channel, instance, chat_id, sender_id)
        if created_at is not None and (type(created_at) not in (float, int) or not math.isfinite(created_at)):
            return {"accepted": False, "reason": "invalid_message_time"}
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                if self._db.execute("SELECT 1 FROM short_events WHERE channel=? AND instance=? AND event_id=?",
                                    (channel, instance, event_id)).fetchone():
                    self._db.execute("ROLLBACK")
                    return {"accepted": False, "reason": "duplicate_event"}
                self._db.execute("INSERT INTO short_events VALUES (?,?,?)", (channel, instance, event_id))
                rows = self._short_candidates(key)
                context = self._short_context(key)
                current = [row["id"] for row in rows]
                reply = None
                if not recognized:
                    reply = {"accepted": False, "reason": "invalid_command"}
                    if context is not None:
                        reply["reply"] = ("已收到文字，但没有把它当作审核决定。请查看当前请求，完整回复“同意”或“拒绝”；"
                                          "多项待审时先按列表回复编号，也可回复“审核”重新查看。")
                elif unverified_reference:
                    reply = {"accepted": False, "reason": "unverified_reference",
                             "reply": "无法核对被引用的旧消息，未处理审核。请查看最新请求并回复“审核”。"}
                elif context is not None and context["state"] in {"menu_sending", "focus_sending"} and text != "审核":
                    reply = {"accepted": False, "reason": "presentation_not_confirmed",
                             "reply": "本次审核说明还未确认送达，未处理决定。请稍后回复“审核”重新查看。"}
                elif (created_at is None and not quoted_message_id) or (context is not None and created_at is not None
                        and (created_at < context["ready_at"] or created_at > self._clock() + 300)):
                    reply = {"accepted": False, "reason": "stale_or_unverifiable_message",
                             "reply": "这条回复的时间无法与当前审核说明对应，未处理决定。请查看最新请求后重新回复。"}
                elif text == "审核":
                    reply = self._prepare_short_menu(key, rows)
                elif context is None:
                    reply = {"accepted": False, "reason": "no_current_review",
                             "reply": "没有支持两字回复的当前审核，请等待新的审核请求。旧版请求请由本机重新发送。"}
                elif context["state"] == "spent":
                    reply = {"accepted": False, "reason": "already_recorded",
                             "reply": "上一项审核已记录，不会重复处理或自动批准下一项。回复“审核”可选择当前待审项。"}
                elif not rows or context["state"] == "needs_choice" or json.loads(context["snapshot"]) != current:
                    reply = self._prepare_short_menu(key, rows)
                else:
                    reference = None
                    if quoted_message_id:
                        reference = self._db.execute(
                            "SELECT challenge_id FROM short_messages WHERE channel=? AND instance=? AND message_id=?",
                            (channel, instance, quoted_message_id)).fetchone()
                    if context["state"] == "menu":
                        if quoted_message_id and quoted_message_id != context["message_id"]:
                            reply = {"accepted": False, "reason": "reference_mismatch",
                                     "reply": "引用的不是当前选择列表，未处理审核。请回复“审核”查看最新列表。"}
                        elif not text.isdecimal() or not 1 <= int(text) <= len(rows):
                            reply = {"accepted": False, "reason": "selection_required",
                                     "reply": "请先回复当前列表里的编号；选择后会重新显示该项内容和费用。"}
                        else:
                            selected = rows[int(text) - 1]
                            generation = uuid.uuid4().hex
                            self._set_short_context(key, state="focus_sending", focus=selected["id"],
                                                    snapshot=current, generation=generation)
                            reply = {"accepted": False, "reason": "confirmation_required",
                                     "reply": "你选择的审核项如下。请核对后回复“同意”或“拒绝”：\n" + self._row_message(selected),
                                     "presentation": {"key": key, "generation": generation, "state": "focus"}}
                    elif context["state"] == "focus":
                        selected = next((row for row in rows if row["id"] == context["focus_id"]), None)
                        if quoted_message_id and (reference is None or reference["challenge_id"] != context["focus_id"]):
                            reply = {"accepted": False, "reason": "reference_mismatch",
                                     "reply": "引用的消息与当前审核项不一致，未处理决定。请回复“审核”重新选择。"}
                        elif selected is None or text not in {"同意", "拒绝"}:
                            reply = self._prepare_short_menu(key, rows)
                        else:
                            decision = {"同意": "approve", "拒绝": "reject"}[text]
                            namespaced = instance + ":" + event_id
                            reply = self._consume(selected, channel=channel, event_id=namespaced,
                                                  sender_id=sender_id, chat_id=chat_id, decision=decision)
                            self._set_short_context(key, state="spent", focus=selected["id"], snapshot=current)
                    else:
                        reply = self._prepare_short_menu(key, rows)
                self._db.execute("COMMIT")
                return reply
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def _consume(self, row: sqlite3.Row, *, channel: str, event_id: str,
                 sender_id: str, chat_id: str, decision: str) -> dict[str, Any]:
        """Caller owns BEGIN IMMEDIATE; both input modes consume the exact row."""
        scope, budget = json.loads(row["scope"]), json.loads(row["budget"])
        _binding(row["stage"], row["revision"], scope, budget)
        if _digest(scope) != row["scope_hash"] or _digest(budget) != row["budget_hash"]:
            raise ConfigurationError("stored approval binding is inconsistent")
        if row["status"] != "pending" or row["expires"] <= self._clock():
            raise ConfigurationError("review changed before consumption")
        if (row["channel"], row["chat_id"]) != (channel, chat_id) or sender_id not in json.loads(row["senders"]):
            raise ConfigurationError("approval recipient binding changed")
        payload = {"project_id": row["job_id"], "job_id": row["job_id"], "revision": row["revision"], "stage": row["stage"],
                   "decision": decision, "sender_id": sender_id, "chat_id": chat_id, "channel": channel,
                   "event_id": event_id, "expires_at": row["expires"], "live_scope": scope,
                   "budget": budget, "challenge_id": row["id"], "binding_hash": row["binding_hash"],
                   "shot_ids": json.loads(row["shot_ids"])}
        self._db.execute("INSERT INTO accepted_events VALUES (?,?)", (channel, event_id))
        self._db.execute("UPDATE challenges SET status='accepted' WHERE id=?", (row["id"],))
        self._db.execute("INSERT INTO approval_queue(challenge_id,payload) VALUES (?,?)", (row["id"], _json(payload)))
        verdict = {"approve": "同意", "reject": "拒绝"}[decision]
        shots = "、".join(payload["shot_ids"]) or "本次全部镜头"
        receipt = (f"已记录{verdict}：{row['job_id']}，修订{row['revision']}，{_STAGE_LABELS[row['stage']]}，镜号：{shots}。"
                   "等待工作流核验；不会扩大本次账号、素材或费用授权。")
        return {"accepted": True, "queued": True, "challenge_id": row["id"], "reply": receipt}

    def accept(self, *, channel: str, event_id: str, sender_id: str,
               chat_id: str, command: str) -> dict[str, Any]:
        if not isinstance(command, str) or len(command) > 1200 or "\n" in command or "\r" in command:
            return {"accepted": False, "reason": "invalid_command"}
        parts = command.strip().split(" ")
        if len(parts) != 8 or any(not part for part in parts) or parts[0] != "/hc" or parts[1] not in {"approve", "reject"}:
            return {"accepted": False, "reason": "invalid_command"}
        _, decision, stage, job_id, revision, nonce, scope_hash, budget_hash = parts
        if not revision.isdecimal() or not re.fullmatch(r"[A-Za-z0-9_-]{40,80}", nonce):
            return {"accepted": False, "reason": "invalid_command"}
        if not re.fullmatch(r"scope=[a-f0-9]{32}", scope_hash) or not re.fullmatch(r"budget=[a-f0-9]{32}", budget_hash):
            return {"accepted": False, "reason": "invalid_command"}
        if not event_id or not isinstance(event_id, str) or len(event_id) > 256:
            return {"accepted": False, "reason": "missing_event_id"}
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute("SELECT * FROM challenges WHERE nonce_hash=?", (hashlib.sha256(nonce.encode()).hexdigest(),)).fetchone()
                reason = None
                if not row or row["status"] != "pending":
                    reason = "unknown_or_consumed_challenge"
                elif row["expires"] <= self._clock():
                    reason = "expired_challenge"
                elif (row["channel"], row["job_id"], row["stage"], row["revision"], row["chat_id"]) != (channel, job_id, stage, int(revision), chat_id):
                    reason = "binding_mismatch"
                elif sender_id not in json.loads(row["senders"]):
                    reason = "sender_not_allowed"
                elif not secrets.compare_digest(scope_hash, "scope=" + row["scope_hash"]) or not secrets.compare_digest(budget_hash, "budget=" + row["budget_hash"]):
                    reason = "scope_or_budget_mismatch"
                elif self._db.execute("SELECT 1 FROM accepted_events WHERE channel=? AND event_id=?", (channel, event_id)).fetchone():
                    reason = "duplicate_event"
                if reason:
                    self._db.execute("ROLLBACK")
                    return {"accepted": False, "reason": reason}
                result = self._consume(row, channel=channel, event_id=event_id, sender_id=sender_id,
                                       chat_id=chat_id, decision=decision)
                self._db.execute("COMMIT")
                return result
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    @staticmethod
    def _project_scope(project_ids: Any) -> list[str]:
        if not isinstance(project_ids, (list, tuple, set, frozenset)):
            raise ConfigurationError("explicit project IDs are required for queue recovery")
        values = sorted(set(project_ids))
        for value in values:
            _identifier(value, "project_id")
        return values

    def recover_claimed(self, project_ids: Any) -> int:
        """Caller must hold the coordinator lock; never replay terminal/expired work."""
        projects = self._project_scope(project_ids)
        if not projects:
            return 0
        marks = ",".join("?" for _ in projects)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                result = self._db.execute(
                    f"UPDATE approval_queue SET state='queued' WHERE state='claimed' AND challenge_id IN (SELECT id FROM challenges WHERE status='accepted' AND expires>? AND job_id IN ({marks}))",
                    (self._clock(), *projects))
                self._db.execute("COMMIT")
                return result.rowcount
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def drain(self, limit: int = 32, *, project_ids: Any = None) -> list[dict[str, Any]]:
        """Claim queue entries on the coordinator thread; engine rechecks bindings."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ConfigurationError("invalid queue drain limit")
        projects = self._project_scope(project_ids) if project_ids is not None else None
        if projects == []:
            return []
        scope_sql = " AND c.job_id IN (" + ",".join("?" for _ in projects) + ")" if projects is not None else ""
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                rows = self._db.execute("SELECT q.id,q.payload FROM approval_queue q JOIN challenges c ON c.id=q.challenge_id WHERE q.state='queued' AND c.status='accepted' AND c.expires>?" + scope_sql + " ORDER BY q.id LIMIT ?", (self._clock(), *(projects or []), limit)).fetchall()
                # Decode before committing claims, so corrupt persisted payloads
                # roll back instead of being stranded after COMMIT.
                claimed = [dict(json.loads(row["payload"]), queue_id=row["id"]) for row in rows]
                for row in rows:
                    self._db.execute("UPDATE approval_queue SET state='claimed' WHERE id=?", (row["id"],))
                self._db.execute("COMMIT")
                return claimed
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def acknowledge(self, queue_id: int, *, applied: bool) -> None:
        with self._lock:
            self._db.execute("UPDATE approval_queue SET state=? WHERE id=? AND state='claimed'", ("applied" if applied else "rejected", queue_id))

    def begin_notification(self, channel: str, event_id: str) -> str:
        _identifier(event_id, "event_id")
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute("SELECT state FROM notifications WHERE channel=? AND event_id=?", (channel, event_id)).fetchone()
                if not row:
                    self._db.execute("INSERT INTO notifications VALUES (?,?,'sending')", (channel, event_id))
                elif row["state"] == "retryable":
                    self._db.execute("UPDATE notifications SET state='sending' WHERE channel=? AND event_id=?", (channel, event_id))
                self._db.execute("COMMIT")
                return "new" if not row or row["state"] == "retryable" else row["state"]
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def finish_notification(self, channel: str, event_id: str, *, delivered: bool) -> None:
        with self._lock:
            self._db.execute("UPDATE notifications SET state=? WHERE channel=? AND event_id=?", ("sent" if delivered else "unknown", channel, event_id))

    def allow_notification_retry(self, channel: str, event_id: str) -> bool:
        """Local operator action only, after checking whether prior delivery landed."""
        with self._lock:
            cursor = self._db.execute("UPDATE notifications SET state='retryable' WHERE channel=? AND event_id=? AND state IN ('sending','unknown')", (channel, event_id))
            return cursor.rowcount == 1


@dataclass(frozen=True)
class ChannelConfig:
    provider: str
    recipient: str
    allowed_chats: frozenset[str]
    allowed_senders: frozenset[str]
    artifact_root: Path

    @classmethod
    def from_env(cls, provider: str, artifact_root: str | Path) -> "ChannelConfig":
        prefix = {"feishu": "HC_FEISHU", "wechat": "HC_WECHAT"}.get(provider)
        if prefix is None:
            raise ConfigurationError("unsupported review channel")
        recipient = _identifier(os.environ.get(prefix + "_RECIPIENT", ""), prefix + "_RECIPIENT")
        chats = _allowlist(os.environ.get(prefix + "_ALLOWED_CHATS", ""), prefix + "_ALLOWED_CHATS")
        senders = _allowlist(os.environ.get(prefix + "_APPROVERS", ""), prefix + "_APPROVERS")
        if recipient not in chats:
            raise ConfigurationError("recipient must be in the explicit chat allowlist")
        root = Path(artifact_root).resolve(strict=True)
        if not root.is_dir():
            raise ConfigurationError("artifact root must be a directory")
        return cls(provider, recipient, chats, senders, root)


def _file(config: ChannelConfig, path: str | Path, *, image: bool) -> Path:
    path = Path(path).resolve(strict=True)
    if not path.is_relative_to(config.artifact_root.resolve(strict=True)) or not path.is_file():
        raise ChannelError("artifact must be a regular file inside the authorized artifact root")
    permitted = {".png", ".jpg", ".jpeg", ".webp"} if image else {".mp4", ".mov", ".webm", ".pdf", ".json"}
    cap = 10 * 1024 * 1024 if image else 25 * 1024 * 1024
    if path.suffix.lower() not in permitted or not 0 < path.stat().st_size <= cap:
        raise ChannelError("unsupported artifact type, empty file, or attachment exceeds local size limit")
    return path


class FeishuSDKTransport:
    """Lazy official SDK transport. Creating this object does not connect."""

    def __init__(self):
        self._app_id = os.environ.get("HC_FEISHU_APP_ID", "")
        self._app_secret = os.environ.get("HC_FEISHU_APP_SECRET", "")
        if not self._app_id or not self._app_secret:
            raise ConfigurationError("set HC_FEISHU_APP_ID and HC_FEISHU_APP_SECRET in the environment")
        try:
            import lark_oapi as lark
            from lark_oapi.api.im import v1
        except ImportError:
            raise ConfigurationError("official optional dependency lark-oapi is not installed") from None
        self._lark, self._v1 = lark, v1
        self._client = lark.Client.builder().app_id(self._app_id).app_secret(self._app_secret).log_level(lark.LogLevel.ERROR).build()

    def __repr__(self) -> str:
        return "FeishuSDKTransport(credentials=<environment>)"

    @staticmethod
    def _check(response: Any) -> Any:
        if not response.success():
            raise ChannelError("Feishu API rejected request; inspect app permissions and configuration")
        return response.data

    def upload_image(self, path: Path) -> str:
        with path.open("rb") as handle:
            body = self._v1.CreateImageRequestBody.builder().image_type("message").image(handle).build()
            request = self._v1.CreateImageRequest.builder().request_body(body).build()
            return self._check(self._client.im.v1.image.create(request)).image_key

    def upload_file(self, path: Path) -> str:
        with path.open("rb") as handle:
            body = self._v1.CreateFileRequestBody.builder().file_type("stream").file_name(path.name).file(handle).build()
            request = self._v1.CreateFileRequest.builder().request_body(body).build()
            return self._check(self._client.im.v1.file.create(request)).file_key

    def send_message(self, chat_id: str, kind: str, content: dict[str, Any]) -> str:
        body = self._v1.CreateMessageRequestBody.builder().receive_id(chat_id).msg_type(kind).content(_json(content)).uuid(str(uuid.uuid4())).build()
        request = self._v1.CreateMessageRequest.builder().receive_id_type("chat_id").request_body(body).build()
        return self._check(self._client.im.v1.message.create(request)).message_id

    def listen(self, callback: Callable[[dict[str, Any]], Any]) -> None:
        def receive(data: Any) -> None:
            try:
                callback(json.loads(self._lark.JSON.marshal(data)))
            except Exception:
                # Do not leak SDK payloads/approval nonce through exception logs.
                return
        dispatcher = self._lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(receive).build()
        self._lark.ws.Client(self._app_id, self._app_secret, event_handler=dispatcher, log_level=self._lark.LogLevel.ERROR).start()


class ReviewChannel:
    def __init__(self, config: ChannelConfig, broker: ApprovalBroker):
        self.config, self.broker = config, broker

    def _chat(self, chat_id: str | None) -> str:
        target = chat_id or self.config.recipient
        if target not in self.config.allowed_chats:
            raise ChannelError("recipient is not in the configured allowlist")
        return target

    def _instance(self) -> str:
        raise ConfigurationError("short replies require a configured bot/app instance")

    @staticmethod
    def _message_time(value: Any) -> float | None:
        # Both supported protocols expose message creation in milliseconds.
        if type(value) not in (int, float, str) or isinstance(value, bool):
            return None
        try:
            result = float(value) / 1000
        except ValueError:
            return None
        return result if math.isfinite(result) and result > 0 else None

    def _receive_text(self, *, event_id: str, sender_id: str, chat_id: str, text: str,
                      created_at: float | None = None, quoted_message_id: str | None = None,
                      unverified_reference: bool = False) -> dict[str, Any]:
        result = self.broker.accept_text(channel=self.config.provider, event_id=event_id,
            sender_id=sender_id, chat_id=chat_id, text=text, instance=self._instance(),
            created_at=created_at, quoted_message_id=quoted_message_id,
            unverified_reference=unverified_reference)
        reply = result.get("reply")
        if result.get("accepted") and not reply:
            reply = "已记录审核决定，等待工作流核验；不会扩大本次账号、素材或费用授权。"
        if reply:
            try:
                message_id = self._send_text(chat_id, reply)
            except Exception:
                # The committed decision must not be rolled back/re-consumed
                # because its acknowledgement could not be delivered.
                result["reply_delivered"] = False
                logging.getLogger(__name__).warning("Review acknowledgement unavailable; recorded decision unchanged")
            else:
                if result.get("presentation"):
                    self.broker.confirm_text_delivery(result["presentation"], message_id=message_id or "")
                result["reply_delivered"] = True
        return result

    def deliver(self, event: dict[str, Any]) -> dict[str, Any]:
        """Core notification interface; never consumes an approval or ticks engine."""
        if not isinstance(event, dict):
            raise ChannelError("notification must be an object")
        chat = self._chat(event.get("chat_id"))
        event_id = event.get("event_id")
        if not isinstance(event_id, str):
            raise ChannelError("core notifications require a persistent event_id")
        # Missing setup/files/context are safe to retry: detect before recording
        # a possibly-sent notification. Once sending begins, retries are manual.
        self._preflight_event(event, chat)
        prior = self.broker.begin_notification(self.config.provider, event_id)
        if prior == "sent":
            return {"delivered": True, "duplicate": True, "capabilities": asdict(self.capabilities)}
        if prior != "new":
            return {"delivered": False, "status": "unknown_delivery", "manual_recovery_required": True}
        try:
            result = self._deliver_event(event, chat)
        except Exception:
            self.broker.finish_notification(self.config.provider, event_id, delivered=False)
            raise
        self.broker.finish_notification(self.config.provider, event_id, delivered=True)
        return result

    def _preflight_event(self, event: dict[str, Any], chat: str) -> None:
        self._prepare_recipient(chat)
        artifacts = event.get("artifacts", [])
        if not isinstance(artifacts, list) or len(artifacts) > 20:
            raise ChannelError("invalid notification artifacts")
        kind = event.get("type", "")
        review = isinstance(kind, str) and (kind.endswith("_review") or kind in {"review", "review_required", "approval_request", "storyboard_ready", "plan_ready", "final_ready"})
        if review:
            _identifier(event.get("project_id", event.get("job_id")), "project_id")
            _binding(event.get("stage", "storyboard"), event.get("revision"), event.get("approval_scope"), event.get("budget"))
            if not isinstance(event.get("binding_hash"), str) or not re.fullmatch(r"[a-f0-9]{64}", event["binding_hash"]):
                raise ChannelError("remote review notification requires a complete core binding hash")
        for item in artifacts:
            path = item.get("path") if isinstance(item, dict) else item
            if not isinstance(path, (str, Path)):
                raise ChannelError("invalid artifact path")
            image = Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            _file(self.config, path, image=image)
            if image and not self.capabilities.image_delivery or not image and not self.capabilities.file_delivery:
                raise ChannelError("required media dependency is unavailable")

    def _deliver_event(self, event: dict[str, Any], chat: str) -> dict[str, Any]:
        artifacts = event.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise ChannelError("artifacts must be a list of local paths")
        paths = [item.get("path") if isinstance(item, dict) else item for item in artifacts]
        if any(not isinstance(path, (str, Path)) for path in paths) or len(paths) > 20:
            raise ChannelError("invalid notification artifacts")
        kind = event.get("type", "")
        review = (isinstance(kind, str) and kind.endswith("_review")) or kind in {"review", "review_required", "approval_request", "storyboard_ready", "plan_ready", "final_ready"}
        if review:
            challenge = self.send_review(job_id=event.get("project_id", event.get("job_id")),
                revision=event.get("revision"), stage=event.get("stage", "storyboard"), chat_id=chat,
                image_paths=paths, summary=str(event.get("message", "")),
                live_scope=event.get("approval_scope"), budget=event.get("budget"),
                expires_at=event.get("expires_at"), binding_hash=event.get("binding_hash"),
                shot_ids=event.get("shot_ids"))
            return {"delivered": True, "review_required": True, "challenge_id": challenge.challenge_id,
                    "capabilities": asdict(self.capabilities)}
        self.send_completion(chat_id=chat, file_paths=paths, message=str(event.get("message", event.get("status", "工作流状态更新"))))
        return {"delivered": True, "review_required": False, "capabilities": asdict(self.capabilities)}

    def send_review(self, *, job_id: str, revision: int, stage: str = "storyboard", chat_id: str | None = None,
                    image_paths: list[str | Path], summary: str = "", live_scope: Mapping[str, Any] | None = None,
                    budget: Mapping[str, Any] | None = None, expires_at: float | None = None,
                    binding_hash: str | None = None, shot_ids: list[str] | None = None) -> ApprovalChallenge:
        chat = self._chat(chat_id)
        _identifier(job_id, "job_id")
        _binding(stage, revision, live_scope, budget)
        images, files = [], []
        for path in image_paths:
            image = Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            if stage == "storyboard" and not image:
                raise ChannelError("storyboard review artifacts must be images")
            (images if image else files).append(_file(self.config, path, image=image))
        if stage == "storyboard" and not images:
            raise ChannelError("storyboard review requires delivered images")
        if images and not self.capabilities.image_delivery:
            raise ChannelError("image delivery dependency unavailable; review cannot be offered")
        self._prepare_recipient(chat)
        for path in images:
            self._send_image(chat, path)
        for path in files:
            self._send_file(chat, path)
        challenge = self.broker.issue(channel=self.config.provider, job_id=job_id, revision=revision, stage=stage,
            chat_id=chat, allowed_sender_ids=self.config.allowed_senders, live_scope=live_scope,
            budget=budget, expires_at=expires_at, binding_hash=binding_hash, shot_ids=shot_ids)
        try:
            message_id = self._send_text(chat, (summary[:4000] + "\n" if summary else "") + challenge.message())
            self.broker.mark_review_delivered(challenge.challenge_id, instance=self._instance(), message_id=message_id or "")
        except Exception:
            self.broker.cancel(challenge.challenge_id)
            raise
        return challenge

    def send_completion(self, *, file_paths: list[str | Path], message: str = "本地工作流已完成", chat_id: str | None = None) -> None:
        chat = self._chat(chat_id)
        files = [_file(self.config, path, image=False) for path in file_paths]
        self._prepare_recipient(chat)
        for path in files:
            self._send_file(chat, path)
        self._send_text(chat, message[:8000])

    def _prepare_recipient(self, chat: str) -> None:
        pass


class FeishuChannel(ReviewChannel):
    capabilities = ChannelCapabilities("feishu", "official-sdk-websocket-text", True, True, True)

    def __init__(self, config: ChannelConfig, broker: ApprovalBroker, *, transport: Any = None):
        super().__init__(config, broker)
        self._transport = transport

    @property
    def transport(self) -> Any:
        if self._transport is None:
            self._transport = FeishuSDKTransport()
        return self._transport

    def _send_image(self, chat: str, path: Path) -> None:
        self.transport.send_message(chat, "image", {"image_key": self.transport.upload_image(path)})

    def _send_file(self, chat: str, path: Path) -> None:
        self.transport.send_message(chat, "file", {"file_key": self.transport.upload_file(path)})

    def _instance(self) -> str:
        app = getattr(self.transport, "_app_id", None) or os.environ.get("HC_FEISHU_APP_ID")
        if not isinstance(app, str) or not app:
            raise ConfigurationError("short replies require the configured Feishu App identity")
        return hashlib.sha256(app.encode()).hexdigest()

    def _send_text(self, chat: str, text: str) -> str:
        # Plain text, not unverified card action callbacks or Markdown injection.
        return self.transport.send_message(chat, "text", {"text": text})

    def _prepare_recipient(self, chat: str) -> None:
        self.transport  # Validate environment/official SDK before any send attempt.

    def receive(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            header, event = payload["header"], payload["event"]
            if header.get("event_type") != "im.message.receive_v1":
                return {"accepted": False, "reason": "unsupported_event"}
            app = getattr(self._transport, "_app_id", None) or os.environ.get("HC_FEISHU_APP_ID")
            if app and header.get("app_id") != app:
                return {"accepted": False, "reason": "wrong_app"}
            sender, message = event["sender"], event["message"]
            sender_id, chat_id = sender["sender_id"]["open_id"], message["chat_id"]
            if sender.get("sender_type") != "user" or message.get("message_type") != "text":
                return {"accepted": False, "reason": "unsupported_message"}
            if sender_id not in self.config.allowed_senders or chat_id not in self.config.allowed_chats:
                return {"accepted": False, "reason": "sender_or_chat_not_allowed"}
            text = json.loads(message["content"])["text"]
            event_id = header["event_id"]
            created_at = self._message_time(message.get("create_time"))
            quoted = message.get("parent_id") or message.get("root_id")
            if quoted is not None and (not isinstance(quoted, str) or len(quoted) > 256):
                return {"accepted": False, "reason": "malformed_reference"}
        except (KeyError, TypeError, ValueError, AttributeError):
            return {"accepted": False, "reason": "malformed_event"}
        # Internal broker errors must remain errors, not be relabeled as bad
        # user input by the parsing catch above.
        return self._receive_text(event_id=event_id, sender_id=sender_id, chat_id=chat_id,
                                  text=text, created_at=created_at, quoted_message_id=quoted)

    def listen(self, stop_event: threading.Event | None = None) -> None:
        # Official SDK owns reconnects. No inbound HTTP server/public port.
        self.transport.listen(self.receive)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: Any, msg: Any, headers: Any, newurl: Any) -> None:
        return None


def _http(method: str, url: str, headers: dict[str, str], data: bytes, timeout: float) -> tuple[int, dict[str, str], bytes]:
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise ChannelError("channel response exceeds limit")
            return response.status, dict(response.headers), body
    except (urllib.error.URLError, OSError):
        raise ChannelError("channel request failed; no automatic resend of messages") from None


class WeChatChannel(ReviewChannel):
    """Official published iLink protocol, private chats only; no private client hooks.

    QR login is deliberately user-owned: use Tencent's official plugin/QR flow,
    then explicitly provide HC_WECHAT_BOT_TOKEN and HC_WECHAT_BOT_ID as env vars.
    This class never reads OpenClaw's credential store or starts QR login itself.
    """
    API_BASE = "https://ilinkai.weixin.qq.com"
    CDN_BASE = "https://novac2c.cdn.weixin.qq.com/c2c"
    PROTOCOL_REFERENCE_VERSION = "2.4.10"

    def __init__(self, config: ChannelConfig, broker: ApprovalBroker, *, request: Callable[..., Any] = _http):
        super().__init__(config, broker)
        self._token, self._bot_id = os.environ.get("HC_WECHAT_BOT_TOKEN", ""), os.environ.get("HC_WECHAT_BOT_ID", "")
        if not self._token or not self._bot_id:
            raise ConfigurationError("set HC_WECHAT_BOT_TOKEN and HC_WECHAT_BOT_ID from your own official QR authorization")
        self._request = request
        self._contexts: dict[str, str] = {}
        initial_context = os.environ.get("HC_WECHAT_CONTEXT_TOKEN")
        if initial_context:
            self._contexts[config.recipient] = initial_context
        self._cursor = self.broker.load_wechat_cursor(self._bot_id)
        self._startup_attempted = False
        self._startup_lock = threading.Lock()

    def __repr__(self) -> str:
        return "WeChatChannel(credentials=<environment>, contexts=<memory-only>)"

    @property
    def capabilities(self) -> ChannelCapabilities:
        media = importlib.util.find_spec("cryptography") is not None
        return ChannelCapabilities("wechat", "official-published-ilink-long-poll-private-chat", True, media, media)

    def _post(self, path: str, body: dict[str, Any], *, timeout: float = 20) -> dict[str, Any]:
        body = dict(body, base_info={"channel_version": self.PROTOCOL_REFERENCE_VERSION, "bot_agent": "HardcoreDirector/3.0.0"})
        headers = {"Content-Type": "application/json", "AuthorizationType": "ilink_bot_token",
                   "Authorization": "Bearer " + self._token,
                   "X-WECHAT-UIN": base64.b64encode(str(secrets.randbits(32)).encode()).decode(),
                   "iLink-App-Id": "bot", "iLink-App-ClientVersion": str((2 << 16) | (4 << 8) | 10)}
        status, _, data = self._request("POST", self.API_BASE + path, headers, _json(body).encode(), timeout)
        if status != 200:
            raise ChannelError("WeChat API returned an unsuccessful HTTP status")
        try:
            result = json.loads(data)
        except (ValueError, TypeError):
            raise ChannelError("WeChat API returned malformed JSON") from None
        if not isinstance(result, dict):
            raise ChannelError("WeChat API returned an invalid response object")
        # Tencent 874637a types.ts marks these codes optional; monitor.ts and
        # api.ts reject an explicitly nonzero code, not an omitted protobuf zero.
        # Do not confuse bool/string/null with a numeric success code.
        if any(field in result and (type(result[field]) is not int or result[field] != 0)
               for field in ("ret", "errcode")):
            raise ChannelError("WeChat API rejected request; session may require user reauthorization")
        if path == "/ilink/bot/getupdates":
            # Require protocol-specific evidence, including an opaque cursor.
            # Empty repeated msgs may be omitted: the official monitor uses
            # resp.msgs ?? []. Accept that idle shape only with a typed timeout.
            cursor = result.get("get_updates_buf")
            timeout_ms = result.get("longpolling_timeout_ms")
            if not isinstance(cursor, str):
                raise ChannelError("WeChat updates did not include a valid cursor")
            if "longpolling_timeout_ms" in result and (type(timeout_ms) is not int or timeout_ms <= 0):
                raise ChannelError("WeChat updates contain an invalid poll timeout")
            if "msgs" not in result:
                if type(timeout_ms) is not int or timeout_ms <= 0:
                    raise ChannelError("WeChat updates did not include a valid message batch")
                result["msgs"] = []
            elif not isinstance(result["msgs"], list) or any(not isinstance(item, dict) for item in result["msgs"]):
                raise ChannelError("WeChat updates contain an invalid message batch")
        elif path == "/ilink/bot/sendmessage":
            # SendMessageResp.ret is also optional; official api.ts accepts its
            # absence and exposes message_id (uint64). A typed server message ID
            # is affirmative evidence when ret is omitted. An arbitrary {} is
            # not a delivery receipt: leave it unknown, without automatic resend.
            ident = result.get("message_id")
            valid_id = ((type(ident) is int and 0 < ident <= 18446744073709551615) or
                        (isinstance(ident, str) and re.fullmatch(r"[0-9]{1,20}", ident) is not None
                         and 0 < int(ident) <= 18446744073709551615))
            if "message_id" in result and not valid_id:
                raise ChannelError("WeChat message response contains an invalid server message ID")
            if "ret" not in result and not valid_id:
                raise ChannelError("WeChat message delivery has no affirmative receipt; outcome is unknown")
        return result

    def _prepare_recipient(self, chat: str) -> None:
        if chat not in self._contexts:
            raise ChannelError("send this bot a private message first, or explicitly set HC_WECHAT_CONTEXT_TOKEN; context is not read from private files")

    def _instance(self) -> str:
        return hashlib.sha256(self._bot_id.encode()).hexdigest()

    @staticmethod
    def _uint64_id(value: Any) -> str | None:
        """Canonical decimal identity; bool/float are not protobuf uint64 IDs."""
        if type(value) is int:
            return str(value) if 0 < value <= 18446744073709551615 else None
        if type(value) is str and re.fullmatch(r"[0-9]{1,20}", value):
            number = int(value)
            return str(number) if 0 < number <= 18446744073709551615 else None
        return None

    @staticmethod
    def _empty_reference(value: Any) -> bool:
        # Do not use truthiness: false/0/[] are malformed references, not clear
        # evidence that the message is unquoted.
        return value is None or (type(value) is dict and not value) or (type(value) is str and value == "")

    @classmethod
    def _reference(cls, message: dict[str, Any], item: dict[str, Any]) -> tuple[str | None, bool]:
        """Only MessageItem.ref_msg.svr_id identifies an official iLink quote.

        RefMessage.message_item/title/partial_text describe its appearance;
        they never supply an approval target. Other meaningful reference
        metadata remains unverified, even if its text resembles this review.
        """
        keys = {"ref_msg", "quote", "quoted_message", "ref_message", "ref_message_id", "parent_id", "root_id"}
        unverified = False
        for container in (message, item):
            for key in keys.intersection(container):
                if container is item and key == "ref_msg":
                    continue
                # Observed iLink wire defaults on unquoted messages. This is
                # only a top-level thread-metadata exception, not a general
                # rule that zero/False means an empty reference.
                if container is message and key in {"parent_id", "root_id"} and type(container[key]) is int and container[key] == 0:
                    continue
                if not cls._empty_reference(container[key]):
                    unverified = True
        reference = item.get("ref_msg")
        if cls._empty_reference(reference):
            return None, unverified
        if type(reference) is not dict:
            return None, True
        ident = cls._uint64_id(reference.get("svr_id"))
        if ident is None:
            return None, True
        # A second nested reference is not evidence for the current quote.
        # Reject ambiguity instead of following another quoted message.
        nested = reference.get("message_item")
        if type(nested) is dict and any(not cls._empty_reference(nested[key]) for key in keys.intersection(nested)):
            unverified = True
        return ident, unverified

    def _send_items(self, chat: str, items: list[dict[str, Any]]) -> str:
        self._prepare_recipient(chat)
        result = self._post("/ilink/bot/sendmessage", {"msg": {"from_user_id": "", "to_user_id": chat,
            "client_id": uuid.uuid4().hex, "message_type": 2, "message_state": 2,
            "context_token": self._contexts[chat], "item_list": items}})
        return self._uint64_id(result.get("message_id")) or ""

    def _send_text(self, chat: str, text: str) -> str:
        return self._send_items(chat, [{"type": 1, "text_item": {"text": text}}])

    def _upload(self, chat: str, path: Path, media_type: int) -> dict[str, Any]:
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        except ImportError:
            raise ConfigurationError("optional cryptography dependency required for official WeChat media encryption") from None
        raw, key, filekey = path.read_bytes(), secrets.token_bytes(16), secrets.token_hex(16)
        padding = 16 - len(raw) % 16
        encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
        encrypted = encryptor.update(raw + bytes([padding]) * padding) + encryptor.finalize()
        parameters = self._post("/ilink/bot/getuploadurl", {"filekey": filekey, "media_type": media_type,
            "to_user_id": chat, "rawsize": len(raw), "rawfilemd5": hashlib.md5(raw).hexdigest(),
            "filesize": len(encrypted), "no_need_thumb": True, "aeskey": key.hex()})
        url = parameters.get("upload_full_url")
        if not url and isinstance(parameters.get("upload_param"), str) and parameters["upload_param"]:
            url = self.CDN_BASE + "/upload?" + urllib.parse.urlencode({"encrypted_query_param": parameters["upload_param"], "filekey": filekey})
        if not isinstance(url, str):
            raise ChannelError("WeChat returned no media upload URL")
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "novac2c.cdn.weixin.qq.com" or parsed.username or parsed.password or parsed.port not in {None, 443}:
            raise ChannelError("WeChat media URL is not the documented official CDN; refusing upload")
        # Bot credentials never accompany a CDN request; redirects are disabled.
        status, headers, _ = self._request("POST", url, {"Content-Type": "application/octet-stream"}, encrypted, 30)
        download = next((value for name, value in headers.items() if name.lower() == "x-encrypted-param"), None)
        if status != 200 or not download:
            raise ChannelError("WeChat CDN did not confirm media upload")
        return {"media": {"encrypt_query_param": download,
                          "aes_key": base64.b64encode(key.hex().encode()).decode(), "encrypt_type": 1},
                "rawsize": len(raw), "cipher_size": len(encrypted)}

    def _send_image(self, chat: str, path: Path) -> None:
        uploaded = self._upload(chat, path, 1)
        self._send_items(chat, [{"type": 2, "image_item": {"media": uploaded["media"], "mid_size": uploaded["cipher_size"]}}])

    def _send_file(self, chat: str, path: Path) -> None:
        uploaded = self._upload(chat, path, 3)
        self._send_items(chat, [{"type": 4, "file_item": {"media": uploaded["media"], "file_name": path.name, "len": str(uploaded["rawsize"])}}])

    def receive(self, message: dict[str, Any]) -> dict[str, Any]:
        try:
            sender = message["from_user_id"]
            if message.get("group_id") or message.get("message_type") != 1 or message.get("to_user_id") != self._bot_id:
                return {"accepted": False, "reason": "unsupported_message_or_wrong_bot"}
            if sender not in self.config.allowed_senders or sender not in self.config.allowed_chats:
                return {"accepted": False, "reason": "sender_or_chat_not_allowed"}
            items = message.get("item_list", [])
            if not isinstance(items, list) or len(items) != 1 or items[0].get("type") != 1:
                return {"accepted": False, "reason": "text_command_required"}
            context = message.get("context_token")
            if not isinstance(context, str) or not context:
                return {"accepted": False, "reason": "missing_context"}
            ident = self._uint64_id(message.get("message_id"))
            if ident is None:
                return {"accepted": False, "reason": "missing_event_id"}
            text = items[0]["text_item"]["text"]
        except (KeyError, TypeError, ValueError, AttributeError):
            return {"accepted": False, "reason": "malformed_event"}
        # Only untrusted field parsing belongs to the try above. Broker failures
        # (including corrupt stored JSON) must abort the batch, not masquerade as
        # a rejected message followed by a committed cursor.
        self._contexts[sender] = context
        event_id = hashlib.sha256(self._bot_id.encode()).hexdigest() + ":" + str(ident)
        # Legacy raw event IDs remain untouched. Previously consumed nonces are
        # still rejected by challenge.status, so namespacing cannot revive them.
        quoted_message_id, unverified_reference = self._reference(message, items[0])
        return self._receive_text(event_id=event_id, sender_id=sender, chat_id=sender, text=text,
                                  created_at=self._message_time(message.get("create_time_ms")),
                                  quoted_message_id=quoted_message_id,
                                  unverified_reference=unverified_reference)

    def poll_once(self) -> int:
        self._notify_start_once()
        result = self._post("/ilink/bot/getupdates", {"get_updates_buf": self._cursor}, timeout=45)
        messages = result.get("msgs", [])
        if not isinstance(messages, list):
            raise ChannelError("WeChat updates contain an invalid message list")
        for message in messages:
            if isinstance(message, dict):
                self.receive(message)
        cursor = result.get("get_updates_buf")
        if isinstance(cursor, str) and cursor:
            # Receive/queue every message first. Persist before changing memory;
            # if this fails, the listener stops and replay remains deduplicated.
            self.broker.save_wechat_cursor(self._bot_id, cursor)
            self._cursor = cursor
        return len(messages)

    def _notify_start_once(self) -> None:
        # Official channel.ts sends this lifecycle notice before monitor startup.
        # It is not a chat message or a required successful handshake. Match its
        # warn-and-continue behavior; never log a response, token, or exception.
        with self._startup_lock:
            if self._startup_attempted:
                return
            self._startup_attempted = True
            try:
                self._post("/ilink/bot/msg/notifystart", {}, timeout=10)
            except Exception:
                logging.getLogger(__name__).warning("WeChat startup notification failed; continuing message polling")

    def listen(self, stop_event: threading.Event | None = None) -> None:
        stop = stop_event or threading.Event()
        failures = 0
        while not stop.is_set():
            try:
                self.poll_once()
                failures = 0
            except CursorStorageError:
                raise
            except ChannelError:
                failures += 1
                if failures >= 3:
                    raise ChannelError("WeChat listener stopped after repeated failures; user must check session") from None
                stop.wait(min(2 ** failures, 10))


def create_channel(provider: str, *, artifact_root: str | Path, approval_db: str | Path,
                   clock: Callable[[], float] = time.time) -> ReviewChannel:
    config = ChannelConfig.from_env(provider, artifact_root)
    broker = ApprovalBroker(approval_db, clock=clock)
    if provider == "feishu":
        return FeishuChannel(config, broker)
    if provider == "wechat":
        return WeChatChannel(config, broker)
    raise ConfigurationError("unsupported channel")
