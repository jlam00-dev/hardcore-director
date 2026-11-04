import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hc_workflow.compositor import assemble, get_compositor, _native_timing_compatibility


class CompositorTests(unittest.TestCase):
    def native_fixture(self):
        times = [Fraction((5 * (index // 2) + (3 if index % 2 else 0)), 60) for index in range(97)]
        frames = [{"media_type": "video", "best_effort_timestamp_time": str(float(time))} for time in times]
        observed = {"fps": "5820/241", "duration_seconds": 4.016667, "has_audio": False,
                    "format_start_time": "0.000000", "audio_timing": None,
                    "video_timing": {"start_time": "0.000000", "duration": "4.016667", "time_base": "1/15360",
                                     "nb_frames": "97", "r_frame_rate": "60/1"}}
        return observed, frames

    def native_proof(self, observed, frames):
        def runner(command, **kwargs):
            self.assertEqual(command[0], "ffprobe")
            return subprocess.CompletedProcess(command, 0, json.dumps({"frames": frames}), "")
        return _native_timing_compatibility(Path("synthetic.mp4"), observed, 4, runner=runner)

    def test_complete_native_grid_proof_keeps_actual_rate_and_timing_evidence(self):
        observed, frames = self.native_fixture()
        proof, relative = self.native_proof(observed, frames)
        self.assertEqual(proof["actual_avg_frame_rate"], "5820/241")
        self.assertEqual(proof["reported_r_frame_rate"], "60/1")
        self.assertEqual(proof["frame_count"], 97)
        self.assertEqual(relative[0], 0)
        self.assertEqual(relative[-1], 4)
        self.assertAlmostEqual(proof["max_grid_drift_seconds"], 1 / 120)
        self.assertFalse(proof["retimed"])

    def test_native_grid_rejects_missing_reversed_gapped_and_drifting_timestamps(self):
        for problem in ("missing", "reversed", "lost_frame", "drift", "padding", "metadata_count", "coarse_clock", "constant25"):
            with self.subTest(problem=problem):
                observed, frames = self.native_fixture()
                if problem == "missing":
                    del frames[20]["best_effort_timestamp_time"]
                elif problem == "reversed":
                    frames[20]["best_effort_timestamp_time"] = frames[19]["best_effort_timestamp_time"]
                elif problem == "lost_frame":
                    del frames[20]
                    observed["video_timing"]["nb_frames"] = "96"
                elif problem == "drift":
                    frames = [{"media_type": "video", "best_effort_timestamp_time": str(float(Fraction(index, 24) + Fraction(index, 1200)))} for index in range(97)]
                elif problem == "padding":
                    observed["duration_seconds"] = 4.08
                elif problem == "metadata_count":
                    observed["video_timing"]["nb_frames"] = "96"
                elif problem == "coarse_clock":
                    observed["video_timing"]["time_base"] = "1/60"
                else:
                    frames = [{"media_type": "video", "best_effort_timestamp_time": str(float(Fraction(index, 25)))} for index in range(10)]
                    observed["video_timing"]["nb_frames"] = "10"
                with self.assertRaises(ValueError):
                    self.native_proof(observed, frames)

    def test_native_aac_boundary_proof_rejects_excess_padding_and_coarse_clock(self):
        observed, frames = self.native_fixture()
        end = Fraction("4.063991")
        audio_period = Fraction(1024, 44100)
        audio_frames = [{"media_type": "audio", "best_effort_timestamp_time": str(float(index * audio_period)),
                         "duration_time": str(float(min(audio_period, end - index * audio_period))), "nb_samples": 1024}
                        for index in range(176)]
        observed.update({"duration_seconds": float(end), "has_audio": True,
                         "audio_timing": {"codec_name": "aac", "sample_rate": "44100", "time_base": "1/44100",
                                          "start_time": "0", "duration": str(float(end))}})
        proof, _ = self.native_proof(observed, frames + audio_frames)
        self.assertAlmostEqual(proof["audio_packet_boundary_seconds"], 1024 / 44100)
        for problem in ("padding", "coarse_clock", "invalid_rate"):
            with self.subTest(problem=problem):
                changed = copy.deepcopy(observed)
                if problem == "padding":
                    changed["duration_seconds"] = 4.09
                elif problem == "coarse_clock":
                    changed["audio_timing"]["time_base"] = "1/60"
                else:
                    changed["audio_timing"]["sample_rate"] = "1"
                with self.assertRaises(ValueError):
                    self.native_proof(changed, frames + audio_frames)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
    def test_true_25_and_30_fps_are_not_relabelled_as_24(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for rate in (25, 30):
                source = root / f"{rate}.mp4"
                subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                                f"color=c=red:s=320x180:r={rate}:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True)
                result = assemble({"mode": "live", "plan": {"aspect_ratio": "16:9", "fps": 24},
                                   "output_dir": str(root / f"out-{rate}"), "inputs": [{"shot_id": "one", "path": str(source),
                                   "duration_seconds": 1, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]})
                self.assertEqual(result["status"], "needs_review")
                self.assertEqual(result["reason"], "fps_differs_from_plan_no_automatic_retime")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
    def test_native_grid_and_aac_are_stream_copied_without_retime_or_packet_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "native-grid.mp4"
            # Original synthetic content: a 60 Hz source sampled on a quantized
            # 24 fps grid, including its terminal frame, plus bounded AAC audio.
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                            "color=c=red:s=320x180:r=60:d=4.016666667", "-f", "lavfi", "-i",
                            "anullsrc=r=44100:cl=stereo:d=4.04", "-vf", "select='eq(mod(n,5),0)+eq(mod(n,5),3)'",
                            "-fps_mode:v", "vfr", "-enc_time_base:v", "1:60", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", str(source)], check=True)
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            commands = []
            def runner(command, **kwargs):
                commands.append(command)
                return subprocess.run(command, **kwargs)
            item = {"shot_id": "one", "path": str(source), "sha256": original_hash, "duration_seconds": 4}
            result = assemble({"mode": "live", "plan": {"aspect_ratio": "16:9", "fps": 24},
                               "output_dir": str(root / "joined"), "inputs": [item]}, runner=runner)
            self.assertEqual(result["status"], "succeeded", result)
            self.assertEqual(result["observed"]["fps"], "5820/241")
            self.assertTrue(result["observed"]["native_timing_compatibility"]["input_relative_pts_preserved"])
            self.assertTrue(result["observed"]["has_audio"])
            command = next(command for command in commands if command[0] == "ffmpeg")
            self.assertEqual(command[command.index("-c") + 1], "copy")
            self.assertIn("-copyts", command)
            self.assertEqual(command[command.index("-auto_convert") + 1], "0")
            self.assertEqual(command[command.index("-avoid_negative_ts") + 1], "disabled")
            self.assertFalse(set(command) & {"-r", "-vf", "-af", "-t", "-ss", "-an", "-shortest"})
            # Compare encoded video AND audio payloads independently of the
            # compositor's PTS checks. Remuxing must retain every packet byte.
            def packet_hashes(path):
                data = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_packets", "-show_data_hash", "sha256",
                                                   "-show_entries", "packet=codec_type,data_hash", "-of", "json", str(path)],
                                                  capture_output=True, text=True, check=True).stdout)
                return {kind: [packet["data_hash"] for packet in data["packets"] if packet["codec_type"] == kind] for kind in ("video", "audio")}
            self.assertEqual(packet_hashes(source), packet_hashes(result["path"]))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)
            multi = assemble({"mode": "live", "plan": {"aspect_ratio": "16:9", "fps": 24},
                              "output_dir": str(root / "multi"), "inputs": [item, copy.deepcopy(item)]})
            self.assertEqual(multi["reason"], "fps_differs_from_plan_no_automatic_retime")

    def test_simulation_is_not_presented_as_media(self):
        with tempfile.TemporaryDirectory() as d:
            r = get_compositor("dry-run")({"output_dir": d, "inputs": [{"shot_id": "one"}]})
            self.assertTrue(r["simulated"])
            self.assertEqual(Path(r["path"]).suffix, ".json")

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "assembled.mp4").write_bytes(b"existing")
            with patch("hc_workflow.compositor.shutil.which", return_value="ffmpeg"):
                r = assemble({"mode": "live", "output_dir": d, "inputs": [{}]})
            self.assertEqual(r["reason"], "output_exists_not_overwritten")
            self.assertEqual((Path(d) / "assembled.mp4").read_bytes(), b"existing")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
    def test_anamorphic_display_aspect_does_not_bypass_plan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "anamorphic.mp4"
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=red:s=320x180:r=24:d=1",
                            "-vf", "setsar=2/1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True)
            result = assemble({"mode": "live", "plan": {"aspect_ratio": "16:9", "fps": 24}, "output_dir": str(root / "out"),
                               "inputs": [{"shot_id": "one", "path": str(source), "duration_seconds": 1,
                                           "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]})
            self.assertEqual(result["status"], "needs_review")
            self.assertEqual(result["reason"], "non_square_or_unknown_pixels_require_explicit_normalization")
            self.assertFalse((root / "out/assembled.mp4").exists())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
    def test_real_ordered_assembly_and_changed_hash_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inputs = []
            for n, color in enumerate(["red", "blue"]):
                source = root / f"{n}.mp4"
                subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                                f"color=c={color}:s=320x180:r=24:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)], check=True)
                inputs.append({"shot_id": str(n), "path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "duration_seconds": 1})
            base = {"mode": "live", "plan": {"aspect_ratio": "16:9", "fps": 24}, "inputs": inputs, "output_dir": str(root / "joined")}
            result = assemble(base)
            self.assertEqual(result["status"], "succeeded", result)
            self.assertFalse(result["creative_editing"])
            self.assertAlmostEqual(result["observed"]["duration_seconds"], 2, delta=.12)
            # First and second segment remain visually distinct and in the approved order.
            for second, dominant in [(0.25, 0), (1.25, 2)]:
                pixel = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(second), "-i", result["path"], "-vf", "scale=1:1", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True, check=True).stdout
                self.assertEqual(len(pixel), 3)
                self.assertEqual(max(range(3), key=lambda i: pixel[i]), dominant)
            inputs[0]["sha256"] = "0" * 64
            changed = assemble({**base, "output_dir": str(root / "changed")})
            self.assertEqual(changed["reason"], "approved_asset_hash_changed")
            missing = assemble({**base, "plan": {}, "output_dir": str(root / "missing-spec")})
            self.assertEqual(missing["reason"], "explicit_approved_aspect_and_fps_required")


if __name__ == "__main__":
    unittest.main()
