#!/usr/bin/env python3
"""Read-only validation of the hardcore-director storyboard contract (stdlib only)."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


ROLES = {"identity", "product", "space", "start_frame", "end_frame", "motion", "camera", "style", "voice", "music"}


def positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def frame(value: Any) -> bool:
    return type(value) is int and value >= 0


def text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def speech_units(value: str) -> int:
    """Chinese characters + Latin/number words; an estimate, never measured audio."""
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]|[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", value))


def ratio(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", value):
        return None
    return tuple(map(int, value.split(":")))


def validate(data: Any, *, expected_aspect_ratio: str | None = None, expected_total_frames: int | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["root: expected object"], "warnings": []}
    if data.get("schema_version") != 1 or type(data.get("schema_version")) is not int:
        errors.append("schema_version: expected integer 1")
    aspect = ratio(data.get("aspect_ratio"))
    if aspect is None:
        errors.append("aspect_ratio: expected positive integer ratio, e.g. 16:9")
    if expected_aspect_ratio is not None:
        expected = ratio(expected_aspect_ratio)
        if expected is None:
            errors.append("expected_aspect_ratio: invalid ratio")
        elif aspect is not None and aspect[0] * expected[1] != expected[0] * aspect[1]:
            errors.append(f"aspect_ratio: differs from requested {expected_aspect_ratio}")
    fps = data.get("fps")
    total = data.get("total_frames")
    if not positive_int(fps):
        errors.append("fps: expected positive integer")
    if not positive_int(total):
        errors.append("total_frames: expected positive integer")
    elif expected_total_frames is not None and total != expected_total_frames:
        errors.append(f"total_frames: differs from requested {expected_total_frames}")
    limits = data.get("limits", {})
    if not isinstance(limits, dict):
        errors.append("limits: expected object")
        limits = {}
    maximum = limits.get("max_shot_frames")
    if maximum is not None and not positive_int(maximum):
        errors.append("limits.max_shot_frames: expected positive integer")
        maximum = None
    rate = limits.get("speech_units_per_second", 4.5)
    if type(rate) not in (int, float) or not math.isfinite(rate) or rate <= 0:
        errors.append("limits.speech_units_per_second: expected positive finite number")
        rate = 4.5

    def objects(key: str) -> list[dict[str, Any]]:
        values = data.get(key)
        if not isinstance(values, list):
            errors.append(f"{key}: expected array")
            return []
        result = []
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                errors.append(f"{key}[{index}]: expected object")
            else:
                result.append(value)
        return result

    def ids(items: list[dict[str, Any]], label: str) -> set[str]:
        result: set[str] = set()
        for index, item in enumerate(items):
            ident = item.get("id")
            if not text(ident):
                errors.append(f"{label}[{index}].id: expected nonempty string")
            elif ident in result:
                errors.append(f"{label}: duplicate id {ident}")
            else:
                result.add(ident)
        return result

    beats = objects("beats")
    assets = objects("assets")
    shots = objects("shots")
    beat_ids = ids(beats, "beats")
    if not beat_ids:
        errors.append("beats: at least one narrative beat required")
    asset_ids = ids(assets, "assets")
    ids(shots, "shots")
    if not shots:
        errors.append("shots: at least one shot required")
    owners: dict[str, str] = {}
    narrative_order: list[str] = []
    cursor = 0
    previous: dict[str, Any] | None = None
    for index, shot in enumerate(shots):
        label = f"shots[{index}]({shot.get('id', '?')})"
        for field in ("scene_id", "purpose"):
            if not text(shot.get(field)):
                errors.append(f"{label}.{field}: expected nonempty string")
        start, end = shot.get("start_frame"), shot.get("end_frame")
        timing_ok = frame(start) and frame(end) and end > start
        if not timing_ok:
            errors.append(f"{label}: invalid start/end frame interval")
        else:
            if start != cursor:
                errors.append(f"{label}: timeline gap/overlap, expected start {cursor}, got {start}")
            cursor = end
            if positive_int(total) and end > total:
                errors.append(f"{label}: end exceeds total_frames")
            if maximum is not None and end - start > maximum:
                errors.append(f"{label}: shot exceeds configured max_shot_frames {maximum}")

        owned = shot.get("beat_ids")
        if not isinstance(owned, list) or any(not text(item) for item in owned):
            errors.append(f"{label}.beat_ids: expected array of nonempty strings")
            owned = []
        for ident in owned:
            if ident not in beat_ids:
                errors.append(f"{label}: undeclared beat {ident}")
            elif ident in owners:
                errors.append(f"{label}: beat {ident} already owned by {owners[ident]}")
            else:
                owners[ident] = label
                narrative_order.append(ident)

        refs = shot.get("references", [])
        if not isinstance(refs, list):
            errors.append(f"{label}.references: expected array")
            refs = []
        seen_refs = set()
        for ref in refs:
            if not isinstance(ref, dict):
                errors.append(f"{label}.references: expected object entries")
                continue
            ident = ref.get("asset_id")
            if not text(ident) or ident not in asset_ids:
                errors.append(f"{label}: unknown asset_id {ident!r}")
            elif ident in seen_refs:
                errors.append(f"{label}: asset {ident} has repeated/multiple primary responsibilities")
            else:
                seen_refs.add(ident)
            role = ref.get("role")
            if not isinstance(role, str) or role not in ROLES:
                errors.append(f"{label}: invalid reference role {role!r}")
            if not text(ref.get("exclude")):
                errors.append(f"{label}: reference must state excluded attributes")

        for field in ("start_state", "end_state"):
            state = shot.get(field)
            if not isinstance(state, dict) or not state or any(not text(key) for key in state):
                errors.append(f"{label}.{field}: expected nonempty object of tracked states")
        transition = shot.get("transition", "continuous")
        if transition not in ("continuous", "time_jump", "scene_change"):
            errors.append(f"{label}: invalid transition {transition!r}")
        if transition in ("time_jump", "scene_change"):
            if not text(shot.get("transition_reason")):
                errors.append(f"{label}: transition requires a narrative reason")
            if previous and transition == "scene_change" and previous.get("scene_id") == shot.get("scene_id"):
                errors.append(f"{label}: scene_change requires a different scene_id")
        if previous and transition == "continuous":
            if previous.get("scene_id") != shot.get("scene_id"):
                errors.append(f"{label}: scene_id changed without scene_change transition")
            before, after = previous.get("end_state"), shot.get("start_state")
            if isinstance(before, dict) and isinstance(after, dict):
                for key, value in before.items():
                    if key not in after or json.dumps(after[key], sort_keys=True) != json.dumps(value, sort_keys=True):
                        errors.append(f"{label}: continuity mismatch for {key}")
        previous = shot

        dialogue = shot.get("dialogue", [])
        if not isinstance(dialogue, list):
            errors.append(f"{label}.dialogue: expected array")
            dialogue = []
        speaker_intervals: dict[str, list[tuple[int, int]]] = {}
        for line_index, line in enumerate(dialogue):
            line_label = f"{label}.dialogue[{line_index}]"
            if not isinstance(line, dict):
                errors.append(f"{line_label}: expected object")
                continue
            if not text(line.get("speaker")) or not text(line.get("text")):
                errors.append(f"{line_label}: speaker and text required")
            lo, hi = line.get("start_frame"), line.get("end_frame")
            if not frame(lo) or not frame(hi) or hi <= lo or not timing_ok or lo < start or hi > end:
                errors.append(f"{line_label}: dialogue interval must fit shot using absolute frames")
                continue
            speaker = line.get("speaker")
            if text(speaker):
                intervals = speaker_intervals.setdefault(speaker, [])
                if any(lo < other_hi and other_lo < hi for other_lo, other_hi in intervals):
                    errors.append(f"{line_label}: overlapping dialogue windows for the same speaker")
                intervals.append((lo, hi))
            measured = line.get("audio_duration_frames")
            if measured is not None:
                if not positive_int(measured):
                    errors.append(f"{line_label}.audio_duration_frames: expected positive integer")
                elif measured > hi - lo:
                    errors.append(f"{line_label}: measured audio exceeds dialogue window")
            elif positive_int(fps) and text(line.get("text")):
                units = speech_units(line["text"])
                if units / rate > (hi - lo) / fps:
                    warnings.append(f"{line_label}: estimated speech ({units} units at {rate}/s) exceeds window; measure or revise")
    for ident in sorted(beat_ids - owners.keys()):
        errors.append(f"beats: missing owner for {ident}")
    declared_order = [item["id"] for item in beats if text(item.get("id"))]
    if narrative_order != declared_order:
        errors.append("beats: shot ownership order differs from declared narrative order")
    if positive_int(total) and cursor != total:
        errors.append(f"timeline: final end {cursor} differs from total_frames {total}")
    return {
        "valid": not errors,
        "summary": {"shots": len(shots), "beats": len(beat_ids), "assets": len(asset_ids), "total_frames": total},
        "errors": errors,
        "warnings": warnings,
        "not_checked": ["actual_asset_files", "visual_continuity", "prompt_to_dialogue_match", "rendered_or_generated_media"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Treat estimated-speech warnings as failures")
    parser.add_argument("--expected-aspect-ratio", help="Verify against the user's requested ratio")
    parser.add_argument("--expected-total-frames", type=int, help="Verify against the user's requested duration at this FPS")
    args = parser.parse_args(argv)
    try:
        result = validate(json.loads(args.storyboard.read_text(encoding="utf-8")), expected_aspect_ratio=args.expected_aspect_ratio, expected_total_frames=args.expected_total_frames)
    except (OSError, ValueError) as exc:
        result = {"valid": False, "errors": [f"cannot read storyboard JSON: {exc}"], "warnings": []}
    result["structurally_valid"] = result["valid"]
    result["valid"] = result["valid"] and not (args.strict and result["warnings"])
    result["validation_policy"] = "strict" if args.strict else "standard"
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for kind in ("errors", "warnings"):
            for item in result[kind]:
                print(f"{kind[:-1].upper()}: {item}")
        print("storyboard validation passed" if result["valid"] else "storyboard validation failed")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
