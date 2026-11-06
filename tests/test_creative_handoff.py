"""Creative contract tests; no media, model, account or network calls."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from creative_handoff import HandoffError, expected_source_hashes, main, to_workflow_plan, validate_packet
from hc_workflow.engine import Engine, Limits


class NoActionProvider:
    def __init__(self):
        self.calls = []
        self.config = {}

    def identity(self):
        return {"provider": "SYNTHETIC_TEST", "account": "SYNTHETIC_TEST", "live": False, "verified": True}

    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            self.calls.append(name)
            raise AssertionError("provider action is outside the creative draft")
        return forbidden


class CreativeHandoffTests(unittest.TestCase):
    def packet(self):
        return json.loads((ROOT / "references/support/creative-handoff.example.json").read_text())

    def authored_fixture(self, packet):
        # Test-authoring only, to isolate structural rules after a mutation.
        # The shipped CLI never rewrites digests or supplies human acceptance.
        for stage, digest in expected_source_hashes(packet).items():
            packet[stage]["source_hash"] = digest
        return packet

    def assert_code(self, packet, code, references=None):
        result = validate_packet(packet, references=references)
        self.assertFalse(result["valid"], result)
        self.assertIn(code, {issue["code"] for issue in result["issues"]}, result)
        with self.assertRaises(HandoffError):
            to_workflow_plan(packet, references=references)
        return result

    def test_complete_example_exports_only_unapproved_supported_workflow_fields(self):
        packet = self.packet()
        result = validate_packet(packet)
        self.assertTrue(result["valid"], result)
        self.assertFalse(result["readiness"]["render_ready"])
        self.assertFalse(result["readiness"]["generation_authorized"])
        self.assertIn("platform_prompt_syntax", result["not_checked"])
        plan = to_workflow_plan(packet)
        self.assertEqual(plan["budget"], {"amount": "0", "currency": "UNAPPROVED"})
        self.assertEqual(plan["providers"], {"image": "mock", "video": "mock"})
        self.assertNotIn("requested_live_scopes", plan)
        self.assertNotIn("composition", plan)
        self.assertEqual(sum(s["duration_seconds"] for s in plan["shots"]), 40)
        self.assertEqual([s["id"] for s in plan["shots"]], ["S01", "S02", "S03", "S04"])

    def test_script_edit_invalidates_all_downstream_handoffs(self):
        packet = self.packet()
        packet["script"]["screenplay"] += "\n新的结尾。"
        result = self.assert_code(packet, "stale_source")
        stale = {x["stage"] for x in result["issues"] if x["code"] == "stale_source"}
        self.assertEqual(stale, {"direction", "storyboard", "audio", "prompts", "editorial"})
        self.assertTrue(all(x["return_to"] == x["stage"] for x in result["issues"]))

    def test_direction_edit_does_not_revalidate_its_downstream_from_old_hashes(self):
        packet = self.packet()
        packet["direction"]["shots"][0]["camera_intent"] = "改为主观视角。"
        result = self.assert_code(packet, "stale_source")
        self.assertEqual({x["stage"] for x in result["issues"] if x["code"] == "stale_source"},
                         {"storyboard", "audio", "prompts", "editorial"})

    def test_old_shot_or_unknown_beat_cannot_pass_even_with_new_digests(self):
        for field, value in [("id", "OLD_SHOT"), ("beat_ids", ["UNKNOWN_BEAT"])]:
            with self.subTest(field=field):
                packet = self.packet()
                packet["storyboard"]["board"]["shots"][0][field] = value
                result = validate_packet(self.authored_fixture(packet))
                self.assertFalse(result["valid"])
                self.assertTrue(any(x["stage"] == "storyboard" for x in result["issues"]))

    def test_left_right_lock_drift_is_not_hidden_by_recomputing_hashes(self):
        packet = self.packet()
        for section in (packet["direction"]["shots"], packet["storyboard"]["board"]["shots"]):
            section[0]["start_state"]["envelope.hand"] = "left"
        self.assert_code(self.authored_fixture(packet), "locked_state_drift")

    def test_board_must_inherit_direction_states(self):
        packet = self.packet()
        packet["storyboard"]["board"]["shots"][3]["end_state"]["envelope.owner"] = "LIN"
        self.assert_code(self.authored_fixture(packet), "direction_drift")

    def test_project_ratio_total_and_fps_constrain_existing_board_gate(self):
        for field, value, code in [("aspect_ratio", "9:16", "storyboard_gate"),
                                   ("total_frames", 984, "storyboard_gate"),
                                   ("fps", 30, "fps_drift")]:
            with self.subTest(field=field):
                packet = self.packet()
                packet["project"][field] = value
                self.assert_code(self.authored_fixture(packet), code)

    def test_creative_packet_checks_default_shot_limit_before_export(self):
        limit = Limits().max_shots
        for count in (limit, limit + 1):
            with self.subTest(count=count):
                packet = self.packet()
                board = packet["storyboard"]["board"]
                packet["project"]["total_frames"] = board["total_frames"] = count * 25
                beat = packet["script"]["beats"][0]
                packet["script"]["beats"], board["beats"] = [], []
                packet["audio"]["cues"] = []
                direction, shot, prompt, event = (
                    packet["direction"]["shots"][0], board["shots"][0],
                    packet["prompts"]["shots"][0], packet["editorial"]["events"][0])
                packet["direction"]["shots"], board["shots"] = [], []
                packet["prompts"]["shots"], packet["editorial"]["events"] = [], []
                for i in range(count):
                    shot_id = f"S{i + 1:02d}"
                    beat_id = f"B{i + 1:02d}"
                    packet["script"]["beats"].append({**beat, "id": beat_id, "dialogue": []})
                    board["beats"].append({"id": beat_id})
                    window = {"start_frame": i * 25, "end_frame": (i + 1) * 25}
                    packet["direction"]["shots"].append({**direction, "shot_id": shot_id, "beat_ids": [beat_id]})
                    board["shots"].append({**shot, **window, "id": shot_id, "beat_ids": [beat_id], "dialogue": []})
                    packet["prompts"]["shots"].append({**prompt, "shot_id": shot_id, "dialogue_ids": [],
                                                        "cue_ids": [], "cue_bindings": []})
                    packet["editorial"]["events"].append({**event, **window, "shot_id": shot_id,
                                                          "beat_ids": [beat_id], "cue_ids": []})
                self.authored_fixture(packet)
                if count == limit:
                    report = validate_packet(packet)
                    self.assertTrue(report["valid"], report)
                    plan = to_workflow_plan(packet)
                    self.assertEqual(len(plan["shots"]), limit)
                    self.assertEqual(plan["shots"][0]["duration_seconds"], 25 / 24)
                else:
                    report = self.assert_code(packet, "shot_count_limit")
                    self.assertFalse(report["readiness"]["workflow_draft_exportable"])

    def test_cue_out_of_bounds_or_undeclared_bridge_is_refused(self):
        for operation in ("end", "bridge", "gap"):
            with self.subTest(operation=operation):
                packet = self.packet()
                cue = next(c for c in packet["audio"]["cues"] if c["id"] == "C_ROOM")
                if operation == "end":
                    cue["end_frame"] += 1
                elif operation == "bridge":
                    cue["bridge"] = False
                else:
                    cue["shot_ids"] = ["S01", "S04"]
                self.assert_code(self.authored_fixture(packet), "cue_window")

    def test_generation_and_post_cues_need_their_actual_consumers(self):
        for stage in ("prompts", "editorial"):
            with self.subTest(stage=stage):
                packet = self.packet()
                entry = packet[stage]["shots" if stage == "prompts" else "events"][0]
                entry["cue_ids"] = []
                self.assert_code(self.authored_fixture(packet), "cue_consumption")

    def test_sound_cue_metadata_without_its_actual_prompt_text_is_not_consumption(self):
        packet = self.packet()
        cue = {"id": "C_RUSTLE", "shot_ids": ["S01"], "beat_ids": ["B01"], "kind": "foley",
               "placement": "generation", "start_frame": 0, "end_frame": 24, "bridge": False,
               "intent": "轻纸面摩擦声。", "dialogue_id": None, "source_asset_id": None,
               "source_kind": "native", "evidence_status": "planned", "rights_note": "无外部素材，不授权生成。"}
        packet["audio"]["cues"].append(cue)
        prompt = packet["prompts"]["shots"][0]
        prompt["cue_ids"].append(cue["id"])
        prompt["cue_bindings"].append({"cue_id": cue["id"], "text": "A soft paper rustle."})
        prompt["video_prompt"] += " A soft paper rustle."
        self.assertTrue(validate_packet(self.authored_fixture(packet))["valid"])
        prompt["video_prompt"] = prompt["video_prompt"].replace(" A soft paper rustle.", "")
        self.assertIn("还寄吗？", prompt["video_prompt"])
        self.assert_code(self.authored_fixture(packet), "cue_text_missing")

    def test_board_dialogue_cannot_rewrite_locked_words_or_speaker(self):
        for key, value in [("text", "不用寄了。"), ("speaker", "周宁")]:
            with self.subTest(key=key):
                packet = self.packet()
                packet["storyboard"]["board"]["shots"][0]["dialogue"][0][key] = value
                self.assert_code(self.authored_fixture(packet), "dialogue_drift")

    def test_prompt_must_keep_exact_dialogue_and_ids(self):
        packet = self.packet()
        packet["prompts"]["shots"][0]["video_prompt"] = "林泽说：不用寄了。"
        self.assert_code(self.authored_fixture(packet), "prompt_dialogue")

    def test_missing_dialogue_cue_and_added_music_are_refused(self):
        packet = self.packet()
        packet["audio"]["cues"] = [c for c in packet["audio"]["cues"] if c["id"] != "C_L01"]
        self.assert_code(self.authored_fixture(packet), "dialogue_cue_coverage")
        packet = self.packet()
        next(c for c in packet["audio"]["cues"] if c["id"] == "C_ROOM")["kind"] = "music"
        self.assert_code(self.authored_fixture(packet), "music_forbidden")

    def add_reference(self, packet, status="provided"):
        asset = {"id": "USER_FRAME", "status": status,
                 "path": "/caller-chosen/never-read.png" if status == "provided" else None,
                 "role": "identity", "sha256": "a" * 64 if status == "provided" else None}
        packet["storyboard"]["board"]["assets"].append(asset)
        packet["storyboard"]["board"]["shots"][0]["references"] = [
            {"asset_id": asset["id"], "role": asset["role"], "exclude": "背景与光线不迁移。"}]
        packet["prompts"]["shots"][0]["reference_asset_ids"] = [asset["id"]]
        return {"path": asset["path"], "role": asset["role"]}

    def test_packet_cannot_allowlist_its_own_reference(self):
        packet = self.packet()
        ref = self.add_reference(packet)
        self.authored_fixture(packet)
        self.assert_code(packet, "unapproved_reference")
        result = validate_packet(packet, references=[ref])
        self.assertTrue(result["valid"], result)
        self.assertFalse(result["readiness"]["reference_files_checked"])
        self.assertFalse(result["readiness"]["render_ready"])
        self.assertEqual(to_workflow_plan(packet, references=[ref])["shots"][0]["reference_assets"], [ref])

    def test_planned_reference_does_not_turn_into_a_real_generation_input(self):
        packet = self.packet()
        self.add_reference(packet, "planned")
        self.assert_code(self.authored_fixture(packet), "unready_reference")

    def test_generation_audio_reference_cannot_be_declared_but_left_unattached(self):
        packet = self.packet()
        packet["storyboard"]["board"]["assets"].append({"id": "VOICE_REF", "status": "provided",
            "path": "/caller-chosen/voice.wav", "role": "voice", "sha256": "a" * 64})
        cue = next(c for c in packet["audio"]["cues"] if c["id"] == "C_L01")
        cue["source_kind"], cue["source_asset_id"] = "user_asset", "VOICE_REF"
        self.assert_code(self.authored_fixture(packet), "generation_cue_reference",
                         references=[{"path": "/caller-chosen/voice.wav", "role": "voice"}])

    def test_planned_or_reported_take_never_claims_ready_media(self):
        packet = self.packet()
        self.assertEqual(validate_packet(packet)["readiness"]["editorial_status"], "planned")
        packet["editorial"]["status"] = "reported_windows"
        self.assert_code(self.authored_fixture(packet), "pending_take")
        packet = self.packet()
        ref = self.add_reference(packet)
        packet["editorial"]["events"][0]["take"] = {"asset_id": "USER_FRAME", "in_frame": 0, "out_frame": 240, "fps": 24}
        result = validate_packet(self.authored_fixture(packet), references=[ref])
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["readiness"]["editorial_status"], "pending_media_verification")
        self.assertFalse(result["readiness"]["render_ready"])

    def test_authority_unknown_fields_and_nonfinite_values_are_rejected(self):
        for mutation in ("approval", "scope", "render_ready", "nan"):
            with self.subTest(mutation=mutation):
                packet = self.packet()
                if mutation == "approval":
                    packet["approval_granted"] = True
                elif mutation == "scope":
                    packet["project"]["requested_live_scopes"] = {"video": {"allow_uploads": True}}
                elif mutation == "render_ready":
                    packet["editorial"]["render_ready"] = True
                else:
                    packet["project"]["fps"] = float("nan")
                self.assert_code(packet, "invalid_structure")

    def test_existing_output_remains_byte_identical_and_invalid_input_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet_path, output = root / "packet.json", root / "draft.json"
            packet = self.packet()
            packet_path.write_text(json.dumps(packet))
            output.write_bytes(b"accepted original\n")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(packet_path), "--output", str(output)]), 2)
            self.assertEqual(output.read_bytes(), b"accepted original\n")
            packet["script"]["screenplay"] += " changed"
            packet_path.write_text(json.dumps(packet))
            missing = root / "must-not-exist.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(packet_path), "--output", str(missing)]), 1)
            self.assertFalse(missing.exists())

    def test_digest_reporting_never_stamps_the_packet(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "packet.json"
            packet = self.packet()
            packet["script"]["screenplay"] += " changed"
            path.write_text(json.dumps(packet))
            before = path.read_bytes()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main([str(path), "--digests"]), 0)
            reported = json.loads(out.getvalue())
            self.assertFalse(reported["valid"])
            self.assertFalse(reported["approval_granted"])
            self.assertEqual(path.read_bytes(), before)

    def test_failed_private_write_never_deletes_a_public_or_concurrent_output(self):
        for kind in ("new", "existing", "concurrent"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                packet_path, output = root / "packet.json", root / "draft.json"
                packet_path.write_text(json.dumps(self.packet()))
                if kind == "existing":
                    output.write_bytes(b"existing accepted bytes")

                def failed_sync(fd):
                    if kind == "concurrent":
                        output.write_bytes(b"concurrent replacement")
                    raise OSError("SYNTHETIC_TEST disk failure")

                with patch("creative_handoff.os.fsync", side_effect=failed_sync), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main([str(packet_path), "--output", str(output)]), 2)
                if kind == "new":
                    self.assertFalse(output.exists())
                else:
                    self.assertEqual(output.read_bytes(), b"concurrent replacement" if kind == "concurrent" else b"existing accepted bytes")
                self.assertEqual(list(root.glob(".creative-handoff-*")), [])

    def test_successful_private_publish_is_the_exact_expected_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet_path, output = root / "packet.json", root / "draft.json"
            packet = self.packet()
            packet_path.write_text(json.dumps(packet))
            expected = (json.dumps(to_workflow_plan(packet), ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(packet_path), "--output", str(output)]), 0)
            self.assertEqual(output.read_bytes(), expected)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(root.glob(".creative-handoff-*")), [])

    def test_actual_draft_import_stops_at_plan_review_without_provider_actions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet_path, output = root / "packet.json", root / "new-draft.json"
            packet_path.write_text(json.dumps(self.packet()))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(packet_path), "--output", str(output)]), 0)
            provider = NoActionProvider()
            engine = Engine(root / "jobs.sqlite3", {"mock": provider}, artifact_dir=root / "assets")
            try:
                pid = engine.init_project("SYNTHETIC_TEST creative handoff", mode="dry-run")["project_id"]
                state = engine.set_plan(pid, json.loads(output.read_text()), actor="SYNTHETIC_TEST")
                self.assertEqual(state["status"], "plan_review")
                self.assertEqual(engine.tick(pid)["status"], "plan_review")
                self.assertEqual(provider.calls, [])
                self.assertEqual(engine.status(pid)["operations"], [])
            finally:
                engine.close()


if __name__ == "__main__":
    unittest.main()
