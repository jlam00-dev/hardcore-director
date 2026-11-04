"""Original, conservative adapters for user-owned media production tools.

No credentials are read here.  The official CLI and desktop application retain
authentication.  Only normalized recovery facts leave this module; raw replies,
temporary URLs and credit confirmation tokens stay in process memory.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request
from urllib.parse import urlparse


class ProviderError(RuntimeError):
    def __init__(self, code: str, status: str = "failed", message: str = ""):
        super().__init__(message or code)
        self.code, self.status = code, status


def _result(status: str, **values: Any) -> dict:
    return {"status": status, **values}


def _failure(exc: Exception) -> dict:
    if isinstance(exc, ProviderError):
        return _result(exc.status, error_code=exc.code, message=str(exc))
    # Never echo arbitrary transport exceptions, stdout or request payloads.
    return _result("unknown", error_code="transport_error", message="Read the same operation again; do not resubmit.")


def _money(value: Any) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ProviderError("invalid_amount", "needs_approval", "A finite non-negative budget is required.") from None
    if not number.is_finite() or number < 0:
        raise ProviderError("invalid_amount", "needs_approval", "A finite non-negative budget is required.")
    return number


def _id(value: Any, name: str) -> str:
    text = str(value or "")
    if not text or len(text) > 512 or any(c.isspace() for c in text) or "/" in text or "\\" in text or "?" in text:
        raise ProviderError("invalid_" + name, "needs_setup", "A public recovery identity is required.")
    return text


def _stable(operation: dict, kind: str) -> str:
    identity = _id(operation.get("operation_id"), "operation_id")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "hardcore-director:3:" + identity + ":" + kind))


def _stable_node(operation: dict) -> str:
    # CLI 1.1.1 canonical Node IDs: ^node_[0-9a-hjkmnp-tv-z]{10}$.
    # Keep UUID identities for updates/submissions; encode 50 deterministic bits
    # in the Node ID's distinct Crockford Base32 namespace.
    alphabet = "0123456789abcdefghjkmnpqrstvwxyz"
    value = uuid.UUID(_stable(operation, "node")).int >> 78
    return "node_" + "".join(alphabet[(value >> shift) & 31] for shift in range(45, -1, -5))


def _payload(operation: dict) -> dict:
    value = operation.get("payload", {})
    if not isinstance(value, dict):
        raise ProviderError("invalid_payload", "failed", "Operation payload must be an object.")
    return value


def _minimax_stage_settings(config: dict, stage: Any) -> dict:
    """Reject unsupported local settings before they can be silently dropped."""
    stages = config.get("stages", {}) if isinstance(config, dict) else None
    if (not isinstance(stages, dict) or set(stages) - {"image", "video"}
            or any(not isinstance(settings, dict)
                   or set(settings) - {"capability_id", "params", "design_output"}
                   for settings in stages.values())):
        raise ProviderError("design_stage_configuration_review_required", "needs_setup",
                            "MiniMax stage settings support only capability_id, params and design_output; no local cost limit is enforced here.")
    return stages.get(stage, {}) if isinstance(stage, str) else {}


def _json_schema(value: Any, schema: dict, path: str = "params") -> None:
    """Validate the small JSON-Schema surface used by discovered tool contracts."""
    if not isinstance(schema, dict):
        raise ProviderError("contract_unavailable", "needs_setup")
    if "$ref" in schema:
        raise ProviderError("unresolved_contract_reference", "needs_setup")
    alternatives = schema.get("anyOf") or schema.get("oneOf")
    if alternatives:
        for child in alternatives:
            try:
                _json_schema(value, child, path)
                return
            except ProviderError:
                pass
        raise ProviderError("invalid_parameters", "failed", path + " does not match the live contract.")
    if "enum" in schema and value not in schema["enum"]:
        raise ProviderError("invalid_parameters", "failed", path + " is outside the live enum.")
    if "const" in schema and value != schema["const"]:
        raise ProviderError("invalid_parameters", "failed", path + " is outside the live contract.")
    kind = schema.get("type")
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "integer": isinstance(value, int) and not isinstance(value, bool),
             "number": isinstance(value, (int, float)) and not isinstance(value, bool),
             "boolean": isinstance(value, bool), "null": value is None}
    if kind and not valid.get(kind, False):
        raise ProviderError("invalid_parameters", "failed", path + " has the wrong type.")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", [])):
            raise ProviderError("missing_parameters", "failed", path + " is missing a live required field.")
        for key, item in value.items():
            if key in props:
                _json_schema(item, props[key], path + "." + key)
            elif schema.get("additionalProperties") is False:
                raise ProviderError("unknown_parameter", "failed", path + " contains an undeclared field.")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise ProviderError("invalid_parameters", "failed", path + " has the wrong number of entries.")
        for item in value:
            if "items" in schema:
                _json_schema(item, schema["items"], path + "[]")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")):
            raise ProviderError("invalid_parameters", "failed", path + " has invalid length.")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = _money(value)
        if number < _money(schema.get("minimum", 0)) or ("maximum" in schema and number > _money(schema["maximum"])):
            raise ProviderError("invalid_parameters", "failed", path + " is outside live bounds.")


class DreaminaCanvasProvider:
    name = "dreamina-canvas"
    currency = "DREAMINA_CREDITS"

    def __init__(self, config: dict | None = None, *, runner=None, transport=None):
        self.config = dict(config or {})
        self.runner = runner or subprocess.run
        self.executable = self.config.get("executable", "dreamina-canvas")
        self._schema: dict | None = None
        self._submit_attempted: set[str] = set()

    def _call(self, args: list[str]) -> dict:
        command = [self.executable, "--format", "json", "--non-interactive",
                   "--profile", self.config.get("profile", "default"), *args]
        try:
            reply = self.runner(command, capture_output=True, text=True, timeout=self.config.get("timeout", 30), check=False)
        except (subprocess.TimeoutExpired, TimeoutError):
            raise ProviderError("cli_timeout", "unknown", "The outcome is unknown; recover the same IDs without repeating writes.") from None
        except FileNotFoundError:
            raise ProviderError("cli_not_installed", "needs_setup", "Install or select the official CLI separately.") from None
        if isinstance(reply, dict):
            envelope = reply
        else:
            output = getattr(reply, "stdout", None)
            exit_code = getattr(reply, "returncode", None)
            # Local CLI validation errors are structured JSON on stderr with an
            # empty stdout. Never echo stderr or parse arbitrary diagnostic text.
            if not output or not output.strip():
                output = getattr(reply, "stderr", None) if exit_code not in (None, 0) else None
            try:
                envelope = json.loads(output)
            except (ValueError, TypeError, AttributeError):
                raise ProviderError("invalid_cli_json", "unknown", "The CLI response was not a valid JSON envelope.") from None
        if not isinstance(envelope, dict) or not isinstance(envelope.get("ok"), bool):
            raise ProviderError("invalid_cli_envelope", "unknown")
        if not envelope["ok"]:
            error = envelope.get("error", {})
            candidate = error.get("code")
            code = candidate if isinstance(candidate, str) and re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", candidate) else "cli_error"
            candidate = error.get("requiredAction")
            action = candidate if isinstance(candidate, str) and candidate in {"login", "upgrade", "authenticate", "confirm", "resume"} else None
            if action in {"login", "upgrade", "authenticate"} or error.get("reason") == "account_changed":
                status = "needs_setup"
            elif action == "confirm" or "confirmation_required" in code:
                status = "needs_approval"
            elif action == "resume" or error.get("class") == "operation_incomplete":
                status = "unknown"
            else:
                status = "failed"
            # Only the structured code crosses the boundary, never the raw message.
            raise ProviderError(code, status, "Official CLI action required: " + str(action or status))
        if not isinstance(reply, dict) and getattr(reply, "returncode", 0) != 0:
            raise ProviderError("cli_exit_status_mismatch", "unknown", "A nonzero CLI exit cannot be treated as success.")
        data = envelope.get("data")
        if not isinstance(data, dict):
            raise ProviderError("missing_cli_data", "unknown")
        return data

    def identity(self) -> dict:
        try:
            status = self._call(["auth", "status"])
            if status.get("loggedIn") is not True:
                raise ProviderError("login_required", "needs_setup")
            account = self._call(["auth", "account"])
            user = _id(account.get("userId"), "account")
            space = self._call(["space", "current"])
            if str(space.get("userId")) != user:
                raise ProviderError("account_changed", "needs_setup")
            kind = space.get("kind")
            if kind not in {"personal", "team"}:
                raise ProviderError("space_identity_unavailable", "needs_setup")
            team = _id(space.get("team", {}).get("teamId"), "team") if kind == "team" else "personal"
            context = [self.config.get("profile", "default"), status.get("region"), status.get("environment"), user, kind, team]
            fingerprint = hashlib.sha256(json.dumps(context, separators=(",", ":")).encode()).hexdigest()
            return {"provider": self.name, "account": fingerprint, "live": True, "verified": True,
                    "verification": "official_cli_account_and_space"}
        except Exception as exc:
            return {"provider": self.name, "account": None, "live": True, "verified": False, **_failure(exc)}

    def _guard(self, operation: dict, *, mutation: bool = False, uploads: bool = False) -> dict:
        identity = self.identity()
        if not identity.get("verified"):
            raise ProviderError(identity.get("error_code", "account_unverified"), "needs_setup")
        if operation.get("account") != identity["account"]:
            raise ProviderError("account_changed", "needs_setup", "Restore the originally approved account, space and profile.")
        if mutation:
            authorization = operation.get("authorization", {})
            scope = authorization.get("scope", {})
            if not authorization.get("approval_id") or scope.get("provider") != self.name or scope.get("account") != identity["account"]:
                raise ProviderError("live_authorization_required", "needs_approval")
            if operation.get("stage") not in scope.get("stages", []):
                raise ProviderError("stage_authorization_required", "needs_approval")
            if scope.get("allow_uploads") is not True:
                raise ProviderError("upload_authorization_required", "needs_approval")
        return identity

    def _commands(self) -> dict:
        if self._schema is None:
            self._schema = self._call(["schema"])
        found = {}
        def visit(node: dict, prefix: tuple = ()) -> None:
            for child in node.get("subcommands", []):
                path = prefix + (child["name"],)
                found[" ".join(path)] = child
                visit(child, path)
        visit(self._schema)
        return found

    def probe(self) -> dict:
        try:
            version = self._call(["version"])
            required = {"node create image", "node create video", "node quote", "node confirm", "node run", "node show", "operation status", "resource download", "resource upload", "model list"}
            if not required.issubset(self._commands()):
                raise ProviderError("cli_contract_incomplete", "needs_setup")
            identity = self.identity()
            return {**identity, "status": "ready" if identity.get("verified") else "needs_setup",
                    "version": version.get("version"), "stages": ["image", "video"],
                    "currency": self.currency, "credentials_managed_by": "official_cli"}
        except Exception as exc:
            return {"provider": self.name, "live": True, "verified": False, **_failure(exc)}

    def _facts(self, operation: dict) -> dict:
        payload = _payload(operation)
        project = payload.get("canvas_id") or payload.get("provider_project_id") or self.config.get("project_id")
        if not project:
            raise ProviderError("canvas_selection_required", "needs_setup", "Select an explicit Dreamina canvas; the current unrelated canvas is not adopted.")
        _id(project, "project_id")
        node = payload["node_id"] if "node_id" in payload else _stable_node(operation)
        if not isinstance(node, str) or re.fullmatch(r"node_[0-9a-hjkmnp-tv-z]{10}", node) is None:
            raise ProviderError("invalid_node_id", "needs_setup", "The saved Node ID is not canonical; inspect the original attempt before explicitly repairing its identity.")
        return {"project_id": str(project),
                "node_id": node,
                "update_id": payload.get("update_id") or _stable(operation, "save"),
                "submit_id": payload.get("submit_id") or _stable(operation, "run")}

    def _plan(self, operation: dict) -> dict:
        payload = _payload(operation)
        stage = operation.get("stage")
        if stage not in {"image", "video"}:
            raise ProviderError("unsupported_stage", "needs_setup")
        shot = payload.get("shot", operation.get("shot", {}))
        params = {**self.config.get(stage, {}), **payload.get("params", {})}
        for key in ("model", "mode", "ratio", "resolution", "duration", "count"):
            if key in payload:
                params[key] = payload[key]
        ratio = payload.get("aspect_ratio") or operation.get("plan", {}).get("aspect_ratio")
        if ratio is not None:
            params.setdefault("ratio", ratio)
        if stage == "video":
            duration = payload.get("duration_seconds", shot.get("duration_seconds"))
            if duration is not None:
                params.setdefault("duration", duration)
        prompt = payload.get(stage + "_prompt") or shot.get(stage + "_prompt") or payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ProviderError("prompt_required", "failed")
        model = params.get("model")
        mode = params.get("mode")
        if not model or not mode:
            raise ProviderError("model_selection_required", "needs_setup", "Choose a model and mode from the live catalog.")
        catalog = self._call(["model", "list", "--type", stage])
        matches = [row for row in catalog.get("items", []) if row.get("model") == model]
        if len(matches) != 1:
            raise ProviderError("canonical_model_required", "needs_setup", "Use one canonical model from the live catalog, not a guessed alias.")
        raw_refs = payload.get("references", [])
        assets = payload.get("input_assets", [])
        if not isinstance(assets, list) or not isinstance(raw_refs, list):
            raise ProviderError("invalid_references", "failed")
        refs = list(raw_refs)
        count = len(refs) + len(assets)
        if mode == "first_last_frame":
            self._frame_slots(payload, refs, assets)
        candidates = []
        for candidate in matches[0].get("modes", []):
            limits = candidate.get("references")
            if candidate.get("name") == mode and (limits is None or limits.get("min", 0) <= count <= limits.get("max", -1)):
                candidates.append(candidate)
        if len(candidates) != 1:
            raise ProviderError("mode_contract_ambiguous", "needs_setup", "The chosen mode and reference count do not identify one live contract.")
        spec = candidates[0]
        values = {**params, "prompt": prompt}
        flags = {field["flag"].removeprefix("--"): field for field in spec.get("flags", [])}
        allowed = {"model", "mode", "prompt", "ratio", "resolution", "duration", "count"}
        if set(values) - allowed:
            raise ProviderError("unknown_generation_parameter", "failed")
        for name, rule in flags.items():
            if rule.get("required") and name not in values:
                raise ProviderError("missing_model_parameter", "failed", "A required live model parameter is absent: " + name)
            if name not in values:
                continue
            value = values[name]
            if "values" in rule and str(value) not in rule["values"]:
                raise ProviderError("model_parameter_out_of_range", "failed", "A parameter is outside the live model enum: " + name)
            if "min" in rule or "max" in rule:
                number = _money(value)
                if number < Decimal(str(rule.get("min", 0))) or number > Decimal(str(rule.get("max", "Infinity"))):
                    raise ProviderError("model_parameter_out_of_range", "failed")
                if rule.get("step") and (number - Decimal(str(rule.get("min", 0)))) % Decimal(str(rule["step"])):
                    raise ProviderError("model_parameter_out_of_range", "failed")
            if isinstance(value, str) and not rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", float("inf")):
                raise ProviderError("model_parameter_out_of_range", "failed")
        for key in values:
            if key not in {"model", "mode"} and key not in flags:
                raise ProviderError("unsupported_model_parameter", "failed")
        return {"stage": stage, "values": values, "references": refs, "input_assets": assets,
                "title": str(payload.get("title") or shot.get("title") or operation.get("shot_id") or "影视素材")}

    @staticmethod
    def _frame_slots(payload: dict, refs: list, assets: list) -> None:
        """The engine's role-bearing assets must not silently become frame anchors.

        Explicit typed direct refs retain the official CLI's ordered frame contract:
        a sole ref is the first frame; two refs are first then last. Callers can
        additionally assert their roles with the aligned `reference_roles` array.
        Engine/snapshotted file inputs always need their actual `role` field.
        """
        expected = ["start_frame"] if len(refs) + len(assets) == 1 else ["start_frame", "end_frame"]
        if len(refs) + len(assets) not in {1, 2}:
            raise ProviderError("frame_slot_count_invalid", "needs_setup", "first_last_frame needs one start frame or an ordered start/end pair; use m2v for other references.")
        aliases = {"start_frame": "start_frame", "first_frame": "start_frame",
                   "end_frame": "end_frame", "last_frame": "end_frame"}
        def normalized(value):
            return aliases.get(value) if isinstance(value, str) else None
        declared = payload.get("reference_roles")
        if declared is not None and (not isinstance(declared, list) or len(declared) != len(refs)):
            raise ProviderError("frame_slot_roles_invalid", "needs_setup", "reference_roles must match the explicit direct reference list.")
        roles = []
        for index, ref in enumerate(refs):
            if not isinstance(ref, str) or not ref.startswith(("node:", "res:")) or not ref.split(":", 1)[1]:
                raise ProviderError("frame_direct_reference_invalid", "needs_setup", "Use explicit typed node/res frame references.")
            roles.append(normalized(declared[index]) if declared is not None else expected[index])
        roles.extend(normalized(asset.get("role")) if isinstance(asset, dict) else None for asset in assets)
        if roles != expected:
            raise ProviderError("frame_slot_roles_invalid", "needs_setup", "Declare start_frame alone or start_frame then end_frame. Character/style references require m2v and a newly reviewed plan.")

    def prepare(self, operation: dict) -> dict:
        try:
            payload = _payload(operation)
            if operation.get("task_id") or payload.get("submit_attempted") or operation.get("operation_id") in self._submit_attempted:
                return self.poll(operation)
            self._guard(operation, mutation=True, uploads=bool(payload.get("input_assets")))
            facts = self._facts(operation)
            if payload.get("saved"):
                return _result("prepared", payload={**facts, "canvas_id": facts["project_id"], "saved": True}, **facts)
            plan = self._plan(operation)
            references = list(plan["references"])
            for index, asset in enumerate(plan["input_assets"]):
                path = Path(asset["path"] if isinstance(asset, dict) else asset).expanduser()
                if not path.is_file() or path.is_symlink():
                    raise ProviderError("input_asset_unavailable", "failed")
                resource_id = _stable(operation, "upload:" + str(index))
                uploaded = self._call(["resource", "upload", "--file", str(path.resolve()), "--project-id", facts["project_id"], "--resource-id", resource_id])
                if uploaded.get("resourceId") != resource_id:
                    raise ProviderError("upload_identity_mismatch", "unknown")
                references.append("res:" + resource_id)
            for ref in references:
                if not isinstance(ref, str) or not ref.startswith(("node:", "res:")):
                    raise ProviderError("unregistered_reference", "failed", "Import local media explicitly; temporary URLs are not recovery references.")
            args = ["node", "create", plan["stage"], "--project-id", facts["project_id"], "--node-id", facts["node_id"], "--update-id", facts["update_id"], "--title", plan["title"]]
            for name, value in plan["values"].items():
                args += ["--" + name, str(value)]
            for ref in references:
                args += ["--ref", ref]
            saved = self._call(args)
            if saved.get("node", {}).get("nodeId") != facts["node_id"]:
                raise ProviderError("save_identity_unknown", "unknown")
            return _result("prepared", payload={**facts, "canvas_id": facts["project_id"], "saved": True}, **facts)
        except Exception as exc:
            return _failure(exc)

    def quote(self, operation: dict) -> dict:
        try:
            self._guard(operation)
            if not _payload(operation).get("saved"):
                return _result("needs_approval", amount=None, currency=self.currency, error_code="saved_node_required")
            facts = self._facts(operation)
            quoted = self._call(["node", "quote", "--project-id", facts["project_id"], "--node-id", facts["node_id"]])
            rows = quoted.get("items", [])
            if len(rows) != 1 or rows[0].get("nodeId") != facts["node_id"] or rows[0].get("error") or quoted.get("confirmable") is not True:
                raise ProviderError("quote_incomplete", "needs_approval")
            amount = _money(quoted.get("totalMaxCredits"))
            if amount != amount.to_integral_value():
                raise ProviderError("invalid_credit_quote", "needs_approval")
            return _result("quoted", amount=str(amount), currency=self.currency,
                           draft_version=quoted.get("draftVersion"), confirmation_required=quoted.get("confirmationRequired"), **facts)
        except Exception as exc:
            return {**_failure(exc), "amount": None, "currency": self.currency}

    def submit(self, operation: dict) -> dict:
        run_attempted = False
        try:
            payload = _payload(operation)
            if operation.get("task_id") or payload.get("submit_attempted") or operation.get("operation_id") in self._submit_attempted:
                return self.poll(operation)
            self._guard(operation, mutation=True)
            if not payload.get("saved"):
                raise ProviderError("saved_node_required", "needs_setup")
            facts = self._facts(operation)
            quoted = self.quote(operation)
            if quoted.get("status") != "quoted":
                return {**quoted, "not_submitted": True, "awaiting_confirmation": True,
                        "payload": {"saved": True, "not_submitted": True, "awaiting_confirmation": True}}
            budget = operation.get("authorization", {}).get("budget", {})
            if budget.get("currency") != self.currency:
                raise ProviderError("budget_currency_mismatch", "needs_approval")
            ceiling = _money(operation.get("reserved_amount", operation.get("reserved", budget.get("amount"))))
            if ceiling != ceiling.to_integral_value() or _money(quoted["amount"]) > ceiling:
                raise ProviderError("credit_ceiling_exceeded", "needs_approval")
            approval = self._call(["node", "confirm", "--project-id", facts["project_id"], "--node-id", facts["node_id"], "--credit-ceiling", str(int(ceiling))])
            token = approval.get("creditConfirmationToken")
            if not isinstance(token, str) or not token:
                raise ProviderError("credit_approval_missing", "needs_approval")
            # Revalidate account after confirmation and before the paid operation.
            self._guard(operation, mutation=True)
            run_attempted = True
            self._submit_attempted.add(operation["operation_id"])
            reply = self._call(["node", "run", "--project-id", facts["project_id"], "--node-id", facts["node_id"], "--submit-id", facts["submit_id"], "--credit-token", token])
            rows = reply.get("items", [])
            if len(rows) != 1 or rows[0].get("submitId") != facts["submit_id"] or rows[0].get("nodeId") != facts["node_id"]:
                raise ProviderError("submission_identity_unknown", "unknown")
            state = str(rows[0].get("state", "")).lower()
            status = "submitted" if state == "accepted" else "failed" if state == "rejected" else "unknown"
            return _result(status, task_id=facts["submit_id"], payload={"submit_attempted": True}, **facts)
        except Exception as exc:
            result = _failure(exc)
            if not run_attempted and _payload(operation).get("saved"):
                result.update(not_submitted=True, awaiting_confirmation=True,
                              payload={"saved": True, "not_submitted": True, "awaiting_confirmation": True})
            elif result["status"] == "unknown":
                result.update(task_id=self._facts(operation)["submit_id"], payload={"submit_attempted": True})
            return result

    def poll(self, operation: dict) -> dict:
        try:
            self._guard(operation)
            facts = self._facts(operation)
            task_id = operation.get("task_id") or facts["submit_id"]
            observed = self._call(["operation", "status", task_id, "--project-id", facts["project_id"]])
            state = str(observed.get("state", "")).lower()
            resources = observed.get("resources", [])
            if state in {"succeeded", "completed"}:
                ready = [r for r in resources if str(r.get("state", "")).lower() in {"succeeded", "success", "ready"} and r.get("resourceId")]
                if not ready or len(ready) != len(resources):
                    return _result("unknown", task_id=task_id, error_code="terminal_resources_unverified", **facts)
                return _result("succeeded", task_id=task_id, resource_id=_id(ready[0]["resourceId"], "resource_id"), **facts)
            if state in {"failed", "rejected", "cancelled"}:
                return _result("failed", task_id=task_id, error_code="generation_" + state, **facts)
            if state in {"running", "pending", "in_progress", "accepted"}:
                return _result("running", task_id=task_id, **facts)
            # A lost save response can be recovered by its predetermined node ID.
            if not _payload(operation).get("submit_attempted") and not operation.get("task_id") and operation.get("operation_id") not in self._submit_attempted:
                nodes = self._call(["node", "show", "--project-id", facts["project_id"], "--node-id", facts["node_id"]]).get("nodes", [])
                if any(row.get("result") == "FOUND" and row.get("node", {}).get("nodeId") == facts["node_id"] for row in nodes):
                    return _result("prepared", payload={**facts, "canvas_id": facts["project_id"], "saved": True}, **facts)
            return _result("unknown", task_id=task_id, error_code="submission_unresolved", **facts)
        except Exception as exc:
            return _failure(exc)

    def download(self, operation: dict) -> dict:
        try:
            self._guard(operation)
            payload = _payload(operation)
            resource_id = operation.get("resource_id") or payload.get("resource_id")
            if not resource_id:
                raise ProviderError("resource_selection_required", "needs_setup")
            folder = Path(operation.get("output_dir") or payload.get("output_dir") or ".").resolve()
            folder.mkdir(parents=True, exist_ok=True)
            suffix = ".png" if operation.get("stage") == "image" else ".mp4"
            path = folder / (_id(operation.get("operation_id"), "operation_id") + suffix)
            if path.exists():
                raise ProviderError("output_already_exists", "failed", "Choose a new output path; existing files are preserved.")
            facts = self._facts(operation)
            result = self._call(["resource", "download", _id(resource_id, "resource_id"), "--project-id", facts["project_id"], "--output", str(path)])
            returned = Path(result.get("path", "")).resolve()
            if returned != path or not path.is_file() or path.stat().st_size <= 0:
                raise ProviderError("download_unverified", "unknown")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if result.get("size") != path.stat().st_size or result.get("sha256") != digest:
                raise ProviderError("download_checksum_mismatch", "failed")
            return _result("downloaded", path=str(path), size=path.stat().st_size, sha256=digest, resource_id=resource_id)
        except Exception as exc:
            return _failure(exc)


class LocalMCPTransport:
    """Streamable HTTP MCP over loopback only; session headers never leave memory."""
    def __init__(self, endpoint: str = "http://127.0.0.1:18810/mcp", timeout: int = 35):
        parsed = urlparse(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
            raise ProviderError("non_loopback_mcp_refused", "needs_setup")
        self.endpoint, self.timeout = endpoint, timeout
        self.session = None
        self.sequence = 0

    def request(self, method: str, params: dict | None = None) -> dict:
        self.sequence += 1
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        payload = {"jsonrpc": "2.0", "id": self.sequence, "method": method, "params": params or {}}
        req = request.Request(self.endpoint, json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout) as reply:
                self.session = reply.headers.get("mcp-session-id") or self.session
                raw = reply.read().decode("utf-8")
        except (urlerror.URLError, OSError):
            raise ProviderError("design_mcp_unreachable", "needs_setup", "Open MiniMax Design and enable its local MCP; no application was started automatically.") from None
        try:
            values = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
            envelope = next((v for v in reversed(values) if v.get("id") == self.sequence), None) if values else json.loads(raw)
        except (ValueError, TypeError):
            raise ProviderError("invalid_mcp_json", "unknown") from None
        if not isinstance(envelope, dict) or "error" in envelope or "result" not in envelope:
            raise ProviderError("mcp_protocol_error", "unknown")
        return envelope["result"]


class MiniMaxDesignProvider:
    name = "minimax-design"
    currency = "MINIMAX_DESIGN_CREDITS"

    def __init__(self, config: dict | None = None, *, runner=None, transport=None):
        self.config = dict(config or {})
        self.transport = transport or LocalMCPTransport(self.config.get("endpoint", "http://127.0.0.1:18810/mcp"))
        self.tools: dict = {}
        self.connected = False
        self.session_nonce = str(uuid.uuid4())
        self._project = None
        self._execute_attempts: set[str] = set()

    def _request(self, method: str, params: dict) -> dict:
        try:
            if callable(self.transport):
                return self.transport(method, params)
            return self.transport.request(method, params)
        except (TimeoutError, subprocess.TimeoutExpired):
            raise ProviderError("design_timeout", "unknown", "The outcome is unknown; never repeat execute without its task ID.") from None

    def _connect(self) -> None:
        if self.connected:
            return
        result = self._request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "hardcore-director", "version": "3.0"}})
        if result.get("serverInfo", {}).get("name") != "minimax-design":
            raise ProviderError("unexpected_mcp_server", "needs_setup")
        listing = self._request("tools/list", {})
        self.tools = {tool["name"]: tool for tool in listing.get("tools", []) if isinstance(tool, dict) and tool.get("name")}
        if "list_projects" not in self.tools:
            raise ProviderError("design_contract_incomplete", "needs_setup")
        self.connected = True

    def _call(self, name: str, arguments: dict) -> dict:
        self._connect()
        if name not in self.tools:
            raise ProviderError("design_tool_unavailable", "needs_setup")
        _json_schema(arguments, self.tools[name].get("inputSchema", {}), "tool")
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise ProviderError("design_tool_error", "needs_setup", "The selected project or capability is not available in this session.")
        data = result.get("structuredContent")
        if data is None:
            texts = [item.get("text") for item in result.get("content", []) if item.get("type") == "text"]
            try:
                data = json.loads(texts[0]) if len(texts) == 1 else None
            except (ValueError, TypeError):
                pass
        if not isinstance(data, dict):
            raise ProviderError("design_result_unstructured", "unknown")
        return data

    def identity(self) -> dict:
        try:
            self._connect()
            # No account-identity tool is exposed by the observed desktop contract.
            return {"provider": self.name, "account": "manual-session:" + self.session_nonce,
                    "live": True, "verified": False, "account_verified": False,
                    "verification": "manual_session_required", "status": "needs_setup"}
        except Exception as exc:
            return {"provider": self.name, "account": None, "live": True, "verified": False, **_failure(exc)}

    def probe(self) -> dict:
        try:
            self._connect()
            projects = self._call("list_projects", {}).get("projects", [])
            if not isinstance(projects, list) or any(not isinstance(project, dict) for project in projects):
                raise ProviderError("design_project_contract_unavailable", "needs_setup")
            required = {"open_project", "capability_list", "capability_get", "execute", "task_query", "task_wait", "confirm_cost", "get_output"}
            selected = self.config.get("project_id")
            matches = [project for project in projects if project.get("projectId") == selected] if isinstance(selected, str) and selected else []
            visible = len(matches) == 1
            opened = visible and matches[0].get("open") is True
            blockers = ["account_identity_unavailable", "no_pre_execute_quote", "no_caller_submit_id"]
            if not selected:
                blockers.insert(0, "explicit_project_selection")
            elif len(matches) > 1:
                blockers.insert(0, "selected_project_ambiguous")
            elif not visible:
                blockers.insert(0, "selected_project_unavailable")
            elif not opened:
                blockers.insert(0, "selected_project_not_open")
            return {**self.identity(), "status": "needs_project_selection" if not selected else "needs_setup",
                    "tools_available": sorted(required.intersection(self.tools)),
                    "project_count": len(projects), "open_project_count": sum(p.get("open") is True for p in projects),
                    "selected_project_visible": visible, "selected_project_open": opened,
                    "currency": self.currency, "generation_contract_verified": False,
                    "blockers": blockers}
        except Exception as exc:
            return {"provider": self.name, "live": True, "verified": False, **_failure(exc)}

    def _guard(self, operation: dict) -> None:
        _minimax_stage_settings(self.config, operation.get("stage"))
        self._connect()
        identity = self.identity()
        authorization = operation.get("authorization", {})
        scope = authorization.get("scope", {})
        # This experimental route is deliberately distinct from automatic identity verification.
        if not self.config.get("manual_session") or scope.get("identity_mode") != "manual_session" or scope.get("account") != identity["account"] or operation.get("account") != identity["account"] or scope.get("provider") != self.name or not authorization.get("approval_id"):
            raise ProviderError("manual_session_authorization_required", "needs_approval", "MiniMax account identity cannot be verified through the exposed MCP.")
        payload_project = _payload(operation).get("design_project_id")
        configured_project = self.config.get("project_id")
        if payload_project and configured_project and payload_project != configured_project:
            raise ProviderError("design_project_configuration_changed", "needs_setup")
        project_id = payload_project or configured_project
        if not project_id:
            raise ProviderError("project_selection_required", "needs_project_selection")
        if not isinstance(project_id, str):
            raise ProviderError("invalid_design_project_id", "needs_setup")
        project_id = _id(project_id, "design_project_id")
        if self._project != project_id:
            projects = self._call("list_projects", {}).get("projects", [])
            if not any(p.get("projectId") == project_id and p.get("open") is True for p in projects):
                raise ProviderError("selected_project_not_open", "needs_setup")
            self._call("open_project", {"projectId": project_id})
            self._project = project_id

    def _request_fields(self, operation: dict) -> tuple[str, dict, dict]:
        payload = _payload(operation)
        capability_id = payload.get("capability_id")
        if not capability_id:
            raise ProviderError("capability_selection_required", "needs_setup", "Choose a capability from this project's live catalog.")
        capability_id = _id(capability_id, "capability_id")
        stage = operation.get("stage")
        if not isinstance(stage, str) or stage not in {"image", "video"} or not capability_id.startswith("generate_" + stage + ":"):
            raise ProviderError("stage_capability_mismatch", "needs_setup")
        params = payload.get("params")
        if not isinstance(params, dict):
            raise ProviderError("explicit_design_params_required", "needs_setup")
        output = payload.get("design_output")
        if not isinstance(output, dict):
            raise ProviderError("explicit_output_required", "needs_setup")
        return capability_id, params, output

    @staticmethod
    def _parameter_rules(params: dict, schema: dict, rules: Any) -> None:
        """Only the observed flat when/disable contract is supported here."""
        def review():
            raise ProviderError("model_parameter_rules_review_required", "needs_setup")

        props = schema.get("properties")
        if not isinstance(rules, list) or not isinstance(props, dict):
            review()
        checked = []
        for rule in rules:
            if not isinstance(rule, dict) or set(rule) != {"when", "disable"}:
                review()
            when, disable = rule["when"], rule["disable"]
            if (not isinstance(when, dict) or set(when) != {"param", "values"}
                    or not isinstance(disable, dict) or set(disable) not in ({"param"}, {"param", "values"})):
                review()
            if (not isinstance(when["param"], str) or when["param"] not in props
                    or not isinstance(disable["param"], str) or disable["param"] not in props
                    or not isinstance(props[when["param"]], dict) or not isinstance(props[disable["param"]], dict)):
                review()
            for name, item in ((when["param"], when), (disable["param"], disable)):
                if "values" not in item:
                    continue
                values = item["values"]
                if not isinstance(values, list) or not values:
                    review()
                for value in values:
                    if isinstance(value, (dict, list)):
                        review()
                    try:
                        _json_schema(value, props[name])
                        json.dumps(value, allow_nan=False)
                    except (ProviderError, ValueError, TypeError):
                        review()
            checked.append((when, disable))
        missing = object()
        for when, disable in checked:
            actual = params.get(when["param"], props[when["param"]].get("default", missing))
            if actual is missing:
                continue
            try:
                _json_schema(actual, props[when["param"]])
            except ProviderError:
                review()
            if not any(type(actual) is type(value) and actual == value for value in when["values"]):
                continue
            target = disable["param"]
            if target in params and ("values" not in disable or any(type(params[target]) is type(value) and params[target] == value for value in disable["values"])):
                raise ProviderError("conditional_parameter_forbidden", "failed", "A supplied parameter is disabled by the selected model mode.")

    @staticmethod
    def _zero_reference_contract(contract: dict, mode: Any, params: dict) -> None:
        """Prove the supported text-only path does not require source media.

        Current-mode reference overrides stay unimplemented rather than being
        ignored. Supporting parameter rules does not imply reference support.
        """
        def review():
            raise ProviderError("model_reference_contract_review_required", "needs_setup")

        def numeric_bounds(value, keys):
            if not isinstance(value, dict) or set(value) - keys:
                review()
            for number in value.values():
                if type(number) not in {int, float}:
                    review()
                try:
                    _money(number)
                except ProviderError:
                    review()

        refs = contract.get("references")
        allowed = {"totalCount", "byKind", "modeOverrides", "description", "combinedCountLimits",
                   "imagesWithVideoMax", "exclusiveKinds", "audioRequiresImageOrVideo", "lastFrameOnly"}
        if not isinstance(refs, dict) or set(refs) - allowed:
            review()
        overrides = refs.get("modeOverrides", {})
        if (not isinstance(overrides, dict) or any(not isinstance(key, str) for key in overrides)
                or (mode is not None and not isinstance(mode, str))
                or (overrides and not isinstance(mode, str))):
            review()
        if mode is not None and mode in overrides:
            review()
        total = refs.get("totalCount")
        if (not isinstance(total, dict) or set(total) - {"min", "max"}
                or type(total.get("min")) is not int or total["min"] != 0
                or ("max" in total and (type(total["max"]) is not int or total["max"] < 0))):
            review()
        kinds = {"image", "video", "audio"}
        by_kind = refs.get("byKind", {})
        if not isinstance(by_kind, dict) or set(by_kind) - kinds:
            review()
        for limits in by_kind.values():
            if (not isinstance(limits, dict) or set(limits) - {"minCount", "maxCount", "durationSeconds", "size", "fps"}
                    or type(limits.get("minCount", 0)) is not int or limits.get("minCount", 0) != 0
                    or ("maxCount" in limits and (type(limits["maxCount"]) is not int or limits["maxCount"] < 0))):
                review()
            for field, keys in (("size", {"minWidth", "maxWidth", "minHeight", "maxHeight", "minPixels", "maxPixels", "minRatio", "maxRatio"}),
                                ("fps", {"min", "max"})):
                if field in limits:
                    numeric_bounds(limits[field], keys)
            if "durationSeconds" in limits:
                durations = limits["durationSeconds"]
                if not isinstance(durations, dict) or set(durations) - {"perItem", "totalMax", "totalWithOutputMax"}:
                    review()
                if "perItem" in durations:
                    numeric_bounds(durations["perItem"], {"min", "max"})
                numeric_bounds({key: value for key, value in durations.items() if key != "perItem"}, {"totalMax", "totalWithOutputMax"})
                if "totalWithOutputMax" in durations:
                    duration_schema = contract.get("paramSchema", {}).get("properties", {}).get("duration", {})
                    duration = params.get("duration", duration_schema.get("default") if isinstance(duration_schema, dict) else None)
                    if type(duration) not in {int, float}:
                        review()
                    try:
                        _json_schema(duration, duration_schema)
                        value = _money(duration)
                    except ProviderError:
                        review()
                    if value > _money(durations["totalWithOutputMax"]):
                        raise ProviderError("reference_output_duration_limit", "failed", "The requested output exceeds the live input/output duration limit.")
        for field in ("audioRequiresImageOrVideo", "lastFrameOnly"):
            if field in refs and type(refs[field]) is not bool:
                review()
        if "imagesWithVideoMax" in refs and (type(refs["imagesWithVideoMax"]) is not int or refs["imagesWithVideoMax"] < 0):
            review()
        if "exclusiveKinds" in refs:
            exclusive = refs["exclusiveKinds"]
            if not isinstance(exclusive, list):
                review()
            for group in exclusive:
                values = [group] if isinstance(group, str) else group
                if not isinstance(values, list) or any(not isinstance(kind, str) or kind not in kinds for kind in values):
                    review()
        combined = refs.get("combinedCountLimits", [])
        if not isinstance(combined, list):
            review()
        for limit in combined:
            if (not isinstance(limit, dict) or set(limit) != {"kinds", "maxCount"}
                    or not isinstance(limit["kinds"], list) or not limit["kinds"]
                    or any(not isinstance(kind, str) or kind not in kinds for kind in limit["kinds"])
                    or type(limit["maxCount"]) is not int or limit["maxCount"] < 0):
                review()

    def _contract(self, operation: dict) -> tuple[dict, dict]:
        payload = _payload(operation)
        capability_id, params, _ = self._request_fields(operation)
        reply = self._call("capability_get", {"ids": [capability_id]})
        rows = reply.get("capabilities", [])
        if isinstance(rows, dict):
            rows = list(rows.values())
        matches = [row for row in rows if row.get("id", row.get("capabilityId")) == capability_id]
        if len(matches) != 1 or not isinstance(matches[0].get("paramSchema"), dict):
            raise ProviderError("capability_contract_unavailable", "needs_setup")
        contract = matches[0]
        if contract.get("operation") != "generate_" + operation["stage"]:
            raise ProviderError("capability_operation_contract_review_required", "needs_setup")
        # Media contracts declare their flat parameter keys; an omitted JSON-
        # Schema additionalProperties flag is not permission to invent a key.
        schema = {**contract["paramSchema"], "additionalProperties": False}
        _json_schema(params, schema)
        if "paramRules" in contract:
            self._parameter_rules(params, schema, contract["paramRules"])
        mode_schema = schema.get("properties", {}).get("mode", {})
        effective_mode = params.get("mode", mode_schema.get("default") if isinstance(mode_schema, dict) else None)
        # Assets need an independently reviewed Design import/version mapping.
        # Merely preparing a request never uploads them or treats paths as refs.
        if (payload.get("input_assets") or payload.get("references") or "file_url" in params
                or (isinstance(effective_mode, str) and effective_mode in {"first-last-frame", "video-edit", "video-extend"})
                or ("input_assets" in payload and not isinstance(payload["input_assets"], list))
                or ("references" in payload and not isinstance(payload["references"], list))):
            raise ProviderError("model_reference_contract_review_required", "needs_setup")
        self._zero_reference_contract(contract, effective_mode, params)
        return contract, params

    def prepare(self, operation: dict) -> dict:
        try:
            self._guard(operation)
            contract, params = self._contract(operation)
            payload = _payload(operation)
            stage = operation.get("stage")
            shot = payload.get("shot", operation.get("shot", {}))
            prompt = payload.get(stage + "_prompt") or (shot.get(stage + "_prompt") if isinstance(shot, dict) else None) or payload.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ProviderError("explicit_design_prompt_required", "needs_setup")
            _json_schema(prompt, {"type": "string", **contract.get("prompt", {})})
            tool_schema = self.tools.get("execute", {}).get("inputSchema", {})
            if not isinstance(tool_schema.get("properties", {}).get("output"), dict):
                raise ProviderError("design_output_contract_unavailable", "needs_setup")
            preview = {"capabilityId": contract.get("id", contract.get("capabilityId")), "prompt": prompt,
                       "params": params, "output": payload["design_output"]}
            _json_schema(preview, tool_schema, "tool")
            # Return a JSON snapshot for review, not a saved Design document or
            # authority to execute. Public submit remains unconditionally gated.
            preview = json.loads(json.dumps(preview, ensure_ascii=False, allow_nan=False))
            return _result("prepared", payload={"capability_id": preview["capabilityId"],
                                                "design_project_id": self._project, "prepared": True},
                           request_preview=preview, design_draft_saved=False, generation_submitted=False,
                           model_prompt_review_required=bool(contract.get("knowledgeCard")))
        except Exception as exc:
            return _failure(exc)

    def quote(self, operation: dict) -> dict:
        try:
            self._guard(operation)
            if not operation.get("task_id"):
                self._request_fields(operation)
                return _result("needs_approval", amount=None, currency=self.currency, error_code="no_pre_execute_quote", message="This MCP exposes cost only on an already staged task; an automatic bounded first submission is unavailable.")
            task = self._call("task_query", {"mode": "get", "taskId": operation["task_id"]}).get("task", {})
            confirmation = task.get("billing", {}).get("confirmation", {})
            if not isinstance(confirmation, dict) or "amount" not in confirmation:
                raise ProviderError("billing_contract_unverified", "needs_approval")
            return _result("quoted", amount=str(_money(confirmation["amount"])), currency=confirmation.get("currency", self.currency), task_id=operation["task_id"])
        except Exception as exc:
            return {**_failure(exc), "amount": None, "currency": self.currency}

    def submit(self, operation: dict) -> dict:
        try:
            self._guard(operation)
            if operation.get("task_id"):
                # A known task is observed, not automatically retried or confirmed.
                return self.poll(operation)
            self._contract(operation)
            # No public preflight cost API or caller-supplied execute identity was found.
            # Keep the execution implementation explicitly unreachable until a verified
            # bounded-submit contract becomes available; no fake quote or model is used.
            return _result("needs_approval", error_code="bounded_execute_unavailable", message="Stage this operation explicitly in MiniMax Design and provide its task ID for read-only recovery.")
        except Exception as exc:
            return _failure(exc)

    def _execute_once(self, operation: dict) -> dict:
        """Verified wire shape, reserved for a future bounded-submit/identity gate.

        Public submit intentionally does not enter this path while the installed
        server lacks an independently enforceable quote and account contract.
        The host generates task IDs: a lost reply without one is unrecoverable
        automatically, even though our local operation ID is stable.
        """
        identity = _id(operation.get("operation_id"), "operation_id")
        if identity in self._execute_attempts:
            return _result("unknown", error_code="execute_already_attempted", message="Recover the original host task; execute is never replayed.")
        self._guard(operation)
        contract, params = self._contract(operation)
        payload = _payload(operation)
        output = payload.get("design_output")
        if not isinstance(output, dict):
            return _result("needs_setup", error_code="explicit_output_required")
        shot = payload.get("shot", operation.get("shot", {}))
        prompt = payload.get(operation.get("stage", "") + "_prompt") or shot.get(operation.get("stage", "") + "_prompt") or payload.get("prompt")
        arguments = {"capabilityId": contract.get("id", contract.get("capabilityId")),
                     "prompt": prompt, "params": params, "output": output}
        self._execute_attempts.add(identity)
        try:
            task = self._call("execute", arguments).get("task", {})
        except Exception:
            return _result("unknown", error_code="execute_response_lost", message="No caller request ID exists; do not create another task.")
        if not task.get("id"):
            return _result("unknown", error_code="task_identity_missing")
        task_id = _id(task["id"], "task_id")
        state = task.get("status")
        if state == "waiting_user":
            return _result("needs_approval", task_id=task_id, error_code="design_cost_confirmation_required")
        if state in {"accepted", "running"}:
            return _result("submitted", task_id=task_id)
        # Even a completed execute response is re-read for usable output facts.
        if state == "completed":
            return self.poll({**operation, "task_id": task_id})
        return _result("failed" if state in {"failed", "cancelled"} else "unknown", task_id=task_id)

    def poll(self, operation: dict) -> dict:
        try:
            self._guard(operation)
            task_id = operation.get("task_id")
            if not task_id:
                return _result("unknown", error_code="task_identity_missing", message="The host assigns task IDs; recover the original task manually, never repeat execute.")
            task = self._call("task_query", {"mode": "get", "taskId": task_id}).get("task", {})
            state = task.get("status")
            if state in {"accepted", "running"}:
                return _result("running", task_id=task_id)
            if state == "waiting_user":
                return _result("needs_approval", task_id=task_id, error_code="design_cost_confirmation_required")
            if state in {"failed", "cancelled"}:
                return _result("failed", task_id=task_id, error_code="design_" + state)
            if state == "completed":
                outputs = task.get("outputs", [])
                if isinstance(outputs, dict):
                    outputs = list(outputs.values())
                versions = [o.get("versionId") for o in outputs if isinstance(o, dict) and o.get("versionId")]
                if not versions:
                    return _result("unknown", task_id=task_id, error_code="completed_output_unverified")
                return _result("succeeded", task_id=task_id, version_id=_id(versions[0], "version_id"))
            return _result("unknown", task_id=task_id, error_code="design_state_unresolved")
        except Exception as exc:
            return _failure(exc)

    def download(self, operation: dict) -> dict:
        try:
            self._guard(operation)
            version = operation.get("version_id") or _payload(operation).get("version_id")
            if not version:
                raise ProviderError("version_selection_required", "needs_setup")
            reply = self._call("get_output", {"versionId": _id(version, "version_id")})
            # Exact output shape must be observed after explicit project selection.
            source = reply.get("path") or reply.get("localPath")
            if not isinstance(source, str) or not Path(source).is_absolute() or not Path(source).is_file():
                raise ProviderError("design_output_contract_unverified", "needs_setup")
            folder = Path(operation.get("output_dir") or ".").resolve()
            folder.mkdir(parents=True, exist_ok=True)
            destination = folder / (_id(operation.get("operation_id"), "operation_id") + Path(source).suffix)
            if destination.exists():
                raise ProviderError("output_already_exists", "failed")
            shutil.copyfile(source, destination)
            if destination.stat().st_size <= 0:
                raise ProviderError("empty_output", "failed")
            return _result("downloaded", path=str(destination), size=destination.stat().st_size, sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
        except Exception as exc:
            return _failure(exc)


class MockProvider:
    """A labelled local simulation; its output is JSON, never playable media."""
    name = "mock"

    def __init__(self, config: dict | None = None, *, runner=None, transport=None):
        self.config = dict(config or {})

    def identity(self) -> dict:
        return {"provider": self.name, "account": "local-simulation", "live": False,
                "verified": True, "verification": "local_simulation", "simulated": True}

    def probe(self) -> dict:
        return {**self.identity(), "status": "ready", "stages": ["image", "video"], "currency": "CNY"}

    def prepare(self, operation: dict) -> dict:
        return _result("prepared", simulated=True, payload={"simulated": True,
                       "submit_id": _stable(operation, "mock-submit")})

    def quote(self, operation: dict) -> dict:
        return _result("quoted", amount="0", currency="CNY", simulated=True)

    def submit(self, operation: dict) -> dict:
        return _result("submitted", task_id=_stable(operation, "mock-submit"), simulated=True)

    def poll(self, operation: dict) -> dict:
        return _result("succeeded", task_id=operation.get("task_id") or _stable(operation, "mock-submit"),
                       resource_id=_stable(operation, "mock-resource"), simulated=True)

    def download(self, operation: dict) -> dict:
        folder = Path(operation.get("output_dir") or _payload(operation).get("output_dir") or ".").resolve()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (_id(operation.get("operation_id"), "operation_id") + ".simulated.json")
        content = json.dumps({"simulated": True, "playable_media": False,
                              "operation_id": operation["operation_id"], "stage": operation.get("stage"),
                              "resource_id": _stable(operation, "mock-resource")}, ensure_ascii=False, sort_keys=True).encode()
        if path.exists():
            if path.read_bytes() != content:
                return _result("failed", error_code="output_already_exists", simulated=True)
        else:
            with path.open("xb") as output:
                output.write(content)
        return _result("downloaded", path=str(path), size=len(content), sha256=hashlib.sha256(content).hexdigest(),
                       simulated=True, playable_media=False)


def get_provider(name: str, config: dict | None = None, *, runner=None, transport=None):
    aliases = {"mock": MockProvider, "dreamina": DreaminaCanvasProvider, "dreamina-canvas": DreaminaCanvasProvider,
               "minimax": MiniMaxDesignProvider, "minimax-design": MiniMaxDesignProvider}
    if name not in aliases:
        raise ProviderError("unknown_provider", "needs_setup", "Choose an explicitly supported provider.")
    return aliases[name](config, runner=runner, transport=transport)
