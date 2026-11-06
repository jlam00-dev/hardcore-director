from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hc_workflow.channels import (
    ApprovalBroker, ChannelConfig, ChannelError, ConfigurationError, CursorStorageError,
    FeishuChannel, FeishuSDKTransport, WeChatChannel,
)
from workflow_bridge import CoordinatorBusy, WorkflowBridge, _read_wechat_credentials, main as bridge_main


class Transport:
    def __init__(self):
        self.sent = []
        self._app_id = "app-fixture"

    def upload_image(self, path):
        self.sent.append(("upload_image", path.name))
        return "image-key"

    def upload_file(self, path):
        self.sent.append(("upload_file", path.name))
        return "file-key"

    def send_message(self, chat, kind, content):
        self.sent.append((chat, kind, content))
        return f"message-{len(self.sent)}"


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = 1000.0
        self.broker = ApprovalBroker(self.root / "approvals.sqlite3", clock=lambda: self.now)
        self.scope = {"stages": ["video"], "provider": "fixture", "account": "own-account",
                      "allow_uploads": False, "revision": 2, "plan_hash": "planhash", "asset_hash": "assethash"}
        self.budget = {"amount": "3.50", "currency": "CNY"}
        self.config = ChannelConfig("feishu", "chat-1", frozenset({"chat-1"}), frozenset({"user-1"}), self.root)
        self.transport = Transport()
        self.feishu = FeishuChannel(self.config, self.broker, transport=self.transport)
        self.image = self.root / "shot.png"
        self.image.write_bytes(b"test image fixture")

    def tearDown(self):
        self.broker.close()
        self.temp.cleanup()

    def issue(self, **overrides):
        arguments = dict(channel="feishu", job_id="job-1", revision=2, stage="storyboard",
                         chat_id="chat-1", allowed_sender_ids={"user-1"},
                         live_scope=self.scope, budget=self.budget, ttl_seconds=120)
        arguments.update(overrides)
        return self.broker.issue(**arguments)

    def accept(self, command, **overrides):
        arguments = dict(channel="feishu", event_id="event-1", sender_id="user-1", chat_id="chat-1", command=command)
        arguments.update(overrides)
        return self.broker.accept(**arguments)

    def event(self, command, **message):
        return {"header": {"event_type": "im.message.receive_v1", "event_id": "ev-1", "app_id": "app-fixture"},
                "event": {"sender": {"sender_type": "user", "sender_id": {"open_id": "user-1"}},
                          "message": {"message_type": "text", "chat_id": "chat-1", "content": json.dumps({"text": command}), **message}}}

    def test_acceptance_only_queues_exact_bound_budget_and_scope(self):
        challenge = self.issue()
        self.assertTrue(self.accept(challenge.approve_command)["accepted"])
        decisions = self.broker.drain()
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["live_scope"], self.scope)
        self.assertEqual(decisions[0]["budget"], self.budget)
        self.assertEqual(decisions[0]["stage"], "storyboard")
        self.assertEqual(self.transport.sent, [])
        self.assertEqual(self.broker.drain(), [])

    def test_nonce_and_event_are_one_use_across_restart(self):
        challenge = self.issue()
        self.assertTrue(self.accept(challenge.approve_command)["accepted"])
        self.broker.close()
        self.broker = ApprovalBroker(self.root / "approvals.sqlite3", clock=lambda: self.now)
        self.assertFalse(self.accept(challenge.approve_command, event_id="another")["accepted"])
        self.assertEqual(len(self.broker.drain()), 1)

    def test_no_plain_nonce_or_credentials_in_database(self):
        challenge = self.issue()
        nonce = challenge.approve_command.split()[5]
        self.accept(challenge.approve_command)
        raw = (self.root / "approvals.sqlite3").read_bytes()
        self.assertNotIn(nonce.encode(), raw)
        self.assertEqual((self.root / "approvals.sqlite3").stat().st_mode & 0o777, 0o600)

    def test_forged_sender_chat_channel_revision_stage_and_job_rejected(self):
        challenge = self.issue()
        for override in ({"sender_id": "outsider"}, {"chat_id": "other-chat"}, {"channel": "wechat"}):
            with self.subTest(override=override):
                self.assertFalse(self.accept(challenge.approve_command, **override)["accepted"])
        for old, new in (("storyboard", "plan"), ("job-1", "job-2"), (" 2 ", " 3 ")):
            with self.subTest(old=old):
                self.assertFalse(self.accept(challenge.approve_command.replace(old, new))["accepted"])
        self.assertEqual(self.broker.drain(), [])
        self.assertTrue(self.accept(challenge.approve_command)["accepted"])

    def test_scope_budget_tampering_and_multiline_commands_fail_closed(self):
        challenge = self.issue()
        for command in (challenge.approve_command + " ;rm", challenge.approve_command + "\n/hc approve",
                        challenge.approve_command.replace("scope=", "scope=0"),
                        challenge.approve_command.replace("budget=", "budget=0"), "/hc approve job-1", "同意"):
            self.assertFalse(self.accept(command)["accepted"])
        self.assertEqual(self.broker.drain(), [])

    def test_expired_and_superseded_reviews_cannot_approve(self):
        challenge = self.issue()
        self.now += 121
        self.assertFalse(self.accept(challenge.approve_command)["accepted"])
        self.now = 1000
        old = self.issue()
        newer = self.issue(revision=3, live_scope=dict(self.scope, revision=3))
        self.assertFalse(self.accept(old.approve_command)["accepted"])
        self.assertTrue(self.accept(newer.approve_command)["accepted"])

    def test_disjoint_bound_shot_reviews_survive_issue_acceptance_and_restart(self):
        first = self.issue(binding_hash="a" * 64, shot_ids=["S01"])
        self.assertTrue(self.accept(first.approve_command, event_id="approve-S01")["accepted"])
        second = self.issue(binding_hash="a" * 64, shot_ids=["S02"])
        self.broker.close()
        self.broker = ApprovalBroker(self.root / "approvals.sqlite3", clock=lambda: self.now)
        self.assertTrue(self.accept(second.reject_command, event_id="reject-S02")["accepted"])
        queued = self.broker.drain()
        self.assertEqual([(item["decision"], item["shot_ids"]) for item in queued], [("approve", ["S01"]), ("reject", ["S02"])])
        self.assertTrue(all(item["binding_hash"] == "a" * 64 and item["live_scope"] == self.scope and item["budget"] == self.budget for item in queued))

    def test_overlapping_new_shot_review_invalidates_old_queue_but_preserves_other_shot(self):
        old = self.issue(binding_hash="a" * 64, shot_ids=["S01"])
        self.assertTrue(self.accept(old.approve_command, event_id="old-S01")["accepted"])
        other = self.issue(binding_hash="a" * 64, shot_ids=["S02"])
        replacement = self.issue(binding_hash="a" * 64, shot_ids=["S01"], budget={"amount": "5", "currency": "CNY"})
        self.assertFalse(self.accept(old.approve_command, event_id="old-replay")["accepted"])
        self.assertTrue(self.accept(other.reject_command, event_id="other-S02")["accepted"])
        self.assertTrue(self.accept(replacement.approve_command, event_id="new-S01")["accepted"])
        queued = self.broker.drain()
        self.assertEqual([(item["decision"], item["shot_ids"], item["budget"]["amount"]) for item in queued],
                         [("reject", ["S02"], "3.50"), ("approve", ["S01"], "5")])

    def test_whole_batch_revision_binding_or_recipient_change_supersedes_all_shots(self):
        for change in ("whole", "revision", "binding", "chat", "senders", "missing_binding"):
            with self.subTest(change=change):
                job = "job-" + change
                first = self.issue(job_id=job, binding_hash="a" * 64, shot_ids=["S01"])
                second = self.issue(job_id=job, binding_hash="a" * 64, shot_ids=["S02"])
                self.assertTrue(self.accept(first.approve_command, event_id=change + "-old")["accepted"])
                overrides = {"job_id": job, "binding_hash": "a" * 64, "shot_ids": ["S03"]}
                if change == "whole":
                    overrides["shot_ids"] = None
                elif change == "revision":
                    overrides.update(revision=3, live_scope=dict(self.scope, revision=3))
                elif change == "binding":
                    overrides["binding_hash"] = "b" * 64
                elif change == "chat":
                    overrides["chat_id"] = "chat-2"
                elif change == "senders":
                    overrides["allowed_sender_ids"] = {"user-2"}
                else:
                    overrides["binding_hash"] = None
                self.issue(**overrides)
                self.assertFalse(self.accept(second.reject_command, event_id=change + "-replay")["accepted"])
                self.assertEqual(self.broker.drain(project_ids=[job]), [])

    def test_corrupt_stored_shot_scope_cannot_be_treated_as_disjoint(self):
        first = self.issue(binding_hash="a" * 64, shot_ids=["S01"])
        self.broker._db.execute("UPDATE challenges SET shot_ids=? WHERE id=?", (json.dumps("S01"), first.challenge_id))
        with self.assertRaises(ConfigurationError):
            self.issue(binding_hash="a" * 64, shot_ids=["S02"])
        self.assertEqual(self.broker._db.execute("SELECT COUNT(*) FROM challenges").fetchone()[0], 1)

    def test_automatic_two_shot_phone_rejection_retains_first_asset_and_rejects_stale_command(self):
        from hc_workflow.engine import Engine
        class FixtureProvider:
            prepares = []
            def identity(inner):
                return {"provider": "offline-fixture", "account": "fake", "live": False, "verified": True}
            def quote(inner, operation):
                return {"amount": "0", "currency": "CNY"}
            def prepare(inner, operation):
                inner.prepares.append(operation["shot_id"])
                return {"status": "prepared"}
            def submit(inner, operation):
                return {"status": "submitted", "task_id": "fake-" + operation["operation_id"]}
            def poll(inner, operation):
                return {"status": "succeeded"}
            def download(inner, operation):
                target = Path(operation["output_dir"]) / (operation["shot_id"] + ".png")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(("unit fixture " + operation["shot_id"]).encode())
                return {"status": "succeeded", "path": str(target)}
        provider = FixtureProvider()
        issued = []
        send_review = self.feishu.send_review
        def collect_review(**kwargs):
            challenge = send_review(**kwargs)
            issued.append(challenge)
            return challenge
        self.feishu.send_review = collect_review
        engine = Engine(self.root / "workflow.sqlite3", {"fixture": provider}, channel=self.feishu,
                        artifact_dir=self.root / "artifacts", clock=lambda: self.now)
        self.addCleanup(engine.close)
        pid = engine.init_project("two-shot phone review")["project_id"]
        engine.set_plan(pid, {"providers": {"image": "fixture", "video": "fixture"},
            "shots": [{"id": sid, "duration_seconds": 1, "image_prompt": "synthetic", "video_prompt": "hold"} for sid in ("S01", "S02")]})
        engine.approve(pid, actor="fixture-director")
        for _ in range(12):
            state = engine.tick(pid)
            if state["status"] == "storyboard_review":
                break
        self.assertEqual(state["status"], "storyboard_review")
        # Long nonce commands remain compatible without being sent to users.
        commands = {challenge.shot_ids[0]: {"reject": challenge.reject_command, "approve": challenge.approve_command}
                    for challenge in issued}
        self.assertEqual(set(commands), {"S01", "S02"})
        first = state["shots"][0]["image"]
        first_bytes = Path(first["path"]).read_bytes()
        self.assertTrue(self.feishu.receive(self.event(commands["S02"]["reject"]))["accepted"])
        bridge = WorkflowBridge(engine, self.feishu, [pid], clock=lambda: self.now)
        self.assertTrue(bridge.run_once()["decisions"][0]["applied"])
        rejected = engine.status(pid)
        self.assertEqual(rejected["shots"][0]["image"], first)
        self.assertEqual(Path(first["path"]).read_bytes(), first_bytes)
        self.assertIsNone(rejected["shots"][1]["image"])
        self.assertEqual(provider.prepares, ["S01", "S02"])
        stale = self.event(commands["S01"]["approve"])
        stale["header"]["event_id"] = "stale-S01"
        self.assertTrue(self.feishu.receive(stale)["accepted"])
        self.assertFalse(bridge.run_once()["decisions"][0]["applied"])
        self.assertEqual(engine.status(pid)["shots"][0]["image"], first)

    def test_duplicate_event_id_cannot_consume_new_challenge(self):
        first = self.issue()
        self.assertTrue(self.accept(first.approve_command)["accepted"])
        second = self.issue()
        self.assertFalse(self.accept(second.approve_command)["accepted"])
        self.assertTrue(self.accept(second.approve_command, event_id="new-event")["accepted"])

    def test_atomic_double_delivery_only_queues_once(self):
        challenge = self.issue()
        results = []
        threads = [threading.Thread(target=lambda i=i: results.append(self.accept(challenge.approve_command, event_id=f"e-{i}"))) for i in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(item["accepted"] for item in results), 1)
        self.assertEqual(len(self.broker.drain()), 1)

    def test_expired_queued_approval_is_not_applied_after_delay(self):
        challenge = self.issue()
        self.accept(challenge.approve_command)
        self.now += 121
        self.assertEqual(self.broker.drain(), [])

    def test_invalid_scope_secret_fields_budgets_and_unbounded_ttl_rejected(self):
        for override in ({"live_scope": dict(self.scope, api_key="never-persist")},
                         {"live_scope": dict(self.scope, stages=["image", "video"])},
                         {"budget": {"amount": "NaN", "currency": "CNY"}},
                         {"budget": {"amount": "-1", "currency": "CNY"}},
                         {"ttl_seconds": 999999}, {"expires_at": float("nan")}):
            with self.subTest(override=override), self.assertRaises(ConfigurationError):
                self.issue(**override)

    def test_review_preflights_paths_and_does_not_upload_outside_artifact_root(self):
        outside = self.root.parent / "not-a-real-authorized-file.png"
        with self.assertRaises((ChannelError, OSError)):
            self.feishu.send_review(job_id="job-1", revision=2, image_paths=[outside])
        self.assertEqual(self.transport.sent, [])
        with self.assertRaises(ChannelError):
            self.feishu.send_review(job_id="job-1", revision=2, image_paths=[], chat_id="outsider")
        self.assertEqual(self.transport.sent, [])

    def test_review_images_arrive_before_challenge_and_missing_images_fail(self):
        challenge = self.feishu.send_review(job_id="job-1", revision=2, image_paths=[self.image], live_scope=self.scope, budget=self.budget)
        self.assertEqual(self.transport.sent[0][0], "upload_image")
        self.assertEqual(self.transport.sent[1][1], "image")
        self.assertNotIn(challenge.approve_command, self.transport.sent[2][2]["text"])
        self.assertIn("请直接回复“同意”或“拒绝”", self.transport.sent[-1][2]["text"])
        self.assertEqual(len([item for item in self.transport.sent if len(item) == 3 and item[1] == "text"]), 1)
        self.assertFalse(self.feishu.capabilities.card_actions)
        with self.assertRaises(ChannelError):
            self.feishu.send_review(job_id="job-1", revision=2, image_paths=[])

    def test_failed_notification_cancels_challenge(self):
        for failing_message in range(1):
            with self.subTest(failing_message=failing_message), mock.patch.object(
                    self.feishu, "_send_text", side_effect=[None] * failing_message + [ChannelError("safe")]):
                with self.assertRaises(ChannelError):
                    self.feishu.send_review(job_id=f"job-fail-{failing_message}", revision=2, image_paths=[self.image])
        statuses = [row[0] for row in self.broker._db.execute("SELECT status FROM challenges")]
        self.assertEqual(statuses, ["cancelled"])
        self.assertEqual(self.broker._db.execute("SELECT count(*) FROM short_reviews").fetchone()[0], 0)

    def test_review_uses_two_char_reply_with_readable_scope_and_keeps_legacy_nonce(self):
        challenge = self.feishu.send_review(job_id="job-1", revision=2, image_paths=[self.image],
            live_scope=self.scope, budget=self.budget, shot_ids=["S01"], binding_hash="a" * 64)
        texts = [entry[2]["text"] for entry in self.transport.sent if len(entry) == 3 and entry[1] == "text"]
        summary, = texts
        for visible in ("job-1", "修订：2", "分镜图审核", "镜号：S01", "供应商：fixture", "own-account",
                        "生成视频", "不允许向生成供应商上传", "3.50 CNY", "累计上限", "到期时间", "请直接回复“同意”或“拒绝”"):
            self.assertIn(visible, summary)
        self.assertNotIn('{"stages"', summary)
        self.assertNotIn('{"amount"', summary)
        self.assertNotIn(challenge.reject_command, summary)
        self.assertNotIn(challenge.approve_command, summary)
        with mock.patch.dict(os.environ, {"HC_FEISHU_APP_ID": "app-fixture"}):
            self.assertTrue(self.feishu.receive(self.event("同意", create_time="1000000"))["accepted"])
        queued = self.broker.drain()
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["live_scope"], self.scope)
        self.assertEqual(queued[0]["budget"], self.budget)
        self.assertEqual(queued[0]["binding_hash"], "a" * 64)
        self.assertEqual(queued[0]["shot_ids"], ["S01"])
        no_generation = self.issue(job_id="review-only", live_scope={"stages": [], "allow_uploads": False}).message()
        self.assertIn("不授权任何模型生成或扣费", no_generation)

    def test_feishu_requires_user_message_event_app_sender_and_chat(self):
        challenge = self.issue()
        with mock.patch.dict(os.environ, {"HC_FEISHU_APP_ID": "app-fixture"}):
            wrong_app = self.event(challenge.approve_command)
            wrong_app["header"]["app_id"] = "unrelated-app"
            self.assertFalse(self.feishu.receive(wrong_app)["accepted"])
            self.assertFalse(self.feishu.receive(self.event(challenge.approve_command, message_type="image"))["accepted"])
            bad_sender = self.event(challenge.approve_command)
            bad_sender["event"]["sender"]["sender_id"]["open_id"] = "outsider"
            self.assertFalse(self.feishu.receive(bad_sender)["accepted"])
            self.assertTrue(self.feishu.receive(self.event(challenge.approve_command))["accepted"])
        self.assertEqual(len(self.broker.drain()), 1)

    def test_configuration_requires_allowlists_and_never_installs_sdk(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError):
                ChannelConfig.from_env("feishu", self.root)
            with self.assertRaises(ConfigurationError):
                FeishuSDKTransport()

    def wechat(self, request=None, *, bot_id="wx-bot"):
        config = ChannelConfig("wechat", "wx-user", frozenset({"wx-user"}), frozenset({"wx-user"}), self.root)
        with mock.patch.dict(os.environ, {"HC_WECHAT_BOT_TOKEN": "synthetic-test-token", "HC_WECHAT_BOT_ID": bot_id, "HC_WECHAT_CONTEXT_TOKEN": ""}):
            return WeChatChannel(config, self.broker, request=request or (lambda *a: (200, {}, b'{"ret":0}')))

    def wx_message(self, command):
        return {"message_id": 1234, "from_user_id": "wx-user", "to_user_id": "wx-bot", "message_type": 1,
                "context_token": "synthetic-context-never-persist", "item_list": [{"type": 1, "text_item": {"text": command}}]}

    def test_wechat_official_private_inbound_only_and_context_memory_only(self):
        channel = self.wechat()
        challenge = self.issue(channel="wechat", chat_id="wx-user", allowed_sender_ids={"wx-user"})
        for changed in ({"to_user_id": "other-bot"}, {"group_id": "a-group"}, {"from_user_id": "outsider"}, {"message_type": 2}):
            self.assertFalse(channel.receive(dict(self.wx_message(challenge.approve_command), **changed))["accepted"])
        self.assertTrue(channel.receive(self.wx_message(challenge.approve_command))["accepted"])
        raw = (self.root / "approvals.sqlite3").read_bytes()
        self.assertNotIn(b"synthetic-test-token", raw)
        self.assertNotIn(b"synthetic-context", raw)
        self.assertNotIn("synthetic-test-token", repr(channel))
        self.assertEqual(len(self.broker.drain()), 1)

    def test_wechat_requires_context_and_explicit_success(self):
        channel = self.wechat(request=lambda *args: (200, {}, b"{}"))
        with self.assertRaises(ChannelError):
            channel._send_text("wx-user", "test")
        channel._contexts["wx-user"] = "synthetic-context"
        with self.assertRaises(ChannelError):
            channel._send_text("wx-user", "test")

    def test_wechat_updates_accept_omitted_ret_with_typed_batch_and_cursor(self):
        calls = []
        def request(*args):
            calls.append(args)
            return 200, {}, b'{"msgs":[],"get_updates_buf":"next-cursor","longpolling_timeout_ms":35000}'
        channel = self.wechat(request=request)
        self.assertEqual(channel.poll_once(), 0)
        self.assertEqual(channel._cursor, "next-cursor")
        channel.poll_once()
        polls = [call for call in calls if call[1].endswith("/getupdates")]
        self.assertEqual(json.loads(polls[0][3])["get_updates_buf"], "")
        self.assertEqual(json.loads(polls[1][3])["get_updates_buf"], "next-cursor")

    def test_wechat_updates_omitted_ret_can_receive_bound_approval(self):
        challenge = self.issue(channel="wechat", chat_id="wx-user", allowed_sender_ids={"wx-user"})
        response = {"msgs": [self.wx_message(challenge.approve_command)], "get_updates_buf": "cursor-after-approval"}
        channel = self.wechat(request=lambda *args: (200, {}, json.dumps(response).encode()))
        self.assertEqual(channel.poll_once(), 1)
        queued = self.broker.drain()
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["decision"], "approve")
        self.assertEqual(channel._cursor, "cursor-after-approval")

    def test_wechat_updates_accept_empty_cursor_and_documented_idle_shape(self):
        for response in ({"ret": 0, "msgs": [], "get_updates_buf": ""},
                         {"get_updates_buf": "idle-cursor", "longpolling_timeout_ms": 35000}):
            with self.subTest(response=response):
                channel = self.wechat(request=lambda *args: (200, {}, json.dumps(response).encode()))
                self.assertEqual(channel.poll_once(), 0)

    def test_wechat_updates_reject_empty_error_or_malformed_contract_without_advancing(self):
        responses = [{}, {"ret": 0}, {"msgs": []}, {"get_updates_buf": "cursor-only"},
                     {"msgs": {}, "get_updates_buf": "bad"},
                     {"msgs": [None], "get_updates_buf": "bad"},
                     {"msgs": [], "get_updates_buf": 123},
                     {"msgs": [], "get_updates_buf": "bad", "longpolling_timeout_ms": False},
                     {"msgs": [], "get_updates_buf": "bad", "ret": -14},
                     {"msgs": [], "get_updates_buf": "bad", "errcode": -1},
                     {"msgs": [], "get_updates_buf": "bad", "ret": "0"},
                     {"msgs": [], "get_updates_buf": "bad", "ret": False},
                     {"msgs": [], "get_updates_buf": "bad", "errcode": None}]
        for response in responses:
            with self.subTest(response=response):
                channel = self.wechat(request=lambda *args: (200, {}, json.dumps(response).encode()))
                channel._cursor = "last-known-good"
                with self.assertRaises(ChannelError):
                    channel.poll_once()
                self.assertEqual(channel._cursor, "last-known-good")
                self.assertEqual(self.broker.drain(), [])

    def test_wechat_updates_reject_non_200_even_with_success_shaped_body(self):
        channel = self.wechat(request=lambda *args: (503, {}, b'{"ret":0,"msgs":[],"get_updates_buf":"bad"}'))
        with self.assertRaises(ChannelError):
            channel.poll_once()

    def test_wechat_send_accepts_missing_ret_only_with_valid_server_message_id(self):
        for response in ({"message_id": "18446744073709551615"}, {"message_id": 1234}, {"ret": 0}):
            with self.subTest(response=response):
                channel = self.wechat(request=lambda *args: (200, {}, json.dumps(response).encode()))
                channel._contexts["wx-user"] = "synthetic-context"
                channel._send_text("wx-user", "one authorized test message")

    def test_wechat_send_rejects_empty_ambiguous_error_and_invalid_receipts(self):
        responses = [{}, {"errmsg": ""}, {"errcode": 0}, {"message_id": ""},
                     {"message_id": "not-an-id"}, {"message_id": False}, {"message_id": -1},
                     {"message_id": "18446744073709551616"}, {"message_id": "123", "ret": -14},
                     {"message_id": "123", "errcode": -1}, {"ret": False}, {"ret": "0"}]
        for response in responses:
            with self.subTest(response=response):
                channel = self.wechat(request=lambda *args: (200, {}, json.dumps(response).encode()))
                channel._contexts["wx-user"] = "synthetic-context"
                with self.assertRaises(ChannelError):
                    channel._send_text("wx-user", "one authorized test message")

    def test_wechat_startup_is_deferred_until_poll_and_once_per_instance(self):
        calls = []
        def request(*args):
            calls.append(args)
            if args[1].endswith("/notifystart"):
                return 200, {}, b'{"ret":0}'
            return 200, {}, b'{"msgs":[],"get_updates_buf":"next"}'
        channel = self.wechat(request=request)
        self.assertEqual(calls, [], "constructing a channel must not use the network")
        channel.poll_once()
        channel.poll_once()
        self.assertEqual([call[1].rsplit("/", 1)[-1] for call in calls], ["notifystart", "getupdates", "getupdates"])
        startup = json.loads(calls[0][3])
        self.assertEqual(set(startup), {"base_info"})
        self.assertNotIn("msg", startup)
        self.assertNotIn("context_token", startup)

    def test_wechat_failed_startup_warns_safely_and_still_polls_without_retrying_notice(self):
        calls = []
        def request(*args):
            calls.append(args)
            if args[1].endswith("/notifystart"):
                raise ChannelError("synthetic-sensitive-response-must-not-log")
            return 200, {}, b'{"msgs":[],"get_updates_buf":"next"}'
        channel = self.wechat(request=request)
        with self.assertLogs("hc_workflow.channels", level="WARNING") as logs:
            self.assertEqual(channel.poll_once(), 0)
            self.assertEqual(channel.poll_once(), 0)
        self.assertEqual(sum(call[1].endswith("/notifystart") for call in calls), 1)
        self.assertEqual(sum(call[1].endswith("/getupdates") for call in calls), 2)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("continuing message polling", logs.output[0])
        self.assertNotIn("synthetic-sensitive", logs.output[0])

    def test_wechat_cursor_restores_after_broker_and_channel_restart(self):
        def request(*args):
            if args[1].endswith("/notifystart"):
                return 200, {}, b'{"ret":0}'
            return 200, {}, b'{"msgs":[],"get_updates_buf":"saved-opaque-cursor"}'
        self.wechat(request=request).poll_once()
        self.broker.close()
        self.broker = ApprovalBroker(self.root / "approvals.sqlite3", clock=lambda: self.now)
        calls = []
        def after_restart(*args):
            calls.append(args)
            return request(*args)
        restarted = self.wechat(request=after_restart)
        self.assertEqual(restarted._cursor, "saved-opaque-cursor")
        restarted.poll_once()
        poll = next(call for call in calls if call[1].endswith("/getupdates"))
        self.assertEqual(json.loads(poll[3])["get_updates_buf"], "saved-opaque-cursor")
        self.assertEqual(restarted._contexts, {})

    def test_wechat_cursor_partitions_are_bot_hashes_and_do_not_cross_accounts(self):
        self.broker.save_wechat_cursor("first@im.bot", "first-cursor")
        second = self.wechat(bot_id="second@im.bot")
        self.assertEqual(second._cursor, "")
        self.broker.save_wechat_cursor("second@im.bot", "second-cursor")
        self.assertEqual(self.wechat(bot_id="first@im.bot")._cursor, "first-cursor")
        self.assertEqual(self.wechat(bot_id="second@im.bot")._cursor, "second-cursor")
        partitions = [row[0] for row in self.broker._db.execute("SELECT bot_hash FROM wechat_cursors")]
        self.assertEqual(len(partitions), 2)
        self.assertTrue(all(len(value) == 64 and "@" not in value for value in partitions))
        raw = (self.root / "approvals.sqlite3").read_bytes()
        self.assertNotIn(b"first@im.bot", raw)
        self.assertNotIn(b"second@im.bot", raw)

    def test_wechat_empty_cursor_does_not_erase_persisted_progress(self):
        self.broker.save_wechat_cursor("wx-bot", "keep-cursor")
        channel = self.wechat(request=lambda *args: (200, {}, b'{"ret":0,"msgs":[],"get_updates_buf":""}'))
        self.assertEqual(channel.poll_once(), 0)
        self.assertEqual(channel._cursor, "keep-cursor")
        self.assertEqual(self.broker.load_wechat_cursor("wx-bot"), "keep-cursor")

    def test_wechat_receive_failure_does_not_advance_memory_or_saved_cursor(self):
        self.broker.save_wechat_cursor("wx-bot", "before-batch")
        reply = {"msgs": [{"message_id": 1}, {"message_id": 2}], "get_updates_buf": "after-batch"}
        def request(*args):
            return (200, {}, b'{"ret":0}') if args[1].endswith("/notifystart") else (200, {}, json.dumps(reply).encode())
        channel = self.wechat(request=request)
        with mock.patch.object(channel, "receive", side_effect=[{"accepted": False}, RuntimeError("processing failed")]):
            with self.assertRaises(RuntimeError):
                channel.poll_once()
        self.assertEqual(channel._cursor, "before-batch")
        self.assertEqual(self.broker.load_wechat_cursor("wx-bot"), "before-batch")

    def test_wechat_cursor_write_failure_stops_listener_immediately_without_advancing(self):
        calls = []
        def request(*args):
            calls.append(args)
            return (200, {}, b'{"ret":0}') if args[1].endswith("/notifystart") else (200, {}, b'{"msgs":[],"get_updates_buf":"after"}')
        channel = self.wechat(request=request)
        self.broker.close()  # Real SQLite write failure, not a mocked success path.
        with self.assertRaisesRegex(CursorStorageError, "listener stopped without advancing"):
            channel.listen(threading.Event())
        self.assertEqual(channel._cursor, "")
        self.assertEqual(sum(call[1].endswith("/getupdates") for call in calls), 1)

    def test_wechat_partial_batch_replay_deduplicates_without_persisting_context(self):
        challenge = self.issue(channel="wechat", chat_id="wx-user", allowed_sender_ids={"wx-user"})
        first = self.wx_message(challenge.approve_command)
        second = dict(self.wx_message("not an approval"), message_id=9999)
        reply = {"msgs": [first, second], "get_updates_buf": "completed-batch-cursor"}
        def request(*args):
            return (200, {}, b'{"ret":0}') if args[1].endswith("/notifystart") else (200, {}, json.dumps(reply).encode())
        channel = self.wechat(request=request)
        original = channel.receive
        def partial(message):
            if message["message_id"] == 9999:
                raise ChannelError("second item could not be processed")
            return original(message)
        with mock.patch.object(channel, "receive", side_effect=partial):
            with self.assertRaises(ChannelError):
                channel.poll_once()
        self.assertEqual(self.broker.load_wechat_cursor("wx-bot"), "")
        self.assertEqual(channel.poll_once(), 2)
        self.assertEqual(len(self.broker.drain()), 1)
        self.assertEqual(self.broker.load_wechat_cursor("wx-bot"), "completed-batch-cursor")
        raw = (self.root / "approvals.sqlite3").read_bytes()
        self.assertNotIn(b"synthetic-context-never-persist", raw)
        self.assertNotIn(b"synthetic-test-token", raw)

    def test_wechat_corrupt_stored_approval_json_aborts_batch_without_cursor_advance(self):
        challenge = self.issue(channel="wechat", chat_id="wx-user", allowed_sender_ids={"wx-user"})
        self.broker._db.execute("UPDATE challenges SET scope=? WHERE id=?", ("{corrupt-json", challenge.challenge_id))
        self.broker.save_wechat_cursor("wx-bot", "before-corrupt-approval")
        reply = {"msgs": [self.wx_message(challenge.approve_command)], "get_updates_buf": "must-not-commit"}
        def request(*args):
            return (200, {}, b'{"ret":0}') if args[1].endswith("/notifystart") else (200, {}, json.dumps(reply).encode())
        channel = self.wechat(request=request)
        with self.assertRaises(json.JSONDecodeError):
            channel.poll_once()
        self.assertEqual(self.broker.drain(), [])
        self.assertEqual(channel._cursor, "before-corrupt-approval")
        self.assertEqual(self.broker.load_wechat_cursor("wx-bot"), "before-corrupt-approval")
        self.assertEqual(self.broker._db.execute("SELECT status FROM challenges WHERE id=?", (challenge.challenge_id,)).fetchone()[0], "pending")

    def test_wechat_broker_internal_errors_are_not_caught_as_malformed_messages(self):
        challenge = self.issue(channel="wechat", chat_id="wx-user", allowed_sender_ids={"wx-user"})
        reply = {"msgs": [self.wx_message(challenge.approve_command)], "get_updates_buf": "must-not-commit"}
        def request(*args):
            return (200, {}, b'{"ret":0}') if args[1].endswith("/notifystart") else (200, {}, json.dumps(reply).encode())
        channel = self.wechat(request=request)
        for error in (ValueError("internal"), TypeError("internal"), KeyError("internal"), AttributeError("internal")):
            with self.subTest(error=type(error).__name__), mock.patch.object(self.broker, "accept", side_effect=error):
                with self.assertRaises(type(error)):
                    channel.poll_once()
            self.assertEqual(channel._cursor, "")
            self.assertEqual(self.broker.load_wechat_cursor("wx-bot"), "")

    def test_wechat_same_message_id_from_two_bots_queues_both_and_isolates_cursors(self):
        first = self.issue(channel="wechat", job_id="job-bot-a", chat_id="wx-user", allowed_sender_ids={"wx-user"})
        second = self.issue(channel="wechat", job_id="job-bot-b", chat_id="wx-user", allowed_sender_ids={"wx-user"})
        for bot, challenge, cursor in (("a@im.bot", first, "cursor-a"), ("b@im.bot", second, "cursor-b")):
            message = dict(self.wx_message(challenge.approve_command), message_id=42, to_user_id=bot)
            reply = {"msgs": [message], "get_updates_buf": cursor}
            def request(*args):
                return (200, {}, b'{"ret":0}') if args[1].endswith("/notifystart") else (200, {}, json.dumps(reply).encode())
            self.assertEqual(self.wechat(request=request, bot_id=bot).poll_once(), 1)
        queued = self.broker.drain()
        self.assertEqual({item["project_id"] for item in queued}, {"job-bot-a", "job-bot-b"})
        self.assertEqual({item["event_id"] for item in queued}, {hashlib.sha256(bot.encode()).hexdigest() + ":42" for bot in ("a@im.bot", "b@im.bot")})
        self.assertTrue(all(item["channel"] == "wechat" for item in queued))
        self.assertEqual(self.broker.load_wechat_cursor("a@im.bot"), "cursor-a")
        self.assertEqual(self.broker.load_wechat_cursor("b@im.bot"), "cursor-b")

    def test_wechat_bot_event_namespace_does_not_revive_legacy_consumed_nonce(self):
        challenge = self.issue(channel="wechat", chat_id="wx-user", allowed_sender_ids={"wx-user"})
        legacy = self.broker.accept(channel="wechat", event_id="42", sender_id="wx-user", chat_id="wx-user", command=challenge.approve_command)
        self.assertTrue(legacy["accepted"])
        self.broker.close()
        self.broker = ApprovalBroker(self.root / "approvals.sqlite3", clock=lambda: self.now)
        channel = self.wechat()
        replay = dict(self.wx_message(challenge.approve_command), message_id=42)
        self.assertFalse(channel.receive(replay)["accepted"])
        self.assertFalse(channel.receive(dict(replay, message_id=43))["accepted"])
        self.assertEqual(len(self.broker.drain()), 1)
        self.assertEqual(self.broker._db.execute("SELECT event_id FROM accepted_events WHERE channel='wechat'").fetchone()[0], "42")

    def test_wechat_outbound_schema_and_auth_follow_official_protocol(self):
        calls = []
        def request(*args):
            calls.append(args)
            return 200, {}, b'{"ret":0}'
        channel = self.wechat(request=request)
        channel._contexts["wx-user"] = "synthetic-context"
        channel._send_text("wx-user", "review command")
        method, url, headers, body, timeout = calls[0]
        self.assertEqual(url, "https://ilinkai.weixin.qq.com/ilink/bot/sendmessage")
        self.assertEqual(headers["AuthorizationType"], "ilink_bot_token")
        self.assertEqual(headers["iLink-App-Id"], "bot")
        payload = json.loads(body)
        self.assertEqual(payload["msg"]["message_type"], 2)
        self.assertEqual(payload["msg"]["context_token"], "synthetic-context")
        self.assertEqual(payload["msg"]["item_list"], [{"type": 1, "text_item": {"text": "review command"}}])

    def test_wechat_refuses_untrusted_cdn_and_does_not_forward_bot_token(self):
        if not self.wechat().capabilities.image_delivery:
            self.skipTest("optional cryptography not installed; no package installed by test")
        calls = []
        def evil(*args):
            calls.append(args)
            return 200, {}, b'{"upload_full_url":"https://attacker.example/upload"}'
        channel = self.wechat(request=evil)
        with self.assertRaises(ChannelError):
            channel._upload("wx-user", self.image, 1)
        self.assertEqual(len(calls), 1)
        def good(*args):
            calls.append(args)
            if args[1].endswith("/getuploadurl"):
                return 200, {}, b'{"upload_full_url":"https://novac2c.cdn.weixin.qq.com/c2c/upload?p=test"}'
            self.assertNotIn("Authorization", args[2])
            self.assertNotEqual(args[3], self.image.read_bytes())
            return 200, {"x-encrypted-param": "download-reference"}, b""
        channel = self.wechat(request=good)
        uploaded = channel._upload("wx-user", self.image, 1)
        self.assertEqual(uploaded["media"]["encrypt_type"], 1)
        self.assertEqual(len(base64.b64decode(uploaded["media"]["aes_key"])), 32)

    def test_credit_currency_preserved_and_not_converted_to_fiat(self):
        challenge = self.issue(budget={"amount": "123", "currency": "DREAMINA_CREDITS"})
        self.accept(challenge.approve_command)
        self.assertEqual(self.broker.drain()[0]["budget"], {"amount": "123", "currency": "DREAMINA_CREDITS"})

    def test_notification_event_id_is_deduplicated_and_unknown_not_retried(self):
        event = {"event_id": "notification-1", "project_id": "job-1", "revision": 2,
                 "type": "storyboard_review", "stage": "storyboard", "artifacts": [str(self.image)],
                 "approval_scope": self.scope, "budget": self.budget, "binding_hash": "a" * 64}
        self.assertTrue(self.feishu.deliver(event)["delivered"])
        count = len(self.transport.sent)
        self.assertTrue(self.feishu.deliver(event)["duplicate"])
        self.assertEqual(len(self.transport.sent), count)
        event["event_id"] = "notification-2"
        with mock.patch.object(self.feishu, "_send_text", side_effect=ChannelError("unknown review send")):
            with self.assertRaises(ChannelError):
                self.feishu.deliver(event)
        count = len(self.transport.sent)
        self.assertEqual(self.feishu.deliver(event)["status"], "unknown_delivery")
        self.assertEqual(len(self.transport.sent), count)
        self.assertTrue(self.broker.allow_notification_retry("feishu", "notification-2"))
        self.assertTrue(self.feishu.deliver(event)["delivered"])
        self.assertFalse(self.broker.allow_notification_retry("feishu", "notification-1"))

    def test_final_review_sends_video_file_with_no_new_spending_scope(self):
        movie = self.root / "final.mp4"
        movie.write_bytes(b"synthetic movie")
        result = self.feishu.deliver({"event_id": "final-event", "project_id": "job-1", "revision": 2,
            "type": "final_review", "stage": "final", "artifacts": [str(movie)], "binding_hash": "a" * 64,
            "approval_scope": {"stages": [], "allow_uploads": False}, "budget": {"amount": "0", "currency": "CNY"}})
        self.assertTrue(result["review_required"])
        self.assertEqual(self.transport.sent[0][0], "upload_file")
        self.assertEqual(self.transport.sent[1][1], "file")

    def test_bridge_consumes_only_on_owner_thread_and_passes_all_bindings(self):
        challenge = self.issue(binding_hash="a" * 64, shot_ids=["S01"])
        self.accept(challenge.approve_command)
        engine = mock.Mock()
        bridge = WorkflowBridge(engine, self.feishu, ["job-1"], clock=lambda: self.now)
        self.assertTrue(bridge.run_once()["decisions"][0]["applied"])
        engine.approve.assert_called_once()
        args = engine.approve.call_args.kwargs
        self.assertEqual(args["expected_revision"], 2)
        self.assertEqual(args["expected_binding_hash"], "a" * 64)
        self.assertEqual(args["shot_ids"], ["S01"])
        self.assertEqual(args["live_scope"], self.scope)
        self.assertEqual(args["budget"], self.budget)
        engine.tick.assert_not_called()
        errors = []
        def wrong_thread():
            try:
                bridge.run_once()
            except ChannelError:
                errors.append(True)
        thread = threading.Thread(target=wrong_thread)
        thread.start()
        thread.join()
        self.assertEqual(errors, [True])

    def test_bridge_rejects_out_of_scope_project_and_core_stale_hash(self):
        challenge = self.issue(binding_hash="a" * 64)
        self.accept(challenge.approve_command)
        engine = mock.Mock()
        bridge = WorkflowBridge(engine, self.feishu, ["different-project"], clock=lambda: self.now)
        self.assertEqual(bridge.run_once()["decisions"], [])
        self.assertEqual(self.broker._db.execute("SELECT state FROM approval_queue").fetchone()[0], "queued")
        engine.approve.assert_not_called()
        challenge = self.issue(binding_hash="b" * 64)
        self.accept(challenge.approve_command, event_id="new-event")
        engine.approve.side_effect = ValueError("stale content hash")
        bridge = WorkflowBridge(engine, self.feishu, ["job-1"], clock=lambda: self.now)
        self.assertFalse(bridge.run_once()["decisions"][0]["applied"])
        self.assertEqual(self.broker.drain(), [])

    def live_review_fixture(self):
        from hc_workflow.engine import Engine
        identity = {"provider": "fixture", "account": "own-account", "live": True, "verified": True}
        provider = SimpleNamespace(identity=lambda: dict(identity))
        engine = Engine(self.root / "review-engine.sqlite3", {"fixture": provider},
                        artifact_dir=self.root / "artifacts", channel=self.feishu, clock=lambda: self.now)
        self.addCleanup(engine.close)
        pid = engine.init_project("offline paid review", mode="live")["project_id"]
        engine.set_plan(pid, {"providers": {"image": "fixture", "video": "fixture"},
            "requested_live_scopes": {"image": {"stages": ["image"], "allow_uploads": True}},
            "budget": {"amount": "3", "currency": "DREAMINA_CREDITS"},
            "shots": [{"id": "S01", "duration_seconds": 1, "image_prompt": "test", "video_prompt": "hold"}]})
        original_send = self.feishu.send_review
        sent = []
        def send_review(**kwargs):
            sent.append(original_send(**kwargs))
            return sent[-1]
        patch = mock.patch.object(self.feishu, "send_review", side_effect=send_review)
        patch.start()
        self.addCleanup(patch.stop)
        engine.tick(pid)
        return engine, pid, identity, sent

    def test_expired_engine_review_renews_once_with_original_scope_and_cap(self):
        engine, pid, identity, sent = self.live_review_fixture()
        original = sent[0]
        self.assertEqual(original.expires_at, self.now + 3600)
        self.now += 901
        engine.tick(pid)
        self.assertEqual(sent, [original])
        with engine._tx() as db:
            db.execute("INSERT INTO budgets VALUES (?,?,?,?)", (pid, "image", "99", "DREAMINA_CREDITS"))
        self.now = original.expires_at
        engine.tick(pid)
        engine.tick(pid)
        self.assertEqual(len(sent), 2)
        fresh = sent[-1]
        self.assertNotEqual(original.challenge_id, fresh.challenge_id)
        self.assertEqual((fresh.scope, fresh.budget, fresh.binding_hash),
                         (original.scope, original.budget, original.binding_hash))
        self.assertFalse(self.accept(original.approve_command)["accepted"])
        self.assertEqual(engine.db.execute("SELECT count(*) FROM approvals").fetchone()[0], 0)
        identity["account"] = "different-account"
        self.now = fresh.expires_at
        engine.tick(pid)
        self.assertEqual(len(sent), 2)

    def test_bridge_retries_temporary_identity_with_original_expiry_and_budget(self):
        engine, pid, identity, sent = self.live_review_fixture()
        challenge = sent[0]
        self.assertTrue(self.accept(challenge.approve_command)["accepted"])
        account = dict(identity)
        identity.update(account=None, verified=False, status="unknown")
        bridge = WorkflowBridge(engine, self.feishu, [pid], clock=lambda: self.now)
        self.assertEqual(bridge.run_once()["decisions"][0]["outcome"], "deferred_account_verification")
        self.assertEqual(engine.db.execute("SELECT count(*) FROM approval_decisions").fetchone()[0], 0)
        identity.clear()
        identity.update(account)
        self.assertEqual(bridge.run_once()["decisions"], [])
        self.now += 5
        restarted = WorkflowBridge(engine, self.feishu, [pid], clock=lambda: self.now)
        self.assertEqual(restarted.run_once()["decisions"][0]["outcome"], "applied")
        row = engine.db.execute("SELECT expires,amount,currency,scope FROM approvals").fetchone()
        self.assertEqual((row["expires"], row["amount"], row["currency"]),
                         (challenge.expires_at, "3", "DREAMINA_CREDITS"))
        self.assertEqual(json.loads(row["scope"]), challenge.scope)
        self.assertEqual(restarted.run_once()["decisions"], [])

    def test_review_cannot_restore_a_lowered_budget(self):
        engine, pid, _, sent = self.live_review_fixture()
        challenge = sent[0]
        with engine._tx() as db:
            db.execute("INSERT INTO budgets VALUES (?,?,?,?)", (pid, "image", "1", "DREAMINA_CREDITS"))
        self.assertTrue(self.accept(challenge.approve_command)["accepted"])
        bridge = WorkflowBridge(engine, self.feishu, [pid], clock=lambda: self.now)
        self.assertEqual(bridge.run_once()["decisions"][0]["outcome"], "rejected")
        self.assertEqual(engine.db.execute("SELECT count(*) FROM approvals").fetchone()[0], 0)
        self.now = challenge.expires_at
        engine.tick(pid)
        self.assertEqual(sent, [challenge])

    def test_expired_rejected_plan_review_does_not_reappear(self):
        engine, pid, _, sent = self.live_review_fixture()
        challenge = sent[0]
        self.assertTrue(self.accept(challenge.reject_command)["accepted"])
        bridge = WorkflowBridge(engine, self.feishu, [pid], clock=lambda: self.now)
        self.assertTrue(bridge.run_once()["decisions"][0]["applied"])
        self.assertNotEqual(engine.status(pid)["revision"], challenge.revision)
        self.now = challenge.expires_at
        engine.tick(pid)
        self.assertEqual(sent, [challenge])

    def test_deferred_decision_is_never_applied_after_original_expiry(self):
        from hc_workflow.engine import ApprovalBindingUnavailable
        challenge = self.issue(binding_hash="a" * 64)
        self.assertTrue(self.accept(challenge.reject_command)["accepted"])
        engine = mock.Mock()
        engine.reject.side_effect = ApprovalBindingUnavailable("offline fixture")
        bridge = WorkflowBridge(engine, self.feishu, ["job-1"], clock=lambda: self.now)
        self.assertEqual(bridge.run_once()["decisions"][0]["outcome"], "deferred_account_verification")
        self.now = challenge.expires_at
        engine.reject.side_effect = None
        self.assertEqual(bridge.run_once()["decisions"], [])
        self.assertEqual(engine.reject.call_count, 1)

    def test_old_queue_migrates_and_can_defer(self):
        path = self.root / "old-approvals.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE approval_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, challenge_id TEXT NOT NULL, "
                       "payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued')")
            db.execute("INSERT INTO approval_queue VALUES (1,'legacy','{}','claimed')")
            db.commit()
        with closing(ApprovalBroker(path, clock=lambda: self.now)) as broker:
            broker.defer(1)
            row = broker._db.execute("SELECT state,attempts,retry_at FROM approval_queue").fetchone()
            self.assertEqual(tuple(row), ("queued", 1, self.now + 5))

    def test_bridge_pauses_if_listener_returns_unexpectedly(self):
        channel = SimpleNamespace(broker=self.broker, listen=lambda stop_event: None)
        bridge = WorkflowBridge(mock.Mock(), channel, ["job-1"], clock=lambda: self.now)
        with self.assertRaisesRegex(ChannelError, "listener stopped"):
            bridge.run(interval=0.5)
        self.assertTrue(bridge.stop_event.is_set())

    def test_bridge_interrupt_preserves_claim_and_releases_lock_for_recovery(self):
        challenge = self.issue(binding_hash="a" * 64)
        self.accept(challenge.approve_command)
        engine = mock.Mock()
        engine.approve.side_effect = KeyboardInterrupt
        bridge = WorkflowBridge(engine, self.feishu, ["job-1"], clock=lambda: self.now)
        with self.assertRaises(KeyboardInterrupt):
            bridge.run_once()
        self.assertEqual(self.broker._db.execute("SELECT state FROM approval_queue").fetchone()[0], "claimed")
        engine.approve.side_effect = None
        restarted = WorkflowBridge(engine, self.feishu, ["job-1"], clock=lambda: self.now)
        self.assertTrue(restarted.run_once()["decisions"][0]["applied"])
        self.assertEqual(self.broker._db.execute("SELECT state FROM approval_queue").fetchone()[0], "applied")

    def test_bridge_recovery_only_replays_scoped_unexpired_accepted_claims(self):
        entries = {}
        for job in ("job-1", "job-2", "expired", "cancelled", "applied", "rejected"):
            challenge = self.issue(job_id=job, binding_hash="a" * 64)
            self.assertTrue(self.accept(challenge.approve_command, event_id=job)["accepted"])
            entries[job] = self.broker.drain(project_ids=[job])[0]["queue_id"]
        self.broker._db.execute("UPDATE challenges SET expires=999 WHERE job_id='expired'")
        self.broker._db.execute("UPDATE challenges SET status='cancelled' WHERE job_id='cancelled'")
        self.broker.acknowledge(entries["applied"], applied=True)
        self.broker.acknowledge(entries["rejected"], applied=False)
        engine = mock.Mock()
        bridge = WorkflowBridge(engine, self.feishu, ["job-1", "expired", "cancelled", "applied", "rejected"], clock=lambda: self.now)
        self.assertEqual([item["project_id"] for item in bridge.run_once()["decisions"]], ["job-1"])
        rows = self.broker._db.execute("SELECT c.job_id,q.state FROM approval_queue q JOIN challenges c ON c.id=q.challenge_id")
        self.assertEqual(dict(rows), {"job-1": "applied", "job-2": "claimed", "expired": "expired",
                                     "cancelled": "claimed", "applied": "applied", "rejected": "rejected"})
        engine.approve.assert_called_once()
        other = WorkflowBridge(engine, self.feishu, ["job-2"], clock=lambda: self.now)
        self.assertTrue(other.run_once()["decisions"][0]["applied"])
        self.assertEqual(self.broker.drain(project_ids=[]), [])

    def test_bridge_rejects_symlink_lock_without_touching_target(self):
        target = self.root / "not-a-lock"
        target.write_text("must remain unchanged")
        lock = self.root / "approvals.sqlite3.coordinator.lock"
        lock.symlink_to(target)
        bridge = WorkflowBridge(mock.Mock(), self.feishu, ["job-1"], clock=lambda: self.now)
        with self.assertRaises(ConfigurationError):
            bridge.run_once()
        self.assertEqual(target.read_text(), "must remain unchanged")

    def test_bridge_separate_process_excludes_second_coordinator(self):
        script = '''import sys
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from hc_workflow.channels import ApprovalBroker
from workflow_bridge import WorkflowBridge
b = ApprovalBroker(sys.argv[2], clock=lambda: 1000)
w = WorkflowBridge(None, SimpleNamespace(broker=b), ['job-1'], clock=lambda: 1000)
with w._coordinator_guard():
 print('locked', flush=True)
 sys.stdin.readline()
b.close()
'''
        process = subprocess.Popen([sys.executable, "-B", "-c", script, str(Path(__file__).resolve().parents[1] / "scripts"),
                                    str(self.broker.path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([process.stdout], [], [], 5)[0], "lock holder did not start")
            self.assertEqual(process.stdout.readline().strip(), "locked")
            engine = mock.Mock()
            bridge = WorkflowBridge(engine, self.feishu, ["job-1"], clock=lambda: self.now)
            with self.assertRaises(CoordinatorBusy):
                bridge.run_once()
            engine.approve.assert_not_called()
            process.stdin.write("release\n")
            process.stdin.flush()
            self.assertEqual(process.wait(timeout=5), 0)
            self.assertEqual(bridge.run_once()["decisions"], [])
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

    def test_bridge_run_holds_lock_across_listener_and_nested_run_once(self):
        channel = SimpleNamespace(broker=self.broker, listen=lambda stop: stop.wait(2))
        bridge = WorkflowBridge(mock.Mock(), channel, ["job-1"], clock=lambda: self.now)
        other = WorkflowBridge(mock.Mock(), channel, ["job-1"], clock=lambda: self.now)
        original = bridge._run_once_locked
        def consume():
            with self.assertRaises(CoordinatorBusy):
                other.run_once()
            result = original()
            bridge.stop_event.set()
            return result
        with mock.patch.object(bridge, "_run_once_locked", side_effect=consume):
            bridge.run(interval=0.5)
        self.assertEqual(other.run_once()["decisions"], [])

    def test_bridge_process_crashes_before_apply_and_after_apply_before_ack(self):
        from hc_workflow.engine import Engine
        script = '''import json, os, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from hc_workflow.channels import ApprovalBroker
from hc_workflow.engine import Engine
from workflow_bridge import WorkflowBridge
root = Path(sys.argv[2])
clock = lambda: 1121 if sys.argv[3] == 'reconcile' else 1001
b = ApprovalBroker(root / 'approvals.sqlite3', clock=clock)
e = Engine(root / 'jobs.sqlite3', clock=clock, artifact_dir=root / 'assets')
w = WorkflowBridge(e, SimpleNamespace(broker=b), ['crash-job'], clock=clock)
if sys.argv[3] == 'before':
 e.approve = lambda *a, **k: os._exit(71)
elif sys.argv[3] == 'after':
 b.acknowledge = lambda *a, **k: os._exit(72)
result = w.run_once()
if sys.argv[3] == 'resume':
 for _ in range(20):
  state = e.tick('crash-job')
  if state['status'] == 'storyboard_review': break
 state = e.status('crash-job')
 result.update(status=state['status'], budgets=state['budgets'],
               operations=[op['operation_id'] for op in state['operations']])
print(json.dumps(result))
b.close()
e.close()
'''
        cases = (("before", 71, "resume"), ("after", 72, "resume"), ("after", 72, "reconcile"))
        for phase, exit_code, recovery in cases:
            with self.subTest(phase=phase, recovery=recovery):
                root = self.root / f"{phase}-{recovery}"
                root.mkdir()
                engine = Engine(root / "jobs.sqlite3", clock=lambda: 1000, artifact_dir=root / "assets")
                engine.init_project({"audience": "offline test"}, project_id="crash-job")
                engine.set_plan("crash-job", {"schema_version": 1, "project_name": "crash proof",
                    "providers": {"image": "mock", "video": "mock"}, "shots": [{"id": "S01", "duration_seconds": 3,
                    "image_prompt": "offline fixture", "video_prompt": "offline fixture"}]})
                binding = engine.status("crash-job")["bindings"]["plan"]
                identity = binding["providers"]["image"]
                scope = {"stages": [], "allow_uploads": False, "provider": identity["provider"], "account": identity["account"],
                         **{key: binding[key] for key in ("revision", "plan_hash", "asset_hash")}}
                broker = ApprovalBroker(root / "approvals.sqlite3", clock=lambda: 1000)
                challenge = broker.issue(channel="feishu", job_id="crash-job", revision=binding["revision"], stage="plan",
                    chat_id="chat-1", allowed_sender_ids={"user-1"}, live_scope=scope,
                    budget={"amount": "0", "currency": "CNY"}, binding_hash=binding["binding_hash"], ttl_seconds=120)
                self.assertTrue(broker.accept(channel="feishu", event_id="crash-event", sender_id="user-1",
                    chat_id="chat-1", command=challenge.approve_command)["accepted"])
                broker.close()
                engine.close()
                command = [sys.executable, "-B", "-c", script, str(Path(__file__).resolve().parents[1] / "scripts"), str(root)]
                crashed = subprocess.run([*command, phase], capture_output=True, text=True, timeout=10)
                self.assertEqual(crashed.returncode, exit_code, crashed.stderr)
                with closing(sqlite3.connect(root / "approvals.sqlite3")) as db:
                    self.assertEqual(db.execute("SELECT state FROM approval_queue").fetchone()[0], "claimed")
                resumed = subprocess.run([*command, recovery], capture_output=True, text=True, timeout=10)
                self.assertEqual(resumed.returncode, 0, resumed.stderr)
                proof = json.loads(resumed.stdout)
                if recovery == "reconcile":
                    self.assertEqual(proof["decisions"], [])
                else:
                    self.assertTrue(proof["decisions"][0]["applied"])
                    self.assertEqual(proof["status"], "storyboard_review")
                    self.assertEqual(len(proof["operations"]), 1)
                    self.assertEqual(proof["budgets"], [{"stage": "image", "amount": "0", "currency": "CNY", "reserved_or_spent": "0"}])
                    repeated = subprocess.run([*command, "resume"], capture_output=True, text=True, timeout=10)
                    self.assertEqual(repeated.returncode, 0, repeated.stderr)
                    repeat = json.loads(repeated.stdout)
                    self.assertEqual(repeat["decisions"], [])
                    self.assertEqual(repeat["operations"], proof["operations"])
                with closing(sqlite3.connect(root / "approvals.sqlite3")) as db:
                    self.assertEqual(db.execute("SELECT state FROM approval_queue").fetchone()[0], "applied")
                with closing(sqlite3.connect(root / "jobs.sqlite3")) as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0], 1)
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE type='approved'").fetchone()[0], 1)

    def test_bridge_reject_calls_core_with_revision_hash_and_selected_shots(self):
        challenge = self.issue(binding_hash="a" * 64, shot_ids=["S01"])
        self.accept(challenge.reject_command)
        engine = mock.Mock()
        bridge = WorkflowBridge(engine, self.feishu, ["job-1"], clock=lambda: self.now)
        self.assertTrue(bridge.run_once()["decisions"][0]["applied"])
        engine.reject.assert_called_once()
        self.assertEqual(engine.reject.call_args.kwargs["expected_binding_hash"], "a" * 64)
        self.assertEqual(engine.reject.call_args.kwargs["shot_ids"], ["S01"])

    def test_doctor_is_offline_and_never_initializes_channel(self):
        with mock.patch("workflow_bridge.create_channel") as create, mock.patch("builtins.print"):
            self.assertEqual(bridge_main(["--channel", "feishu", "--doctor"]), 0)
            self.assertEqual(bridge_main(["--channel", "wechat"]), 0)
        create.assert_not_called()

    def test_non_ascii_scope_token_and_malformed_feishu_do_not_crash(self):
        challenge = self.issue()
        command = challenge.approve_command.replace("scope=", "scope=é")
        self.assertFalse(self.accept(command)["accepted"])
        self.assertFalse(self.feishu.receive({"header": None})["accepted"])

    def test_partial_setup_failure_does_not_mark_notification_unknown(self):
        event = {"event_id": "setup-failure", "type": "update", "artifacts": [], "message": "state"}
        with mock.patch.object(self.feishu, "_prepare_recipient", side_effect=ConfigurationError("setup missing")):
            with self.assertRaises(ConfigurationError):
                self.feishu.deliver(event)
        self.assertEqual(self.broker._db.execute("SELECT count(*) FROM notifications").fetchone()[0], 0)
        self.assertTrue(self.feishu.deliver(event)["delivered"])

    def test_wechat_explicit_private_credentials_schema_permissions_and_host(self):
        path = self.root / "qr-credentials.json"
        data = {"schema_version": 1, "provider": "wechat", "bot_token": "synthetic-token",
                "ilink_bot_id": "wx-bot", "api_base": "https://ilinkai.weixin.qq.com", "ilink_user_id": "wx-user", "created_at": 1}
        path.write_text(json.dumps(data))
        path.chmod(0o600)
        self.assertEqual(_read_wechat_credentials(path)["HC_WECHAT_BOT_TOKEN"], "synthetic-token")
        path.chmod(0o644)
        with self.assertRaises(ConfigurationError):
            _read_wechat_credentials(path)
        path.chmod(0o600)
        data["api_base"] = "https://attacker.example"
        path.write_text(json.dumps(data))
        with self.assertRaises(ConfigurationError):
            _read_wechat_credentials(path)

    def test_doctor_does_not_read_even_explicit_credential_path(self):
        with mock.patch("workflow_bridge._read_wechat_credentials") as read, mock.patch("builtins.print"):
            self.assertEqual(bridge_main(["--channel", "wechat", "--doctor", "--wechat-credentials", "/not-read/private.json"]), 0)
        read.assert_not_called()

    def test_bridge_explicit_config_reaches_selected_provider_and_is_not_read_offline(self):
        settings = {"project_id": "explicit-test-canvas", "profile": "explicit-test-profile",
                    "model": "explicit-test-model", "models": {"image": "explicit-image-model"}}
        config = self.root / "explicit-provider-config.json"
        config.write_text(json.dumps({"providers": {"dreamina-canvas": settings,
                                                    "minimax-design": {"project_id": "not-selected"}}}))
        database = self.root / "existing-workflow.sqlite3"
        database.write_bytes(b"mocked engine; not opened")
        with mock.patch("hc_workflow.providers.get_provider", return_value=mock.sentinel.provider) as get_provider, \
             mock.patch("hc_workflow.engine.Engine") as engine, \
             mock.patch("workflow_bridge.create_channel"), \
             mock.patch("workflow_bridge.WorkflowBridge") as bridge, mock.patch("builtins.print"):
            result = bridge_main(["--channel", "feishu", "--run", "--engine-db", str(database),
                "--approval-db", str(self.root / "separate-channel.sqlite3"), "--artifact-root", str(self.root),
                "--project-id", "job-1", "--generation-provider", "dreamina-canvas", "--config", str(config)])
        self.assertEqual(result, 0)
        get_provider.assert_called_once_with("dreamina-canvas", settings)
        self.assertEqual(engine.call_args.kwargs["providers"], {"dreamina-canvas": mock.sentinel.provider})
        bridge.return_value.run.assert_called_once()
        with mock.patch("workflow_bridge._read_provider_config") as read, mock.patch("builtins.print"):
            self.assertEqual(bridge_main(["--channel", "feishu", "--doctor", "--config", "/not-read/config.json"]), 0)
            self.assertEqual(bridge_main(["--channel", "feishu", "--config", "/not-read/config.json"]), 0)
        read.assert_not_called()

    def local_processing_scope(self):
        return {"stages": [], "allow_uploads": False, "revision": 2,
                "plan_hash": "a" * 64, "asset_hash": "b" * 64,
                "composition": {"mode": "normalize_cfr", "fps": 24, "aspect_ratio": "16:9",
                                "shots": [{"shot_id": "S01", "sha256": "c" * 64, "duration_seconds": 4}]}}

    def test_local_processing_review_displays_exact_action_and_queues_no_generation_scope(self):
        scope = self.local_processing_scope()
        challenge = self.feishu.send_review(job_id="job-1", revision=2, stage="composition",
            image_paths=[], live_scope=scope, budget={"amount": "0", "currency": "CNY"},
            binding_hash="d" * 64, shot_ids=["S01"])
        self.assertFalse(any(item[0] in ("upload_image", "upload_file") for item in self.transport.sent))
        text = challenge.message()
        for required in ("本地规格处理审批", "24帧/秒", "S01：4秒", "H.264 CRF18/yuv420p",
                         "复制或丢弃帧", "2个目标帧", "一次AAC编码", "保留原片", "不上传", "终片验收"):
            self.assertIn(required, text)
        self.assertNotIn("仅记录本次审核结论", text)
        self.assertTrue(self.accept(challenge.approve_command)["accepted"])
        queued = self.broker.drain()[0]
        self.assertEqual(queued["stage"], "composition")
        self.assertEqual(queued["live_scope"], scope)
        self.assertEqual(queued["budget"]["amount"], "0")
        self.assertEqual(queued["binding_hash"], "d" * 64)

    def test_local_processing_scope_rejects_spending_uploads_unknown_policy_and_missing_details(self):
        valid = self.local_processing_scope()
        bad = []
        for key, value in (("stages", ["video"]), ("allow_uploads", True), ("provider", "fixture")):
            changed = json.loads(json.dumps(valid))
            changed[key] = value
            bad.append(changed)
        changed = json.loads(json.dumps(valid))
        changed["composition"]["authorized"] = True
        bad.append(changed)
        changed = json.loads(json.dumps(valid))
        changed["composition"]["shots"][0]["duration_seconds"] = True
        bad.append(changed)
        bad.append({k: v for k, v in valid.items() if k != "composition"})
        for scope in bad:
            with self.subTest(scope=scope), self.assertRaises(ConfigurationError):
                self.issue(stage="composition", live_scope=scope, budget={"amount": "0", "currency": "CNY"})
        with self.assertRaises(ConfigurationError):
            self.issue(stage="composition", live_scope=valid, budget={"amount": "1", "currency": "CNY"})
        with self.assertRaises(ConfigurationError):
            self.issue(stage="storyboard", live_scope=valid, budget={"amount": "0", "currency": "CNY"})

    def test_local_processing_old_command_cannot_authorize_new_source_binding(self):
        old = self.issue(stage="composition", live_scope=self.local_processing_scope(),
                         budget={"amount": "0", "currency": "CNY"}, binding_hash="d" * 64, shot_ids=["S01"])
        changed = self.local_processing_scope()
        changed["composition"]["shots"][0]["sha256"] = "e" * 64
        new = self.issue(stage="composition", live_scope=changed,
                         budget={"amount": "0", "currency": "CNY"}, binding_hash="f" * 64, shot_ids=["S01"])
        self.assertFalse(self.accept(old.approve_command)["accepted"])
        self.assertTrue(self.accept(new.approve_command, event_id="new-source-decision")["accepted"])
        self.assertEqual(self.broker.drain()[0]["live_scope"], changed)


class ShortReplyTests(unittest.TestCase):
    setUp = ChannelTests.setUp
    tearDown = ChannelTests.tearDown
    issue = ChannelTests.issue
    event = ChannelTests.event
    wechat = ChannelTests.wechat
    wx_message = ChannelTests.wx_message

    def send_review(self, **overrides):
        args = dict(job_id="short-job", revision=2, image_paths=[self.image],
                    live_scope=self.scope, budget=self.budget, shot_ids=["S01"], binding_hash="a" * 64)
        args.update(overrides)
        return self.feishu.send_review(**args)

    def reply(self, text, *, event_id=None, **fields):
        event = self.event(text, create_time=str(int(self.now * 1000)), **fields)
        event["header"]["event_id"] = event_id or "event-" + str(len(self.transport.sent))
        return self.feishu.receive(event)

    def test_single_reply_preserves_paid_scope_budget_and_assets(self):
        challenge = self.send_review()
        self.assertTrue(self.reply("同意")["accepted"])
        row, = self.broker.drain()
        self.assertEqual(row["challenge_id"], challenge.challenge_id)
        self.assertEqual(row["live_scope"], self.scope)
        self.assertEqual(row["budget"], self.budget)
        self.assertEqual(row["binding_hash"], "a" * 64)
        self.assertEqual(row["shot_ids"], ["S01"])
        self.assertIn("等待工作流核验", self.transport.sent[-1][2]["text"])
        self.assertIn("分镜图审核", self.transport.sent[-1][2]["text"])
        self.assertIn("镜号：S01", self.transport.sent[-1][2]["text"])

    def test_reject_is_a_bound_decision_not_a_generation_request(self):
        self.send_review()
        self.assertTrue(self.reply("拒绝")["accepted"])
        self.assertEqual(self.broker.drain()[0]["decision"], "reject")

    def test_zero_cost_content_review_keeps_empty_generation_scope(self):
        self.send_review(stage="final", image_paths=[], live_scope={"stages": [], "allow_uploads": False},
                         budget={"amount": "0", "currency": "DREAMINA_CREDITS"})
        self.assertTrue(self.reply("同意")["accepted"])
        row, = self.broker.drain()
        self.assertEqual(row["live_scope"], {"stages": [], "allow_uploads": False})
        self.assertEqual(row["budget"], {"amount": "0", "currency": "DREAMINA_CREDITS"})

    def test_legacy_rows_do_not_enable_plain_reply_but_keep_nonce_compatibility(self):
        challenge = self.issue()
        self.assertFalse(self.reply("同意", event_id="plain-old")["accepted"])
        self.assertEqual(self.broker.drain(), [])
        self.assertTrue(self.reply(challenge.approve_command, event_id="nonce-old")["accepted"])

    def test_failed_review_send_does_not_enable_short_approval(self):
        with mock.patch.object(self.feishu, "_send_text", side_effect=ChannelError("unknown send")):
            with self.assertRaises(ChannelError):
                self.send_review()
        self.assertFalse(self.reply("同意")["accepted"])
        self.assertEqual(self.broker.drain(), [])
        self.assertEqual(self.broker._db.execute("SELECT count(*) FROM short_reviews").fetchone()[0], 0)

    def test_ack_api_failure_cannot_undo_or_repeat_received_approval(self):
        self.send_review()
        with mock.patch.object(self.feishu, "_send_text", side_effect=RuntimeError("secret must not log")):
            with self.assertLogs("hc_workflow.channels", level="WARNING") as logs:
                result = self.reply("同意", event_id="one-decision")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["reply_delivered"])
        self.assertNotIn("secret", "\n".join(logs.output))
        self.assertFalse(self.reply("同意", event_id="one-decision")["accepted"])
        self.assertFalse(self.reply("同意", event_id="physical-repeat")["accepted"])
        self.assertEqual(len(self.broker.drain()), 1)

    def test_menu_choice_is_not_approval_and_selected_scope_is_represented(self):
        first = self.send_review(job_id="first-job")
        second = self.send_review(job_id="second-job", budget={"amount": "72", "currency": "DREAMINA_CREDITS"})
        menu = self.reply("同意", event_id="open-menu")
        self.assertEqual(menu["reason"], "selection_required")
        self.assertIn("分镜图审核", menu["reply"])
        self.assertIn("72 即梦积分", menu["reply"])
        self.assertIn("3.50 人民币", menu["reply"])
        self.assertNotIn("｜storyboard｜", menu["reply"])
        self.assertEqual(self.broker.drain(), [])
        context = self.broker._short_context(("feishu", self.feishu._instance(), "chat-1", "user-1"))
        snapshot = json.loads(context["snapshot"])
        choice = snapshot.index(second.challenge_id) + 1
        selected = self.reply(str(choice), event_id="choose-second")
        self.assertEqual(selected["reason"], "confirmation_required")
        self.assertIn("72 DREAMINA_CREDITS", selected["reply"])
        self.assertIn("own-account", selected["reply"])
        self.assertEqual(self.broker.drain(), [])
        self.assertTrue(self.reply("拒绝", event_id="reject-second")["accepted"])
        queued, = self.broker.drain()
        self.assertEqual(queued["challenge_id"], second.challenge_id)
        self.assertEqual(queued["budget"]["amount"], "72")
        # A new event carrying the same text must not approve the remaining item.
        self.assertFalse(self.reply("同意", event_id="repeat-for-other")["accepted"])
        self.assertEqual(self.broker.drain(), [])
        self.assertEqual(self.broker._db.execute("SELECT status FROM challenges WHERE id=?", (first.challenge_id,)).fetchone()[0], "pending")

    def test_spent_reply_does_not_roll_forward_into_next_stage(self):
        self.send_review(job_id="first")
        self.assertTrue(self.reply("同意", event_id="first-done")["accepted"])
        self.send_review(job_id="next")
        self.assertEqual(self.reply("同意", event_id="repeated-text")["reason"], "selection_required")
        self.assertEqual(self.reply("同意", event_id="repeated-again")["reason"], "selection_required")
        self.assertEqual(len(self.broker.drain()), 1)

    def test_revision_change_requires_selection_and_old_event_is_not_fresh(self):
        old = self.send_review()
        self.now += 10
        replacement = self.send_review(revision=3, live_scope=dict(self.scope, revision=3))
        old_event = self.event("同意", create_time="1000000")
        old_event["header"]["event_id"] = "late-old-reply"
        self.assertEqual(self.feishu.receive(old_event)["reason"], "stale_or_unverifiable_message")
        self.assertEqual(self.reply("同意", event_id="review-updated")["reason"], "selection_required")
        self.reply("1", event_id="select-updated")
        self.assertTrue(self.reply("同意", event_id="approve-updated")["accepted"])
        row, = self.broker.drain()
        self.assertEqual(row["challenge_id"], replacement.challenge_id)
        self.assertNotEqual(row["challenge_id"], old.challenge_id)

    def test_old_menu_event_replay_cannot_select_new_snapshot(self):
        self.send_review(job_id="first")
        self.send_review(job_id="second")
        self.reply("审核", event_id="menu-one")
        self.assertEqual(self.reply("1", event_id="old-selection")["reason"], "confirmation_required")
        self.send_review(job_id="third")
        self.reply("审核", event_id="menu-two")
        self.assertEqual(self.reply("1", event_id="old-selection")["reason"], "duplicate_event")
        self.assertEqual(self.reply("同意", event_id="unselected-new-menu")["reason"], "selection_required")
        self.assertEqual(self.broker.drain(), [])

    def test_menu_changed_between_select_and_send_is_not_activated(self):
        self.send_review(job_id="first")
        self.send_review(job_id="second")
        key = ("feishu", self.feishu._instance(), "chat-1", "user-1")
        menu = self.broker.accept_text(channel="feishu", instance=key[1], event_id="menu", sender_id=key[3],
                                       chat_id=key[2], text="审核", created_at=self.now)
        self.send_review(job_id="third")
        with self.assertRaises(ConfigurationError):
            self.broker.confirm_text_delivery(menu["presentation"], message_id="old-menu")
        self.assertEqual(self.broker.drain(), [])

    def test_failed_menu_delivery_requires_explicit_reopen_before_choice(self):
        self.send_review(job_id="first")
        self.send_review(job_id="second")
        with mock.patch.object(self.feishu, "_send_text", side_effect=ChannelError("unknown menu send")):
            with self.assertLogs("hc_workflow.channels", level="WARNING"):
                menu = self.reply("同意", event_id="missing-menu")
        self.assertFalse(menu["reply_delivered"])
        self.assertEqual(self.reply("1", event_id="no-visible-menu")["reason"], "presentation_not_confirmed")
        self.assertEqual(self.reply("审核", event_id="reopen-menu")["reason"], "selection_required")
        self.assertEqual(self.reply("1", event_id="visible-choice")["reason"], "confirmation_required")
        self.assertEqual(self.broker.drain(), [])

    def test_expiry_never_extends_from_receipt_or_reply(self):
        self.send_review(expires_at=self.now + 1)
        self.now += 2
        self.assertFalse(self.reply("同意")["accepted"])
        self.assertEqual(self.broker.drain(), [])

    def test_no_time_and_unknown_reference_fail_closed(self):
        self.send_review()
        missing_time = self.event("同意")
        missing_time["header"]["event_id"] = "missing-time"
        self.assertEqual(self.feishu.receive(missing_time)["reason"], "stale_or_unverifiable_message")
        self.assertEqual(self.reply("同意", event_id="old-quote", parent_id="unrelated-old-message")["reason"], "reference_mismatch")
        self.assertEqual(self.broker.drain(), [])

    def test_verified_reference_can_identify_current_review_without_clock(self):
        self.send_review()
        message_id = self.broker._db.execute("SELECT message_id FROM short_reviews").fetchone()[0]
        event = self.event("同意", parent_id=message_id)
        self.assertTrue(self.feishu.receive(event)["accepted"])
        self.assertEqual(len(self.broker.drain()), 1)

    def test_two_character_parser_does_not_extract_approval_from_prose(self):
        self.send_review()
        for i, text in enumerate(("同 意", "同意\n额外", "同意\n拒绝", "我同意", "不同意", "同意；运行", "拒绝一下")):
            self.assertFalse(self.reply(text, event_id=f"not-exact-{i}")["accepted"])
        self.assertEqual(self.broker.drain(), [])

    def test_outer_whitespace_around_approval_is_ignored(self):
        self.send_review()
        self.assertTrue(self.reply(" \n\t同意 \r\n")["accepted"])
        self.assertEqual(self.broker.drain()[0]["decision"], "approve")

    def test_outer_whitespace_around_rejection_is_ignored(self):
        self.send_review()
        self.assertTrue(self.reply(" \t拒绝 \r\n")["accepted"])
        self.assertEqual(self.broker.drain()[0]["decision"], "reject")

    def test_unrecognized_owner_text_gives_clear_feedback_without_approval(self):
        self.send_review()
        result = self.reply("我觉得再考虑一下", event_id="ordinary-text")
        self.assertFalse(result["accepted"])
        self.assertTrue(result["reply_delivered"])
        self.assertIn("没有把它当作审核决定", result["reply"])
        self.assertEqual(self.broker.drain(), [])
        sent = len(self.transport.sent)
        self.assertEqual(self.reply("我觉得再考虑一下", event_id="ordinary-text")["reason"], "duplicate_event")
        self.assertEqual(len(self.transport.sent), sent)

    def test_unrecognized_text_without_review_remains_ordinary_chat(self):
        result = self.reply("你好", event_id="no-review-chat")
        self.assertFalse(result["accepted"])
        self.assertNotIn("reply", result)
        self.assertEqual(self.transport.sent, [])

    def test_first_new_style_review_with_unmapped_legacy_history_requires_choice(self):
        for old_state in ("pending", "accepted", "superseded", "cancelled", "expired", "disjoint"):
            with self.subTest(old_state=old_state), closing(ApprovalBroker(self.root / f"legacy-{old_state}.sqlite3", clock=lambda: self.now)) as broker:
                channel = FeishuChannel(self.config, broker, transport=Transport())
                old = broker.issue(channel="feishu", job_id="paid-new" if old_state == "disjoint" else "legacy-old",
                    revision=2, stage="storyboard", chat_id="chat-1", allowed_sender_ids={"user-1"},
                    live_scope=self.scope, budget=self.budget, binding_hash="a" * 64, shot_ids=["S01"])
                if old_state == "accepted":
                    broker.accept(channel="feishu", event_id="legacy-done", sender_id="user-1", chat_id="chat-1", command=old.approve_command)
                    broker.drain()
                elif old_state in {"superseded", "cancelled"}:
                    broker._db.execute("UPDATE challenges SET status=? WHERE id=?", (old_state, old.challenge_id))
                elif old_state == "expired":
                    broker._db.execute("UPDATE challenges SET expires=? WHERE id=?", (self.now - 1, old.challenge_id))
                new = channel.send_review(job_id="paid-new", revision=2, image_paths=[self.image], live_scope=self.scope,
                    budget={"amount": "72", "currency": "DREAMINA_CREDITS"}, binding_hash="a" * 64, shot_ids=["S02"])
                def respond(text, event_id):
                    event = self.event(text, create_time=str(int(self.now * 1000)))
                    event["header"]["event_id"] = event_id
                    return channel.receive(event)
                self.assertEqual(respond("同意", "repeated-legacy-approval")["reason"], "selection_required")
                self.assertEqual(broker._db.execute("SELECT count(*) FROM approval_queue WHERE challenge_id=?", (new.challenge_id,)).fetchone()[0], 0)
                self.assertEqual(respond("1", "choose-current")["reason"], "confirmation_required")
                self.assertTrue(respond("同意", "fresh-current-approval")["accepted"])
                queued, = broker.drain()
                self.assertEqual(queued["challenge_id"], new.challenge_id)
                self.assertEqual(queued["budget"], {"amount": "72", "currency": "DREAMINA_CREDITS"})

    def test_unmapped_history_for_other_chat_or_approver_does_not_block_first_review(self):
        self.issue(job_id="other-chat", chat_id="chat-2")
        self.issue(job_id="other-approver", allowed_sender_ids={"user-2"})
        self.send_review()
        self.assertTrue(self.reply("同意")["accepted"])
        self.assertEqual(len(self.broker.drain()), 1)

    def test_nonstring_user_text_is_rejected_as_input_not_internal_failure(self):
        self.send_review()
        for i, value in enumerate((None, {}, [], 123, True)):
            event = self.event(value, create_time="1000000")
            event["header"]["event_id"] = f"bad-text-{i}"
            self.assertEqual(self.feishu.receive(event)["reason"], "invalid_command")
        self.assertEqual(self.broker.drain(), [])

    def test_changed_stored_budget_cannot_use_the_previously_shown_binding(self):
        challenge = self.send_review()
        self.broker._db.execute("UPDATE challenges SET budget=? WHERE id=?",
                                (json.dumps({"amount": "9999", "currency": "CNY"}), challenge.challenge_id))
        with self.assertRaises(ConfigurationError):
            self.reply("同意", event_id="budget-mutated")
        self.assertEqual(self.broker.drain(), [])
        self.assertEqual(self.broker._db.execute("SELECT status FROM challenges WHERE id=?", (challenge.challenge_id,)).fetchone()[0], "pending")
        self.assertEqual(self.broker._db.execute("SELECT count(*) FROM short_events WHERE event_id='budget-mutated'").fetchone()[0], 0)

    def test_other_sender_chat_and_app_cannot_use_short_focus(self):
        self.send_review()
        for field, value in (("sender", "intruder"), ("chat", "another-chat"), ("app", "other-app")):
            event = self.event("同意", create_time="1000000")
            if field == "sender":event["event"]["sender"]["sender_id"]["open_id"] = value
            elif field == "chat":event["event"]["message"]["chat_id"] = value
            else:event["header"]["app_id"] = value
            self.assertFalse(self.feishu.receive(event)["accepted"])
        self.assertEqual(self.broker.drain(), [])

    def test_two_feishu_apps_have_separate_contexts_even_with_same_event_id(self):
        first = self.send_review(job_id="app-one")
        transport = Transport();transport._app_id = "app-two"
        other = FeishuChannel(self.config, self.broker, transport=transport)
        second = other.send_review(job_id="app-two", revision=2, image_paths=[self.image], live_scope=self.scope,
                                   budget=self.budget, binding_hash="b" * 64, shot_ids=["S02"])
        self.assertTrue(self.reply("同意", event_id="same-platform-id")["accepted"])
        event = self.event("拒绝", create_time="1000000")
        event["header"].update(app_id="app-two", event_id="same-platform-id")
        self.assertTrue(other.receive(event)["accepted"])
        self.assertEqual({row["challenge_id"] for row in self.broker.drain()}, {first.challenge_id, second.challenge_id})

    def test_focus_and_replay_guards_survive_broker_restart(self):
        self.send_review()
        self.broker.close()
        self.broker = ApprovalBroker(self.root / "approvals.sqlite3", clock=lambda: self.now)
        self.feishu = FeishuChannel(self.config, self.broker, transport=self.transport)
        self.assertTrue(self.reply("同意", event_id="across-restart")["accepted"])
        self.broker.close()
        self.broker = ApprovalBroker(self.root / "approvals.sqlite3", clock=lambda: self.now)
        self.feishu = FeishuChannel(self.config, self.broker, transport=self.transport)
        self.assertFalse(self.reply("同意", event_id="across-restart")["accepted"])
        self.assertFalse(self.reply("同意", event_id="new-repeat")["accepted"])
        self.assertEqual(len(self.broker.drain()), 1)

    def test_concurrent_short_replies_queue_only_once(self):
        self.send_review()
        results = []
        def accept(i):
            results.append(self.broker.accept_text(channel="feishu", instance=self.feishu._instance(),
                event_id=f"concurrent-{i}", sender_id="user-1", chat_id="chat-1", text="同意", created_at=self.now))
        threads = [threading.Thread(target=accept, args=(i,)) for i in range(6)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(sum(r["accepted"] for r in results), 1)
        self.assertEqual(len(self.broker.drain()), 1)

    def test_wechat_two_char_review_uses_current_context_and_never_saves_tokens(self):
        channel = self.wechat()
        channel._contexts["wx-user"] = "synthetic-context-never-persist"
        channel.send_review(job_id="wx-short", revision=1, stage="final", image_paths=[],
                            live_scope={"stages": [], "allow_uploads": False}, budget={"amount": "0", "currency": "CNY"})
        event = dict(self.wx_message("同意"), create_time_ms=1000000)
        self.assertTrue(channel.receive(event)["accepted"])
        self.assertFalse(channel.receive(event)["accepted"])
        self.assertEqual(len(self.broker.drain()), 1)
        raw = (self.root / "approvals.sqlite3").read_bytes()
        self.assertNotIn(b"synthetic-context-never-persist", raw)
        self.assertNotIn(b"synthetic-test-token", raw)

    def test_wechat_short_reviews_do_not_cross_bot_instances(self):
        channels = []
        for bot in ("first@im.bot", "second@im.bot"):
            channel = self.wechat(bot_id=bot)
            channel._contexts["wx-user"] = "synthetic-context"
            channel.send_review(job_id=bot.split("@")[0], revision=1, stage="final", image_paths=[],
                                live_scope={"stages": [], "allow_uploads": False})
            channels.append((bot, channel))
        for i, (bot, channel) in enumerate(channels):
            event = dict(self.wx_message("同意"), to_user_id=bot, message_id=42, create_time_ms=1000000)
            self.assertTrue(channel.receive(event)["accepted"])
        self.assertEqual({row["project_id"] for row in self.broker.drain()}, {"first", "second"})

    def test_wechat_unknown_quote_or_missing_time_does_not_approve(self):
        channel = self.wechat();channel._contexts["wx-user"] = "synthetic-context"
        channel.send_review(job_id="wx-short", revision=1, stage="final", image_paths=[])
        event = dict(self.wx_message("同意"), create_time_ms=1000000, ref_msg={"message_id": "old"})
        self.assertEqual(channel.receive(event)["reason"], "unverified_reference")
        missing = dict(self.wx_message("同意"), message_id=999)
        self.assertEqual(channel.receive(missing)["reason"], "stale_or_unverifiable_message")
        self.assertEqual(self.broker.drain(), [])

    def wx_reference_channel(self, *, bot_id="wx-bot", server_id=123):
        sends = []
        def request(*args):
            sends.append(args)
            ident = server_id if len(sends) == 1 else 9000 + len(sends)
            return 200, {}, json.dumps({"ret": 0, "message_id": ident}).encode()
        channel = self.wechat(request=request, bot_id=bot_id)
        channel._contexts["wx-user"] = "synthetic-context"
        challenge = channel.send_review(job_id="quote-" + bot_id, revision=1, stage="final", image_paths=[],
            live_scope={"stages": [], "allow_uploads": False}, budget={"amount": "0", "currency": "CNY"})
        return channel, challenge

    def wx_quote_event(self, reference, *, bot_id="wx-bot", event_id=54321, text="同意", **fields):
        message = dict(self.wx_message(text), to_user_id=bot_id, message_id=event_id, create_time_ms=1000000, **fields)
        message["item_list"][0]["ref_msg"] = reference
        return message

    def test_wechat_clear_empty_reference_markers_allow_direct_two_char_reply(self):
        for index, value in enumerate((None, {}, "")):
            with self.subTest(reference=value):
                bot = f"empty-{index}@im.bot"
                channel, challenge = self.wx_reference_channel(bot_id=bot)
                message = self.wx_quote_event(value, bot_id=bot, text="拒绝")
                # Empty unknown/legacy fields are also absence, not a quote.
                message.update(parent_id="", quote=None, ref_msg={})
                self.assertTrue(channel.receive(message)["accepted"])
                queued, = self.broker.drain()
                self.assertEqual(queued["challenge_id"], challenge.challenge_id)
                self.assertEqual(queued["decision"], "reject")

    def test_wechat_real_unquoted_wire_thread_zero_defaults_preserve_exact_bound_rejection(self):
        channel = self.wechat()
        channel._contexts["wx-user"] = "synthetic-context"
        scope = {"stages": [], "allow_uploads": False, "revision": 7,
                 "plan_hash": "a" * 64, "asset_hash": "b" * 64}
        budget = {"amount": "0", "currency": "DREAMINA_CREDITS"}
        challenge = channel.send_review(job_id="wire-defaults", revision=7, stage="final", image_paths=[],
            live_scope=scope, budget=budget, binding_hash="c" * 64, shot_ids=["RLS03"])
        message = dict(self.wx_message("拒绝"), create_time_ms=1000000, parent_id=0, root_id=0)
        self.assertTrue(channel.receive(message)["accepted"])
        queued, = self.broker.drain()
        self.assertEqual(queued["challenge_id"], challenge.challenge_id)
        self.assertEqual((queued["decision"], queued["stage"], queued["revision"]), ("reject", "final", 7))
        self.assertEqual(queued["live_scope"], scope)
        self.assertEqual(queued["budget"], budget)
        self.assertEqual(queued["binding_hash"], "c" * 64)
        self.assertEqual(queued["shot_ids"], ["RLS03"])
        self.assertFalse(channel.receive(message)["accepted"])
        self.assertFalse(channel.receive(dict(message, message_id=1235))["accepted"])
        self.assertEqual(self.broker.drain(), [])

    def test_wechat_thread_zero_default_exception_is_exact_in_type_name_and_level(self):
        channel, _ = self.wx_reference_channel()
        cases = []
        for field in ("parent_id", "root_id"):
            for value in (False, True, 1, -1, 0.0, "0"):
                cases.append(("message", field, value))
            cases.append(("item", field, 0))
        for field in ("ref_msg", "quote", "ref_message_id"):
            cases.extend((("message", field, 0), ("item", field, 0)))
        for index, (level, field, value) in enumerate(cases):
            with self.subTest(level=level, field=field, value=value):
                message = dict(self.wx_message("拒绝"), message_id=30001 + index, create_time_ms=1000000)
                (message if level == "message" else message["item_list"][0])[field] = value
                self.assertEqual(channel.receive(message)["reason"], "unverified_reference")
        self.assertEqual(self.broker.drain(), [])

    def test_wechat_false_zero_and_empty_list_are_not_clear_empty_references(self):
        channel, _ = self.wx_reference_channel()
        for index, value in enumerate((False, 0, [], True, 1)):
            with self.subTest(reference=value):
                result = channel.receive(self.wx_quote_event(value, event_id=54321 + index))
                self.assertEqual(result["reason"], "unverified_reference")
        self.assertEqual(self.broker.drain(), [])

    def test_wechat_official_svr_id_matches_current_review_with_int_or_string(self):
        for index, ident in enumerate((123, "123", "000123", 18446744073709551615, "18446744073709551615")):
            with self.subTest(identity=ident):
                bot = f"known-{index}@im.bot"
                channel, challenge = self.wx_reference_channel(bot_id=bot, server_id=ident)
                reference = {"svr_id": ident, "title": "this text is not used as an identity", "message_item": {"type": 1}}
                message = self.wx_quote_event(reference, bot_id=bot)
                message.update(parent_id=0, root_id=0)
                # An exact known server-message reference can identify the
                # review even when this platform omitted its creation time.
                del message["create_time_ms"]
                self.assertTrue(channel.receive(message)["accepted"])
                queued, = self.broker.drain()
                self.assertEqual(queued["challenge_id"], challenge.challenge_id)
                self.assertEqual(queued["live_scope"]["stages"], [])

    def test_wechat_unknown_svr_id_never_falls_back_to_latest_review(self):
        channel, _ = self.wx_reference_channel(server_id=123)
        result = channel.receive(self.wx_quote_event({"svr_id": "456"}))
        self.assertEqual(result["reason"], "reference_mismatch")
        self.assertEqual(self.broker.drain(), [])

    def test_wechat_old_svr_id_cannot_approve_replacement_focus(self):
        channel, old = self.wx_reference_channel(server_id=123)
        self.assertTrue(channel.receive(self.wx_quote_event({"svr_id": "123"}, event_id=10001))["accepted"])
        self.broker.drain()
        newer = channel.send_review(job_id="replacement", revision=1, stage="final", image_paths=[])
        def reply(text, ident):
            return channel.receive(dict(self.wx_message(text), message_id=ident, create_time_ms=1000000))
        self.assertEqual(reply("审核", 10002)["reason"], "selection_required")
        self.assertEqual(reply("1", 10003)["reason"], "confirmation_required")
        rejected = channel.receive(self.wx_quote_event({"svr_id": "123"}, event_id=10004))
        self.assertEqual(rejected["reason"], "reference_mismatch")
        self.assertNotEqual(old.challenge_id, newer.challenge_id)
        self.assertEqual(self.broker.drain(), [])

    def test_wechat_quote_message_ids_are_isolated_by_bot_instance(self):
        first, _ = self.wx_reference_channel(bot_id="first@im.bot", server_id=101)
        second, second_review = self.wx_reference_channel(bot_id="second@im.bot", server_id=202)
        cross = second.receive(self.wx_quote_event({"svr_id": "101"}, bot_id="second@im.bot", event_id=10001))
        self.assertEqual(cross["reason"], "reference_mismatch")
        self.assertEqual(self.broker.drain(), [])
        self.assertTrue(second.receive(self.wx_quote_event({"svr_id": "202"}, bot_id="second@im.bot", event_id=10002))["accepted"])
        self.assertEqual(self.broker.drain()[0]["challenge_id"], second_review.challenge_id)

    def test_wechat_quote_without_svr_id_never_uses_title_or_message_text(self):
        channel, _ = self.wx_reference_channel(server_id=123)
        references = ({"title": "123"}, {"message_item": {"type": 1, "text_item": {"text": "123 同意"}}},
                      {"partial_text": {"text": "123"}}, {"message_id": "123"}, {"svr_id": ""})
        for index, reference in enumerate(references):
            self.assertEqual(channel.receive(self.wx_quote_event(reference, event_id=10001 + index))["reason"], "unverified_reference")
        self.assertEqual(self.broker.drain(), [])

    def test_wechat_quote_rejects_invalid_uint64_or_conflicting_reference_metadata(self):
        channel, _ = self.wx_reference_channel(server_id=123)
        bad_ids = (False, True, 0, -1, 18446744073709551616, "18446744073709551616", "0", "-1", "1e3", "+123", 123.0, "１２３", " 123 ")
        for index, ident in enumerate(bad_ids):
            self.assertEqual(channel.receive(self.wx_quote_event({"svr_id": ident}, event_id=20001 + index))["reason"], "unverified_reference")
        conflicting = self.wx_quote_event({"svr_id": "123"}, event_id=21001, parent_id="456")
        self.assertEqual(channel.receive(conflicting)["reason"], "unverified_reference")
        nested = self.wx_quote_event({"svr_id": "123", "message_item": {"ref_msg": {"svr_id": "456"}}}, event_id=21002)
        self.assertEqual(channel.receive(nested)["reason"], "unverified_reference")
        guessed_path = self.wx_quote_event(None, event_id=21003, ref_msg={"svr_id": "123"})
        self.assertEqual(channel.receive(guessed_path)["reason"], "unverified_reference")
        self.assertEqual(self.broker.drain(), [])

    def test_wechat_valid_quote_cannot_revive_expired_review(self):
        channel, _ = self.wx_reference_channel(server_id=123)
        self.now += 901
        expired = self.wx_quote_event({"svr_id": "123"}, event_id=10001)
        expired["create_time_ms"] = int(self.now * 1000)
        self.assertFalse(channel.receive(expired)["accepted"])
        self.assertEqual(self.broker.drain(), [])

    def test_wechat_event_id_requires_real_positive_uint64(self):
        channel, _ = self.wx_reference_channel()
        for value in (False, 0, -1, "abc", "18446744073709551616", 18446744073709551616, 123.0):
            event = self.wx_quote_event(None)
            event["message_id"] = value
            self.assertEqual(channel.receive(event)["reason"], "missing_event_id")
        self.assertEqual(self.broker.drain(), [])

    def test_migrated_challenge_has_no_short_authority(self):
        challenge = self.issue()
        self.broker.close()
        connection = sqlite3.connect(self.root / "approvals.sqlite3")
        for table in ("short_reviews", "short_contexts", "short_events", "short_messages"):
            connection.execute("DROP TABLE " + table)
        connection.commit();connection.close()
        self.broker = ApprovalBroker(self.root / "approvals.sqlite3", clock=lambda: self.now)
        self.feishu = FeishuChannel(self.config, self.broker, transport=self.transport)
        self.assertFalse(self.reply("同意", event_id="plain-migrated")["accepted"])
        self.assertTrue(self.reply(challenge.approve_command, event_id="nonce-migrated")["accepted"])


if __name__ == "__main__":
    unittest.main()
