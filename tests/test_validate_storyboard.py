from __future__ import annotations

import copy
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("storyboard_validator", Path(__file__).resolve().parents[1] / "scripts/validate_storyboard.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def fixture():
    state = {"hero.hand": "right", "product.open": False}
    return {
        "schema_version": 1, "aspect_ratio": "16:9", "fps": 30, "total_frames": 300,
        "limits": {"max_shot_frames": 180, "speech_units_per_second": 4.5},
        "beats": [{"id": "reveal"}, {"id": "use"}],
        "assets": [{"id": "product"}],
        "shots": [
            {"id": "s1", "scene_id": "room", "purpose": "展示产品", "start_frame": 0, "end_frame": 150,
             "beat_ids": ["reveal"], "start_state": state, "end_state": state,
             "references": [{"asset_id": "product", "role": "product", "exclude": "背景与光线"}],
             "dialogue": [{"speaker": "旁白", "text": "打开就能用。", "start_frame": 30, "end_frame": 120}]},
            {"id": "s2", "scene_id": "room", "purpose": "完成操作", "start_frame": 150, "end_frame": 300,
             "beat_ids": ["use"], "start_state": state, "end_state": {"hero.hand": "right", "product.open": True}}
        ],
    }


class StoryboardTests(unittest.TestCase):
    def test_complete_storyboard_passes(self):
        result = MODULE.validate(fixture())
        self.assertTrue(result["valid"], result)
        self.assertFalse(result["warnings"])

    def test_gap_overlap_and_total_rejected(self):
        for start, end in [(151, 300), (149, 300), (150, 301)]:
            data = fixture()
            data["shots"][1].update(start_frame=start, end_frame=end)
            self.assertFalse(MODULE.validate(data)["valid"])

    def test_missing_and_duplicate_beat_ownership(self):
        data = fixture()
        data["shots"][1]["beat_ids"] = ["reveal"]
        errors = MODULE.validate(data)["errors"]
        self.assertTrue(any("already owned" in item for item in errors))
        self.assertTrue(any("missing owner" in item for item in errors))

    def test_reference_mapping_rejected(self):
        data = fixture()
        data["shots"][0]["references"][0]["asset_id"] = "unknown"
        self.assertFalse(MODULE.validate(data)["valid"])
        data = fixture()
        data["shots"][0]["references"].append(copy.deepcopy(data["shots"][0]["references"][0]))
        self.assertFalse(MODULE.validate(data)["valid"])

    def test_measured_audio_must_fit(self):
        data = fixture()
        data["shots"][0]["dialogue"][0]["audio_duration_frames"] = 91
        self.assertFalse(MODULE.validate(data)["valid"])

    def test_same_speaker_cannot_speak_two_lines_at_once(self):
        data = fixture()
        data["shots"][0]["dialogue"].append({"speaker": "旁白", "text": "完成。", "start_frame": 90, "end_frame": 140})
        self.assertFalse(MODULE.validate(data)["valid"])

    def test_beat_order_cannot_be_silently_reversed(self):
        data = fixture()
        data["shots"][0]["beat_ids"], data["shots"][1]["beat_ids"] = ["use"], ["reveal"]
        self.assertFalse(MODULE.validate(data)["valid"])

    def test_estimated_speech_is_warning_not_measured_proof(self):
        data = fixture()
        data["shots"][0]["dialogue"][0]["text"] = "这一段对白非常长明显无法在如此短的时间之内自然清楚地说完。"
        result = MODULE.validate(data)
        self.assertTrue(result["valid"])
        self.assertTrue(result["warnings"])

    def test_changed_and_missing_continuity_state_rejected(self):
        for state in [{"hero.hand": "left", "product.open": False}, {"hero.hand": "right"}]:
            data = fixture()
            data["shots"][1]["start_state"] = state
            self.assertFalse(MODULE.validate(data)["valid"])

    def test_explicit_time_jump_requires_reason(self):
        data = fixture()
        data["shots"][1]["start_state"] = {"hero.hand": "left", "product.open": True}
        data["shots"][1]["transition"] = "time_jump"
        self.assertFalse(MODULE.validate(data)["valid"])
        data["shots"][1]["transition_reason"] = "剧本注明一分钟后"
        self.assertTrue(MODULE.validate(data)["valid"])

    def test_no_universal_fifteen_second_limit(self):
        data = fixture()
        data["shots"] = [data["shots"][0]]
        data["shots"][0]["beat_ids"] = ["reveal", "use"]
        data["shots"][0]["end_frame"] = data["total_frames"] = 900
        data["limits"] = {}
        self.assertTrue(MODULE.validate(data)["valid"])

    def test_bool_frames_and_bad_nested_types_fail_without_crash(self):
        data = fixture()
        data["shots"][0]["start_frame"] = False
        data["shots"][1]["references"] = [{"asset_id": {}, "role": []}]
        data["shots"][1]["dialogue"] = [None]
        self.assertFalse(MODULE.validate(data)["valid"])

    def test_expected_ratio_and_duration_checked(self):
        self.assertFalse(MODULE.validate(fixture(), expected_aspect_ratio="9:16")["valid"])
        self.assertFalse(MODULE.validate(fixture(), expected_total_frames=600)["valid"])
        self.assertTrue(MODULE.validate(fixture(), expected_aspect_ratio="32:18", expected_total_frames=300)["valid"])

    def test_empty_beat_list_rejected(self):
        data = fixture()
        data["beats"] = []
        for shot in data["shots"]:
            shot["beat_ids"] = []
        self.assertFalse(MODULE.validate(data)["valid"])

    def test_strict_cli_json_valid_matches_exit_code(self):
        data = fixture()
        data["shots"][0]["dialogue"][0]["text"] = "这一段对白非常长明显无法在如此短的时间之内自然清楚地说完。"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "board.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = MODULE.main([str(path), "--strict", "--json"])
            result = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertFalse(result["valid"])
            self.assertTrue(result["structurally_valid"])


if __name__ == "__main__":
    unittest.main()
