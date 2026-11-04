"""Explicitly approved, copy-preserving CFR assembly; never a fallback.

The Engine owns fresh human approval. The three hashes below only ensure that
its explicit dispatch snapshot still matches the exact plan and ordered inputs.
They are not a signature or an authentication mechanism for a hostile caller.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path


class _Refusal(ValueError):
    pass


def _hash_json(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def normalization_binding(operation):
    """Return the non-secret, exact dispatch snapshot expected by this module."""
    plan = operation["plan"]
    return {
        "plan_hash": _hash_json(plan),
        "inputs_hash": _hash_json([{key: item[key] for key in ("shot_id", "sha256", "duration_seconds")}
                                  for item in operation["inputs"]]),
        "policy_hash": _hash_json({"composition": plan["composition"], "fps": plan["fps"],
                                   "aspect_ratio": plan["aspect_ratio"]}),
    }


def _file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require(condition, code):
    if not condition:
        raise _Refusal(code)


def _run(command, runner):
    result = runner(command, capture_output=True, text=True, timeout=300, check=False)
    _require(result.returncode == 0, "normalization_command_failed")
    return result.stdout


def _ffmpeg(args, runner):
    return _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n", *args], runner)


def _probe_json(path, options, runner):
    return json.loads(_run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", *options,
                            "-of", "json", str(path)], runner))


def _guarded_runner(runner):
    def guarded(command, **kwargs):
        return runner([command[0], "-protocol_whitelist", "file,pipe", *command[1:]], **kwargs)
    return guarded


def _fraction(value):
    return Fraction(str(value))


def _publish(staged_output, staged_report, output, evidence, record):
    # Complete the receipt before making either public filename visible. This
    # handles catchable process errors; it is not cross-file crash atomicity.
    fd = os.open(staged_report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    attempted = []
    try:
        for staged, public in ((staged_output, output), (staged_report, evidence)):
            identity = staged.stat()
            attempted.append((public, identity.st_dev, identity.st_ino))
            os.link(staged, public)
    except Exception:
        for public, device, inode in reversed(attempted):
            try:
                current = public.lstat()
                if (current.st_dev, current.st_ino) == (device, inode):
                    public.unlink()
            except OSError:
                pass
        raise


def assemble_normalized(operation, *, runner=subprocess.run):
    """Normalize only the explicitly selected mode and publish a new MP4."""
    from .compositor import _probe
    try:
        _require(operation.get("mode") == "live", "live_assembly_requires_live_mode")
        plan = operation.get("plan")
        _require(isinstance(plan, dict) and plan.get("composition") == {"mode": "normalize_cfr"},
                 "normalization_invalid_policy")
        _require(type(plan.get("fps")) is int and 1 <= plan["fps"] <= 120,
                 "explicit_approved_aspect_and_fps_required")
        ratio = re.fullmatch(r"([1-9][0-9]{0,3}):([1-9][0-9]{0,3})", str(plan.get("aspect_ratio", "")))
        _require(ratio is not None, "explicit_approved_aspect_and_fps_required")
        inputs = operation.get("inputs")
        _require(isinstance(inputs, list) and 1 <= len(inputs) <= 64, "requires_1_to_64_inputs")
        _require(type(operation.get("normalization_authorized")) is dict
                 and operation["normalization_authorized"] == normalization_binding(operation),
                 "normalization_authorization_required")
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            return {"status": "needs_setup", "reason": "ffmpeg_or_ffprobe_not_installed", "simulated": False}
        fps = plan["fps"]
        aspect = Fraction(int(ratio[1]), int(ratio[2]))
        output_dir = Path(operation["output_dir"]).resolve()
        output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        output = output_dir / "assembled.mp4"
        evidence = output_dir / "assembly-report.json"
        _require(not output.exists() and not evidence.exists(), "output_exists_not_overwritten")
        manifest, sources, snapshots = [], [], []
        with tempfile.TemporaryDirectory(prefix="hc-normalize-", dir=output_dir) as temporary:
            staging = Path(temporary)
            first_audio = None
            has_audio = None
            total_duration = Fraction(0)
            total_frames = total_samples = 0
            expected_audio = staging / "expected-audio.f32le"
            with expected_audio.open("xb") as expected:
                for index, item in enumerate(inputs):
                    source = Path(item["path"]).resolve(strict=True)
                    _require(source.is_file() and source.stat().st_size <= 2_000_000_000
                             and re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256", ""))), "invalid_or_unapproved_input")
                    duration = _fraction(item["duration_seconds"])
                    frames = duration * fps
                    _require(0 < duration <= 120 and frames.denominator == 1, "normalization_nonintegral_frame_duration")
                    total_duration += duration
                    total_frames += int(frames)
                    _require(total_duration <= 3600, "media_outside_assembly_limits")
                    copied = staging / f"segment-{index:04d}.mp4"
                    shutil.copyfile(source, copied)
                    _require(_file_hash(copied) == item["sha256"], "approved_asset_hash_changed")
                    observed = _probe(copied, _guarded_runner(runner))
                    _require(observed["width"] % 2 == 0 and observed["height"] % 2 == 0,
                             "normalization_even_dimensions_required")
                    _require(abs(Fraction(observed["width"], observed["height"]) - aspect) <= Fraction(1, 100),
                             "aspect_differs_from_plan_no_automatic_crop")
                    if manifest:
                        _require((observed["width"], observed["height"]) ==
                                 (manifest[0]["observed"]["width"], manifest[0]["observed"]["height"]),
                                 "normalization_dimensions_differ")
                    audio = observed["audio_timing"]
                    video = observed["video_timing"]
                    _require(all(video.get(k) not in (None, "N/A") for k in ("start_time", "duration")),
                             "normalization_timing_incomplete")
                    # At most two target frames of terminal container/codec
                    #余量 may be trimmed. This never arbitrarily cuts long clips.
                    epsilon = Fraction(2, 1_000_000)
                    for observed_duration in (_fraction(observed["duration_seconds"]), _fraction(video["duration"])):
                        _require(duration - epsilon <= observed_duration <= duration + Fraction(2, fps) + epsilon,
                                 "normalization_duration_outside_approved_tail")
                    if has_audio is None:
                        has_audio = observed["has_audio"]
                    _require(observed["has_audio"] == has_audio, "normalization_mixed_audio_tracks")
                    samples = 0
                    audio_args, audio_filter = [], ""
                    if has_audio:
                        _require(all(audio.get(k) not in (None, "N/A") for k in
                                     ("sample_rate", "channels", "channel_layout", "start_time", "duration")),
                                 "normalization_audio_format_unknown")
                        rate, channels, layout = int(audio["sample_rate"]), int(audio["channels"]), audio["channel_layout"]
                        _require(rate in {8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000, 64000, 88200, 96000}
                                 and (channels, layout) in {(1, "mono"), (2, "stereo")}, "normalization_audio_format_unsupported")
                        current_audio = (rate, channels, layout)
                        if first_audio is None:
                            first_audio = current_audio
                        _require(current_audio == first_audio, "normalization_audio_formats_differ")
                        _require(abs(_fraction(audio["start_time"]) - _fraction(video["start_time"])) <= Fraction(1, rate),
                                 "normalization_av_start_offset")
                        _require(duration - epsilon <= _fraction(audio["duration"]) <= duration + Fraction(2, fps) + epsilon,
                                 "normalization_duration_outside_approved_tail")
                        sample_count = duration * rate
                        _require(sample_count.denominator == 1, "normalization_nonintegral_audio_duration")
                        samples = int(sample_count)
                        total_samples += samples
                        audio_filter = f";[0:a:0]atrim=end_sample={samples},asetpts=PTS-STARTPTS[a]"
                        audio_args = ["-map", "[a]", "-c:a", "pcm_f32le", "-f", "f32le", str(staging / f"audio-{index}.f32le")]
                    framehash = staging / f"frames-{index}.txt"
                    graph = f"[0:v:0]setpts=PTS-STARTPTS,fps={fps}:start_time=0,trim=end_frame={int(frames)}[v]" + audio_filter
                    _ffmpeg(["-protocol_whitelist", "file,pipe", "-i", str(copied), "-filter_complex", graph,
                             "-map", "[v]", "-c:v", "rawvideo", "-pix_fmt", "yuv420p", "-f", "framehash", str(framehash),
                             *audio_args], runner)
                    rows = [line for line in framehash.read_text().splitlines() if line and not line.startswith("#")]
                    _require(len(rows) == frames, "normalization_short_video_no_padding")
                    if has_audio:
                        pcm = staging / f"audio-{index}.f32le"
                        _require(pcm.stat().st_size == samples * first_audio[1] * 4, "normalization_short_audio_no_padding")
                        with pcm.open("rb") as stream:
                            shutil.copyfileobj(stream, expected)
                    manifest.append({"shot_id": item["shot_id"], "sha256": item["sha256"], "observed": observed,
                                     "approved_duration_seconds": float(duration), "normalized_frames": int(frames),
                                     "normalized_audio_samples_per_channel": samples})
                    sources.append(source)
                    snapshots.append(copied)
            command, graph = [], []
            for index, copied in enumerate(snapshots):
                command += ["-protocol_whitelist", "file,pipe", "-i", str(copied)]
                graph.append(f"[{index}:v:0]setpts=PTS-STARTPTS,fps={fps}:start_time=0,trim=end_frame={manifest[index]['normalized_frames']}[v{index}]")
                if has_audio:
                    graph.append(f"[{index}:a:0]atrim=end_sample={manifest[index]['normalized_audio_samples_per_channel']},asetpts=PTS-STARTPTS[a{index}]")
            slots = "".join(f"[v{i}][a{i}]" if has_audio else f"[v{i}]" for i in range(len(inputs)))
            if has_audio:
                graph += [f"{slots}concat=n={len(inputs)}:v=1:a=1[v][ajoin]", "[ajoin]asplit=2[a][pcm]"]
            else:
                graph.append(f"{slots}concat=n={len(inputs)}:v=1:a=0[v]")
            staged_output = staging / "assembled.mp4"
            command += ["-filter_complex", ";".join(graph), "-map", "[v]"]
            if has_audio:
                command += ["-map", "[a]"]
            command += ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps), "-fps_mode", "cfr"]
            if has_audio:
                command += ["-c:a", "aac", "-ar", str(first_audio[0]), "-ac", str(first_audio[1])]
            command += ["-movflags", "+faststart", str(staged_output)]
            if has_audio:
                actual_pcm = staging / "actual-audio.f32le"
                command += ["-map", "[pcm]", "-c:a", "pcm_f32le", "-f", "f32le", str(actual_pcm)]
            _ffmpeg(command, runner)
            _require(staged_output.is_file() and staged_output.stat().st_size > 0, "normalization_output_missing")
            if has_audio:
                _require(actual_pcm.stat().st_size == total_samples * first_audio[1] * 4
                         and _file_hash(actual_pcm) == _file_hash(expected_audio), "normalization_pcm_changed_or_padded")
            combined = _probe(staged_output, _guarded_runner(runner))
            metadata = _probe_json(staged_output, ["-count_frames", "-show_streams", "-show_format"], runner)
            video_out = next(s for s in metadata["streams"] if s["codec_type"] == "video")
            _require(video_out.get("codec_name") == "h264" and video_out.get("pix_fmt") == "yuv420p"
                     and Fraction(video_out["avg_frame_rate"]) == fps and int(video_out["nb_read_frames"]) == total_frames
                     and (combined["width"], combined["height"]) == (manifest[0]["observed"]["width"], manifest[0]["observed"]["height"])
                     and abs(_fraction(combined["duration_seconds"]) - total_duration) <= Fraction(1, 1000),
                     "normalization_output_spec_mismatch")
            frames_out = _probe_json(staged_output, ["-select_streams", "v:0", "-show_frames", "-show_entries",
                                                     "frame=best_effort_timestamp_time"], runner)["frames"]
            times = [_fraction(frame["best_effort_timestamp_time"]) for frame in frames_out]
            _require(len(times) == total_frames and all(abs(t - Fraction(i, fps)) <= Fraction(1, 1_000_000)
                                                       for i, t in enumerate(times)), "normalization_frame_grid_mismatch")
            audio_proof = {"has_audio": bool(has_audio)}
            _require(combined["has_audio"] == bool(has_audio), "normalization_output_spec_mismatch")
            if has_audio:
                audio_out = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
                _require(audio_out.get("codec_name") == "aac" and
                         (int(audio_out["sample_rate"]), int(audio_out["channels"]), audio_out.get("channel_layout")) == first_audio
                         and abs(_fraction(audio_out["start_time"])) <= Fraction(2, 1_000_000)
                         and abs(_fraction(audio_out["duration"]) - total_duration) <= Fraction(1, 1000),
                         "normalization_output_spec_mismatch")
                packets = _probe_json(staged_output, ["-select_streams", "a:0", "-show_packets", "-show_entries",
                                                       "packet=pts_time,dts_time,duration_time,side_data_list"], runner)["packets"]
                _require(bool(packets), "normalization_audio_timeline_mismatch")
                dts = [_fraction(p["dts_time"]) for p in packets]
                epsilon = Fraction(2, 1_000_000)
                _require(all(b > a and abs(a + _fraction(p["duration_time"]) - b) <= epsilon
                             for a, b, p in zip(dts, dts[1:], packets))
                         and all(abs(_fraction(p["pts_time"]) - t) <= epsilon for p, t in zip(packets, dts)),
                         "normalization_audio_timeline_mismatch")
                initial_skip = sum(s.get("skip_samples", 0) for s in packets[0].get("side_data_list", []))
                _require(abs(dts[0] + Fraction(initial_skip, first_audio[0])) <= epsilon
                         and abs(dts[-1] + _fraction(packets[-1]["duration_time"]) - total_duration) <= epsilon
                         and not any(s.get("skip_samples", 0) for p in packets[1:] for s in p.get("side_data_list", [])),
                         "normalization_audio_timeline_mismatch")
                decoded = staging / "decoded-audio.f32le"
                _ffmpeg(["-protocol_whitelist", "file,pipe", "-i", str(staged_output), "-map", "0:a:0",
                         "-c:a", "pcm_f32le", "-f", "f32le", str(decoded)], runner)
                decoded_samples = decoded.stat().st_size // (first_audio[1] * 4)
                _require(total_samples <= decoded_samples <= total_samples + 1024, "normalization_unexplained_audio_padding")
                audio_proof.update({"sample_rate": first_audio[0], "channels": first_audio[1], "channel_layout": first_audio[2],
                                    "pre_encode_samples_per_channel": total_samples, "actual_concat_pcm_matches_exact_preflight": True,
                                    "pcm_sha256": _file_hash(actual_pcm), "initial_priming_samples": initial_skip,
                                    "interior_priming_count": 0, "packet_timestamps_continuous": True,
                                    "decoded_tail_padding_samples": decoded_samples - total_samples})
            decode_command = ["-protocol_whitelist", "file,pipe", "-i", str(staged_output), "-map", "0:v:0"]
            if has_audio:
                decode_command += ["-map", "0:a:0"]
            _ffmpeg([*decode_command, "-f", "null", "-"], runner)
            _require(all(_file_hash(source) == item["sha256"] and _file_hash(copied) == item["sha256"]
                         for source, copied, item in zip(sources, snapshots, inputs)), "approved_asset_hash_changed")
            os.chmod(staged_output, 0o600)
            digest = _file_hash(staged_output)
            record = {"status": "succeeded", "path": str(output), "sha256": digest, "simulated": False,
                      "assembly": "approved_cfr_normalization", "observed": combined, "shots": manifest,
                      "normalization_binding": normalization_binding(operation), "originals_preserved": True,
                      "output_frames": total_frames, "output_fps": fps, "audio_validation": audio_proof,
                      "creative_editing": False, "visual_quality_checked": False}
            _publish(staged_output, staging / "assembly-report.json", output, evidence, record)
            return record
    except _Refusal as exc:
        return {"status": "needs_review", "reason": str(exc), "simulated": False}
    except subprocess.TimeoutExpired:
        return {"status": "needs_review", "reason": "normalization_command_timeout", "simulated": False}
    except Exception:
        # Never forward runner stderr, filenames, raw parser errors or payloads.
        return {"status": "needs_review", "reason": "normalization_failed", "simulated": False}
