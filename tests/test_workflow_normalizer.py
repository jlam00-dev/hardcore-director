import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hc_workflow.compositor import assemble
from hc_workflow.normalizer import normalization_binding


class NormalizationGateTests(unittest.TestCase):
    def operation(self, root):
        op = {"mode": "live", "plan": {"fps": 24, "aspect_ratio": "16:9", "composition": {"mode": "normalize_cfr"}},
              "output_dir": str(root / "out"), "inputs": [
                  {"shot_id": "one", "sha256": "a" * 64, "path": str(root / "source.mp4"), "duration_seconds": 1}]}
        op["normalization_authorized"] = normalization_binding(op)
        return op

    def test_explicit_snapshot_required_before_any_process_or_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = self.operation(root)
            cases = []
            for supplied in (None, True, {}, {"plan_hash": "a" * 64}):
                cases.append({**base, "normalization_authorized": supplied})
            for field in ("plan", "order", "duration_type", "hash"):
                altered = copy.deepcopy(base)
                if field == "plan":
                    altered["plan"]["fps"] = 25
                elif field == "order":
                    altered["inputs"].insert(0, {**altered["inputs"][0], "shot_id": "other"})
                elif field == "duration_type":
                    altered["inputs"][0]["duration_seconds"] = 1.0
                else:
                    altered["inputs"][0]["sha256"] = "b" * 64
                cases.append(altered)
            runner = Mock(side_effect=AssertionError("must not spawn a process"))
            with patch("hc_workflow.compositor.shutil.which", return_value="ffmpeg"):
                for op in cases:
                    with self.subTest(op=op):
                        self.assertEqual(assemble(op, runner=runner)["reason"], "normalization_authorization_required")
            runner.assert_not_called()
            self.assertFalse((root / "out").exists())

    def test_unknown_policy_is_never_an_implicit_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for policy in ({"mode": "normalize_cfr", "crop": True}, {"mode": "auto"}, None, []):
                op = self.operation(root)
                op["plan"]["composition"] = policy
                with patch("hc_workflow.compositor.shutil.which", return_value="ffmpeg"):
                    result = assemble(op, runner=Mock(side_effect=AssertionError("must not run")))
                self.assertEqual(result["reason"], "normalization_invalid_policy")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
class NormalizationMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def source(self, name, *, color="red", vfr=True, audio=True, duration=1, rate=44100, dimensions="160x90"):
        path = self.root / (name + ".mp4")
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n", "-f", "lavfi", "-i",
                   f"color=c={color}:s={dimensions}:r={60 if vfr else 25}:d={duration + (1/60 if vfr else 0)}"]
        if audio:
            command += ["-f", "lavfi", "-i", f"sine=frequency={440 if color == 'red' else 880}:sample_rate={rate}:duration={duration + .04}"]
        if vfr:
            command += ["-vf", "select='eq(mod(n,5),0)+eq(mod(n,5),3)'", "-fps_mode:v", "vfr", "-enc_time_base:v", "1:60"]
        command += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if audio:
            command += ["-c:a", "aac", "-ac", "2"]
        subprocess.run([*command, str(path)], capture_output=True, check=True)
        return {"shot_id": name, "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "duration_seconds": duration}

    def operation(self, inputs, name="out", **plan):
        op = {"mode": "live", "plan": {"aspect_ratio": "16:9", "fps": 24, "composition": {"mode": "normalize_cfr"}, **plan},
              "inputs": inputs, "output_dir": str(self.root / name)}
        op["normalization_authorized"] = normalization_binding(op)
        return op

    def pixel(self, path, second):
        return subprocess.run(["ffmpeg", "-v", "error", "-ss", str(second), "-i", str(path), "-vf", "scale=1:1",
                               "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True, check=True).stdout

    def test_vfr_aac_inputs_are_normalized_in_order_with_continuous_audio_and_originals_preserved(self):
        inputs = [self.source("first"), self.source("second", color="blue")]
        original = [Path(x["path"]).read_bytes() for x in inputs]
        commands = []
        def runner(command, **kwargs):
            commands.append(command)
            return subprocess.run(command, **kwargs)
        result = assemble(self.operation(inputs), runner=runner)
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(result["output_frames"], 48)
        self.assertEqual(result["observed"]["fps"], "24")
        self.assertAlmostEqual(result["observed"]["duration_seconds"], 2, delta=.001)
        self.assertTrue(result["audio_validation"]["actual_concat_pcm_matches_exact_preflight"])
        self.assertTrue(result["audio_validation"]["packet_timestamps_continuous"])
        self.assertEqual(result["audio_validation"]["pre_encode_samples_per_channel"], 88200)
        self.assertEqual(result["audio_validation"]["interior_priming_count"], 0)
        self.assertFalse(result["visual_quality_checked"])
        for second, dominant in ((.25, 0), (1.25, 2)):
            pixel = self.pixel(result["path"], second)
            self.assertEqual(len(pixel), 3)
            self.assertEqual(max(range(3), key=lambda i: pixel[i]), dominant)
        self.assertEqual([Path(x["path"]).read_bytes() for x in inputs], original)
        self.assertFalse(any(token in {"-shortest", "-an"} or "apad" in token or "tpad" in token
                             for command in commands for token in command))
        self.assertEqual(json.loads((self.root / "out/assembly-report.json").read_text())["sha256"], result["sha256"])

    def test_no_audio_branch_does_not_invent_an_audio_track_and_default_copy_still_refuses_fps_change(self):
        inputs = [self.source("first", audio=False, vfr=False), self.source("second", audio=False, vfr=False, color="blue")]
        op = self.operation(inputs)
        result = assemble(op)
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(result["output_frames"], 48)
        self.assertFalse(result["observed"]["has_audio"])
        default = self.operation(inputs, name="copy", composition={"mode": "stream_copy"})
        self.assertEqual(assemble(default)["reason"], "fps_differs_from_plan_no_automatic_retime")

    def test_short_or_excessively_long_inputs_require_manual_processing(self):
        for duration, name in ((.5, "short"), (1.5, "long")):
            with self.subTest(name=name):
                item = self.source(name, duration=duration)
                item["duration_seconds"] = 1
                result = assemble(self.operation([item], name=name + "-out"))
                self.assertEqual(result["reason"], "normalization_duration_outside_approved_tail")
                self.assertFalse((self.root / (name + "-out/assembled.mp4")).exists())

    def test_mixed_tracks_and_audio_formats_are_not_silently_filled_or_resampled(self):
        base = self.source("base")
        for item, code, name in ((self.source("silent", audio=False), "normalization_mixed_audio_tracks", "mixed"),
                                 (self.source("other-rate", rate=48000), "normalization_audio_formats_differ", "rate")):
            with self.subTest(name=name):
                result = assemble(self.operation([base, item], name=name))
                self.assertEqual(result["reason"], code)
                self.assertFalse((self.root / name / "assembled.mp4").exists())

    def test_changed_input_and_existing_output_are_not_overwritten(self):
        item = self.source("base")
        op = self.operation([item])
        source = Path(item["path"])
        source.write_bytes(source.read_bytes() + b"test-change")
        before = source.read_bytes()
        result = assemble(op)
        self.assertEqual(result["reason"], "approved_asset_hash_changed")
        self.assertEqual(source.read_bytes(), before)
        existing_dir = self.root / "existing"
        existing_dir.mkdir()
        output = existing_dir / "assembled.mp4"
        output.write_bytes(b"existing")
        result = assemble({**op, "output_dir": str(existing_dir)})
        self.assertEqual(result["reason"], "output_exists_not_overwritten")
        self.assertEqual(output.read_bytes(), b"existing")

    def test_av_offset_and_fractional_frame_duration_are_rejected_before_render(self):
        item = self.source("base")
        from hc_workflow.compositor import _probe
        def offset_probe(path, runner):
            observed = _probe(path, runner)
            observed["audio_timing"]["start_time"] = ".02"
            return observed
        with patch("hc_workflow.compositor._probe", side_effect=offset_probe):
            result = assemble(self.operation([item]))
        self.assertEqual(result["reason"], "normalization_av_start_offset")
        item["duration_seconds"] = .1
        self.assertEqual(assemble(self.operation([item], name="fractional"))["reason"], "normalization_nonintegral_frame_duration")

    def test_existing_json_duration_for_an_integer_frame_span_is_normalized(self):
        item = self.source("integer-span", duration=25 / 24, audio=False, vfr=False)
        item = json.loads(json.dumps(item))
        result = assemble(self.operation([item]))
        self.assertEqual(result["status"], "succeeded", result)
        self.assertEqual(result["output_frames"], 25)
        self.assertEqual(hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest(), item["sha256"])

        item["duration_seconds"] = math.nextafter(item["duration_seconds"], math.inf)
        result = assemble(self.operation([item], name="nearby-fractional"))
        self.assertEqual(result["reason"], "normalization_nonintegral_frame_duration")

    def test_staged_receipt_write_or_sync_failure_publishes_neither_file(self):
        item = self.source("base", audio=False)
        original = Path(item["path"]).read_bytes()
        for operation in ("json.dump", "os.fsync"):
            with self.subTest(operation=operation):
                name = operation.replace(".", "-")
                with patch("hc_workflow.normalizer." + operation, side_effect=OSError("injected failure")):
                    result = assemble(self.operation([item], name=name))
                self.assertEqual(result["reason"], "normalization_failed")
                self.assertFalse((self.root / name / "assembled.mp4").exists())
                self.assertFalse((self.root / name / "assembly-report.json").exists())
                self.assertEqual(Path(item["path"]).read_bytes(), original)

    def test_second_publication_failure_removes_only_this_attempts_links(self):
        item = self.source("base", audio=False)
        original = Path(item["path"]).read_bytes()
        real_link = os.link
        output_dir = self.root / "out"
        calls = []
        def fail_receipt(source, target):
            calls.append(Path(target).name)
            if Path(target).name == "assembly-report.json":
                # A syscall wrapper may fail after publishing the link; the
                # rollback must recognize both links by their staged inodes.
                real_link(source, target)
                raise OSError("injected second-link failure after creation")
            return real_link(source, target)
        with patch("hc_workflow.normalizer.os.link", side_effect=fail_receipt):
            result = assemble(self.operation([item]))
        self.assertEqual(calls, ["assembled.mp4", "assembly-report.json"])
        self.assertEqual(result["reason"], "normalization_failed")
        self.assertFalse((output_dir / "assembled.mp4").exists())
        self.assertFalse((output_dir / "assembly-report.json").exists())
        self.assertEqual(Path(item["path"]).read_bytes(), original)

    def test_publication_failure_does_not_remove_concurrent_files_with_different_inodes(self):
        item = self.source("base", audio=False)
        original = Path(item["path"]).read_bytes()
        real_link = os.link
        output_dir = self.root / "out"
        def concurrent_writer(source, target):
            target = Path(target)
            if target.name == "assembly-report.json":
                published = output_dir / "assembled.mp4"
                published.unlink()
                published.write_bytes(b"another writer's video")
                target.write_bytes(b"another writer's receipt")
                raise FileExistsError("concurrent writer owns target")
            return real_link(source, target)
        with patch("hc_workflow.normalizer.os.link", side_effect=concurrent_writer):
            result = assemble(self.operation([item]))
        self.assertEqual(result["reason"], "normalization_failed")
        self.assertEqual((output_dir / "assembled.mp4").read_bytes(), b"another writer's video")
        self.assertEqual((output_dir / "assembly-report.json").read_bytes(), b"another writer's receipt")
        self.assertEqual(Path(item["path"]).read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
