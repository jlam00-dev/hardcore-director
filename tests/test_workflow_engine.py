"""Offline workflow acceptance tests: fake clock/provider, temporary local files."""

import copy
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hc_workflow.engine import Engine, Limits, WorkflowError


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Provider:
    def __init__(self, live=False, amount="0", currency="CNY"):
        self.live = live
        self.amount = amount
        self.currency = currency
        self.account = "account-1"
        self.verified = True
        self.calls = []
        self.raise_prepare = False
        self.raise_submit = False
        self.poll_state = "succeeded"

    def identity(self):
        return {"provider": "test", "account": self.account, "live": self.live, "verified": self.verified}

    def probe(self):
        return {"status": "ready"}

    def quote(self, operation):
        self.calls.append(("quote", operation["operation_id"]))
        return {"amount": self.amount, "currency": self.currency}

    def prepare(self, operation):
        self.calls.append(("prepare", operation["operation_id"]))
        if self.raise_prepare:
            raise TimeoutError("response lost after remote draft write")
        return {"status": "prepared", "payload": {"node_id": "node-" + operation["operation_id"]}}

    def submit(self, operation):
        self.calls.append(("submit", operation["operation_id"]))
        if self.raise_submit:
            raise TimeoutError("response lost after charging")
        return {"status": "submitted", "task_id": "task-" + operation["operation_id"]}

    def poll(self, operation):
        self.calls.append(("poll", operation["operation_id"]))
        return {"status": self.poll_state, "task_id": "task-" + operation["operation_id"]}

    def download(self, operation):
        self.calls.append(("download", operation["operation_id"]))
        path = Path(operation["output_dir"]) / (operation["stage"] + ".mock")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(operation["operation_id"], encoding="utf-8")
        return {"status": "succeeded", "path": str(path)}


class Channel:
    def __init__(self):
        self.events = []

    def deliver(self, event):
        self.events.append(event)
        return {"delivered": True}


def plan(count=2):
    return {"schema_version": 1, "project_name": "offline proof", "providers": {"image": "mock", "video": "mock"},
            "shots": [{"id": f"shot-{i + 1:03}", "duration_seconds": 3,
                       "image_prompt": "a local mock frame", "video_prompt": "one slow action"} for i in range(count)]}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clock = Clock()
        self.provider = Provider()
        self.channel = Channel()
        self.engine = self.open_engine()
        self.addCleanup(lambda: self.engine.close())

    def open_engine(self, limits=None):
        return Engine(self.root / "jobs.sqlite3", {"mock": self.provider}, channel=self.channel,
                      clock=self.clock, limits=limits, artifact_dir=self.root / "assets")

    def create(self, count=2, mode="dry-run"):
        pid = self.engine.init_project({"audience": "test"}, mode=mode)["project_id"]
        self.engine.set_plan(pid, plan(count))
        return pid

    def until(self, pid, target, limit=40):
        for _ in range(limit):
            state = self.engine.tick(pid)
            if state["status"] == target:
                return state
        self.fail(f"did not reach {target}: {state}")

    def scope(self, pid, stage="image"):
        name = "plan" if stage == "image" else "storyboard"
        binding = self.engine.status(pid)["bindings"][name]
        return {"stages": [stage], "provider": "test", "account": self.provider.account,
                "allow_uploads": True, "revision": binding["revision"],
                "plan_hash": binding["plan_hash"], "asset_hash": binding["asset_hash"]}

    def use_design_mapping_fixture(self):
        # The registration key stays "mock" to exercise canonical provider
        # routing; this fake never reaches the real Design transport.
        self.provider.identity = lambda: {"provider": "minimax-design", "account": self.provider.account,
                                         "live": self.provider.live, "verified": self.provider.verified}
        self.provider.config = {"project_id": "fixture-project", "stages": {
            "image": {"capability_id": "generate_image:fixture", "params": {"quality": "high"},
                      "design_output": {"resources": [{"mode": "create", "name": "fixture-image"}]}},
            "video": {"capability_id": "generate_video:fixture", "params": {"duration": 3},
                      "design_output": {"resources": [{"mode": "create", "name": "fixture-video"}]}},
        }}
        return self.provider.config

    def test_design_stage_mapping_is_frozen_for_each_operation_without_prompt_rewriting(self):
        config = self.use_design_mapping_fixture()
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        self.until(pid, "storyboard_review")
        self.engine.approve(pid, "storyboard", actor="human")
        self.engine.tick(pid)
        ops = self.engine.status(pid)["operations"]
        self.assertEqual({op["stage"] for op in ops}, {"image", "video"})
        for op in ops:
            settings = config["stages"][op["stage"]]
            for key in ("capability_id", "params", "design_output"):
                self.assertEqual(op["payload"][key], settings[key])
            self.assertEqual(op["payload"]["design_project_id"], "fixture-project")
            self.assertEqual(op["payload"]["design_execution_config_hash"],
                             self.engine._identity(self.provider)["execution_config_hash"])
            self.assertEqual(op["payload"]["image_prompt"], plan(1)["shots"][0]["image_prompt"])
            self.assertEqual(op["payload"]["video_prompt"], plan(1)["shots"][0]["video_prompt"])
        config["stages"]["image"]["params"]["quality"] = "changed"
        config["stages"]["video"]["design_output"]["resources"][0]["name"] = "changed"
        frozen = {op["stage"]: op["payload"] for op in self.engine.status(pid)["operations"]}
        self.assertEqual(frozen["image"]["params"], {"quality": "high"})
        self.assertEqual(frozen["video"]["design_output"]["resources"][0]["name"], "fixture-video")

    def test_design_model_params_and_output_edits_require_new_plan_even_after_reapproval(self):
        for changed in ("capability_id", "params", "design_output"):
            with self.subTest(changed=changed):
                config = self.use_design_mapping_fixture()
                pid = self.create(1)
                self.engine.approve(pid, actor="human")
                self.engine.tick(pid)
                old = self.engine.status(pid)["operations"][0]
                before = list(self.provider.calls)
                settings = config["stages"]["image"]
                if changed == "capability_id":
                    settings[changed] = "generate_image:different"
                elif changed == "params":
                    settings[changed]["quality"] = "different"
                else:
                    settings[changed]["resources"][0]["name"] = "different"
                self.assertIsNone(self.engine._approval(self.engine._project(pid), "plan"))
                self.engine.tick(pid)
                self.assertEqual(self.provider.calls, before)
                self.engine.approve(pid, actor="human")
                blocked = self.engine.tick(pid)
                self.assertIn("replan", blocked["blocked_reason"])
                self.assertEqual(self.provider.calls, before)
                self.engine.set_plan(pid, plan(1))
                self.engine.approve(pid, actor="human")
                self.engine.tick(pid)
                new = self.engine.status(pid)["operations"][-1]
                self.assertNotEqual(new["id"], old["id"])
                self.assertEqual(new["payload"][changed], settings[changed])

    def test_design_mapping_rejects_credential_fields_and_invalid_json_before_persisting(self):
        config = self.use_design_mapping_fixture()
        config["stages"]["image"]["params"]["secret"] = "fixture-private-value"
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        result = self.engine.tick(pid)
        self.assertIn("credentials", result["blocked_reason"])
        self.assertNotIn("fixture-private-value", json.dumps(result))
        self.assertEqual(self.engine.status(pid)["operations"], [])
        self.assertFalse(self.provider.calls)
        config["stages"]["image"]["params"] = {"invalid": float("nan")}
        with self.assertRaisesRegex(WorkflowError, "finite JSON"):
            self.engine._identity(self.provider)

    def test_design_config_read_race_cannot_freeze_a_different_approved_request(self):
        config = self.use_design_mapping_fixture()
        pid = self.create(1)
        original = self.engine._provider
        def changed_during_read(value, stage):
            result = original(value, stage)
            config["stages"][stage]["params"]["quality"] = "changed-after-fingerprint"
            return result
        self.engine._provider = changed_during_read
        with self.assertRaisesRegex(WorkflowError, "changed while creating"):
            self.engine._new_operation(self.engine._project(pid), self.engine._shots(pid)[0], "image")
        self.assertEqual(self.engine.db.execute("SELECT COUNT(*) FROM operations").fetchone()[0], 0)
        self.assertFalse(self.provider.calls)

    def test_design_unsupported_stage_settings_block_before_creating_any_operation(self):
        for stage in ("image", "video"):
            for key in ("max_cost", "budget", "unknown"):
                with self.subTest(stage=stage, key=key):
                    config = self.use_design_mapping_fixture()
                    config["stages"][stage][key] = "fixture-unsupported-value"
                    pid = self.create(1)
                    self.engine.approve(pid, actor="human")
                    result = self.engine.tick(pid)
                    self.assertIn("no local cost limit is enforced", result["blocked_reason"])
                    self.assertNotIn("fixture-unsupported-value", json.dumps(result))
                    self.assertEqual(self.engine.status(pid)["operations"], [])
                    self.assertFalse(self.provider.calls)
        # Other providers retain their own configuration contract.
        self.provider.identity = lambda: {"provider": "test", "account": self.provider.account,
                                         "live": False, "verified": True}
        self.provider.config = {"stages": {"image": {"budget": "1"}}}
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        self.engine.tick(pid)
        self.assertEqual(len(self.engine.status(pid)["operations"]), 1)
        self.assertTrue(self.provider.calls)

    def test_design_recovery_patch_cannot_change_frozen_capability_or_project(self):
        self.use_design_mapping_fixture()
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        self.engine.tick(pid)
        op = self.engine.status(pid)["operations"][0]
        for key, value in (("capability_id", "generate_image:different"), ("design_project_id", "different-project")):
            with self.subTest(key=key), self.assertRaisesRegex(WorkflowError, "frozen MiniMax"):
                self.engine._record(op["id"], "prepared", result={"payload": {key: value}})
            self.assertEqual(self.engine._op(op["id"])["payload"][key], op["payload"][key])

    def test_design_unverified_live_identity_remains_blocked_before_provider_calls(self):
        self.use_design_mapping_fixture()
        self.provider.live = True
        self.provider.verified = False
        pid = self.create(1, mode="live")
        with self.assertRaisesRegex(WorkflowError, "verified"):
            self.engine.approve(pid, actor="human", live_scope={"stages": ["image"], "provider": "minimax-design",
                                "account": self.provider.account, "allow_uploads": True}, budget={"amount": "1", "currency": "CNY"})
        self.assertFalse(self.provider.calls)

    def test_complete_mock_cycle_requires_both_reviews_and_final_acceptance(self):
        pid = self.create()
        self.engine.tick(pid)
        self.assertFalse(self.provider.calls)
        self.engine.approve(pid, actor="director", stage="plan")
        images = self.until(pid, "storyboard_review")
        self.assertTrue(all(s["image"] for s in images["shots"]))
        self.assertFalse(any(s["video"] for s in images["shots"]))
        self.engine.approve(pid, actor="director", stage="storyboard", shot_ids=["shot-001"])
        self.engine.tick(pid)
        self.assertFalse(any(s["video"] for s in self.engine.status(pid)["shots"]))
        self.engine.approve(pid, actor="director", stage="storyboard", shot_ids=["shot-002"])
        final = self.until(pid, "final_review")
        self.assertTrue(final["final_artifact"]["simulated"])
        assembly = json.loads(Path(final["final_artifact"]["path"]).read_text())
        order = assembly.get("order") or [s["shot_id"] for s in assembly["inputs"]]
        self.assertEqual(order, ["shot-001", "shot-002"])
        self.engine.approve(pid, actor="director", stage="final")
        self.assertEqual(self.engine.status(pid)["status"], "completed")
        reviews = [e for e in self.channel.events if e["type"] == "storyboard_review"]
        self.assertEqual([e["shot_ids"] for e in reviews], [["shot-001"], ["shot-002"]])
        self.assertEqual([e["artifacts"] for e in reviews], [[s["image"]["path"]] for s in images["shots"]])
        self.assertEqual(reviews[0]["binding_hash"], reviews[1]["binding_hash"])
        self.assertTrue(all("asset_hash" in review["approval_scope"] for review in reviews))

    def test_internal_audits_and_locally_approved_review_do_not_notify(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        self.engine.tick(pid)
        self.assertEqual(self.channel.events, [])
        audits = self.engine.db.execute("SELECT type,delivered FROM events WHERE project_id=?", (pid,)).fetchall()
        self.assertEqual({row["type"] for row in audits}, {"project_created", "plan_review", "approved"})
        self.assertTrue(all(row["delivered"] for row in audits))

    def test_old_revision_review_is_skipped_but_current_unapproved_review_is_sent(self):
        pid = self.create(1)
        changed = plan(1)
        changed["shots"][0]["image_prompt"] = "a revised image"
        self.engine.set_plan(pid, changed)
        self.engine.tick(pid)
        self.assertEqual([(event["type"], event["revision"]) for event in self.channel.events], [("plan_review", 2)])
        self.assertFalse(self.provider.calls)
        self.assertEqual(self.engine.db.execute("SELECT COUNT(*) FROM events WHERE project_id=? AND type='plan_review'", (pid,)).fetchone()[0], 2)

    def test_default_content_review_never_inherits_a_plan_spending_cap(self):
        self.provider.live = True
        pid = self.engine.init_project("review content first", mode="live")["project_id"]
        value = plan(1)
        value["budget"] = {"amount": "99", "currency": "DREAMINA_CREDITS"}
        self.engine.set_plan(pid, value)
        self.engine.tick(pid)
        review = self.channel.events[-1]
        self.assertEqual(review["approval_scope"]["stages"], [])
        self.assertEqual(review["budget"], {"amount": "0", "currency": "DREAMINA_CREDITS"})
        self.assertFalse(self.provider.calls)

    def test_current_storyboard_and_explicit_failure_still_notify(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        state = self.until(pid, "storyboard_review")
        reviews = [event for event in self.channel.events if event["type"] == "storyboard_review"]
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0]["artifacts"], [state["shots"][0]["image"]["path"]])
        with self.engine._tx() as db:
            self.engine._event(db, pid, "account_changed", {"message": "Restore the selected account."})
        self.engine.tick(pid)
        self.assertEqual(self.channel.events[-1]["type"], "account_changed")

    def test_live_content_approval_does_not_authorize_video_upload_or_spending(self):
        self.provider.live = True
        self.provider.amount = "1"
        pid = self.create(1, mode="live")
        self.engine.approve(pid, actor="human", budget={"amount": "1", "currency": "CNY"}, live_scope=self.scope(pid))
        self.until(pid, "storyboard_review")
        review = next(event for event in self.channel.events if event["type"] == "storyboard_review")
        self.assertEqual(review["approval_scope"]["stages"], [])
        self.assertIs(review["approval_scope"]["allow_uploads"], False)
        self.assertEqual(review["budget"]["amount"], "0")
        before = list(self.provider.calls)
        state = self.engine.approve(pid, "storyboard", actor="wechat:director", live_scope=review["approval_scope"],
                                    budget=review["budget"], expected_revision=review["revision"],
                                    expected_binding_hash=review["binding_hash"])
        self.assertEqual(state["status"], "video_generation_approval")
        self.assertTrue(state["shots"][0]["approved"])
        for _ in range(3):
            self.assertEqual(self.engine.tick(pid)["status"], "video_generation_approval")
        self.assertEqual(self.provider.calls, before)
        self.assertFalse(any(op["stage"] == "video" for op in self.engine.status(pid)["operations"]))
        # Content approval has not pinned a spending currency; a later explicit
        # fee grant may use the provider's real unit without mixing any ledger.
        self.provider.currency = "DREAMINA_CREDITS"
        self.engine.approve(pid, "storyboard", actor="local", live_scope=self.scope(pid, "video"),
                            budget={"amount": "1", "currency": "DREAMINA_CREDITS"})
        self.engine.tick(pid)
        self.assertEqual(sum(name == "prepare" for name, _ in self.provider.calls), 2)

    def test_live_content_scope_must_match_binding_and_cannot_lower_reserved_budget(self):
        self.provider.live = True
        self.provider.amount = "1"
        pid = self.create(1, mode="live")
        content_scope = {**self.scope(pid), "stages": [], "allow_uploads": False}
        for change in ({"account": "another-account"}, {"asset_hash": "wrong"}, {"plan_hash": None}):
            with self.assertRaises(WorkflowError):
                self.engine.approve(pid, actor="human", live_scope={**content_scope, **change}, budget={"amount": "0", "currency": "CNY"})
        approved = self.engine.approve(pid, actor="human", live_scope=content_scope, budget={"amount": "0", "currency": "CNY"})
        self.assertEqual(approved["status"], "image_generation_approval")
        self.engine.tick(pid)
        self.assertFalse(self.provider.calls)
        self.engine.approve(pid, actor="human", live_scope=self.scope(pid), budget={"amount": "1", "currency": "CNY"})
        self.engine.tick(pid)
        with self.assertRaisesRegex(WorkflowError, "reserved or spent"):
            self.engine.approve(pid, actor="human", live_scope=content_scope, budget={"amount": "0", "currency": "CNY"})

    def test_submit_timeout_restarts_with_poll_only_same_id(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        self.engine.tick(pid)  # prepare
        self.provider.raise_submit = True
        self.engine.tick(pid)  # remote accepted, response lost
        old = self.engine.status(pid)["operations"][0]
        self.assertEqual(old["status"], "unknown")
        self.engine.close()
        self.engine = self.open_engine()
        self.provider.poll_state = "unknown"
        for _ in range(3):
            self.engine.tick(pid)
        calls = [(name, oid) for name, oid in self.provider.calls if name in ("prepare", "submit", "poll")]
        self.assertEqual([n for n, _ in calls], ["prepare", "submit", "poll", "poll", "poll"])
        self.assertEqual({oid for _, oid in calls}, {old["operation_id"]})

    def test_prepare_timeout_never_repeats_prepare(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        self.provider.raise_prepare = True
        self.provider.poll_state = "unknown"
        self.engine.tick(pid)
        self.engine.tick(pid)
        self.engine.tick(pid)
        self.assertEqual([n for n, _ in self.provider.calls if n != "quote"], ["prepare", "poll", "poll"])

    def test_expired_approval_blocks_new_writes(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human", ttl_seconds=5)
        self.clock.now += 6
        self.assertEqual(self.engine.tick(pid)["status"], "plan_review")
        self.assertFalse(self.provider.calls)

    def test_completed_images_survive_expiry_for_content_and_fresh_video_approval_only(self):
        self.provider.live = True
        self.provider.amount = "1"
        pid = self.create(1, mode="live")
        self.engine.approve(pid, actor="human", ttl_seconds=5, live_scope=self.scope(pid),
                            budget={"amount": "1", "currency": "CNY"})
        self.until(pid, "storyboard_review")
        image_operation = self.engine.status(pid)["operations"][0]
        review = next(event for event in self.channel.events if event["type"] == "storyboard_review")
        before = list(self.provider.calls)
        self.clock.now += 6
        self.assertEqual(self.engine.tick(pid)["status"], "storyboard_review")
        self.assertEqual(self.provider.calls, before)
        with self.assertRaisesRegex(WorkflowError, "need human approval"):
            self.engine._authorized(image_operation)
        state = self.engine.approve(pid, "storyboard", actor="wechat:director", live_scope=review["approval_scope"],
                                    budget=review["budget"], expected_revision=review["revision"],
                                    expected_binding_hash=review["binding_hash"])
        self.assertEqual(state["status"], "video_generation_approval")
        self.engine.tick(pid)
        self.assertEqual(self.provider.calls, before)
        self.provider.amount, self.provider.currency = "48", "DREAMINA_CREDITS"
        self.engine.approve(pid, "storyboard", actor="human", live_scope=self.scope(pid, "video"),
                            budget={"amount": "48", "currency": "DREAMINA_CREDITS"})
        state = self.engine.tick(pid)
        self.assertEqual([op["stage"] for op in state["operations"]], ["image", "video"])
        self.assertEqual(sum(name == "prepare" for name, _ in self.provider.calls), 2)

    def test_completed_videos_may_compose_after_all_generation_grants_expire(self):
        pid = self.create()
        self.engine.approve(pid, actor="human", ttl_seconds=5)
        self.until(pid, "storyboard_review")
        self.engine.approve(pid, "storyboard", actor="human", ttl_seconds=5)
        self.until(pid, "ready_to_compose")
        before = list(self.provider.calls)
        self.clock.now += 6
        self.assertEqual(self.engine.status(pid)["status"], "ready_to_compose")
        result = self.engine.tick(pid)
        self.assertEqual(result["status"], "final_review")
        self.assertTrue(result["final_artifact"]["simulated"])
        self.assertEqual(self.provider.calls, before)

    def test_expired_video_approval_cannot_generate_a_missing_video(self):
        pid = self.create()
        self.engine.approve(pid, actor="human", ttl_seconds=5)
        self.until(pid, "storyboard_review")
        self.engine.approve(pid, "storyboard", actor="human", ttl_seconds=5)
        for _ in range(4):
            self.engine.tick(pid)
        self.assertIsNotNone(self.engine.status(pid)["shots"][0]["video"])
        self.assertIsNone(self.engine.status(pid)["shots"][1]["video"])
        before = list(self.provider.calls)
        self.clock.now += 6
        for _ in range(3):
            self.assertEqual(self.engine.tick(pid)["status"], "storyboard_review")
        self.assertEqual(self.provider.calls, before)
        self.assertEqual(len(self.engine.status(pid)["operations"]), 3)

    def test_completed_history_requires_unchanged_outputs_config_and_unrevoked_binding(self):
        for change in ("output", "reference", "config", "account", "revoke", "plan", "reject"):
            with self.subTest(change=change):
                reference = self.root / (change + ".reference")
                reference.write_bytes(b"approved reference")
                value = plan(1)
                value["shots"][0]["reference_assets"] = [{"path": str(reference), "role": "identity"}]
                pid = self.engine.init_project("history boundary")["project_id"]
                self.engine.set_plan(pid, value)
                self.engine.approve(pid, actor="human", ttl_seconds=5)
                state = self.until(pid, "storyboard_review")
                self.clock.now += 6
                if change == "output":
                    Path(state["shots"][0]["image"]["path"]).write_bytes(b"modified output")
                elif change == "reference":
                    reference.write_bytes(b"modified reference")
                elif change == "config":
                    self.provider.config = {"model": "changed-model"}
                elif change == "account":
                    self.provider.account = "changed-account"
                elif change == "revoke":
                    with self.engine._tx() as db:
                        db.execute("UPDATE approvals SET revoked=1 WHERE project_id=?", (pid,))
                elif change == "plan":
                    value["project_name"] = "new plan"
                    self.engine.set_plan(pid, value)
                else:
                    self.engine.reject(pid, actor="human", shot_ids=["shot-001"])
                self.assertEqual(self.engine.status(pid)["status"], "plan_review")
                with self.assertRaises(WorkflowError):
                    self.engine.approve(pid, "storyboard", actor="human")
                self.provider.account = "account-1"
                if hasattr(self.provider, "config"):
                    del self.provider.config

    def test_plan_change_and_asset_change_invalidate_approval(self):
        reference = self.root / "reference.png"
        reference.write_bytes(b"first")
        value = plan(1)
        value["shots"][0]["reference_assets"] = [{"path": str(reference), "role": "identity"}]
        pid = self.engine.init_project("a")["project_id"]
        self.engine.set_plan(pid, value)
        self.engine.approve(pid, actor="human")
        reference.write_bytes(b"modified")
        self.assertEqual(self.engine.tick(pid)["status"], "plan_review")
        self.engine.set_plan(pid, value)
        self.assertEqual(self.engine.status(pid)["revision"], 2)
        self.assertFalse(self.provider.calls)

    def test_live_requires_explicit_mode_scope_account_budget_and_verified_identity(self):
        self.provider.live = True
        pid = self.create(1, mode="live")
        with self.assertRaises(WorkflowError):
            self.engine.approve(pid, actor="human")
        with self.assertRaises(WorkflowError):
            self.engine.approve(pid, actor="human", budget={"amount": "3", "currency": "CNY"})
        self.provider.verified = False
        with self.assertRaises(WorkflowError):
            self.engine.approve(pid, actor="human", budget={"amount": "3", "currency": "CNY"}, live_scope=self.scope(pid))
        self.provider.verified = True
        self.engine.approve(pid, actor="human", budget={"amount": "3", "currency": "CNY"}, live_scope=self.scope(pid))
        self.provider.account = "another-account"
        self.assertEqual(self.engine.tick(pid)["status"], "plan_review")
        self.assertFalse(self.provider.calls)

    def test_stage_budget_is_cumulative_and_survives_revision(self):
        self.provider.amount = "0.70"
        pid = self.create()
        self.engine.approve(pid, actor="human", budget={"amount": "1.00", "currency": "CNY"})
        for _ in range(8):
            state = self.engine.tick(pid)
        self.assertIn("budget", state["blocked_reason"])
        self.assertEqual(sum(n == "submit" for n, _ in self.provider.calls), 1)
        self.assertEqual(state["budgets"][0]["reserved_or_spent"], "0.70")
        self.engine.reject(pid, actor="human", stage="storyboard", shot_ids=["shot-001"])
        with self.assertRaises(WorkflowError):
            self.engine.approve(pid, actor="human", budget={"amount": "0.50", "currency": "CNY"})

    def test_different_currency_and_nonfinite_or_float_budget_refused(self):
        pid = self.create(1)
        for bad in ("NaN", "Infinity", "-1", 0.5, True):
            with self.assertRaises(WorkflowError):
                self.engine.approve(pid, actor="human", budget={"amount": bad, "currency": "CNY"})
        self.engine.approve(pid, actor="human", budget={"amount": "10", "currency": "CNY"})
        self.provider.currency = "DREAMINA_CREDITS"
        result = self.engine.tick(pid)
        self.assertIn("currencies", result["blocked_reason"])
        self.assertFalse(any(n == "prepare" for n, _ in self.provider.calls))

    def test_reject_specific_image_preserves_other_image_but_invalidates_approvals(self):
        pid = self.create()
        self.engine.approve(pid, actor="human")
        before = self.until(pid, "storyboard_review")
        self.engine.reject(pid, actor="human", stage="storyboard", shot_ids=["shot-002"], reason="bad face")
        after = self.engine.status(pid)
        self.assertEqual(after["shots"][0]["image"], before["shots"][0]["image"])
        self.assertIsNone(after["shots"][1]["image"])
        self.assertEqual(after["status"], "plan_review")
        with self.assertRaises(WorkflowError):
            self.engine.approve(pid, actor="human", expected_revision=1)

    def test_limits_bound_work(self):
        with self.assertRaises(WorkflowError):
            Limits(max_concurrent=999)
        with self.assertRaises(WorkflowError):
            self.engine.set_plan(self.engine.init_project("a")["project_id"], plan(25))

    def test_minimal_plan_freezes_defaults_and_spec_change_invalidates_approval(self):
        value = plan(1)
        pid = self.engine.init_project("two-shot product brief")["project_id"]
        state = self.engine.set_plan(pid, value)
        self.assertNotIn("aspect_ratio", value)  # caller's object is not edited
        self.assertNotIn("fps", value)
        self.assertEqual(state["plan"]["aspect_ratio"], "16:9")
        self.assertEqual(state["plan"]["fps"], 24)
        self.engine.approve(pid, actor="human")
        operation = self.engine.tick(pid)["operations"][0]
        self.assertEqual(operation["payload"]["ratio"], state["plan"]["aspect_ratio"])
        self.assertEqual(operation["payload"]["fps"], state["plan"]["fps"])
        changed = copy.deepcopy(state["plan"])
        changed["aspect_ratio"], changed["fps"] = "9:16", 25
        updated = self.engine.set_plan(pid, changed)
        self.assertNotEqual(updated["plan_hash"], state["plan_hash"])
        self.assertEqual(updated["status"], "plan_review")
        for key, bad_values in (("fps", [True, False, 0, 121, 24.0, "24", None]),
                                ("aspect_ratio", [None, "0:9", "16:0", "16/9", "-16:9", " 16:9 ", True])):
            for bad in bad_values:
                invalid = copy.deepcopy(changed)
                invalid[key] = bad
                with self.subTest(field=key, value=bad), self.assertRaises(WorkflowError):
                    self.engine.set_plan(pid, invalid)

    def test_local_plan_edit_retains_only_unchanged_approved_assets(self):
        pid = self.create()
        self.engine.approve(pid, actor="human")
        self.until(pid, "storyboard_review")
        self.engine.approve(pid, stage="storyboard", actor="human")
        before = self.until(pid, "final_review")
        changed = copy.deepcopy(before["plan"])
        changed["shots"][1]["image_prompt"] = "change only the rejected shot"
        after = self.engine.set_plan(pid, changed)
        self.assertEqual(after["status"], "plan_review")
        self.assertEqual(after["shots"][0]["image"], before["shots"][0]["image"])
        self.assertEqual(after["shots"][0]["video"], before["shots"][0]["video"])
        self.assertIsNone(after["shots"][1]["image"])
        self.assertIsNone(after["shots"][1]["video"])
        self.assertIsNone(after["final_artifact"])
        changed["aspect_ratio"] = "9:16"
        after = self.engine.set_plan(pid, changed)
        self.assertTrue(all(s["image"] is None for s in after["shots"]))

    def test_state_permissions_and_distribution_guard(self):
        self.assertEqual(stat.S_IMODE((self.root / "jobs.sqlite3").stat().st_mode), 0o600)
        for suffix in ("-wal", "-shm"):
            sidecar = self.root / ("jobs.sqlite3" + suffix)
            if sidecar.exists():
                self.assertEqual(stat.S_IMODE(sidecar.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.root / "assets").stat().st_mode), 0o700)
        parent = self.root / "existing-user-directory"
        parent.mkdir(mode=0o755)
        before = stat.S_IMODE(parent.stat().st_mode)
        extra = Engine(parent / "private.sqlite3", {"mock": self.provider})
        extra.close()
        self.assertEqual(stat.S_IMODE(parent.stat().st_mode), before)
        distribution = Path(__file__).resolve().parents[1]
        with self.assertRaises(WorkflowError):
            Engine(distribution / "must-not-create.sqlite3", {"mock": self.provider})
        self.assertFalse((distribution / "must-not-create.sqlite3").exists())

    def test_account_change_after_prepare_revokes_approval_even_if_restored(self):
        self.provider.live = True
        pid = self.create(1, mode="live")
        self.engine.approve(pid, actor="human", budget={"amount": "1", "currency": "CNY"}, live_scope=self.scope(pid))
        original_prepare = self.provider.prepare
        def switched(operation):
            result = original_prepare(operation)
            self.provider.account = "account-2"
            return result
        self.provider.prepare = switched
        result = self.engine.tick(pid)
        self.assertEqual(result["status"], "plan_review")
        self.provider.account = "account-1"
        self.assertEqual(self.engine.tick(pid)["status"], "plan_review")
        self.assertFalse(any(n == "submit" for n, _ in self.provider.calls))

    def test_unknown_initial_quote_reserves_whole_stage_before_prepare(self):
        self.provider.live = True
        pid = self.create(1, mode="live")
        self.engine.approve(pid, actor="human", budget={"amount": "7", "currency": "CNY"}, live_scope=self.scope(pid))
        self.provider.quote = lambda op: {"amount": None if not op["payload"].get("node_id") else "2", "currency": "CNY"}
        original_prepare = self.provider.prepare
        observed = []
        def observe(operation):
            observed.append(operation["reserved_amount"])
            return original_prepare(operation)
        self.provider.prepare = observe
        self.engine.tick(pid)
        self.assertEqual(observed, ["7"])
        self.engine.tick(pid)
        self.assertEqual(self.engine.status(pid)["budgets"][0]["reserved_or_spent"], "2")

    def test_quote_setup_refusal_can_resume_without_new_operation(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        ordinary = self.provider.quote
        self.provider.quote = lambda op: {"status": "needs_setup", "amount": None, "currency": "CNY"}
        state = self.engine.tick(pid)
        operation = state["operations"][0]
        self.assertFalse(any(n == "prepare" for n, _ in self.provider.calls))
        self.provider.quote = ordinary
        resumed = self.engine.resume(pid, operation["operation_id"], actor="human")
        self.assertEqual(resumed["resume_action"], "quote_only_preflight")
        self.until(pid, "storyboard_review")
        self.assertEqual(len(self.engine.status(pid)["operations"]), 1)

    def test_explicit_not_submitted_receipt_reuses_saved_node(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        self.engine.tick(pid)
        ordinary = self.provider.submit
        self.provider.submit = lambda op: {"status": "needs_approval", "not_submitted": True,
            "awaiting_confirmation": True, "payload": {"saved": True, "not_submitted": True, "awaiting_confirmation": True}}
        state = self.engine.tick(pid)
        operation = state["operations"][0]
        self.provider.submit = ordinary
        self.engine.approve(pid, actor="human")
        result = self.engine.resume(pid, operation["operation_id"], actor="human")
        self.assertEqual(result["resume_action"], "same_saved_node_after_approval")
        self.until(pid, "storyboard_review")
        self.assertEqual(sum(n == "prepare" for n, _ in self.provider.calls), 1)

    def test_ambiguous_needs_approval_can_only_resume_poll(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        self.engine.tick(pid)
        self.provider.submit = lambda op: {"status": "needs_approval", "message": "submission may have happened"}
        operation = self.engine.tick(pid)["operations"][0]
        result = self.engine.resume(pid, operation["operation_id"], actor="human")
        self.assertEqual(result["resume_action"], "poll_only_no_write_retry")
        self.provider.poll_state = "unknown"
        self.engine.tick(pid)
        self.assertEqual(self.provider.calls[-1][0], "poll")
        self.assertEqual(sum(n == "prepare" for n, _ in self.provider.calls), 1)

    def test_old_not_submitted_receipt_cannot_authorize_retry_after_lost_reply(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        self.engine.tick(pid)
        ordinary = self.provider.submit
        self.provider.submit = lambda op: {"status": "needs_approval", "not_submitted": True,
            "awaiting_confirmation": True, "payload": {"saved": True, "not_submitted": True, "awaiting_confirmation": True}}
        operation = self.engine.tick(pid)["operations"][0]
        self.engine.resume(pid, operation["operation_id"], actor="human")
        self.provider.submit = ordinary
        self.provider.raise_submit = True
        self.engine.tick(pid)
        result = self.engine.resume(pid, operation["operation_id"], actor="human")
        self.assertEqual(result["resume_action"], "poll_only_no_write_retry")

    def test_cli_text_brief_and_draft_default_do_not_call_a_model(self):
        brief = self.root / "brief.txt"
        brief.write_text("为新手做一支20秒产品视频。", encoding="utf-8")
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/director_workflow.py"),
                   "--db", str(self.root / "cli.sqlite3")]
        initialized = subprocess.run(command + ["init", "--brief-file", str(brief)], capture_output=True, text=True, check=True)
        project = json.loads(initialized.stdout)
        self.assertEqual(project["brief"], brief.read_text())
        drafted = subprocess.run(command + ["draft", project["project_id"], "--brief-file", str(brief)], capture_output=True, text=True, check=True)
        response = json.loads(drafted.stdout)
        self.assertEqual(response["status"], "needs_approval")
        self.assertEqual(response["reason"], "model_usage_not_authorized")

    def test_final_asset_replacement_refuses_acceptance(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        self.until(pid, "storyboard_review")
        self.engine.approve(pid, stage="storyboard", actor="human")
        state = self.until(pid, "final_review")
        Path(state["final_artifact"]["path"]).write_text("replaced")
        with self.assertRaises(WorkflowError):
            self.engine.approve(pid, stage="final", actor="human")

    def composition_ready(self):
        pid = self.create(2)
        self.engine.approve(pid, actor="human")
        self.until(pid, "storyboard_review")
        self.engine.approve(pid, stage="storyboard", actor="human")
        self.until(pid, "ready_to_compose")
        return pid

    def test_composition_reason_is_delivered_once_and_restart_does_not_repeat_it(self):
        pid = self.composition_ready()
        before = self.engine.status(pid)
        provider_calls = list(self.provider.calls)
        compositor_calls = []
        def refused(operation):
            compositor_calls.append(operation["operation_id"])
            return {"status": "needs_review", "reason": "fps_differs_from_plan_no_automatic_retime",
                    "message": "RAW-SECRET-MESSAGE", "stderr": "RAW-SECRET-STDERR", "path": "/private/secret"}
        self.engine.compositor = refused
        for _ in range(3):
            result = self.engine.tick(pid)
            self.assertEqual(result["blocked_reason"], "fps_differs_from_plan_no_automatic_retime")
        notices = [event for event in self.channel.events if event["type"] == "composition_failed"]
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["message"], "本地成片合成需要处理，请回电脑检查素材规格并选择处理方式。")
        self.assertEqual(notices[0]["artifacts"], [])
        self.assertEqual(notices[0]["reason"], "fps_differs_from_plan_no_automatic_retime")
        rows = self.engine.db.execute("SELECT id,payload,delivered FROM events WHERE type='composition_failed'").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], notices[0]["event_id"])
        self.assertEqual(json.loads(rows[0]["payload"])["event_id"], rows[0]["id"])
        self.assertEqual(rows[0]["delivered"], 1)
        self.assertNotIn("SECRET", rows[0]["payload"])
        self.assertNotIn("/private/secret", rows[0]["payload"])
        self.engine.close()
        self.engine = self.open_engine()
        self.engine.compositor = refused
        self.assertEqual(self.engine.tick(pid)["blocked_reason"], "fps_differs_from_plan_no_automatic_retime")
        self.assertEqual(len([event for event in self.channel.events if event["type"] == "composition_failed"]), 1)
        self.assertEqual(len(compositor_calls), 4)  # No hidden pause/retry policy.
        after = self.engine.status(pid)
        for field in ("operations", "budgets", "shots", "revision", "plan_hash"):
            self.assertEqual(after[field], before[field])
        self.assertEqual(self.provider.calls, provider_calls)

    def test_composition_unknown_reason_is_sanitized_without_leaking_callback_fields(self):
        pid = self.composition_ready()
        before = self.engine.status(pid)
        provider_calls = list(self.provider.calls)
        for reason in (None, {"secret": "HIDDEN"}, "/private/secret", "lowercase_secret_token",
                       "fps_differs_from_plan_no_automatic_retime\nHIDDEN", "x" * 129):
            self.engine.compositor = lambda operation, value=reason: {
                "status": "needs_review", "reason": value, "message": "HIDDEN-MESSAGE", "stderr": "HIDDEN-STDERR"}
            result = self.engine.tick(pid)
            self.assertEqual(result["blocked_reason"], "composition_failed")
        rows = self.engine.db.execute("SELECT payload FROM events WHERE type='composition_failed'").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0]["payload"])["reason"], "composition_failed")
        for forbidden in ("HIDDEN", "/private/secret", "lowercase_secret_token"):
            self.assertNotIn(forbidden, rows[0]["payload"])
        self.assertEqual(self.provider.calls, provider_calls)
        self.assertEqual(self.engine.status(pid)["budgets"], before["budgets"])

    def test_composition_notification_changes_for_reason_revision_and_approved_video_hash(self):
        pid = self.composition_ready()
        provider_calls = list(self.provider.calls)
        self.engine.compositor = lambda operation: {"status": "needs_review", "reason": "media_probe_failed"}
        self.engine.tick(pid)
        self.engine.compositor = lambda operation: {"status": "needs_review", "reason": "incompatible_streams_no_automatic_transcode"}
        self.engine.tick(pid)
        # A completed-output fixture is replaced with a separately approved hash,
        # without changing project/revision, to exercise asset-key sensitivity.
        state = self.engine.status(pid)
        asset = dict(state["shots"][0]["video"])
        replacement = self.root / "approved-replacement.mock"
        replacement.write_bytes(b"a new approved local completed-output fixture")
        import hashlib
        asset.update(path=str(replacement), size=replacement.stat().st_size,
                     sha256=hashlib.sha256(replacement.read_bytes()).hexdigest())
        with self.engine._tx() as db:
            db.execute("UPDATE shots SET video=? WHERE project_id=? AND id=?", (json.dumps(asset), pid, "shot-001"))
        self.engine.tick(pid)
        unchanged = self.engine.status(pid)
        revised = copy.deepcopy(unchanged["plan"])
        revised["project_name"] = "new reviewed plan with existing clips"
        self.engine.set_plan(pid, revised)
        self.engine.approve(pid, actor="human")
        self.engine.approve(pid, stage="storyboard", actor="human")
        self.engine.tick(pid)
        notices = [event for event in self.channel.events if event["type"] == "composition_failed"]
        self.assertEqual(len(notices), 4)
        self.assertEqual(len({event["event_id"] for event in notices}), 4)
        self.assertEqual(self.provider.calls, provider_calls)

    def test_composition_without_channel_persists_one_notice_and_later_delivers_it(self):
        pid = self.composition_ready()
        self.engine.channel = None
        self.engine.compositor = lambda operation: {"status": "needs_review", "reason": "media_probe_failed"}
        for _ in range(2):
            self.assertEqual(self.engine.tick(pid)["blocked_reason"], "media_probe_failed")
        self.assertFalse(any(event["type"] == "composition_failed" for event in self.channel.events))
        rows = self.engine.db.execute("SELECT delivered FROM events WHERE type='composition_failed'").fetchall()
        self.assertEqual([row["delivered"] for row in rows], [0])
        self.engine.channel = self.channel
        self.engine.tick(pid)
        self.engine.tick(pid)
        self.assertEqual(len([event for event in self.channel.events if event["type"] == "composition_failed"]), 1)

    def test_second_process_cannot_submit_same_operation_twice(self):
        pid = self.create(1)
        self.engine.approve(pid, actor="human")
        other = self.open_engine()
        self.addCleanup(other.close)
        self.engine.tick(pid)
        other.tick(pid)
        self.engine.tick(pid)
        other.tick(pid)
        self.assertEqual(sum(n == "prepare" for n, _ in self.provider.calls), 1)
        self.assertEqual(sum(n == "submit" for n, _ in self.provider.calls), 1)

    def normalization_ready(self):
        value = plan(2)
        value["composition"] = {"mode": "normalize_cfr"}
        pid = self.engine.init_project("offline local processing fixture")["project_id"]
        self.engine.set_plan(pid, value)
        self.engine.approve(pid, actor="human")
        self.until(pid, "storyboard_review")
        self.engine.approve(pid, "storyboard", actor="human")
        self.until(pid, "composition_review")
        return pid

    def mock_local_compositor(self, operations, before_return=None):
        def compose(operation):
            operations.append(operation)
            if before_return:
                before_return(operation)
            output = Path(operation["output_dir"]) / "explicitly-simulated-normalization.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({"simulated": True, "operation_id": operation["operation_id"]}))
            return {"status": "succeeded", "path": str(output), "simulated": True}
        self.engine.compositor = compose

    def test_normalization_plan_policy_is_strict_and_copy_remains_default(self):
        pid = self.create(1)
        self.assertNotIn("composition", self.engine.status(pid)["plan"])
        with self.assertRaises(WorkflowError):
            self.engine.approve(pid, "composition", actor="human")
        for bad in (None, True, "normalize_cfr", {}, {"mode": "unknown"},
                    {"mode": "normalize_cfr", "authorized": True}, {"mode": "stream_copy", "fps": 30}):
            value = plan(1)
            value["composition"] = bad
            with self.subTest(bad=bad), self.assertRaises(WorkflowError):
                self.engine.set_plan(pid, value)

    def test_normalization_waits_for_distinct_fresh_zero_cost_local_approval(self):
        pid = self.normalization_ready()
        operations = []
        self.mock_local_compositor(operations)
        before_calls = list(self.provider.calls)
        before_budget = self.engine.status(pid)["budgets"]
        self.clock.now += 3601  # completed content reviews may expire, local permission may not
        for _ in range(3):
            self.assertEqual(self.engine.tick(pid)["status"], "composition_review")
        self.assertEqual(operations, [])
        reviews = [e for e in self.channel.events if e["type"] == "composition_review"]
        self.assertEqual(len(reviews), 1)
        event = reviews[0]
        self.assertEqual(event["approval_scope"]["stages"], [])
        self.assertIs(event["approval_scope"]["allow_uploads"], False)
        self.assertEqual(event["budget"]["amount"], "0")
        for bad_scope, bad_budget in (({**event["approval_scope"], "stages": ["video"]}, None),
                                      ({**event["approval_scope"], "allow_uploads": True}, None),
                                      (event["approval_scope"], {"amount": "1", "currency": "CNY"})):
            with self.assertRaises(WorkflowError):
                self.engine.approve(pid, "composition", actor="human", live_scope=bad_scope, budget=bad_budget)
        self.engine.approve(pid, "composition", actor="human", ttl_seconds=1)
        self.clock.now += 2
        self.assertEqual(self.engine.tick(pid)["status"], "composition_review")
        self.assertEqual(operations, [])
        self.engine.approve(pid, "composition", actor="human")
        state = self.engine.tick(pid)
        self.assertEqual(state["status"], "final_review")
        self.assertEqual(len(operations), 1)
        token = operations[0]["normalization_authorized"]
        self.assertEqual(set(token), {"plan_hash", "inputs_hash", "policy_hash"})
        self.assertEqual(token["plan_hash"], state["plan_hash"])
        self.assertFalse(self.engine._generation_allowed(self.engine._project(pid), "composition"))
        self.assertEqual(self.provider.calls, before_calls)
        self.assertEqual(state["budgets"], before_budget)
        self.engine.close()
        self.engine = self.open_engine()
        self.mock_local_compositor(operations)
        self.assertEqual(self.engine.tick(pid)["status"], "final_review")
        self.assertEqual(len(operations), 1)

    def test_normalization_rejection_preserves_assets_and_invalidates_old_phone_challenge(self):
        pid = self.normalization_ready()
        self.engine.tick(pid)
        before = self.engine.status(pid)
        binding = before["bindings"]["composition"]
        calls = list(self.provider.calls)
        self.engine.reject(pid, "composition", actor="human", expected_binding_hash=binding["binding_hash"])
        after = self.engine.status(pid)
        self.assertEqual(after["status"], "composition_rejected")
        self.assertEqual(after["revision"], before["revision"])
        self.assertEqual(after["shots"], before["shots"])
        self.assertEqual(after["budgets"], before["budgets"])
        self.assertNotEqual(after["bindings"]["composition"]["binding_hash"], binding["binding_hash"])
        for _ in range(3):
            self.engine.tick(pid)
        self.assertEqual(len([e for e in self.channel.events if e["type"] == "composition_review"]), 1)
        with self.assertRaisesRegex(WorkflowError, "changed"):
            self.engine.approve(pid, "composition", actor="phone", expected_binding_hash=binding["binding_hash"])
        self.assertEqual(self.provider.calls, calls)
        self.engine.approve(pid, "composition", actor="local-human")
        operations = []
        self.mock_local_compositor(operations)
        self.assertEqual(self.engine.tick(pid)["status"], "final_review")
        self.assertEqual(len(operations), 1)

    def test_normalization_changed_plan_order_and_source_bytes_invalidate_permission(self):
        pid = self.normalization_ready()
        self.engine.approve(pid, "composition", actor="human")
        previous = self.engine.status(pid)
        changed = copy.deepcopy(previous["plan"])
        changed["shots"].reverse()
        after = self.engine.set_plan(pid, changed)
        self.assertEqual([s["video"] for s in after["shots"]], [s["video"] for s in reversed(previous["shots"])])
        self.assertIsNone(self.engine._composition_approval(self.engine._project(pid)))
        self.engine.approve(pid, actor="human")
        self.engine.approve(pid, "storyboard", actor="human")
        self.engine.approve(pid, "composition", actor="human")
        video = self.engine.status(pid)["shots"][0]["video"]
        Path(video["path"]).write_text("changed fixture bytes")
        operations = []
        self.mock_local_compositor(operations)
        self.assertIsNone(self.engine._composition_approval(self.engine._project(pid)))
        self.assertIn("changed", self.engine.tick(pid)["blocked_reason"])
        self.assertEqual(operations, [])

    def test_normalization_policy_only_edit_reuses_generation_but_requires_new_permission(self):
        pid = self.composition_ready()
        before = self.engine.status(pid)
        calls = list(self.provider.calls)
        changed = copy.deepcopy(before["plan"])
        changed["composition"] = {"mode": "normalize_cfr"}
        after = self.engine.set_plan(pid, changed)
        self.assertEqual([s["video"] for s in after["shots"]], [s["video"] for s in before["shots"]])
        self.assertNotEqual(after["plan_hash"], before["plan_hash"])
        self.engine.approve(pid, actor="human")
        self.engine.approve(pid, "storyboard", actor="human")
        operations = []
        self.mock_local_compositor(operations)
        self.assertEqual(self.engine.tick(pid)["status"], "composition_review")
        self.assertEqual(operations, [])
        self.assertEqual(self.provider.calls, calls)

    def test_normalization_post_callback_input_change_or_revocation_cannot_attach_final(self):
        for change in ("source", "revoke", "order"):
            with self.subTest(change=change):
                pid = self.normalization_ready()
                self.engine.approve(pid, "composition", actor="human")
                def mutate(operation):
                    if change == "source":
                        Path(operation["inputs"][0]["path"]).write_text("changed during local callback")
                    elif change == "revoke":
                        self.engine.db.execute("UPDATE approvals SET revoked=1 WHERE project_id=? AND stage='composition'", (pid,))
                    else:
                        self.engine.db.execute("UPDATE shots SET ordinal=99-ordinal WHERE project_id=?", (pid,))
                operations = []
                self.mock_local_compositor(operations, mutate)
                state = self.engine.tick(pid)
                self.assertIn("changed while composing", state["blocked_reason"])
                self.assertIsNone(state["final_artifact"])

    def test_normalization_expired_unsent_review_does_not_block_fresh_notification(self):
        pid = self.normalization_ready()
        self.engine.channel = None
        self.engine.tick(pid)
        self.clock.now += 3601
        self.engine.channel = self.channel
        self.engine.tick(pid)
        reviews = [event for event in self.channel.events if event["type"] == "composition_review"]
        self.assertEqual(len(reviews), 1)
        self.assertGreater(reviews[0]["expires_at"], self.clock())
        rows = self.engine.db.execute("SELECT delivered FROM events WHERE type='composition_review'").fetchall()
        self.assertEqual([row["delivered"] for row in rows], [1, 1])


if __name__ == "__main__":
    unittest.main()
