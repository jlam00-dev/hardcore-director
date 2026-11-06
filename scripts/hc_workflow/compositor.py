"""Local, order-preserving assembly. Not an autonomous creative editor."""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class _AssemblyConflict(ValueError):
    def __init__(self):
        super().__init__("output_exists_not_overwritten")


def _assembly_binding(operation):
    inputs = [{key: item[key] for key in ("shot_id", "sha256", "duration_seconds", "duration_frames") if key in item}
              for item in operation["inputs"]]
    scope = {key: operation.get(key) for key in ("operation_id", "project_id", "revision", "plan")}
    scope["inputs"] = inputs
    serialized = json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


@contextmanager
def _lock_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _recover_assembly(directory, binding, *, staged_commit=None):
    # Serialize the short publication/rollback section, never FFmpeg itself.
    with _lock_directory(directory):
        commit = directory / ".assembly-commit"
        output, receipt = directory / "assembled.mp4", directory / "assembly-report.json"
        pairs = ((commit / output.name, output), (commit / receipt.name, receipt))
        if not commit.exists() and not commit.is_symlink():
            if any(path.exists() or path.is_symlink() for path in (output, receipt)):
                raise _AssemblyConflict()
            if staged_commit is None:
                return None
            staged_commit.rename(commit)
        if commit.is_symlink() or not all(path.is_file() and not path.is_symlink() for path, _ in pairs):
            raise _AssemblyConflict()
        record = json.loads(pairs[1][0].read_text(encoding="utf-8"))
        if (not isinstance(record, dict) or record.get("status") != "succeeded"
                or record.get("assembly_binding") != binding or record.get("path") != str(output)
                or record.get("sha256") != _hash(pairs[0][0])):
            raise _AssemblyConflict()
        attempted = []
        try:
            for staged, public in pairs:
                if public.exists() or public.is_symlink():
                    if public.is_symlink() or not public.samefile(staged):
                        raise _AssemblyConflict()
                    continue
                attempted.append((staged, public))
                os.link(staged, public)
        except Exception:
            for staged, public in reversed(attempted):
                try:
                    if not public.is_symlink() and public.samefile(staged):
                        public.unlink()
                except OSError:
                    pass
            raise
        return record


def _publish_assembly(staged_output, directory, binding, record):
    # Commit the checked MP4 and report together before exposing either public
    # path. A restarted process can finish the links or reuse the exact result.
    record = {**record, "assembly_binding": binding}
    staged_commit = staged_output.parent / "commit"
    staged_commit.mkdir(mode=0o700)
    with staged_output.open("rb") as stream:
        os.fsync(stream.fileno())
    staged_output.rename(staged_commit / "assembled.mp4")
    with (staged_commit / "assembly-report.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    return _recover_assembly(directory, binding, staged_commit=staged_commit)


def _probe(path: Path, runner=subprocess.run) -> dict:
    result = runner(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                    capture_output=True, text=True, timeout=45, check=False)
    if result.returncode != 0:
        raise ValueError("media_probe_failed")
    data = json.loads(result.stdout)
    videos = [x for x in data.get("streams", []) if x.get("codec_type") == "video" and not x.get("disposition", {}).get("attached_pic")]
    audios = [x for x in data.get("streams", []) if x.get("codec_type") == "audio"]
    if len(videos) != 1 or len(audios) > 1:
        raise ValueError("requires_one_video_and_at_most_one_audio_track")
    video = videos[0]
    try:
        duration = float(data["format"]["duration"])
        fps = Fraction(video["avg_frame_rate"])
        width, height = int(video["width"]), int(video["height"])
    except (ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        raise ValueError("unusable_media_metadata") from exc
    if not 0 < duration <= 3600 or not 0 < fps <= 120 or min(width, height) <= 0:
        raise ValueError("media_outside_assembly_limits")
    # Storage dimensions are not necessarily display dimensions. Do not let
    # anamorphic pixels or container rotation pass the approved aspect check.
    if video.get("sample_aspect_ratio") not in ("1:1",):
        raise ValueError("non_square_or_unknown_pixels_require_explicit_normalization")
    rotations = [video.get("tags", {}).get("rotate", 0)]
    rotations.extend(x["rotation"] for x in video.get("side_data_list", []) if "rotation" in x)
    try:
        if any(float(rotation) % 360 for rotation in rotations):
            raise ValueError("rotated_media_requires_explicit_normalization")
    except (TypeError, ValueError) as exc:
        raise ValueError("rotated_or_unknown_orientation_requires_explicit_normalization") from exc
    if video.get("color_transfer") in {"smpte2084", "arib-std-b67"}:
        raise ValueError("hdr_requires_explicit_color_workflow")
    # Exact stream-copy compatibility: no implicit crop, retiming, silence or remix.
    signature = [video.get(k) for k in ("codec_name", "profile", "width", "height", "pix_fmt", "time_base", "sample_aspect_ratio")]
    signature += [str(fps), len(audios)]
    if audios:
        signature += [audios[0].get(k) for k in ("codec_name", "sample_rate", "channels", "channel_layout", "time_base")]
    timing_fields = ("start_time", "duration", "time_base", "nb_frames", "r_frame_rate")
    return {"duration_seconds": duration, "width": width, "height": height, "fps": str(fps), "sample_aspect_ratio": "1:1", "rotation": 0,
            "has_audio": bool(audios), "signature": signature,
            "video_timing": {key: video.get(key) for key in timing_fields},
            "audio_timing": {key: audios[0].get(key) for key in (*timing_fields, "codec_name", "sample_rate", "channels", "channel_layout")} if audios else None,
            "format_start_time": data["format"].get("start_time")}


def _native_timing_compatibility(path, observed, approved_duration, *, runner=subprocess.run):
    """Prove a single clip follows the 24 fps grid without changing its PTS.

    This narrow fallback is for native quantized timestamps and a terminal
    frame/codec padding boundary. It never relabels the actual average rate.
    """
    if Fraction(observed["fps"]).denominator == 1:
        raise ValueError("fps_differs_from_plan_no_automatic_retime")
    result = runner(["ffprobe", "-v", "error", "-show_frames", "-show_entries",
                     "frame=media_type,best_effort_timestamp_time,duration_time,nb_samples", "-of", "json", str(path)],
                    capture_output=True, text=True, timeout=45, check=False)
    if result.returncode != 0:
        raise ValueError("native_frame_timing_probe_failed")
    data = json.loads(result.stdout)
    videos = [frame for frame in data.get("frames", []) if frame.get("media_type") == "video"]
    audio = [frame for frame in data.get("frames", []) if frame.get("media_type") == "audio"]
    try:
        times = [Fraction(frame["best_effort_timestamp_time"]) for frame in videos]
        video = observed["video_timing"]
        tick = Fraction(video["time_base"])
        start = Fraction(video["start_time"])
        video_end = start + Fraction(video["duration"])
        format_start = Fraction(observed["format_start_time"])
        duration = Fraction(str(approved_duration))
        if video.get("nb_frames") not in (None, "N/A") and int(video["nb_frames"]) != len(times):
            raise ValueError("native_frame_count_mismatch")
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        raise ValueError("native_frame_timing_incomplete") from exc
    period = Fraction(1, 24)
    epsilon = max(Fraction(2, 1_000_000), 2 * tick)
    if not 0 < tick or epsilon > period / 100 or not 3 <= len(times) <= 86_401:
        raise ValueError("native_frame_timing_insufficient")
    relative = [time - times[0] for time in times]
    gaps = [b - a for a, b in zip(times, times[1:])]
    phase = [time - index * period for index, time in enumerate(relative)]
    if any(gap <= 0 or abs(gap - period) > period / 2 + epsilon for gap in gaps):
        raise ValueError("native_frame_gap_differs_from_plan")
    if max(map(abs, phase)) > period + epsilon:
        raise ValueError("native_frame_grid_drift_exceeds_one_frame")
    # Short, constant 25/30 fps clips must not pass just because their total
    # drift has not reached one frame yet, even if rate metadata is misleading.
    if max(gaps) - min(gaps) <= epsilon and abs(sum(gaps) / len(gaps) - period) > epsilon:
        raise ValueError("native_constant_cadence_differs_from_plan")
    if (abs(times[0] - start) > epsilon or abs(format_start - start) > epsilon
            or abs(len(times) * period - duration) > period + epsilon
            or abs(relative[-1] - duration) > period + epsilon
            or abs(video_end - start - duration) > period + epsilon
            or not times[-1] - epsilon <= video_end <= times[-1] + period + epsilon):
        raise ValueError("native_video_boundary_not_explained")
    audio_period, stream_end = Fraction(0), video_end
    if observed["has_audio"]:
        a = observed["audio_timing"]
        try:
            sample_rate = int(a["sample_rate"])
            audio_period = Fraction(1024, sample_rate)
            audio_start = Fraction(a["start_time"])
            audio_end = audio_start + Fraction(a["duration"])
            audio_tick = Fraction(a["time_base"])
            audio_times = [Fraction(frame["best_effort_timestamp_time"]) for frame in audio]
            audio_durations = [Fraction(frame["duration_time"]) for frame in audio]
            samples = [int(frame["nb_samples"]) for frame in audio]
        except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
            raise ValueError("native_audio_boundary_incomplete") from exc
        audio_epsilon = max(Fraction(2, 1_000_000), 2 * audio_tick)
        if (a["codec_name"] != "aac" or not 8000 <= sample_rate <= 192000 or audio_tick != Fraction(1, sample_rate) or not audio_times
                or any(not 0 < sample <= 1024 for sample in samples)
                or any(not 0 < size <= audio_period + audio_epsilon for size in audio_durations)
                or any(not 0 < b - a <= audio_period + audio_epsilon for a, b in zip(audio_times, audio_times[1:]))
                or abs(audio_times[0] - audio_start) > audio_epsilon
                or abs(audio_times[-1] + audio_durations[-1] - audio_end) > audio_epsilon
                or abs(audio_start - start) > audio_epsilon
                or audio_end < start + duration - audio_period - audio_epsilon
                or audio_end > start + len(times) * period + audio_period + audio_epsilon):
            raise ValueError("native_audio_boundary_not_explained")
        stream_end = max(stream_end, audio_end)
    format_duration = Fraction(str(observed["duration_seconds"]))
    if (abs(format_start + format_duration - stream_end) > epsilon
            or not duration - period - epsilon <= format_duration <= duration + period + audio_period + epsilon):
        raise ValueError("native_container_padding_not_explained")
    proof = {"policy": "single_input_native_24fps_grid", "approved_fps": 24,
             "approved_duration_seconds": float(duration), "actual_avg_frame_rate": observed["fps"],
             "reported_r_frame_rate": video["r_frame_rate"], "frame_count": len(times),
             "first_pts_seconds": str(times[0]), "last_pts_seconds": str(times[-1]),
             "max_grid_drift_seconds": float(max(map(abs, phase))),
             "min_frame_gap_seconds": float(min(gaps)), "max_frame_gap_seconds": float(max(gaps)),
             "one_frame_bound_seconds": float(period), "timestamp_tolerance_seconds": float(epsilon),
             "nominal_frame_envelope_seconds": float(len(times) * period),
             "video_stream_duration_seconds": float(video_end - start),
             "audio_packet_boundary_seconds": float(audio_period), "format_duration_seconds": float(format_duration),
             "relative_pts_sha256": hashlib.sha256(json.dumps([str(time) for time in relative]).encode()).hexdigest(),
             "retimed": False}
    return proof, relative


def assemble(operation: dict, *, runner=subprocess.run) -> dict:
    if operation.get("mode") != "live":
        return {"status": "needs_setup", "reason": "live_assembly_requires_live_mode", "simulated": True}
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return {"status": "needs_setup", "reason": "ffmpeg_or_ffprobe_not_installed"}
    plan = operation.get("plan", {})
    if isinstance(plan, dict):
        policy = plan.get("composition", {"mode": "stream_copy"})
        if not isinstance(policy, dict) or set(policy) != {"mode"} or policy.get("mode") not in {"stream_copy", "normalize_cfr"}:
            return {"status": "needs_review", "reason": "normalization_invalid_policy", "simulated": False}
        if policy["mode"] == "normalize_cfr":
            from .normalizer import assemble_normalized
            return assemble_normalized(operation, runner=runner)
    inputs = operation.get("inputs", [])
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 64:
        return {"status": "failed", "reason": "requires_1_to_64_inputs"}
    output_dir = Path(operation["output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output = output_dir / "assembled.mp4"
    manifest = []
    native_reference = None
    try:
        binding = _assembly_binding(operation)
        recovered = _recover_assembly(output_dir, binding)
        if recovered is not None:
            return recovered
        if not isinstance(plan, dict) or not plan.get("aspect_ratio") or type(plan.get("fps")) is not int:
            return {"status": "needs_review", "reason": "explicit_approved_aspect_and_fps_required"}
        with tempfile.TemporaryDirectory(prefix="hc-assemble-", dir=output_dir) as temp:
            staging = Path(temp)
            for index, item in enumerate(inputs):
                source = Path(item["path"]).resolve(strict=True)
                expected = item.get("sha256")
                if not source.is_file() or source.stat().st_size > 2_000_000_000 or not expected:
                    raise ValueError("invalid_or_unapproved_input")
                # Snapshot first, then check the approved hash. Render only this snapshot.
                copied = staging / f"segment-{index:04d}.mp4"
                shutil.copyfile(source, copied)
                if _hash(copied) != expected:
                    raise ValueError("approved_asset_hash_changed")
                observed = _probe(copied, runner)
                if manifest and observed["signature"] != manifest[0]["observed"]["signature"]:
                    raise ValueError("incompatible_streams_no_automatic_transcode")
                duration = float(item["duration_seconds"])
                if not math.isfinite(duration) or duration <= 0:
                    raise ValueError("invalid_approved_duration")
                if abs(observed["duration_seconds"] - duration) > 2 / float(Fraction(observed["fps"])):
                    raise ValueError("duration_differs_from_approved_plan_no_automatic_trim")
                expected_fps = operation.get("plan", {}).get("fps")
                if expected_fps and Fraction(observed["fps"]) != Fraction(str(expected_fps)):
                    if expected_fps != 24 or len(inputs) != 1:
                        raise ValueError("fps_differs_from_plan_no_automatic_retime")
                    proof, native_reference = _native_timing_compatibility(copied, observed, duration, runner=runner)
                    observed["native_timing_compatibility"] = proof
                aspect = plan.get("aspect_ratio")
                if aspect:
                    a, b = map(int, aspect.split(":"))
                    if abs(observed["width"] / observed["height"] - a / b) > 0.01:
                        raise ValueError("aspect_differs_from_plan_no_automatic_crop")
                manifest.append({"shot_id": item["shot_id"], "sha256": expected, "observed": observed})
            listing = staging / "sequence.ffconcat"
            listing.write_text("ffconcat version 1.0\n" + "".join(f"file 'segment-{i:04d}.mp4'\n" for i in range(len(inputs))))
            staged_output = staging / "assembled.mp4"
            command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n", "-protocol_whitelist", "file,pipe",
                       "-f", "concat", "-safe", "1", "-i", str(listing), "-map", "0:v:0", "-map", "0:a:0?",
                       "-c", "copy", "-movflags", "+faststart", str(staged_output)]
            if native_reference is not None:
                # AAC priming must not silently shift the video timeline during
                # remux. Preserve timestamps, including legitimate negative DTS,
                # and avoid concat's automatic H.264 bitstream conversion.
                command[command.index("-i"):command.index("-i")] = ["-auto_convert", "0"]
                command[-1:-1] = ["-copyts", "-avoid_negative_ts", "disabled"]
            result = runner(command, capture_output=True, text=True, timeout=300, check=False)
            if result.returncode != 0 or not staged_output.is_file() or staged_output.stat().st_size == 0:
                raise ValueError("stream_copy_failed_no_automatic_reencode")
            combined = _probe(staged_output, runner)
            if native_reference is not None:
                proof, combined_times = _native_timing_compatibility(staged_output, combined, duration, runner=runner)
                original = manifest[0]["observed"]
                original_proof = original["native_timing_compatibility"]
                tolerance = max(proof["timestamp_tolerance_seconds"], original_proof["timestamp_tolerance_seconds"])
                if (combined["signature"] != original["signature"] or len(combined_times) != len(native_reference)
                        or abs(float(Fraction(proof["first_pts_seconds"]) - Fraction(original_proof["first_pts_seconds"]))) > tolerance
                        or any(abs(float(a - b)) > tolerance for a, b in zip(combined_times, native_reference))):
                    raise ValueError("stream_copy_changed_native_frame_timing")
                if original["has_audio"]:
                    audio_tolerance = max(Fraction(2, 1_000_000), 2 * Fraction(original["audio_timing"]["time_base"]))
                    if any(abs(Fraction(combined["audio_timing"][key]) - Fraction(original["audio_timing"][key])) > audio_tolerance for key in ("start_time", "duration")):
                        raise ValueError("stream_copy_changed_native_audio_timing")
                combined["native_timing_compatibility"] = {**proof, "input_relative_pts_preserved": True}
            total = sum(x["observed"]["duration_seconds"] for x in manifest)
            if abs(combined["duration_seconds"] - total) > max(0.15, len(inputs) * 2 / float(Fraction(combined["fps"]))):
                raise ValueError("assembled_duration_does_not_match_inputs")
            record = {"status": "succeeded", "path": str(output), "sha256": _hash(staged_output), "simulated": False,
                      "assembly": "ordered_stream_copy", "observed": combined,
                      "shots": manifest, "creative_editing": False, "visual_quality_checked": False}
            return _publish_assembly(staged_output, output_dir, binding, record)
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        # Errors are stable codes; no child stderr, tokens or media URLs are forwarded.
        code = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        return {"status": "needs_review", "reason": code, "simulated": False}


def get_compositor(mode: str):
    if mode == "live":
        return assemble
    def simulate(operation: dict) -> dict:
        directory = Path(operation["output_dir"])
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = directory / "simulated-sequence.json"
        content = json.dumps({"simulated": True, "not_a_video": True,
                              "order": [x["shot_id"] for x in operation["inputs"]]}).encode()
        with tempfile.TemporaryDirectory(prefix="hc-simulate-", dir=directory) as staging:
            candidate = Path(staging) / target.name
            candidate.write_bytes(content)
            try:
                os.link(candidate, target)
            except FileExistsError:
                if target.is_symlink() or not target.is_file() or target.read_bytes() != content:
                    return {"status": "needs_review", "reason": "output_exists_not_overwritten", "simulated": True}
        return {"status": "succeeded", "path": str(target), "sha256": hashlib.sha256(content).hexdigest(), "simulated": True}
    return simulate
