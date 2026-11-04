"""A small SQLite production state machine, with no implicit remote execution.

An operation identity and its mutation phase are committed *before* calling a
provider. A restarted PREPARING/SUBMITTING/UNKNOWN operation is only polled.
Reservations include failed and uncertain writes: a missing receipt is never
evidence that a provider did not charge. All money is finite Decimal text.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import stat
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable


class WorkflowError(ValueError):
    """A workflow refusal that is safe to show to a human."""


@dataclass(frozen=True)
class Limits:
    max_shots: int = 24
    max_concurrent: int = 1
    max_operations: int = 96
    max_attempts: int = 2
    approval_ttl: int = 3600

    def __post_init__(self):
        for key, maximum in (("max_shots", 48), ("max_concurrent", 4),
                             ("max_operations", 192), ("max_attempts", 3),
                             ("approval_ttl", 86400)):
            value = getattr(self, key)
            if type(value) is not int or not 1 <= value <= maximum:
                raise WorkflowError(f"{key} must be between 1 and hard limit {maximum}")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _money(value: Any) -> Decimal:
    if isinstance(value, (float, bool)):
        raise WorkflowError("budget amounts must be Decimal strings, not floats or booleans")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise WorkflowError("invalid budget amount") from None
    if not result.is_finite() or result < 0:
        raise WorkflowError("budget must be finite and non-negative")
    return result


def _file(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise WorkflowError(f"asset is not a regular file: {p}")
    digest = hashlib.sha256()
    with p.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(p), "sha256": digest.hexdigest(), "size": p.stat().st_size}


def _private_dir(path: Path):
    """Make new directories private, without chmod-ing an existing user folder."""
    missing = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    if not cursor.is_dir():
        raise WorkflowError("state parent is not a directory")
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            if not directory.is_dir():
                raise WorkflowError("state directory was replaced") from None


def _no_credentials(value):
    forbidden = {"api_key", "access_token", "refresh_token", "password", "secret", "credentials", "cookie", "cookies"}
    if isinstance(value, dict):
        if any(str(key).lower().replace("-", "_") in forbidden for key in value):
            raise WorkflowError("credentials belong in the provider's own authentication store, not a plan")
        for child in value.values():
            _no_credentials(child)
    elif isinstance(value, list):
        for child in value:
            _no_credentials(child)


class Engine:
    """Persistent core. Provider/channel calls are injected, never shell commands.

    Provider: identity(), probe(), prepare/quote/submit/poll/download(operation).
    Each action receives one JSON-compatible operation dict. Compositor accepts
    one operation dict, returning {status, path, simulated}. Channel.deliver takes
    an event dict. A channel callback must only enqueue decisions, never tick.
    """

    ACTIVE = ("preparing", "submitting", "submitted", "running", "unknown")
    # Only known local compositor codes may leave this boundary. A regex alone
    # cannot distinguish a code-shaped secret supplied by an injected callback.
    COMPOSITION_REASONS = frozenset({
        "approved_asset_hash_changed", "aspect_differs_from_plan_no_automatic_crop",
        "assembled_duration_does_not_match_inputs", "duration_differs_from_approved_plan_no_automatic_trim",
        "explicit_approved_aspect_and_fps_required", "ffmpeg_or_ffprobe_not_installed",
        "fps_differs_from_plan_no_automatic_retime", "hdr_requires_explicit_color_workflow",
        "incompatible_streams_no_automatic_transcode", "invalid_approved_duration", "invalid_or_unapproved_input",
        "live_assembly_requires_live_mode", "media_outside_assembly_limits", "media_probe_failed",
        "native_audio_boundary_incomplete", "native_audio_boundary_not_explained",
        "native_constant_cadence_differs_from_plan", "native_container_padding_not_explained",
        "native_frame_count_mismatch", "native_frame_gap_differs_from_plan",
        "native_frame_grid_drift_exceeds_one_frame", "native_frame_timing_incomplete",
        "native_frame_timing_insufficient", "native_frame_timing_probe_failed", "native_video_boundary_not_explained",
        "non_square_or_unknown_pixels_require_explicit_normalization", "output_exists_not_overwritten",
        "requires_1_to_64_inputs", "requires_one_video_and_at_most_one_audio_track",
        "rotated_media_requires_explicit_normalization", "rotated_or_unknown_orientation_requires_explicit_normalization",
        "stream_copy_changed_native_audio_timing", "stream_copy_changed_native_frame_timing",
        "stream_copy_failed_no_automatic_reencode", "unusable_media_metadata",
        "normalization_invalid_policy", "normalization_authorization_required", "normalization_nonintegral_frame_duration",
        "normalization_even_dimensions_required", "normalization_dimensions_differ", "normalization_timing_incomplete",
        "normalization_duration_outside_approved_tail", "normalization_mixed_audio_tracks", "normalization_audio_format_unknown",
        "normalization_audio_format_unsupported", "normalization_audio_formats_differ", "normalization_av_start_offset",
        "normalization_nonintegral_audio_duration", "normalization_short_video_no_padding", "normalization_short_audio_no_padding",
        "normalization_command_failed", "normalization_command_timeout", "normalization_output_missing",
        "normalization_pcm_changed_or_padded", "normalization_output_spec_mismatch", "normalization_frame_grid_mismatch",
        "normalization_audio_timeline_mismatch", "normalization_unexplained_audio_padding", "normalization_failed",
    })

    def __init__(self, db_path, providers=None, channel=None, clock=None,
                 compositor=None, limits=None, artifact_dir=None):
        raw_db = Path(db_path).expanduser() if str(db_path) != ":memory:" else None
        if raw_db is not None and raw_db.is_symlink():
            raise WorkflowError("workflow database cannot be a symlink")
        self.db_path = str(raw_db.resolve()) if raw_db is not None else ":memory:"
        self.clock: Callable[[], float] = clock or time.time
        self.limits = limits or Limits()
        self.channel = channel
        self.compositor = compositor
        self.lock = threading.RLock()
        distribution = Path(__file__).resolve().parents[2]
        state_root = Path.home() / ".local" / "state" / "hardcore-director"
        if self.db_path != ":memory:":
            db_file = Path(self.db_path)
            if db_file.is_relative_to(distribution):
                raise WorkflowError("workflow state must be outside the Skill/release repository")
            _private_dir(db_file.parent)
            try:
                descriptor = os.open(str(db_file), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            except FileExistsError:
                if db_file.is_symlink() or not db_file.is_file() or stat.S_IMODE(db_file.stat().st_mode) & 0o077:
                    raise WorkflowError("existing workflow database must be a private regular file (0600)") from None
            else:
                os.close(descriptor)
        self.artifact_dir = Path(artifact_dir or (
            (Path(self.db_path).parent if raw_db is not None else state_root) / "workflow-artifacts")).expanduser().resolve()
        if self.artifact_dir.is_relative_to(distribution):
            raise WorkflowError("workflow artifacts must be outside the Skill/release repository")
        _private_dir(self.artifact_dir)
        if providers is None:
            from .providers import get_provider
            providers = {"mock": get_provider("mock")}
        self.providers = providers
        if self.db_path != ":memory:":
            for suffix in ("-wal", "-shm"):
                existing = Path(self.db_path + suffix)
                if existing.is_symlink() or (existing.exists() and not existing.is_file()):
                    raise WorkflowError("unsafe SQLite sidecar path")
        self.db = sqlite3.connect(self.db_path, timeout=30, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, brief TEXT NOT NULL, mode TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 0, plan TEXT, plan_hash TEXT,
            final_artifact TEXT, final_accepted INTEGER NOT NULL DEFAULT 0,
            created REAL NOT NULL, updated REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS shots (
            project_id TEXT NOT NULL REFERENCES projects(id), id TEXT NOT NULL,
            ordinal INTEGER NOT NULL, spec TEXT NOT NULL,
            image TEXT, video TEXT, PRIMARY KEY(project_id,id));
          CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            stage TEXT NOT NULL, revision INTEGER NOT NULL, actor TEXT NOT NULL,
            binding TEXT NOT NULL, binding_hash TEXT NOT NULL, shot_ids TEXT NOT NULL,
            scope TEXT NOT NULL, amount TEXT NOT NULL, currency TEXT NOT NULL,
            created REAL NOT NULL, expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS budgets (
            project_id TEXT NOT NULL, stage TEXT NOT NULL, amount TEXT NOT NULL,
            currency TEXT NOT NULL, PRIMARY KEY(project_id,stage));
          CREATE TABLE IF NOT EXISTS operations (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            revision INTEGER NOT NULL, stage TEXT NOT NULL, shot_id TEXT NOT NULL,
            attempt INTEGER NOT NULL, provider_key TEXT NOT NULL, provider TEXT NOT NULL,
            account TEXT NOT NULL, live INTEGER NOT NULL, status TEXT NOT NULL,
            phase TEXT NOT NULL, payload TEXT NOT NULL, result TEXT, task_id TEXT,
            quote TEXT, reserved TEXT NOT NULL DEFAULT '0', currency TEXT,
            approval_id TEXT, error TEXT, created REAL NOT NULL, updated REAL NOT NULL,
            UNIQUE(project_id,revision,stage,shot_id));
          CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, type TEXT NOT NULL,
            payload TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
        """)
        self._secure_sidecars()

    def _secure_sidecars(self):
        if self.db_path == ":memory:":
            return
        for suffix in ("-wal", "-shm"):
            path = Path(self.db_path + suffix)
            if path.exists():
                if path.is_symlink() or not path.is_file():
                    raise WorkflowError("unsafe SQLite sidecar path")
                os.chmod(path, 0o600)

    def close(self):
        self.db.close()

    @contextmanager
    def _tx(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            else:
                self.db.execute("COMMIT")
                self._secure_sidecars()

    def _project(self, project_id):
        row = self.db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise WorkflowError("unknown project")
        return dict(row)

    def _shots(self, project_id):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM shots WHERE project_id=? ORDER BY ordinal", (project_id,))]

    def _plan(self, project):
        return json.loads(project["plan"]) if project["plan"] else None

    @staticmethod
    def _actor(actor):
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 200:
            raise WorkflowError("an identified human actor is required")
        return actor.strip()

    def init_project(self, brief, actor="local", mode="dry-run", project_id=None):
        actor = self._actor(actor)
        _no_credentials(brief)
        if mode not in ("dry-run", "mock", "live"):
            raise WorkflowError("mode must be dry-run, mock or live")
        pid = project_id or "hc-" + uuid.uuid4().hex[:16]
        if not isinstance(pid, str) or not pid or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in pid):
            raise WorkflowError("project_id must contain only letters, numbers, hyphen or underscore")
        with self._tx() as db:
            db.execute("INSERT INTO projects(id,brief,mode,created,updated) VALUES(?,?,?,?,?)",
                       (pid, _json(brief), mode, self.clock(), self.clock()))
            self._event(db, pid, "project_created", {"actor": actor})
        return self.status(pid)

    def set_plan(self, project_id, plan, actor="local"):
        actor = self._actor(actor)
        if not isinstance(plan, dict) or not isinstance(plan.get("shots"), list):
            raise WorkflowError("plan.shots must be a list")
        try:
            plan = json.loads(_json(plan))
        except (TypeError, ValueError):
            raise WorkflowError("plan must contain only finite JSON values") from None
        # Effective generation defaults are part of what the human reviews,
        # not hidden provider-only values that composition can later ignore.
        plan.setdefault("aspect_ratio", "16:9")
        plan.setdefault("fps", 24)
        if not isinstance(plan["aspect_ratio"], str) or not re.fullmatch(r"[1-9][0-9]{0,3}:[1-9][0-9]{0,3}", plan["aspect_ratio"]):
            raise WorkflowError("aspect_ratio must be an explicit positive integer ratio such as 16:9")
        if type(plan["fps"]) is not int or not 1 <= plan["fps"] <= 120:
            raise WorkflowError("fps must be an integer between 1 and 120, not a boolean")
        composition = plan.get("composition", {"mode": "stream_copy"})
        if (not isinstance(composition, dict) or set(composition) != {"mode"}
                or composition["mode"] not in ("stream_copy", "normalize_cfr")):
            raise WorkflowError("composition must explicitly select stream_copy or normalize_cfr without extra fields")
        _no_credentials(plan)
        shots = plan["shots"]
        if not 1 <= len(shots) <= self.limits.max_shots:
            raise WorkflowError(f"plan requires 1..{self.limits.max_shots} shots")
        seen = set()
        for shot in shots:
            sid = shot.get("id") if isinstance(shot, dict) else None
            if not isinstance(sid, str) or not sid or sid in seen:
                raise WorkflowError("shot IDs must be nonempty and unique")
            seen.add(sid)
            seconds = shot.get("duration_seconds")
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 < seconds <= 180:
                raise WorkflowError("duration_seconds must be finite and between 0 and 180")
            for key in ("image_prompt", "video_prompt"):
                if not isinstance(shot.get(key), str) or not shot[key].strip():
                    raise WorkflowError(f"shot {sid} requires {key}")
            for asset in shot.get("reference_assets", []):
                if not isinstance(asset, dict) or not asset.get("path"):
                    raise WorkflowError("reference assets require explicit local paths")
                _file(asset["path"])
        for stage in ("image", "video"):
            self._provider(plan, stage)
        with self._tx() as db:
            project = self._project(project_id)
            previous = self._plan(project) or {}
            preserve = all(previous.get(k) == plan.get(k) for k in ("aspect_ratio", "fps", "providers"))
            old = {s["id"]: s for s in self._shots(project_id)} if preserve else {}
            db.execute("UPDATE projects SET plan=?,plan_hash=?,revision=revision+1,final_artifact=NULL,final_accepted=0,updated=? WHERE id=?",
                       (_json(plan), _hash(plan), self.clock(), project_id))
            db.execute("DELETE FROM shots WHERE project_id=?", (project_id,))
            for i, shot in enumerate(shots):
                image, video = None, None
                retained = old.get(shot["id"])
                if retained and retained["spec"] == _json(shot):
                    for field in ("image", "video"):
                        if retained[field]:
                            asset = json.loads(retained[field])
                            try:
                                valid = _file(asset["path"])["sha256"] == asset["sha256"]
                                operation = db.execute("SELECT payload FROM operations WHERE id=?", (asset.get("operation_id"),)).fetchone()
                                if not operation:
                                    valid = False
                                else:
                                    for source in json.loads(operation["payload"]).get("input_assets", []):
                                        valid = valid and _file(source.get("source_path", source["path"]))["sha256"] == source["sha256"]
                            except WorkflowError:
                                valid = False
                            if valid and field == "image":
                                image = retained[field]
                            elif valid and image is not None:
                                video = retained[field]
                db.execute("INSERT INTO shots(project_id,id,ordinal,spec,image,video) VALUES(?,?,?,?,?,?)", (project_id, shot["id"], i, _json(shot), image, video))
            db.execute("UPDATE approvals SET revoked=1 WHERE project_id=?", (project_id,))
            self._event(db, project_id, "plan_review", {"actor": actor, "stage": "plan"})
        return self.status(project_id)

    # The shorter name is useful to API consumers as well as the CLI.
    plan = set_plan

    def _provider(self, plan, stage):
        key = plan.get("providers", {}).get(stage, "mock")
        if key not in self.providers:
            raise WorkflowError(f"provider is not configured: {key}")
        provider = self.providers[key]
        identity = self._identity(provider)
        if not isinstance(identity, dict) or not identity.get("provider") or not identity.get("account"):
            raise WorkflowError("provider must identify its provider and account")
        return key, provider, identity

    @staticmethod
    def _identity(provider):
        identity = dict(provider.identity())
        # Credentials remain in the provider's own store. Hash configuration
        # rather than copying it: model/mode/canvas/profile edits revoke consent.
        try:
            identity["execution_config_hash"] = _hash(getattr(provider, "config", {}))
        except (TypeError, ValueError):
            raise WorkflowError("provider configuration must contain only finite JSON values") from None
        return identity

    def _binding(self, project, stage):
        plan = self._plan(project)
        if not plan:
            raise WorkflowError("a plan is required")
        if stage == "composition":
            details = self._composition_details(project)
            epoch = ""
            for row in self.db.execute("SELECT id,payload FROM events WHERE project_id=? AND type='composition_rejected' ORDER BY created DESC,rowid DESC", (project["id"],)):
                if json.loads(row["payload"]).get("revision") == project["revision"]:
                    epoch = row["id"]
                    break
            return {"revision": project["revision"], "plan_hash": project["plan_hash"],
                    "asset_hash": _hash(details["shots"]), "providers": {}, "composition": details,
                    "local_review_epoch": epoch}
        assets = []
        for shot in self._shots(project["id"]):
            spec = json.loads(shot["spec"])
            assets.extend({"shot_id": shot["id"], "role": a.get("role", "reference"), **_file(a["path"])}
                          for a in spec.get("reference_assets", []))
            for field in (("image",) if stage == "storyboard" else ("image", "video") if stage == "final" else ()):
                if not shot[field]:
                    raise WorkflowError(f"{shot['id']} has no {field} to review")
                asset = json.loads(shot[field])
                current = _file(asset["path"])
                if current["sha256"] != asset["sha256"]:
                    raise WorkflowError(f"generated {field} changed; reject and regenerate {shot['id']}")
                assets.append({"shot_id": shot["id"], "role": field, **current})
        stages = ("image", "video") if stage == "final" else ("image",) if stage == "plan" else ("video",)
        if stage == "final" and project["final_artifact"]:
            final = json.loads(project["final_artifact"])
            actual = _file(final["path"])
            if actual["sha256"] != final["sha256"]:
                raise WorkflowError("composition changed after delivery")
            assets.append({"role": "composition", **actual})
        identities = {s: self._provider(plan, s)[2] for s in stages}
        return {"revision": project["revision"], "plan_hash": project["plan_hash"],
                "asset_hash": _hash(assets), "providers": identities}

    def _normalizes(self, project):
        return (self._plan(project) or {}).get("composition", {}).get("mode") == "normalize_cfr"

    def _composition_details(self, project):
        plan = self._plan(project)
        if not plan or not self._normalizes(project):
            raise WorkflowError("this plan does not request normalization")
        inputs = []
        for shot in self._shots(project["id"]):
            if not shot["video"]:
                raise WorkflowError("all videos must be complete before local processing review")
            asset = json.loads(shot["video"])
            actual = _file(asset["path"])
            if actual["sha256"] != asset["sha256"]:
                raise WorkflowError("video asset changed before composition")
            inputs.append({"shot_id": shot["id"], "sha256": actual["sha256"],
                           "duration_seconds": json.loads(shot["spec"])["duration_seconds"]})
        if not inputs:
            raise WorkflowError("local processing requires video inputs")
        return {"mode": "normalize_cfr", "fps": plan["fps"], "aspect_ratio": plan["aspect_ratio"], "shots": inputs}

    @staticmethod
    def _local_composition_scope(binding):
        return {"stages": [], "allow_uploads": False,
                **{key: binding[key] for key in ("revision", "plan_hash", "asset_hash", "composition")}}

    def _composition_approval(self, project, binding=None):
        if not self._normalizes(project):
            return None
        try:
            binding = binding or self._binding(project, "composition")
            approval = self._approval(project, "composition", binding=binding)
            if (approval and _money(approval["amount"]) == 0
                    and json.loads(approval["scope"]) == self._local_composition_scope(binding)
                    and set(json.loads(approval["shot_ids"])) == {s["id"] for s in self._shots(project["id"])}):
                return approval
        except (WorkflowError, ValueError, KeyError):
            pass
        return None

    def _request_composition_review(self, project):
        binding = self._binding(project, "composition")
        if self._composition_rejected(project, binding):
            return
        expected = _hash(binding)
        for row in self.db.execute("SELECT type,payload FROM events WHERE project_id=? AND type IN ('composition_review','composition_rejected') ORDER BY created DESC,rowid DESC",
                                   (project["id"],)):
            event = json.loads(row["payload"])
            if event.get("revision") != project["revision"] or event.get("binding_hash") != expected:
                continue
            if row["type"] == "composition_rejected" or event.get("expires_at", 0) > self.clock():
                return
            break
        with self._tx() as db:
            self._event(db, project["id"], "composition_review", {"stage": "composition",
                        "shot_ids": [s["id"] for s in self._shots(project["id"])],
                        "message": "原片规格统一需要本次明确同意；保留原件，不上传、不生成新镜头，也不新增模型费用。"})

    def _composition_rejected(self, project, binding):
        identity = _hash({key: value for key, value in binding.items() if key != "local_review_epoch"})
        for row in self.db.execute("SELECT type,payload FROM events WHERE project_id=? AND type IN ('approved','composition_rejected') ORDER BY created DESC,rowid DESC", (project["id"],)):
            event = json.loads(row["payload"])
            if event.get("revision") != project["revision"] or event.get("stage") != "composition":
                continue
            return row["type"] == "composition_rejected" and event.get("processing_identity") == identity
        return False

    def _approval(self, project, stage, shot_id=None, binding=None):
        try:
            binding = binding if binding is not None else self._binding(project, stage)
        except WorkflowError:
            return None
        for row in self.db.execute("SELECT * FROM approvals WHERE project_id=? AND stage=? AND revoked=0 AND expires>? ORDER BY created DESC",
                                   (project["id"], stage, self.clock())):
            approval = dict(row)
            if approval["binding_hash"] == _hash(binding) and (shot_id is None or shot_id in json.loads(approval["shot_ids"])):
                return approval
        return None

    def _content_approval(self, project, stage, shot_id=None, binding=None):
        """A finished action retains its review history, never spending power.

        Only expiry may be ignored here. Plan, reference bytes, provider/account
        configuration, revocation and every completed output hash still match.
        New provider writes deliberately keep using _approval/_authorized.
        """
        try:
            binding = binding if binding is not None else self._binding(project, stage)
            current = self._approval(project, stage, shot_id, binding=binding)
            if current:
                return current
            field = {"plan": "image", "storyboard": "video"}.get(stage)
            shots = self._shots(project["id"])
            if field is None or not shots or any(not shot[field] for shot in shots):
                return None
            for shot in shots:
                asset = json.loads(shot[field])
                if _file(asset["path"])["sha256"] != asset["sha256"]:
                    return None
            for row in self.db.execute("SELECT * FROM approvals WHERE project_id=? AND stage=? AND revision=? AND revoked=0 ORDER BY created DESC",
                                       (project["id"], stage, project["revision"])):
                approval = dict(row)
                if approval["binding_hash"] == _hash(binding) and (shot_id is None or shot_id in json.loads(approval["shot_ids"])):
                    return approval
        except WorkflowError:
            return None
        return None

    def approve(self, project_id, stage="plan", actor="local", shot_ids=None,
                ttl_seconds=None, budget=None, live_scope=None, expected_revision=None,
                expected_binding_hash=None, expires_at=None):
        actor = self._actor(actor)
        if stage not in ("plan", "storyboard", "composition", "final"):
            raise WorkflowError("unknown approval stage")
        with self._tx() as db:
            project = self._project(project_id)
            if expected_revision is not None and expected_revision != project["revision"]:
                raise WorkflowError("approval revision is stale")
            binding = self._binding(project, stage)
            if expected_binding_hash is not None and expected_binding_hash != _hash(binding):
                raise WorkflowError("approval content changed")
            ids = [s["id"] for s in self._shots(project_id)]
            selected = list(shot_ids or ids)
            if not selected or any(s not in ids for s in selected):
                raise WorkflowError("approval contains an unknown shot")
            if stage == "plan" and set(selected) != set(ids):
                raise WorkflowError("plan approval covers the complete plan; review specific images at storyboard stage")
            if stage == "storyboard" and not self._content_approval(project, "plan"):
                raise WorkflowError("approve the current plan before the storyboard")
            if stage == "final" and not project["final_artifact"]:
                raise WorkflowError("there is no composition to accept")
            if stage == "composition":
                if set(selected) != set(ids):
                    raise WorkflowError("local processing approval covers all ordered inputs")
                if (not self._content_approval(project, "plan")
                        or not all(self._content_approval(project, "storyboard", sid) for sid in ids)):
                    raise WorkflowError("review the current plan and storyboard before local processing")
            action_stage = "image" if stage == "plan" else "video"
            plan = self._plan(project)
            identity = {} if stage == "composition" else self._provider(plan, action_stage)[2]
            live = bool(identity.get("live", False)) and stage not in ("composition", "final")
            scope = dict(live_scope or {})
            for binding_key in ("revision", "plan_hash", "asset_hash"):
                if binding_key in scope and scope[binding_key] != binding[binding_key]:
                    raise WorkflowError(f"approval {binding_key} is stale")
            budget_explicit = budget is not None
            budget = budget or {"amount": "0", "currency": "CNY"}
            amount = _money(budget.get("amount"))
            currency = budget.get("currency")
            if not isinstance(currency, str) or not currency.strip():
                raise WorkflowError("budget requires a currency")
            content_only = False
            if stage == "composition":
                expected_scope = self._local_composition_scope(binding)
                if live_scope is None:
                    scope = expected_scope
                if amount != 0 or scope != expected_scope:
                    raise WorkflowError("local processing approval must exactly bind this action with zero generation and no uploads")
                content_only = True
            elif live:
                if project["mode"] != "live":
                    raise WorkflowError("live provider cannot run in a dry-run project")
                if not budget_explicit:
                    raise WorkflowError("live approval requires an explicit stage budget")
                content_only = (live_scope is not None and scope.get("stages") == []
                                and scope.get("allow_uploads") is False and amount == 0)
                if content_only:
                    # Reviewing content is not authority to upload or spend. Bind
                    # even this non-spending decision to the displayed account
                    # and the exact plan/assets so it cannot drift into a grant.
                    if scope.get("provider") != identity["provider"] or scope.get("account") != identity["account"]:
                        raise WorkflowError("content approval is for a different provider/account")
                    if any(scope.get(key) != binding[key] for key in ("revision", "plan_hash", "asset_hash")):
                        raise WorkflowError("content approval requires the exact revision, plan and assets")
                else:
                    self._check_scope(scope, binding, action_stage, identity)
            else:
                scope.setdefault("stages", [])
            ttl = ttl_seconds if ttl_seconds is not None else self.limits.approval_ttl
            if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or not 0 < ttl <= 86400:
                raise WorkflowError("approval TTL must be between 0 and 86400 seconds")
            expires = min(float(expires_at) if expires_at is not None else self.clock() + ttl, self.clock() + ttl)
            if not expires > self.clock():
                raise WorkflowError("approval has expired")
            if stage not in ("composition", "final"):
                previous = db.execute("SELECT * FROM budgets WHERE project_id=? AND stage=?", (project_id, action_stage)).fetchone()
                used, used_currency = self._reserved(project_id, action_stage)
                if previous and previous["currency"] != currency:
                    raise WorkflowError("a stage budget cannot mix currencies")
                if used_currency and used_currency != currency:
                    raise WorkflowError("reserved operations use a different currency")
                if amount < used:
                    raise WorkflowError("budget cannot fall below already reserved or spent amount")
                if not content_only:
                    # A content decision stores its displayed zero cap only in
                    # the approval; it does not establish a spending currency.
                    db.execute("INSERT OR REPLACE INTO budgets VALUES(?,?,?,?)", (project_id, action_stage, str(amount), currency))
            aid = "approval-" + uuid.uuid4().hex
            for old in db.execute("SELECT id,shot_ids FROM approvals WHERE project_id=? AND stage=? AND revoked=0", (project_id, stage)).fetchall():
                if set(json.loads(old["shot_ids"])) & set(selected):
                    db.execute("UPDATE approvals SET revoked=1 WHERE id=?", (old["id"],))
            db.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
                       (aid, project_id, stage, project["revision"], actor, _json(binding), _hash(binding), _json(selected),
                        _json(scope), str(amount), currency, self.clock(), expires))
            if stage == "final":
                db.execute("UPDATE projects SET final_accepted=1,updated=? WHERE id=?", (self.clock(), project_id))
            self._event(db, project_id, "approved", {"actor": actor, "stage": stage, "shot_ids": selected, "approval_id": aid})
        return self.status(project_id)

    def _check_scope(self, scope, binding, stage, identity):
        if identity.get("verified") is not True:
            raise WorkflowError("live account identity is not verified")
        if stage not in scope.get("stages", []):
            raise WorkflowError(f"live {stage} generation is not authorized")
        if scope.get("provider") != identity["provider"] or scope.get("account") != identity["account"]:
            raise WorkflowError("live authorization is for a different provider/account")
        if scope.get("allow_uploads") is not True:
            raise WorkflowError("live prompt/reference uploads require explicit authorization")
        for key in ("revision", "plan_hash", "asset_hash"):
            if key in scope and scope[key] != binding[key]:
                raise WorkflowError(f"live authorization {key} is stale")

    def _generation_allowed(self, project, review_stage, shot_id=None, binding=None, approval=None):
        """Content approval alone must not allocate a live generation operation."""
        if review_stage not in ("plan", "storyboard"):
            return False
        try:
            binding = binding if binding is not None else self._binding(project, review_stage)
            approval = approval if approval is not None else self._approval(project, review_stage, shot_id, binding=binding)
            if not approval:
                return False
            action_stage = "image" if review_stage == "plan" else "video"
            identity = binding["providers"][action_stage]
            if identity.get("live"):
                if project["mode"] != "live":
                    return False
                self._check_scope(json.loads(approval["scope"]), binding, action_stage, identity)
            return True
        except WorkflowError:
            return False

    def reject(self, project_id, stage="storyboard", actor="local", shot_ids=None, reason="", expected_revision=None, expected_binding_hash=None):
        actor = self._actor(actor)
        if stage not in ("plan", "storyboard", "composition", "final"):
            raise WorkflowError("unknown rejection stage")
        with self._tx() as db:
            project = self._project(project_id)
            if expected_revision is not None and expected_revision != project["revision"]:
                raise WorkflowError("rejection revision is stale")
            if expected_binding_hash is not None and expected_binding_hash != _hash(self._binding(project, stage)):
                raise WorkflowError("rejection content changed")
            ids = [s["id"] for s in self._shots(project_id)]
            selected = list(shot_ids or ids)
            if any(s not in ids for s in selected):
                raise WorkflowError("rejection contains unknown shots")
            if stage == "composition":
                binding = self._binding(project, stage)
                db.execute("UPDATE approvals SET revoked=1 WHERE project_id=? AND stage='composition'", (project_id,))
                self._event(db, project_id, "composition_rejected", {"actor": actor, "stage": stage,
                            "shot_ids": ids, "binding_hash": _hash(binding), "reason": reason,
                            "processing_identity": _hash({key: value for key, value in binding.items() if key != "local_review_epoch"})})
                return self.status(project_id)
            if stage in ("storyboard", "final"):
                for sid in selected:
                    fields = "image=NULL,video=NULL" if stage == "storyboard" else "video=NULL"
                    db.execute(f"UPDATE shots SET {fields} WHERE project_id=? AND id=?", (project_id, sid))
            db.execute("UPDATE projects SET revision=revision+1,final_artifact=NULL,final_accepted=0,updated=? WHERE id=?", (self.clock(), project_id))
            db.execute("UPDATE approvals SET revoked=1 WHERE project_id=?", (project_id,))
            self._event(db, project_id, "rejected", {"actor": actor, "stage": stage, "shot_ids": selected, "reason": reason})
        return self.status(project_id)

    def resume(self, project_id, operation_id, actor="local"):
        """Locally recover a refusal using evidence, without repeating a write.

        A quote-only refusal can be preflighted again. A saved node can proceed
        only with an explicit provider receipt that generation was not submitted.
        Every other interrupted mutation becomes poll-only on the original ID.
        This method is intentionally absent from remote channel commands.
        """
        actor = self._actor(actor)
        op = self._op(operation_id)
        if op["project_id"] != project_id:
            raise WorkflowError("operation belongs to another project")
        if op["status"] not in ("needs_approval", "needs_setup", "needs_project_selection", "unknown"):
            raise WorkflowError("only refused or uncertain operations can be resumed")
        proof = {**op["result"], **op["payload"]}
        no_submission = not op["task_id"] and not proof.get("submit_attempted")
        if op["phase"] == "planned" and no_submission:
            self._authorized(op)
            state, phase, action = "planned", "planned", "quote_only_preflight"
        elif (proof.get("saved") is True and proof.get("not_submitted") is True
              and proof.get("awaiting_confirmation") is True and no_submission):
            self._authorized(op)
            state, phase, action = "prepared", "prepared", "same_saved_node_after_approval"
        elif proof.get("side_effects") == "none" and op["phase"] == "prepare" and no_submission and not proof.get("saved"):
            self._authorized(op)
            state, phase, action = "planned", "planned", "provider_proved_no_side_effects"
        else:
            # Recovery polling may outlive an approval; it cannot incur a new
            # generation. The provider still verifies its original account.
            state, phase, action = "unknown", op["phase"], "poll_only_no_write_retry"
        with self._tx() as db:
            current = db.execute("SELECT status FROM operations WHERE id=?", (operation_id,)).fetchone()
            if current["status"] != op["status"]:
                raise WorkflowError("operation changed during recovery")
            db.execute("UPDATE operations SET status=?,phase=?,error=NULL,updated=? WHERE id=?", (state, phase, self.clock(), operation_id))
            self._event(db, project_id, "operation_resumed", {"actor": actor, "operation_id": operation_id, "recovery": action})
        result = self.status(project_id)
        result["resume_action"] = action
        return result

    def _reserved(self, project_id, stage, excluding=None):
        total, currency = Decimal("0"), None
        for row in self.db.execute("SELECT id,reserved,currency FROM operations WHERE project_id=? AND stage=?", (project_id, stage)):
            if row["id"] == excluding or not row["currency"]:
                continue
            if currency is not None and currency != row["currency"]:
                raise WorkflowError("operation ledger contains mixed currencies")
            currency = row["currency"]
            total += _money(row["reserved"])
        return total, currency

    def _event(self, db, project_id, kind, extra=None, *, event_id=None):
        project = self._project(project_id)
        event_id = event_id or "event-" + uuid.uuid4().hex
        payload = {"event_id": event_id, "project_id": project_id, "job_id": project_id,
                   "revision": project["revision"], "type": kind, "stage": "", "message": kind,
                   "artifacts": [], **(extra or {})}
        review_stage = payload.get("stage")
        if kind.endswith("_review") and review_stage in ("plan", "storyboard", "composition", "final"):
            try:
                binding = self._binding(project, review_stage)
                if review_stage == "composition":
                    payload.update({"approval_scope": self._local_composition_scope(binding),
                                    "budget": {"amount": "0", "currency": "CNY"},
                                    "binding_hash": _hash(binding), "expires_at": self.clock() + self.limits.approval_ttl})
                    db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?,?,0,?)", (event_id, project_id, kind, _json(payload), self.clock()))
                    return
                action_stage = "image" if review_stage == "plan" else "video"
                identity = self._provider(self._plan(project), action_stage)[2]
                scope = {} if review_stage == "final" else dict(self._plan(project).get("requested_live_scopes", {}).get(action_stage, {}))
                scope.update({"revision": project["revision"], "plan_hash": binding["plan_hash"], "asset_hash": binding["asset_hash"]})
                scope.setdefault("stages", [])
                scope.setdefault("provider", identity["provider"])
                scope.setdefault("account", identity["account"])
                scope.setdefault("allow_uploads", False)
                budget = self.db.execute("SELECT amount,currency FROM budgets WHERE project_id=? AND stage=?", (project_id, action_stage)).fetchone()
                cap = dict(budget) if budget else self._plan(project).get("budget", {"amount": "0", "currency": "CNY"})
                if review_stage == "final" or (scope.get("stages") == [] and scope.get("allow_uploads") is False):
                    cap = {"amount": "0", "currency": cap["currency"]}
                payload.update({"approval_scope": scope, "budget": cap,
                                "binding_hash": _hash(binding), "expires_at": self.clock() + self.limits.approval_ttl})
            except WorkflowError as exc:
                payload["review_error"] = str(exc)
        db.execute("INSERT OR IGNORE INTO events VALUES(?,?,?,?,0,?)", (event_id, project_id, kind, _json(payload), self.clock()))

    def _op(self, operation_id):
        row = self.db.execute("SELECT * FROM operations WHERE id=?", (operation_id,)).fetchone()
        if row is None:
            raise WorkflowError("unknown operation")
        op = dict(row)
        op["operation_id"] = op["id"]
        op["payload"] = json.loads(op["payload"])
        op["result"] = json.loads(op["result"]) if op["result"] else {}
        op["quote"] = json.loads(op["quote"]) if op["quote"] else {}
        op["output_dir"] = str(self.artifact_dir / op["project_id"] / op["id"])
        project = self._project(op["project_id"])
        op["mode"] = project["mode"]
        op["plan"] = self._plan(project)
        op["shot"] = op["payload"].get("shot", {})
        op["input_assets"] = op["payload"].get("input_assets", [])
        op["reserved_amount"] = op["reserved"]
        if op["approval_id"]:
            approval = self.db.execute("SELECT * FROM approvals WHERE id=?", (op["approval_id"],)).fetchone()
            if approval:
                a = dict(approval)
                op["authorization"] = {"approval_id": a["id"], "actor": a["actor"], "expires_at": a["expires"],
                    **json.loads(a["binding"]), "scope": json.loads(a["scope"]), "budget": {"amount": a["amount"], "currency": a["currency"]}}
        for key in ("node_id", "update_id", "submit_id", "resource_id", "canvas_id", "provider_project_id", "version_id"):
            if key in op["payload"]:
                op[key] = op["payload"][key]
            elif key in op["result"]:
                op[key] = op["result"][key]
        return op

    def _new_operation(self, project, shot, stage):
        plan = self._plan(project)
        key, provider, identity = self._provider(plan, stage)
        if identity.get("live") and project["mode"] != "live":
            raise WorkflowError("dry-run refuses a live provider")
        design_mapping = None
        if identity["provider"] == "minimax-design":
            try:
                config = json.loads(_json(getattr(provider, "config", {})))
            except (TypeError, ValueError):
                raise WorkflowError("MiniMax stage configuration requires finite JSON values") from None
            if not isinstance(config, dict):
                raise WorkflowError("MiniMax stage configuration requires an object")
            if _hash(config) != identity["execution_config_hash"]:
                raise WorkflowError("MiniMax configuration changed while creating the operation; review again")
            from .providers import ProviderError, _minimax_stage_settings
            try:
                settings = _minimax_stage_settings(config, stage)
            except ProviderError as exc:
                raise WorkflowError(str(exc)) from None
            design_mapping = dict(settings)
            if config.get("project_id"):
                design_mapping["design_project_id"] = config["project_id"]
            _no_credentials(design_mapping)
            design_mapping["design_execution_config_hash"] = identity["execution_config_hash"]
        spec = json.loads(shot["spec"])
        assets = [{**a, **_file(a["path"])} for a in spec.get("reference_assets", [])]
        if stage == "video":
            assets.insert(0, {**json.loads(shot["image"]), "role": "start_frame"})
        with self._tx() as db:
            existing = db.execute("SELECT id FROM operations WHERE project_id=? AND revision=? AND stage=? AND shot_id=?",
                                  (project["id"], project["revision"], stage, shot["id"])).fetchone()
            if existing:
                return existing["id"]
            count = db.execute("SELECT COUNT(*) FROM operations WHERE project_id=?", (project["id"],)).fetchone()[0]
            attempt = db.execute("SELECT COUNT(*) FROM operations WHERE project_id=? AND shot_id=? AND stage=?",
                                 (project["id"], shot["id"], stage)).fetchone()[0] + 1
            if count >= self.limits.max_operations or attempt > self.limits.max_attempts:
                raise WorkflowError("hard operation/attempt limit reached")
            oid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"hc:{project['id']}:{project['revision']}:{stage}:{shot['id']}"))
            payload = {"shot": spec, "image_prompt": spec["image_prompt"], "video_prompt": spec["video_prompt"],
                       "duration_seconds": spec["duration_seconds"], "input_assets": assets,
                       "aspect_ratio": plan.get("aspect_ratio", "16:9"), "ratio": plan.get("aspect_ratio", "16:9"), "fps": plan.get("fps", 24)}
            if stage == "video":
                payload["duration"] = spec["duration_seconds"]
            if design_mapping is not None:
                payload.update(design_mapping)
            db.execute("INSERT INTO operations(id,project_id,revision,stage,shot_id,attempt,provider_key,provider,account,live,status,phase,payload,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,'planned','planned',?,?,?)",
                       (oid, project["id"], project["revision"], stage, shot["id"], attempt, key, identity["provider"], identity["account"], int(bool(identity.get("live"))), _json(payload), self.clock(), self.clock()))
            return oid

    def _authorized(self, op):
        project = self._project(op["project_id"])
        if project["revision"] != op["revision"]:
            raise WorkflowError("operation belongs to a superseded revision")
        stage = "plan" if op["stage"] == "image" else "storyboard"
        approval = self._approval(project, stage, op["shot_id"])
        if not approval:
            raise WorkflowError("current plan/assets need human approval")
        identity = self._identity(self.providers[op["provider_key"]])
        if identity["provider"] != op["provider"] or identity["account"] != op["account"]:
            raise WorkflowError("operation account/provider changed")
        if op["provider"] == "minimax-design" and op["payload"].get("design_execution_config_hash") != identity["execution_config_hash"]:
            raise WorkflowError("MiniMax execution configuration changed; replan before reusing this operation")
        if op["live"]:
            if project["mode"] != "live":
                raise WorkflowError("live mode was not authorized")
            self._check_scope(json.loads(approval["scope"]), json.loads(approval["binding"]), op["stage"], identity)
        return approval

    def _reserve(self, op, quote, approval):
        if not isinstance(quote, dict):
            raise WorkflowError("provider quote must be an object")
        currency = quote.get("currency", approval["currency"])
        if currency != approval["currency"]:
            raise WorkflowError("provider quote and approved budget currencies differ")
        amount = _money(quote["amount"]) if quote.get("amount") is not None else None
        with self._tx() as db:
            budget = db.execute("SELECT * FROM budgets WHERE project_id=? AND stage=?", (op["project_id"], op["stage"])).fetchone()
            if not budget or budget["currency"] != currency:
                raise WorkflowError("no matching stage budget")
            used, _ = self._reserved(op["project_id"], op["stage"], excluding=op["id"])
            cap = min(_money(budget["amount"]), _money(approval["amount"]))
            reserve = amount if amount is not None else cap - used
            if reserve < 0 or used + reserve > cap or (op["live"] and amount is None and reserve <= 0):
                raise WorkflowError("stage budget exhausted (including uncertain/spent reservations)")
            db.execute("UPDATE operations SET reserved=?,currency=?,quote=?,approval_id=?,updated=? WHERE id=?",
                       (str(reserve), currency, _json(quote), approval["id"], self.clock(), op["id"]))
        return amount

    def _record(self, oid, status, phase=None, result=None, error=None, expected_status=None):
        with self._tx() as db:
            if expected_status is not None:
                current = db.execute("SELECT status FROM operations WHERE id=?", (oid,)).fetchone()
                if not current or current["status"] != expected_status:
                    return False
            db.execute("UPDATE operations SET status=?,phase=COALESCE(?,phase),result=COALESCE(?,result),error=?,updated=? WHERE id=?",
                       (status, phase, _json(result) if result is not None else None, error, self.clock(), oid))
            if result and result.get("task_id"):
                db.execute("UPDATE operations SET task_id=? WHERE id=?", (str(result["task_id"]), oid))
            if result:
                op = self._op(oid)
                patch = result.get("payload", {})
                if not isinstance(patch, dict):
                    raise WorkflowError("provider payload patch must be an object")
                recovery_keys = {"node_id", "update_id", "submit_id", "task_id", "resource_id", "canvas_id", "provider_project_id",
                                 "project_id", "saved", "prepared", "capability_id", "design_project_id", "version_id", "simulated", "submit_attempted",
                                 "not_submitted", "awaiting_confirmation", "side_effects"}
                if set(patch) - recovery_keys:
                    raise WorkflowError("provider attempted to change an approved operation payload")
                if op["provider"] == "minimax-design" and any(
                        key in patch and patch[key] != op["payload"].get(key)
                        for key in ("capability_id", "design_project_id")):
                    raise WorkflowError("provider attempted to change a frozen MiniMax request")
                merged = {**op["payload"], **patch}
                for key in ("node_id", "update_id", "submit_id", "resource_id", "canvas_id", "provider_project_id", "version_id"):
                    if key in result:
                        merged[key] = result[key]
                db.execute("UPDATE operations SET payload=? WHERE id=?", (_json(merged), oid))
        return True

    def _snapshot_inputs(self, op):
        """Upload only immutable copies that still match the approved bytes."""
        assets = []
        directory = Path(op["output_dir"])
        _private_dir(directory)
        for index, asset in enumerate(op["input_assets"]):
            source = Path(asset["path"])
            target = directory / (f"input-{index:03}" + source.suffix.lower())
            if not target.exists():
                with source.open("rb") as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
            actual = _file(str(target))
            if actual["sha256"] != asset["sha256"]:
                raise WorkflowError("approved input changed before upload")
            assets.append({**asset, **actual, "source_path": asset.get("source_path", asset["path"])})
        with self._tx() as db:
            payload = {**op["payload"], "input_assets": assets}
            db.execute("UPDATE operations SET payload=? WHERE id=?", (_json(payload), op["id"]))

    def _audit_after_write(self, op):
        if not op["live"]:
            return
        try:
            current = self._identity(self.providers[op["provider_key"]])
            approved_identity = op.get("authorization", {}).get("providers", {}).get(op["stage"])
            same = current.get("verified") is True and current == approved_identity
        except Exception:
            same = False
        if not same:
            with self._tx() as db:
                db.execute("UPDATE approvals SET revoked=1 WHERE project_id=? AND revision=?", (op["project_id"], op["revision"]))
                db.execute("UPDATE operations SET error='account fingerprint changed after provider write',updated=? WHERE id=?", (self.clock(), op["id"]))
                self._event(db, op["project_id"], "account_changed", {"message": "Restore and locally reapprove the intended provider/account; existing operation IDs are retained."})

    def _advance(self, oid):
        op = self._op(oid)
        provider = self.providers[op["provider_key"]]
        if op["status"] in self.ACTIVE:
            # No prepare or submit here, even when a process died between the
            # persisted intent and the network write. Recovery is read-only.
            try:
                result = provider.poll(op)
            except Exception as exc:
                self._record(oid, "unknown", error=f"poll: {type(exc).__name__}; recover the same operation", expected_status=op["status"])
                return
            state = result.get("status", "unknown")
            if state in ("prepared", "ready") and op["phase"] == "prepare":
                self._record(oid, "prepared", "prepared", result, expected_status=op["status"])
            elif state in ("succeeded", "completed", "success"):
                self._record(oid, "generated", "download", result, expected_status=op["status"])
            elif state in ("failed", "cancelled", "needs_setup", "needs_approval"):
                self._record(oid, state, result=result, expected_status=op["status"])
            else:
                self._record(oid, state if state in self.ACTIVE else "unknown", result=result, expected_status=op["status"])
            return
        if op["status"] == "planned":
            approval = self._authorized(op)
            quote = provider.quote(op)  # may report amount=None until a draft exists
            if quote.get("status") in ("failed", "needs_setup", "unknown"):
                self._record(oid, quote["status"], "planned", quote)
                return
            self._reserve(op, quote, approval)
            with self._tx() as db:
                active = db.execute("SELECT COUNT(*) FROM operations WHERE status IN ('preparing','submitting','submitted','running','unknown')").fetchone()[0]
                if active >= self.limits.max_concurrent:
                    return
                # Compare-and-set means another process cannot claim this write.
                clean = dict(self._op(oid)["payload"])
                for evidence in ("not_submitted", "awaiting_confirmation", "side_effects"):
                    clean.pop(evidence, None)
                changed = db.execute("UPDATE operations SET status='preparing',phase='prepare',payload=?,result=NULL,error=NULL,updated=? WHERE id=? AND status='planned'", (_json(clean), self.clock(), oid)).rowcount
            if not changed:
                return
            try:
                op = self._op(oid)
                self._authorized(op)
                self._snapshot_inputs(op)
                op = self._op(oid)
                result = provider.prepare(op)
            except Exception as exc:
                self._record(oid, "unknown", error=f"prepare: {type(exc).__name__}; outcome unknown, poll only", expected_status="preparing")
                return
            state = result.get("status", "prepared")
            ready = state in ("prepared", "ready", "ok", "succeeded")
            self._record(oid, "prepared" if ready else state, "prepared" if ready else "prepare", result, expected_status="preparing")
            self._audit_after_write(self._op(oid))
            return
        if op["status"] == "prepared":
            approval = self._authorized(op)
            quote = provider.quote(op)
            amount = self._reserve(op, quote, approval)
            if amount is None:
                raise WorkflowError("provider has no usable quote; spending remains blocked")
            with self._tx() as db:
                active = db.execute("SELECT COUNT(*) FROM operations WHERE status IN ('preparing','submitting','submitted','running','unknown')").fetchone()[0]
                if active >= self.limits.max_concurrent:
                    return
                clean = dict(self._op(oid)["payload"])
                for evidence in ("not_submitted", "awaiting_confirmation", "side_effects"):
                    clean.pop(evidence, None)
                # Negative evidence belongs to one attempt only. Persistently
                # clear it before a fresh write so a lost reply cannot reuse an
                # older "not submitted" receipt to authorize another charge.
                changed = db.execute("UPDATE operations SET status='submitting',phase='submit',payload=?,result=NULL,error=NULL,updated=? WHERE id=? AND status='prepared'", (_json(clean), self.clock(), oid)).rowcount
            if not changed:
                return
            try:
                op = self._op(oid)
                self._authorized(op)
                result = provider.submit(op)
            except Exception as exc:
                self._record(oid, "unknown", error=f"submit: {type(exc).__name__}; outcome unknown, poll only", expected_status="submitting")
                return
            state = result.get("status", "unknown")
            if state in ("succeeded", "completed", "success"):
                state = "generated"
            self._record(oid, state, "download" if state == "generated" else "submit", result, expected_status="submitting")
            self._audit_after_write(self._op(oid))
            return
        if op["status"] == "generated":
            try:
                result = provider.download(op)
                if result.get("status") in ("unknown", "failed", "needs_setup"):
                    raise WorkflowError(result.get("message", "download unavailable"))
                path = result.get("path") or op["result"].get("path")
                asset = {**result, **_file(path), "operation_id": oid, "simulated": not bool(op["live"])}
            except Exception as exc:
                # Downloads may be retried, but never turn back into submissions.
                self._record(oid, "generated", "download", error=f"download: {type(exc).__name__}; no generation retried")
                return
            with self._tx() as db:
                project = self._project(op["project_id"])
                if project["revision"] == op["revision"]:
                    db.execute(f"UPDATE shots SET {op['stage']}=? WHERE project_id=? AND id=?", (_json(asset), op["project_id"], op["shot_id"]))
                db.execute("UPDATE operations SET status='done',phase='done',result=?,error=NULL,updated=? WHERE id=?", (_json(asset), self.clock(), oid))
                if project["revision"] == op["revision"] and op["stage"] == "image":
                    shots = self._shots(op["project_id"])
                    if all(s["image"] for s in shots):
                        for shot in shots:
                            self._event(db, op["project_id"], "storyboard_review", {"stage": "storyboard",
                                "shot_ids": [shot["id"]], "artifacts": [json.loads(shot["image"])["path"]],
                                "message": f"Review storyboard {shot['id']}; rejecting this review changes only this shot. Approve video spending separately."})
            return

    def tick(self, project_id):
        """Advance at most one provider action. Never spin or sleep internally."""
        project = self._project(project_id)
        try:
            # Recover old revisions too, without attaching their assets to a new plan.
            pending = self.db.execute("SELECT id FROM operations WHERE project_id=? AND status IN ('preparing','submitting','submitted','running','unknown','generated') ORDER BY created LIMIT 1", (project_id,)).fetchone()
            if pending:
                self._advance(pending["id"])
            else:
                shots = self._shots(project_id)
                if self._content_approval(project, "plan"):
                    missing = next((s for s in shots if not s["image"]), None)
                    if missing:
                        if self._generation_allowed(project, "plan", missing["id"]):
                            self._advance(self._new_operation(project, missing, "image"))
                    elif all(self._content_approval(project, "storyboard", s["id"]) for s in shots):
                        missing = next((s for s in shots if not s["video"]), None)
                        if missing:
                            if self._generation_allowed(project, "storyboard", missing["id"]):
                                self._advance(self._new_operation(project, missing, "video"))
                        elif not project["final_artifact"]:
                            if self._normalizes(project) and not self._composition_approval(project):
                                self._request_composition_review(project)
                            else:
                                self._compose(project)
        except WorkflowError as exc:
            self._deliver(project_id)
            result = self.status(project_id)
            result["blocked_reason"] = str(exc)
            return result
        self._deliver(project_id)
        return self.status(project_id)

    def _compose(self, project):
        inputs = []
        for shot in self._shots(project["id"]):
            asset = json.loads(shot["video"])
            actual = _file(asset["path"])
            if actual["sha256"] != asset["sha256"]:
                raise WorkflowError("video asset changed before composition")
            inputs.append({"shot_id": shot["id"], **actual, "duration_seconds": json.loads(shot["spec"])["duration_seconds"]})
        operation = {"operation_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"compose:{project['id']}:{project['revision']}")),
                     "project_id": project["id"], "revision": project["revision"], "mode": project["mode"],
                     "output_dir": str(self.artifact_dir / project["id"] / f"composition-r{project['revision']}"),
                     "inputs": inputs, "plan": self._plan(project)}
        normalization_binding_at_start = None
        if self._normalizes(project):
            normalization_binding_at_start = self._binding(project, "composition")
            if not self._composition_approval(project, normalization_binding_at_start):
                raise WorkflowError("a fresh exact local processing approval is required")
            from .normalizer import normalization_binding
            operation["normalization_authorized"] = normalization_binding(operation)
        compositor = self.compositor
        if compositor is None:
            try:
                from .compositor import get_compositor
                compositor = get_compositor(project["mode"])
            except ImportError:
                if project["mode"] == "live":
                    raise WorkflowError("no sequential compositor configured") from None
                def compositor(op):
                    directory = Path(op["output_dir"])
                    _private_dir(directory)
                    path = directory / "assembly-dry-run.json"
                    path.write_text(_json({"simulated": True, "editing": "sequential-only", "inputs": op["inputs"]}) + "\n", encoding="utf-8")
                    return {"status": "succeeded", "path": str(path), "simulated": True}
        callback = compositor.compose if hasattr(compositor, "compose") else compositor
        result = callback(operation)
        if not isinstance(result, dict) or result.get("status") not in ("succeeded", "completed", "success"):
            candidate = result.get("reason") if isinstance(result, dict) else None
            reason = (candidate if type(candidate) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", candidate)
                      and candidate in self.COMPOSITION_REASONS else "composition_failed")
            identity = {"project_id": project["id"], "revision": project["revision"],
                        "plan_hash": project["plan_hash"],
                        "videos": [{"shot_id": item["shot_id"], "sha256": item["sha256"]} for item in inputs],
                        "reason": reason}
            event_id = "event-composition-" + _hash(identity)
            with self._tx() as db:
                latest = self._project(project["id"])
                if latest["revision"] != project["revision"] or latest["plan_hash"] != project["plan_hash"]:
                    raise WorkflowError("plan changed while composing")
                self._event(db, project["id"], "composition_failed", {
                    "message": "本地成片合成需要处理，请回电脑检查素材规格并选择处理方式。", "reason": reason,
                }, event_id=event_id)
            raise WorkflowError(reason)
        asset = {**result, **_file(result["path"]), "operation_id": operation["operation_id"]}
        if project["mode"] != "live" and asset.get("simulated") is not True:
            raise WorkflowError("a mock/dry-run composition must identify itself as simulated")
        with self._tx() as db:
            latest = self._project(project["id"])
            if latest["revision"] != project["revision"] or latest["plan_hash"] != project["plan_hash"]:
                raise WorkflowError("plan changed while composing")
            if normalization_binding_at_start is not None:
                try:
                    current_binding = self._binding(latest, "composition")
                    valid = (current_binding == normalization_binding_at_start
                             and self._composition_approval(latest, current_binding))
                except WorkflowError:
                    valid = False
                if not valid:
                    raise WorkflowError("local processing approval or inputs changed while composing")
            db.execute("UPDATE projects SET final_artifact=?,updated=? WHERE id=?", (_json(asset), self.clock(), project["id"]))
            self._event(db, project["id"], "final_review", {"stage": "final", "artifacts": [asset["path"]],
                         "message": "Sequential composition awaits human final review; no creative edit was applied."})

    def _should_notify(self, event, project):
        kind = event.get("type", "")
        if kind.endswith("_review"):
            stage = event.get("stage")
            if event.get("revision") != project["revision"]:
                return False
            if event.get("approval_scope", {}).get("plan_hash", project["plan_hash"]) != project["plan_hash"]:
                return False
            if stage == "final" and project["final_accepted"]:
                return False
            if stage == "composition":
                try:
                    binding = self._binding(project, "composition")
                    if (event.get("expires_at", 0) <= self.clock()
                            or event.get("binding_hash") != _hash(binding) or self._composition_rejected(project, binding)):
                        return False
                except WorkflowError:
                    return False
            binding_hash = event.get("binding_hash")
            if binding_hash:
                requested = set(event.get("shot_ids") or [shot["id"] for shot in self._shots(project["id"])])
                accepted = set()
                for row in self.db.execute("SELECT shot_ids FROM approvals WHERE project_id=? AND stage=? AND revision=? AND binding_hash=? AND revoked=0 AND expires>?",
                                           (project["id"], stage, project["revision"], binding_hash, self.clock())):
                    accepted.update(json.loads(row["shot_ids"]))
                if requested and requested <= accepted:
                    return False
            return True
        # Keep every internal audit row without sending it to a human. Explicit
        # failures remain actionable even if a generation itself has stopped.
        return (kind == "account_changed" or kind.endswith(("_failed", "_error"))
                or kind in ("delivery_succeeded", "artifact_delivered"))

    def _deliver(self, project_id):
        if self.channel is None:
            return
        for row in self.db.execute("SELECT * FROM events WHERE project_id=? AND delivered=0 ORDER BY created", (project_id,)).fetchall():
            event = json.loads(row["payload"])
            if not self._should_notify(event, self._project(project_id)):
                with self._tx() as db:
                    db.execute("UPDATE events SET delivered=1 WHERE id=?", (row["id"],))
                continue
            try:
                result = self.channel.deliver(event)
            except Exception:
                # event_id permits deduplication by channels; never generate again.
                break
            if result.get("delivered"):
                with self._tx() as db:
                    db.execute("UPDATE events SET delivered=1 WHERE id=?", (row["id"],))
            else:
                break

    def status(self, project_id):
        project = self._project(project_id)
        shots = self._shots(project_id)
        # One account read per stage, not one network read per shot. Mutations
        # still call _authorized afresh immediately before each provider write.
        raw_bindings, bindings = {}, {}
        for name in ("plan", "storyboard", "composition", "final"):
            try:
                binding = self._binding(project, name)
                raw_bindings[name] = binding
                bindings[name] = {**binding, "binding_hash": _hash(binding)}
            except WorkflowError:
                pass
        approved_plan = "plan" in raw_bindings and self._content_approval(project, "plan", binding=raw_bindings["plan"])
        approved_shots = {s["id"]: bool("storyboard" in raw_bindings and self._content_approval(project, "storyboard", s["id"], binding=raw_bindings["storyboard"])) for s in shots}
        stage = "brief"
        if project["plan"]:
            stage = "plan_review"
            if approved_plan:
                stage = "generating_images" if any(not s["image"] for s in shots) else "storyboard_review"
                if stage == "generating_images" and not self._generation_allowed(project, "plan", binding=raw_bindings["plan"], approval=approved_plan):
                    stage = "image_generation_approval"
                if shots and all(s["image"] for s in shots) and all(approved_shots.values()):
                    stage = "generating_videos" if any(not s["video"] for s in shots) else "ready_to_compose"
                    if stage == "ready_to_compose" and self._normalizes(project) and not self._composition_approval(project, raw_bindings.get("composition")):
                        stage = ("composition_rejected" if raw_bindings.get("composition") and self._composition_rejected(project, raw_bindings["composition"])
                                 else "composition_review")
                    if stage == "generating_videos":
                        missing = next(s for s in shots if not s["video"])
                        if not self._generation_allowed(project, "storyboard", missing["id"], binding=raw_bindings["storyboard"]):
                            stage = "video_generation_approval"
        if project["final_artifact"]:
            stage = "completed" if project["final_accepted"] else "final_review"
        operations = [self._op(r["id"]) for r in self.db.execute("SELECT id FROM operations WHERE project_id=? ORDER BY created", (project_id,)).fetchall()]
        budgets = []
        for row in self.db.execute("SELECT * FROM budgets WHERE project_id=?", (project_id,)):
            used, _ = self._reserved(project_id, row["stage"])
            budgets.append({"stage": row["stage"], "amount": row["amount"], "currency": row["currency"], "reserved_or_spent": str(used)})
        return {"project_id": project_id, "mode": project["mode"], "revision": project["revision"], "status": stage,
                "brief": json.loads(project["brief"]), "plan": self._plan(project), "plan_hash": project["plan_hash"],
                "bindings": bindings, "shots": [{"id": s["id"], "spec": json.loads(s["spec"]),
                    "image": json.loads(s["image"]) if s["image"] else None,
                    "video": json.loads(s["video"]) if s["video"] else None,
                    "approved": approved_shots[s["id"]]} for s in shots],
                "operations": operations, "budgets": budgets,
                "final_artifact": json.loads(project["final_artifact"]) if project["final_artifact"] else None,
                "limits": dict(vars(self.limits))}

    def doctor(self):
        reports = {}
        for key, provider in self.providers.items():
            try:
                reports[key] = {"identity": provider.identity(), "probe": provider.probe()}
            except Exception as exc:
                reports[key] = {"status": "needs_setup", "message": str(exc)}
        return {"database": self.db_path, "providers": reports, "limits": dict(vars(self.limits)),
                "mode": "inspection-only", "sqlite_version": sqlite3.sqlite_version}
