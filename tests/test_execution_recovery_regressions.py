"""Exercise real state transitions using a fake official CLI and offline media."""

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_workflow_providers import CLI, DreaminaCanvasProvider
from hc_workflow.compositor import assemble
from hc_workflow.engine import Engine


class ExecutionRecoveryTests(unittest.TestCase):
    settings = {"model": "live-model", "mode": "t2i", "ratio": "16:9", "resolution": "720p"}

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.cli = CLI()

    def create(self, *, configured=True):
        self.config = {"project_id": "canvas-original"}
        if configured:
            self.config["image"] = dict(self.settings)
        self.provider = DreaminaCanvasProvider(self.config, runner=self.cli)
        self.engine = self.open_engine()
        self.addCleanup(lambda: self.engine.close())
        self.pid = self.engine.init_project("offline recovery", mode="live")["project_id"]
        self.plan = {"shots": [{"id": "one", "duration_seconds": 4, "image_prompt": "a cup", "video_prompt": "a slow cup"}],
                     "providers": {"image": "dreamina-canvas", "video": "dreamina-canvas"}}
        self.engine.set_plan(self.pid, self.plan)
        self.approve()

    def open_engine(self):
        return Engine(self.root / "state.sqlite3", providers={"dreamina-canvas": self.provider}, artifact_dir=self.root / "artifacts")

    def approve(self):
        binding = self.engine.status(self.pid)["bindings"]["plan"]
        scope = {key: binding[key] for key in ("revision", "plan_hash", "asset_hash")}
        scope.update(stages=["image"], provider="dreamina-canvas", account=self.provider.identity()["account"], allow_uploads=True)
        self.engine.approve(self.pid, actor="human", budget={"amount": "40", "currency": "DREAMINA_CREDITS"}, live_scope=scope)

    def calls(self, action):
        return [args for args in self.cli.calls if tuple(args[:2]) == action]

    def test_reapproving_configuration_cannot_reuse_old_draft_even_in_legacy_database(self):
        self.create()
        draft = self.engine.tick(self.pid)["operations"][0]
        self.assertEqual(draft["status"], "prepared")
        persisted = self.engine._op(draft["id"])["payload"]
        persisted.pop("execution_config_hash")
        self.engine.db.execute("UPDATE operations SET payload=? WHERE id=?", (json.dumps(persisted), draft["id"]))
        self.provider.config["project_id"] = "canvas-new"
        self.approve()
        refusal = self.engine.tick(self.pid)
        self.assertIn("execution configuration changed", refusal["blocked_reason"])
        self.assertEqual(self.calls(("node", "run")), [])
        self.engine.set_plan(self.pid, self.plan)
        self.approve()
        self.engine.tick(self.pid)
        self.engine.tick(self.pid)
        [run] = self.calls(("node", "run"))
        self.assertEqual(run[run.index("--project-id") + 1], "canvas-new")

    def test_known_preflight_refusal_can_resume_same_id_after_configuration_fix(self):
        self.create(configured=False)
        refused = self.engine.tick(self.pid)["operations"][0]
        self.assertEqual(refused["status"], "needs_setup")
        self.assertEqual(refused["result"]["payload"]["side_effects"], "none")
        self.assertEqual(self.calls(("node", "create")), [])
        # Exercise legacy rows whose exact local error predated the marker.
        row = self.engine._op(refused["id"])
        del row["result"]["payload"]
        row["payload"].pop("side_effects")
        self.engine.db.execute("UPDATE operations SET payload=?,result=? WHERE id=?",
                               (json.dumps(row["payload"]), json.dumps(row["result"]), row["id"]))
        self.provider.config["image"] = dict(self.settings)
        self.approve()
        self.assertEqual(self.engine.resume(self.pid, refused["id"])["resume_action"], "provider_proved_no_side_effects")
        [draft] = self.engine.tick(self.pid)["operations"]
        self.assertEqual((draft["id"], draft["status"], draft["task_id"]), (refused["id"], "prepared", None))
        self.assertEqual(len(self.calls(("node", "create"))), 1)

    def test_unknown_save_keeps_polling_original_node_without_fabricating_task_id(self):
        self.create()
        self.cli.state = "absent"
        self.cli.timeout_action = ("node", "create")
        op = self.engine.tick(self.pid)["operations"][0]
        self.assertEqual(op["status"], "unknown")
        self.cli.timeout_action = None
        result = self.engine.tick(self.pid)["operations"][0]
        self.assertEqual(result["result"]["error_code"], "preparation_unresolved")
        self.assertIsNone(result["task_id"])
        self.cli.node = self.provider._facts(self.engine._op(op["id"]))["node_id"]
        # 3.0.0 also stored the derived submit ID in this exact case.
        legacy = {**result["result"], "error_code": "submission_unresolved", "task_id": result["result"]["submit_id"]}
        legacy_json = json.dumps(legacy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.engine.db.execute("UPDATE operations SET result=?,task_id=? WHERE id=?", (legacy_json, legacy["task_id"], op["id"]))
        recovered = self.engine.tick(self.pid)["operations"][0]
        self.assertEqual((recovered["status"], recovered["task_id"]), ("prepared", None))
        self.assertEqual(len(self.calls(("node", "create"))), 1)
        self.assertEqual(self.calls(("node", "run")), [])

    def test_download_recovers_lost_reply_and_preexisting_verified_file_after_restart(self):
        self.create()
        self.cli.state = "completed"
        self.cli.resources = [{"resourceId": "resource-one", "state": "succeeded"}]
        for _ in range(3):
            result = self.engine.tick(self.pid)
        operation = result["operations"][0]
        self.assertEqual(operation["status"], "generated")

        def lose_reply(command, **kwargs):
            data = self.cli(command, **kwargs)
            if tuple(command[6:8]) == ("resource", "download"):
                raise subprocess.TimeoutExpired("redacted", 1)
            return data

        with patch.object(self.provider, "runner", lose_reply):
            failed = self.engine.tick(self.pid)["operations"][0]
        self.assertEqual(failed["status"], "generated")
        self.assertEqual(list((self.root / "artifacts").rglob("*.png")), [])
        published = self.provider.download(self.engine._op(operation["id"]))
        self.assertEqual(published["status"], "downloaded")
        self.engine.close()
        self.engine = self.open_engine()
        recovered = self.engine.tick(self.pid)["operations"][0]
        self.assertEqual(recovered["status"], "done")
        self.assertEqual(recovered["result"]["sha256"], published["sha256"])
        self.assertEqual(len(self.calls(("node", "run"))), 1)


class CompositionRecoveryTests(unittest.TestCase):
    def test_stream_copy_can_restore_receipt_after_interrupted_link_and_reuse_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.mp4"
            source.write_bytes(b"synthetic source")
            output = root / "out"
            operation = {"operation_id": "offline-composition", "mode": "live", "output_dir": str(output),
                         "plan": {"fps": 24, "aspect_ratio": "16:9"},
                         "inputs": [{"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                                     "duration_seconds": 1, "shot_id": "one"}]}
            probe = {"signature": "matching", "duration_seconds": 1, "fps": "24", "width": 320, "height": 180}

            def ffmpeg(command, **kwargs):
                Path(command[-1]).write_bytes(b"synthetic assembled bytes")
                return subprocess.CompletedProcess(command, 0)

            link = os.link

            def stop_before_receipt(source, target):
                if target.name == "assembly-report.json":
                    raise KeyboardInterrupt("simulate interruption outside ordinary exception cleanup")
                return link(source, target)

            with patch("hc_workflow.compositor.shutil.which", return_value="fixture"), patch("hc_workflow.compositor._probe", return_value=probe):
                with patch("hc_workflow.compositor.os.link", side_effect=stop_before_receipt):
                    with self.assertRaises(KeyboardInterrupt):
                        assemble(operation, runner=ffmpeg)
                self.assertTrue((output / "assembled.mp4").is_file())
                self.assertFalse((output / "assembly-report.json").exists())
                no_render = lambda *_args, **_kwargs: self.fail("recovery must not rerender")
                recovered = assemble(operation, runner=no_render)
                self.assertEqual(recovered["status"], "succeeded")
                self.assertEqual(json.loads((output / "assembly-report.json").read_text()), recovered)
                self.assertEqual(assemble(operation, runner=no_render), recovered)
                self.assertEqual(assemble({**operation, "operation_id": "different"}, runner=no_render)["reason"],
                                 "output_exists_not_overwritten")
