#!/usr/bin/env python3
"""Validate a shared creative packet and optionally export an unapproved draft.

Stdlib only. Reads the explicitly selected JSON documents, never media or a
network. Digests detect stale handoffs; they are not signatures or approvals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any

from validate_storyboard import validate as validate_storyboard
from hc_workflow.planner import validate_creative_plan, to_engine_plan


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "references/support/creative-handoff.schema.json"
STAGES = ("direction", "storyboard", "audio", "prompts", "editorial")
NOT_CHECKED = ["narrative_semantics", "acting_or_visual_quality", "platform_prompt_syntax",
               "actual_reference_files_or_reported_hashes", "reported_take_windows",
               "provider_model_matches_selected_platform",
               "generated_or_rendered_media", "audio_measurements_and_listening",
               "user_approval_and_generation_authorization"]


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def expected_source_hashes(packet: dict) -> dict[str, str]:
    """Report upstream-content digests, without changing or approving a packet."""
    upstream = {"project": packet["project"], "script": packet["script"]}
    result = {}
    for stage in STAGES:
        result[stage] = hashlib.sha256(canonical(upstream).encode("utf-8")).hexdigest()
        upstream[stage] = {k: v for k, v in packet[stage].items() if k != "source_hash"}
    return result


def _schema_errors(value, spec, root, path="packet"):
    """The limited JSON-Schema vocabulary used by our bundled contract only."""
    if "$ref" in spec:
        ref = spec["$ref"]
        if not ref.startswith("#/$defs/"):
            return [(path, "unsupported bundled schema reference")]
        return _schema_errors(value, root["$defs"][ref.split("/")[-1]], root, path)
    kinds = spec.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    checks = {"object": type(value) is dict, "array": type(value) is list,
              "string": type(value) is str, "integer": type(value) is int,
              "number": type(value) is int or (type(value) is float and math.isfinite(value)),
              "boolean": type(value) is bool, "null": value is None}
    if kinds and not any(checks.get(k, False) for k in kinds):
        return [(path, "expected " + "/".join(kinds))]
    errors = []
    if "const" in spec and canonical(value) != canonical(spec["const"]):
        errors.append((path, "unexpected constant"))
    if "enum" in spec and not any(canonical(value) == canonical(x) for x in spec["enum"]):
        errors.append((path, "value outside supported choices"))
    if type(value) is dict:
        properties = spec.get("properties", {})
        for key in spec.get("required", []):
            if key not in value:
                errors.append((path + "." + key, "required field missing"))
        if len(value) < spec.get("minProperties", 0):
            errors.append((path, "empty state object"))
        additional = spec.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                errors.extend(_schema_errors(item, properties[key], root, path + "." + key))
            elif additional is False:
                errors.append((path + "." + key, "unsupported field; no authority or execution fields accepted"))
            elif isinstance(additional, dict):
                errors.extend(_schema_errors(item, additional, root, path + "." + key))
    if type(value) is list:
        if not spec.get("minItems", 0) <= len(value) <= spec.get("maxItems", 10000):
            errors.append((path, "array length outside contract"))
        if spec.get("uniqueItems") and len({canonical(x) for x in value}) != len(value):
            errors.append((path, "duplicate entries"))
        for index, item in enumerate(value):
            errors.extend(_schema_errors(item, spec.get("items", {}), root, f"{path}[{index}]"))
    if type(value) is str:
        if not spec.get("minLength", 0) <= len(value) <= spec.get("maxLength", 30000):
            errors.append((path, "string length outside contract"))
        if spec.get("minLength", 0) and not value.strip():
            errors.append((path, "nonblank text required"))
        if "pattern" in spec and not re.fullmatch(spec["pattern"], value):
            errors.append((path, "string does not match contract"))
    if type(value) in (int, float):
        if "minimum" in spec and value < spec["minimum"]:
            errors.append((path, "number below minimum"))
        if "maximum" in spec and value > spec["maximum"]:
            errors.append((path, "number above maximum"))
        if "exclusiveMinimum" in spec and value <= spec["exclusiveMinimum"]:
            errors.append((path, "number must be positive"))
    return errors


def _readiness(valid=False, editorial="planned"):
    return {"workflow_draft_exportable": valid, "render_ready": False,
            "editorial_status": editorial, "reference_files_checked": False,
            "human_creative_acceptance": False, "generation_authorized": False,
            "engine_composition": "existing_sequential_path_only; post cues and EDL are not executed"}


def validate_packet(packet: Any, *, references: list[dict] | None = None) -> dict:
    issues, warnings = [], []

    def fail(stage, code, message):
        issues.append({"stage": stage, "code": code, "message": message, "return_to": stage})

    try:
        canonical(packet)
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        structural = _schema_errors(packet, schema, schema)
    except (ValueError, TypeError, RecursionError):
        structural = [("packet", "finite, bounded JSON values required")]
    for path, message in structural:
        stage = path.split(".")[1].split("[")[0] if "." in path else "script"
        if stage not in ("project", "script", *STAGES):
            stage = "script"
        fail(stage, "invalid_structure", f"{path}: {message}")
    if issues:
        return {"valid": False, "issues": issues, "warnings": [], "expected_source_hashes": {},
                "readiness": _readiness(), "not_checked": NOT_CHECKED}

    expected = expected_source_hashes(packet)
    for stage, digest in expected.items():
        if packet[stage]["source_hash"] != digest:
            fail(stage, "stale_source", "upstream content changed; review and regenerate this handoff before supplying its new source_hash")

    project, script = packet["project"], packet["script"]
    board = packet["storyboard"]["board"]
    if project["total_frames"] / project["fps"] > 3600:
        fail("project", "duration_limit", "project exceeds the one-hour planning limit")
    board_result = validate_storyboard(board, expected_aspect_ratio=project["aspect_ratio"],
                                       expected_total_frames=project["total_frames"])
    for error in board_result["errors"]:
        fail("storyboard", "storyboard_gate", error)
    warnings.extend(board_result["warnings"])
    if board["fps"] != project["fps"]:
        fail("storyboard", "fps_drift", "storyboard FPS differs from project FPS")

    def index(items, key, stage, label):
        result = {}
        for item in items:
            ident = item[key]
            if ident in result:
                fail(stage, "duplicate_id", f"duplicate {label}: {ident}")
            result[ident] = item
        return result

    beats = index(script["beats"], "id", "script", "beat")
    lines = {}
    for beat in script["beats"]:
        for line in beat["dialogue"]:
            if line["id"] in lines:
                fail("script", "duplicate_dialogue", f"duplicate dialogue id: {line['id']}")
            lines[line["id"]] = {**line, "beat_id": beat["id"]}
    shots = index(board["shots"], "id", "storyboard", "shot")
    ordered_shots = [s["id"] for s in board["shots"]]
    staging = index(packet["direction"]["shots"], "shot_id", "direction", "shot")
    if [x["id"] for x in board["beats"]] != [x["id"] for x in script["beats"]]:
        fail("storyboard", "beat_drift", "board beats/order must exactly inherit the script beat IDs")
    if [x["shot_id"] for x in packet["direction"]["shots"]] != ordered_shots:
        fail("storyboard", "direction_shot_drift", "storyboard must inherit exactly the ordered direction shots")
    dialogue_owners = {}
    for sid, shot in shots.items():
        director = staging.get(sid)
        if director:
            for key in ("scene_id", "beat_ids", "start_state", "end_state"):
                if canonical(shot[key]) != canonical(director[key]):
                    fail("storyboard", "direction_drift", f"{sid}.{key} differs from the direction handoff")
        for stage, item in (("direction", director), ("storyboard", shot)):
            if item is None:
                continue
            for edge in ("start_state", "end_state"):
                for key, value in project["locked_state"].items():
                    if key not in item[edge] or canonical(item[edge][key]) != canonical(value):
                        fail(stage, "locked_state_drift", f"{sid}.{edge}: locked state {key} changed or disappeared")
        for bid in shot["beat_ids"]:
            if bid not in beats or beats[bid]["scene_id"] != shot["scene_id"]:
                fail("storyboard", "scene_beat_mismatch", f"{sid}: unknown beat or wrong scene: {bid}")
        if (shot["end_frame"] - shot["start_frame"]) / project["fps"] > 120:
            fail("storyboard", "shot_duration_limit", f"{sid}: draft planner supports at most 120 seconds per shot")
        for line in shot["dialogue"]:
            lid = line["line_id"]
            original = lines.get(lid)
            if (original is None or original["beat_id"] not in shot["beat_ids"]
                    or original["text"] != line["text"] or original["speaker"] != line["speaker"]):
                fail("storyboard", "dialogue_drift", f"{sid}: dialogue {lid} is not the exact script line/speaker")
            if lid in dialogue_owners:
                fail("storyboard", "dialogue_duplicate", f"dialogue {lid} assigned more than once")
            dialogue_owners[lid] = sid
    if set(dialogue_owners) != set(lines):
        fail("storyboard", "dialogue_coverage", "every script dialogue line must appear exactly once on the board")

    allowed = [] if references is None else references
    if (type(allowed) is not list or any(type(x) is not dict or set(x) != {"path", "role"}
            or type(x["path"]) is not str or type(x["role"]) is not str for x in allowed)):
        fail("storyboard", "reference_allowlist", "caller references must be an explicit array of {path,role}")
        allowed = []
    assets = index(board["assets"], "id", "storyboard", "asset")
    for asset in assets.values():
        if asset["status"] == "planned":
            if asset["path"] is not None or asset["sha256"] is not None:
                fail("storyboard", "planned_asset_claim", f"planned asset {asset['id']} cannot claim a real path or hash")
        elif (not asset["path"] or not Path(asset["path"]).is_absolute()
              or {"path": asset["path"], "role": asset["role"]} not in allowed):
            fail("storyboard", "unapproved_reference", f"asset {asset['id']} is not in the caller's explicit path/role allowlist")
    for shot in shots.values():
        for ref in shot["references"]:
            asset = assets.get(ref["asset_id"])
            if asset and (asset["status"] != "provided" or asset["role"] != ref["role"]):
                fail("storyboard", "unready_reference", f"{shot['id']}: planned reference or role drift cannot enter a workflow draft")

    cues = index(packet["audio"]["cues"], "id", "audio", "cue")
    for cid, cue in cues.items():
        overlaps = [sid for sid in ordered_shots if cue["start_frame"] < shots[sid]["end_frame"]
                    and shots[sid]["start_frame"] < cue["end_frame"]]
        if (cue["end_frame"] <= cue["start_frame"] or cue["end_frame"] > project["total_frames"]
                or overlaps != cue["shot_ids"] or cue["bridge"] != (len(overlaps) > 1)):
            fail("audio", "cue_window", f"{cid}: cue must name its exact overlapped shots and explicitly declare a cross-shot bridge")
        cue_beats = [bid for sid in overlaps for bid in shots[sid]["beat_ids"]]
        if any(bid not in cue_beats for bid in cue["beat_ids"]):
            fail("audio", "cue_beat", f"{cid}: cue points to a beat outside its shots")
        if cue["kind"] == "music" and project["sound_policy"]["music"] == "forbidden":
            fail("audio", "music_forbidden", f"{cid}: project forbids background music")
        lid = cue["dialogue_id"]
        if cue["kind"] == "dialogue":
            if lid not in lines or dialogue_owners.get(lid) not in cue["shot_ids"]:
                fail("audio", "cue_dialogue", f"{cid}: unknown or misplaced script dialogue")
            else:
                if cue["beat_ids"] != [lines[lid]["beat_id"]]:
                    fail("audio", "cue_dialogue_beat", f"{cid}: dialogue cue must retain its original script beat")
                line = next((x for x in shots[dialogue_owners[lid]]["dialogue"] if x["line_id"] == lid), None)
                if line and (cue["start_frame"], cue["end_frame"]) != (line["start_frame"], line["end_frame"]):
                    fail("audio", "dialogue_window", f"{cid}: dialogue cue must inherit its exact board window")
        elif lid is not None:
            fail("audio", "cue_dialogue", f"{cid}: a non-dialogue cue cannot claim a dialogue id")
        aid = cue["source_asset_id"]
        if aid is not None and aid not in assets:
            fail("audio", "cue_asset", f"{cid}: unknown source asset")
        if cue["placement"] == "generation":
            if (cue["source_kind"] in ("user_asset", "library") and aid is None
                    or aid is not None and (aid not in assets or assets[aid]["status"] != "provided"
                       or any(aid not in [r["asset_id"] for r in shots[sid]["references"]]
                              for sid in cue["shot_ids"] if sid in shots))):
                fail("audio", "generation_cue_reference", f"{cid}: a generation reference must be a provided allowed asset attached to every consuming shot")
        if cue["evidence_status"] == "reported" and (aid not in assets or not assets[aid]["sha256"]):
            fail("audio", "unproven_audio", f"{cid}: reported evidence needs an identified source/hash, still not verified by this tool")
    if sorted(c["dialogue_id"] for c in cues.values() if c["kind"] == "dialogue" and c["dialogue_id"] is not None) != sorted(lines):
        fail("audio", "dialogue_cue_coverage", "each script line requires exactly one identified dialogue cue")

    prompts = index(packet["prompts"]["shots"], "shot_id", "prompts", "shot")
    if [x["shot_id"] for x in packet["prompts"]["shots"]] != ordered_shots:
        fail("prompts", "prompt_coverage", "exactly one ordered prompt pair is required per board shot")
    for sid, shot in shots.items():
        prompt = prompts.get(sid)
        if not prompt:
            continue
        required_lines = [x["line_id"] for x in shot["dialogue"]]
        if prompt["dialogue_ids"] != required_lines or any(x["text"] not in prompt["video_prompt"] for x in shot["dialogue"]):
            fail("prompts", "prompt_dialogue", f"{sid}: exact dialogue text and IDs must pass to the video prompt")
        required_cues = [cid for cid, cue in cues.items() if cue["placement"] == "generation" and sid in cue["shot_ids"]]
        if prompt["cue_ids"] != required_cues:
            fail("prompts", "cue_consumption", f"{sid}: prompt must consume exactly its generation cues")
        if [x["cue_id"] for x in prompt["cue_bindings"]] != required_cues:
            fail("prompts", "cue_text_binding", f"{sid}: cue bindings must project each generation cue exactly once in order")
        for binding in prompt["cue_bindings"]:
            if binding["text"] not in prompt["video_prompt"]:
                fail("prompts", "cue_text_missing", f"{sid}: the platform text for cue {binding['cue_id']} is absent from the actual video prompt")
        if prompt["reference_asset_ids"] != [x["asset_id"] for x in shot["references"]]:
            fail("prompts", "prompt_reference", f"{sid}: prompt references differ from the approved board roles")

    events = packet["editorial"]["events"]
    if [x["shot_id"] for x in events] != ordered_shots:
        fail("editorial", "edit_coverage", "editorial events must cover every shot once in approved order")
    for event in events:
        sid = event["shot_id"]
        shot = shots.get(sid)
        if not shot:
            continue
        for key in ("beat_ids", "start_frame", "end_frame"):
            if canonical(event[key]) != canonical(shot[key]):
                fail("editorial", "edit_drift", f"{sid}.{key} no longer matches the board")
        required_cues = [cid for cid, cue in cues.items() if cue["placement"] == "post" and sid in cue["shot_ids"]]
        if event["cue_ids"] != required_cues:
            fail("editorial", "cue_consumption", f"{sid}: EDL must consume exactly its post cues; bridge cues retain the same ID")
        take = event["take"]
        if take:
            asset = assets.get(take["asset_id"])
            if (not asset or asset["status"] != "provided" or not asset["sha256"]
                    or take["out_frame"] <= take["in_frame"]):
                fail("editorial", "take_window", f"{sid}: reported take needs an allowed source/hash and valid window")
        if packet["editorial"]["status"] == "reported_windows" and take is None:
            fail("editorial", "pending_take", f"{sid}: a missing take window cannot be reported as supplied")
    editorial_status = "pending_media_verification" if any(e["take"] for e in events) else "planned"
    return {"valid": not issues, "issues": issues, "warnings": warnings,
            "expected_source_hashes": expected, "readiness": _readiness(not issues, editorial_status),
            "not_checked": NOT_CHECKED}


class HandoffError(ValueError):
    def __init__(self, report):
        super().__init__("creative handoff failed validation")
        self.report = report


def to_workflow_plan(packet: dict, *, references=None, image_provider="mock", video_provider="mock") -> dict:
    report = validate_packet(packet, references=references)
    if not report["valid"]:
        raise HandoffError(report)
    project, script, board = packet["project"], packet["script"], packet["storyboard"]["board"]
    assets = {a["id"]: a for a in board["assets"]}
    prompts = {p["shot_id"]: p for p in packet["prompts"]["shots"]}
    creative = {"schema_version": 1, "project_name": project["name"], "brief": project["brief"],
                "aspect_ratio": project["aspect_ratio"], "fps": project["fps"],
                "screenplay": script["screenplay"], "shooting_script": script["shooting_script"], "shots": []}
    for shot in board["shots"]:
        prompt = prompts[shot["id"]]
        creative["shots"].append({"id": shot["id"], "duration_seconds": (shot["end_frame"] - shot["start_frame"]) / project["fps"],
                                  "purpose": shot["purpose"], "start_state": canonical(shot["start_state"]),
                                  "end_state": canonical(shot["end_state"]), "image_prompt": prompt["image_prompt"],
                                  "video_prompt": prompt["video_prompt"],
                                  "reference_assets": [{"path": assets[r["asset_id"]]["path"], "role": r["role"]}
                                                       for r in shot["references"]]})
    validate_creative_plan(creative, references=references)
    return to_engine_plan(creative, image_provider=image_provider, video_provider=video_provider, references=references)


def _read_json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("JSON document exceeds 2 MB")
    return json.loads(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--references", type=Path, help="caller-selected JSON array of allowed {path,role}; never inferred from packet")
    parser.add_argument("--digests", action="store_true", help="report expected source hashes only; never stamp or approve")
    parser.add_argument("--output", type=Path, help="new draft plan file; no overwrite, no permission or generation")
    parser.add_argument("--image-provider", default="mock")
    parser.add_argument("--video-provider", default="mock")
    args = parser.parse_args(argv)
    try:
        packet = _read_json(args.packet)
        allowed = _read_json(args.references) if args.references else []
        report = validate_packet(packet, references=allowed)
        if args.digests:
            print(json.dumps({"expected_source_hashes": report["expected_source_hashes"],
                              "valid": report["valid"], "approval_granted": False,
                              "meaning": "content drift check only; no packet is modified"}, ensure_ascii=False, indent=2))
            return 0 if report["expected_source_hashes"] else 1
        if args.output and report["valid"]:
            plan = to_workflow_plan(packet, references=allowed, image_provider=args.image_provider, video_provider=args.video_provider)
            payload = (json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
            # Finish the one draft privately before atomically linking it into
            # the caller-selected new path. Never unlink a public output on an
            # exception: another process may have replaced it in the meantime.
            with tempfile.TemporaryDirectory(prefix=".creative-handoff-", dir=args.output.parent) as temp:
                staged = Path(temp) / "draft.json"
                fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.link(staged, args.output)
            report["workflow_draft_exported"] = str(args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if report["valid"] else 1
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"valid": False, "error": "input_or_output_refused", "workflow_draft_exported": False,
                          "generation_authorized": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
