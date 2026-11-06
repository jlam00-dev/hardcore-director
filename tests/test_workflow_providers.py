"""Contract tests: no real provider, credentials, uploads or generation calls."""

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hc_workflow.providers import (DreaminaCanvasProvider, LocalMCPTransport,
                                   MiniMaxDesignProvider, ProviderError, get_provider)


def ok(data):
    return {"ok": True, "data": data}


def schema():
    return {"subcommands": [
        {"name": "node", "subcommands": [
            {"name": "create", "subcommands": [{"name": "image"}, {"name": "video"}]},
            *[{"name": n} for n in ("quote", "confirm", "run", "show")]]},
        {"name": "operation", "subcommands": [{"name": "status"}]},
        {"name": "resource", "subcommands": [{"name": "upload"}, {"name": "download"}]},
        {"name": "model", "subcommands": [{"name": "list"}]}]}


class CLI:
    def __init__(self):
        self.calls = []
        self.user = 17
        self.team = None
        self.price = 12
        self.node = None
        self.state = "running"
        self.resources = []
        self.timeout_action = None
        self.override = {}

    def __call__(self, command, **kwargs):
        args = command[6:]
        self.calls.append(args)
        action = tuple(args[:2])
        if action == self.timeout_action:
            raise subprocess.TimeoutExpired("redacted", 1)
        if action in self.override:
            return self.override[action]
        def flag(name):
            return args[args.index("--" + name) + 1]
        if "--node-id" in args and re.fullmatch(r"node_[0-9a-hjkmnp-tv-z]{10}", flag("node-id")) is None:
            return {"ok": False, "error": {"code": "cli.invalid_node_id", "class": "invalid_input"}}
        if action == ("auth", "status"):
            return ok({"loggedIn": True, "region": "cn", "environment": "production"})
        if action == ("auth", "account"):
            return ok({"userId": self.user})
        if action == ("space", "current"):
            return ok({"userId": str(self.user), "kind": "team" if self.team else "personal", "team": {"teamId": self.team}})
        if args == ["version"]:
            return ok({"version": "1.1.1"})
        if args == ["schema"]:
            return ok(schema())
        if action == ("model", "list"):
            kind = flag("type")
            flags = [{"flag": "--prompt", "required": True, "minLength": 1, "maxLength": 1000},
                     {"flag": "--ratio", "required": True, "values": ["16:9"]},
                     {"flag": "--resolution", "required": True, "values": ["720p"]}]
            return ok({"items": [{"model": "live-model", "aliases": ["marketing-alias"], "modes": [
                {"name": "t2i" if kind == "image" else "t2v", "flags": flags,
                 "references": {"min": 0, "max": 0, "types": []}}]}]})
        if action == ("node", "create"):
            self.node = flag("node-id")
            return ok({"node": {"nodeId": self.node}, "mutation": {"savedDraftVersion": 3}})
        if action == ("node", "quote"):
            return ok({"items": [{"nodeId": flag("node-id"), "maxCredits": self.price}],
                       "totalMaxCredits": self.price, "confirmable": True,
                       "confirmationRequired": True, "draftVersion": 3})
        if action == ("node", "confirm"):
            return ok({"creditConfirmationToken": "SECRET-CREDIT-TOKEN", "creditCeiling": int(flag("credit-ceiling"))})
        if action == ("node", "run"):
            return ok({"items": [{"nodeId": flag("node-id"), "submitId": flag("submit-id"), "state": "ACCEPTED", "resources": []}]})
        if action == ("operation", "status"):
            return ok({"operationRef": args[2], "state": self.state, "resources": self.resources})
        if action == ("node", "show"):
            return ok({"nodes": [{"result": "FOUND", "node": {"nodeId": flag("node-id")}}] if self.node else []})
        if action == ("resource", "download"):
            path = Path(flag("output"))
            path.write_bytes(b"fixture-media-data")
            return ok({"path": str(path), "size": path.stat().st_size,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        raise AssertionError("Unexpected command shape: " + str(args[:2]))


class DreaminaTests(unittest.TestCase):
    def setUp(self):
        self.cli = CLI()
        self.provider = DreaminaCanvasProvider({"project_id": "canvas-1"}, runner=self.cli)
        self.account = self.provider.identity()["account"]
        self.operation = {"operation_id": "operation-one", "stage": "image", "shot_id": "S01",
                          "account": self.account,
                          "payload": {"image_prompt": "A cup on a table", "params": {
                              "model": "live-model", "mode": "t2i", "ratio": "16:9", "resolution": "720p"}},
                          "authorization": {"approval_id": "approval-one", "scope": {
                              "provider": "dreamina-canvas", "account": self.account,
                              "stages": ["image", "video"], "allow_uploads": True},
                              "budget": {"amount": "20", "currency": "DREAMINA_CREDITS"}},
                          "reserved": "20"}
        self.cli.calls.clear()

    def prepared(self):
        result = self.provider.prepare(self.operation)
        self.assertEqual(result["status"], "prepared")
        self.operation["payload"].update(result["payload"])
        return result

    def test_probe_real_contract_and_identity_shape(self):
        result = self.provider.probe()
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["verified"])
        self.assertEqual(result["version"], "1.1.1")
        self.assertNotIn("userId", result)

    def test_pre_quote_is_not_a_fake_zero_or_cny_quote(self):
        result = self.provider.quote(self.operation)
        self.assertEqual(result["status"], "needs_approval")
        self.assertIsNone(result["amount"])
        self.assertEqual(result["currency"], "DREAMINA_CREDITS")
        self.assertFalse(any(c[:2] == ["node", "quote"] for c in self.cli.calls))

    def test_save_then_quote_no_generation_and_ids_are_stable(self):
        result = self.prepared()
        quote = self.provider.quote(self.operation)
        self.assertEqual(quote["amount"], "12")
        create = next(c for c in self.cli.calls if c[:2] == ["node", "create"])
        self.assertNotIn("--run", create)
        self.assertNotIn("--credit-token", create)
        self.assertRegex(result["node_id"], r"^node_[0-9a-hjkmnp-tv-z]{10}$")
        self.assertEqual(result["node_id"], self.provider._facts(self.operation)["node_id"])
        self.assertEqual(result["submit_id"], self.provider._facts(self.operation)["submit_id"])

    def test_node_ids_follow_cli_canonical_format_and_remain_stable(self):
        first = self.provider._facts(self.operation)
        restarted = DreaminaCanvasProvider(self.provider.config, runner=self.cli)
        self.assertEqual(first["node_id"], restarted._facts(self.operation)["node_id"])
        another = {**self.operation, "operation_id": "operation-two"}
        self.assertNotEqual(first["node_id"], self.provider._facts(another)["node_id"])
        self.operation["payload"]["node_id"] = "node_0000000001"
        self.assertEqual(self.provider._facts(self.operation)["node_id"], "node_0000000001")

    def test_saved_invalid_node_id_is_not_silently_replaced_or_sent(self):
        for invalid in ("node_" + "a" * 32, "node_abcdefghiu", "node_000000000I", "node_000000000"):
            with self.subTest(node_id=invalid):
                self.operation["payload"]["node_id"] = invalid
                result = self.provider.prepare(self.operation)
                self.assertEqual(result["status"], "needs_setup")
                self.assertEqual(result["error_code"], "invalid_node_id")
                self.assertEqual(self.operation["payload"]["node_id"], invalid)
        self.assertFalse(any(c[:2] == ["node", "create"] for c in self.cli.calls))

    def test_explicit_empty_saved_node_ids_never_derive_a_replacement(self):
        for invalid in ("", None, False, 0):
            with self.subTest(node_id=invalid):
                self.operation["payload"].update(node_id=invalid, saved=True)
                result = self.provider.prepare(self.operation)
                self.assertEqual(result["status"], "needs_setup")
                self.assertEqual(result["error_code"], "invalid_node_id")
                self.assertIs(self.operation["payload"]["node_id"], invalid)
                self.assertNotIn("payload", result)
        self.assertFalse(any(c[:2] in (["node", "create"], ["node", "show"]) for c in self.cli.calls))

    def test_acceptance_is_not_success_and_token_is_not_returned(self):
        self.prepared()
        result = self.provider.submit(self.operation)
        self.assertEqual(result["status"], "submitted")
        self.assertNotIn("SECRET-CREDIT-TOKEN", json.dumps(result))
        self.assertEqual(result["task_id"], self.operation["payload"]["submit_id"])

    def test_changed_live_quote_stops_before_confirm_or_run(self):
        self.prepared()
        self.cli.price = 21
        result = self.provider.submit(self.operation)
        self.assertEqual(result["error_code"], "credit_ceiling_exceeded")
        self.assertFalse(any(c[:2] in (["node", "run"], ["node", "confirm"]) for c in self.cli.calls))

    def test_currency_mismatch_does_not_spend(self):
        self.prepared()
        self.operation["authorization"]["budget"]["currency"] = "CNY"
        self.assertEqual(self.provider.submit(self.operation)["error_code"], "budget_currency_mismatch")
        self.assertFalse(any(c[:2] == ["node", "run"] for c in self.cli.calls))

    def test_account_change_and_team_change_block_every_mutation(self):
        self.cli.user = 18
        self.assertEqual(self.provider.prepare(self.operation)["error_code"], "account_changed")
        self.cli.user = 17
        self.cli.team = "another-team"
        self.assertEqual(self.provider.prepare(self.operation)["error_code"], "account_changed")
        self.assertFalse(any(c[:2] == ["node", "create"] for c in self.cli.calls))

    def test_stage_and_upload_scopes_are_independent(self):
        self.operation["authorization"]["scope"]["stages"] = ["video"]
        self.assertEqual(self.provider.prepare(self.operation)["error_code"], "stage_authorization_required")
        self.operation["authorization"]["scope"]["stages"] = ["image"]
        self.operation["authorization"]["scope"]["allow_uploads"] = False
        self.operation["payload"]["input_assets"] = ["/unused/reference.png"]
        self.assertEqual(self.provider.prepare(self.operation)["error_code"], "upload_authorization_required")

    def test_alias_and_unknown_parameter_rejected_before_save(self):
        self.operation["payload"]["params"]["model"] = "marketing-alias"
        self.assertEqual(self.provider.prepare(self.operation)["error_code"], "canonical_model_required")
        self.operation["payload"]["params"]["model"] = "live-model"
        self.operation["payload"]["params"]["guessed_model_field"] = True
        self.assertEqual(self.provider.prepare(self.operation)["error_code"], "unknown_generation_parameter")

    def test_submit_timeout_recovers_same_id_without_second_run(self):
        self.prepared()
        self.cli.timeout_action = ("node", "run")
        result = self.provider.submit(self.operation)
        self.assertEqual(result["status"], "unknown")
        self.operation["task_id"] = result["task_id"]
        self.operation["payload"].update(result["payload"])
        self.cli.timeout_action = None
        recovered = self.provider.submit(self.operation)
        self.assertEqual(recovered["status"], "running")
        self.assertEqual(sum(c[:2] == ["node", "run"] for c in self.cli.calls), 1)

    def test_same_in_memory_operation_cannot_repeat_run(self):
        self.prepared()
        first = self.provider.submit(self.operation)
        self.assertEqual(first["status"], "submitted")
        self.assertEqual(self.provider.submit(self.operation)["status"], "running")
        self.assertEqual(sum(c[:2] == ["node", "run"] for c in self.cli.calls), 1)

    def test_success_requires_nonempty_ready_resource_facts(self):
        self.prepared()
        self.operation["task_id"] = self.operation["payload"]["submit_id"]
        self.cli.state = "completed"
        self.assertEqual(self.provider.poll(self.operation)["status"], "unknown")
        self.cli.resources = [{"resourceId": "resource-one", "state": "running"}]
        self.assertEqual(self.provider.poll(self.operation)["status"], "unknown")
        self.cli.resources[0]["state"] = "succeeded"
        self.assertEqual(self.provider.poll(self.operation)["status"], "succeeded")

    def test_absent_submission_never_resubmits(self):
        self.prepared()
        self.operation["task_id"] = self.operation["payload"]["submit_id"]
        self.cli.state = "absent"
        self.assertEqual(self.provider.submit(self.operation)["status"], "unknown")
        self.assertFalse(any(c[:2] == ["node", "run"] for c in self.cli.calls))

    def test_download_is_checked_and_never_overwrites(self):
        self.prepared()
        self.operation["resource_id"] = "resource-one"
        with tempfile.TemporaryDirectory() as folder:
            self.operation["output_dir"] = folder
            result = self.provider.download(self.operation)
            self.assertEqual(result["status"], "downloaded")
            path = Path(result["path"])
            self.assertTrue(path.is_file())
            self.assertEqual(self.provider.download(self.operation), result)
            path.write_bytes(b"a foreign file must survive recovery")
            self.assertEqual(self.provider.download(self.operation)["error_code"], "output_already_exists")
            self.assertEqual(path.read_bytes(), b"a foreign file must survive recovery")

    def test_structured_cli_errors_do_not_leak_messages(self):
        self.cli.override[("auth", "status")] = {"ok": False, "error": {
            "code": "auth.expired", "requiredAction": "login", "message": "SECRET https://signed/private?token=SECRET"}}
        result = self.provider.probe()
        self.assertEqual(result["status"], "needs_setup")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_nonzero_empty_stdout_uses_stderr_json_error_without_leaking(self):
        self.cli.override[("node", "create")] = subprocess.CompletedProcess([], 2, stdout="", stderr=json.dumps({
            "ok": False, "error": {"code": "cli.invalid_node_id", "class": "invalid_input",
                                      "message": "SECRET signed-url?token=SECRET"}}))
        result = self.provider.prepare(self.operation)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "cli.invalid_node_id")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_unknown_required_action_is_not_echoed(self):
        for action in ("SECRET-DO-NOT-LOG", "https://private?token=SECRET", {"token": "SECRET"}):
            with self.subTest(action=action):
                self.cli.override[("node", "create")] = {"ok": False, "error": {
                    "code": "cli.invalid_node_id", "class": "invalid_input", "requiredAction": action}}
                result = self.provider.prepare(self.operation)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["message"], "Official CLI action required: failed")
                self.assertNotIn("SECRET", json.dumps(result))

    def test_unsafe_or_oversized_error_codes_use_fixed_fallback(self):
        for code in ("SECRET-DO-NOT-LOG", "cli.error\nSECRET", "https://private?token=SECRET", "a" * 129, None, 123):
            with self.subTest(code=code):
                self.cli.override[("node", "create")] = subprocess.CompletedProcess([], 2, stdout="", stderr=json.dumps({
                    "ok": False, "error": {"code": code, "class": "invalid_input", "message": "SECRET"}}))
                result = self.provider.prepare(self.operation)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["error_code"], "cli_error")
                self.assertNotIn("SECRET", json.dumps(result))

    def test_nonzero_stderr_diagnostics_and_false_success_stay_unknown(self):
        for stderr, code in (("SECRET non-JSON diagnostics", "invalid_cli_json"),
                             (json.dumps(ok({"unexpected": "SECRET"})), "cli_exit_status_mismatch")):
            with self.subTest(code=code):
                self.cli.override[("node", "create")] = subprocess.CompletedProcess([], 2, stdout="", stderr=stderr)
                result = self.provider.prepare(self.operation)
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(result["error_code"], code)
                self.assertNotIn("SECRET", json.dumps(result))

    def test_invalid_json_is_not_success(self):
        self.cli.override[("auth", "status")] = subprocess.CompletedProcess([], 0, stdout="not-json", stderr="SECRET")
        result = self.provider.prepare(self.operation)
        self.assertEqual(result["status"], "needs_setup")
        self.assertNotIn("SECRET", json.dumps(result))


class FrameSlotRegressionTests(unittest.TestCase):
    """Mirror Engine._new_operation/_snapshot_inputs without touching live assets."""
    def setUp(self):
        self.cli = CLI()
        flags = [{"flag": "--prompt", "required": False, "minLength": 0, "maxLength": 15000},
                 {"flag": "--ratio", "required": True, "values": ["16:9"]},
                 {"flag": "--resolution", "required": True, "values": ["480p", "720p", "1080p"]},
                 {"flag": "--duration", "required": True, "min": 4, "max": 30, "step": 1},
                 {"flag": "--count", "required": False, "min": 1, "max": 4}]
        self.cli.override[("model", "list")] = ok({"items": [{"model": "seedance_2.5", "modes": [
            {"name": "first_last_frame", "flags": flags, "references": {"min": 2, "max": 2, "types": [{"mediaType": "image", "min": 2, "max": 2}]}},
            {"name": "first_last_frame", "flags": flags, "references": {"min": 1, "max": 1, "types": [{"mediaType": "image", "min": 1, "max": 1}]}}]}]})
        self.provider = DreaminaCanvasProvider({"video": {"model": "seedance_2.5", "mode": "first_last_frame", "resolution": "480p", "count": 1}}, runner=self.cli)
        self.operation = {"operation_id": "engine-shaped-no-generation", "stage": "video", "shot_id": "S01",
                          "payload": {"shot": {"id": "S01", "duration_seconds": 4, "reference_assets": []},
                                      "video_prompt": "Contract fixture only.", "duration_seconds": 4, "duration": 4,
                                      "aspect_ratio": "16:9", "ratio": "16:9", "fps": 24, "input_assets": []}}

    def asset(self, index, role):
        return {"path": f"/not-read/operation/input-{index:03}.png", "source_path": f"/not-read/source-{index}.png",
                "sha256": "0" * 64, "size": 100, "operation_id": "earlier-image", "role": role}

    def test_engine_single_start_frame_preserves_slot_and_snapshot_fields(self):
        asset = self.asset(0, "start_frame")
        self.operation["payload"]["input_assets"] = [asset]
        planned = self.provider._plan(self.operation)
        self.assertEqual(planned["input_assets"], [asset])
        self.assertEqual(planned["values"]["duration"], 4)
        self.assertEqual(planned["values"]["ratio"], "16:9")
        self.assertTrue(all(call[:2] == ["model", "list"] for call in self.cli.calls))

    def test_engine_explicit_start_end_pair_preserves_order(self):
        assets = [self.asset(0, "start_frame"), self.asset(1, "end_frame")]
        self.operation["payload"]["input_assets"] = assets
        self.assertEqual(self.provider._plan(self.operation)["input_assets"], assets)

    def test_start_plus_style_or_character_is_not_silently_a_last_frame(self):
        for role in ("style", "style_reference", "character", "identity", None):
            with self.subTest(role=role):
                self.operation["payload"]["input_assets"] = [self.asset(0, "start_frame"), self.asset(1, role)]
                with self.assertRaises(ProviderError) as caught:
                    self.provider._plan(self.operation)
                self.assertEqual(caught.exception.code, "frame_slot_roles_invalid")
                self.assertEqual(caught.exception.status, "needs_setup")
                self.assertIn("m2v", str(caught.exception))
        self.assertFalse(any(call[:2] in (["resource", "upload"], ["node", "create"], ["node", "run"]) for call in self.cli.calls))

    def test_missing_single_role_and_reversed_pair_fail_closed(self):
        for assets in ([{"path": "/not-read/input-000.png"}],
                       [self.asset(0, "end_frame"), self.asset(1, "start_frame")],
                       [self.asset(0, "end_frame")]):
            with self.subTest(roles=[item.get("role") for item in assets]):
                self.operation["payload"]["input_assets"] = assets
                with self.assertRaises(ProviderError) as caught:
                    self.provider._plan(self.operation)
                self.assertEqual(caught.exception.status, "needs_setup")

    def test_explicit_typed_direct_refs_keep_official_ordered_frame_semantics(self):
        for refs in (["node:node_first"], ["node:node_first", "node:node_last"]):
            with self.subTest(refs=refs):
                self.operation["payload"]["references"] = refs
                self.assertEqual(self.provider._plan(self.operation)["references"], refs)
        self.operation["payload"]["reference_roles"] = ["start_frame", "style"]
        with self.assertRaises(ProviderError):
            self.provider._plan(self.operation)

    def test_explicit_mixed_direct_start_and_file_end_is_valid(self):
        self.operation["payload"].update(references=["node:node_first"], reference_roles=["first_frame"],
                                          input_assets=[self.asset(0, "last_frame")])
        self.assertEqual(self.provider._plan(self.operation)["input_assets"][0]["role"], "last_frame")


class MCP:
    def __init__(self):
        self.calls = []
        self.task = {"status": "running"}
        self.projects = [{"projectId": "selected", "open": True}, {"projectId": "unrelated", "open": True}]
        self.contracts = [{"id": "generate_image:live", "operation": "generate_image", "paramSchema": {"type": "object", "properties": {"ratio": {"type": "string", "enum": ["16:9"]}}, "additionalProperties": False},
                           "references": {"totalCount": {"min": 0, "max": 0}}}]
        self.tools = {name: {"name": name, "inputSchema": {"type": "object", "additionalProperties": True}}
                      for name in ("list_projects", "open_project", "capability_list", "capability_get",
                                   "execute", "task_query", "task_wait", "confirm_cost", "get_output")}
        self.tools["execute"]["inputSchema"] = {
            "type": "object", "properties": {
                "capabilityId": {"type": "string"}, "prompt": {"type": "string"},
                "params": {"type": "object"},
                "output": {"type": "object", "properties": {
                    "resources": {"type": "array", "minItems": 1, "items": {
                        "type": "object", "properties": {"mode": {"const": "create"}, "name": {"type": "string"}},
                        "required": ["mode", "name"], "additionalProperties": False}},
                }, "required": ["resources"], "additionalProperties": False},
            }, "required": ["capabilityId", "prompt", "params", "output"], "additionalProperties": False,
        }

    def request(self, method, params):
        self.calls.append((method, params))
        if method == "initialize":
            return {"serverInfo": {"name": "minimax-design", "version": "1.0.0"}}
        if method == "tools/list":
            return {"tools": list(self.tools.values())}
        name = params["name"]
        args = params["arguments"]
        if name == "list_projects":
            data = {"projects": self.projects}
        elif name == "open_project":
            data = {"projectId": args["projectId"]}
        elif name == "capability_get":
            data = {"capabilities": self.contracts}
        elif name == "task_query":
            data = {"task": self.task}
        else:
            raise AssertionError("A forbidden or unimplemented tool was called: " + name)
        return {"structuredContent": data}


class MiniMaxTests(unittest.TestCase):
    def setUp(self):
        self.transport = MCP()
        self.provider = MiniMaxDesignProvider(transport=self.transport)

    def manual_operation(self):
        self.provider.config.update({"manual_session": True, "project_id": "selected"})
        identity = self.provider.identity()
        return {"operation_id": "op-minimax", "stage": "image", "account": identity["account"],
                "payload": {"capability_id": "generate_image:live", "params": {"ratio": "16:9"},
                            "image_prompt": "the unchanged fixture description",
                            "design_output": {"resources": [{"mode": "create", "name": "fixture-image"}]}},
                "authorization": {"approval_id": "manual-local", "scope": {"provider": "minimax-design", "identity_mode": "manual_session", "account": identity["account"]}}}

    def test_probe_lists_but_never_opens_unrelated_project(self):
        result = self.provider.probe()
        self.assertEqual(result["status"], "needs_project_selection")
        self.assertFalse(result["verified"])
        self.assertFalse(result["account_verified"])
        names = [p.get("name") for method, p in self.transport.calls if method == "tools/call"]
        self.assertEqual(names, ["list_projects"])

    def test_probe_reports_explicit_project_visibility_without_unlocking_generation(self):
        for projects, blocker in (([{"projectId": "selected", "open": True}], None),
                                  ([{"projectId": "selected", "open": False}], "selected_project_not_open"),
                                  ([{"projectId": "different", "open": True}], "selected_project_unavailable"),
                                  ([{"projectId": "selected", "open": True}] * 2, "selected_project_ambiguous")):
            with self.subTest(blocker=blocker):
                transport = MCP()
                transport.projects = projects
                p = MiniMaxDesignProvider({"project_id": "selected"}, transport=transport)
                result = p.probe()
                self.assertEqual(result["status"], "needs_setup")
                self.assertFalse(result["verified"])
                self.assertFalse(result["account_verified"])
                self.assertFalse(result["generation_contract_verified"])
                self.assertEqual(result["selected_project_visible"], blocker in {None, "selected_project_not_open"})
                self.assertEqual(result["selected_project_open"], blocker is None)
                self.assertNotIn("explicit_project_selection", result["blockers"])
                if blocker:
                    self.assertIn(blocker, result["blockers"])
                self.assertEqual([p.get("name") for m, p in transport.calls if m == "tools/call"], ["list_projects"])

    def test_missing_explicit_request_fields_require_setup_without_any_execute(self):
        for key, code in (("capability_id", "capability_selection_required"),
                          ("params", "explicit_design_params_required"), ("design_output", "explicit_output_required")):
            with self.subTest(key=key):
                operation = self.manual_operation()
                operation["payload"].pop(key)
                self.assertEqual(self.provider.prepare(operation)["error_code"], code)
                self.assertEqual(self.provider.quote(operation)["status"], "needs_setup")
        self.assertFalse(any(p.get("name") in {"execute", "confirm_cost"} for _, p in self.transport.calls))

    def test_preparation_returns_an_unchanged_local_request_preview_only(self):
        operation = self.manual_operation()
        result = self.provider.prepare(operation)
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(result["request_preview"], {"capabilityId": "generate_image:live",
                         "prompt": operation["payload"]["image_prompt"], "params": {"ratio": "16:9"},
                         "output": operation["payload"]["design_output"]})
        self.assertFalse(result["design_draft_saved"])
        self.assertFalse(result["generation_submitted"])
        result["request_preview"]["output"]["resources"][0]["name"] = "changed-later"
        self.assertEqual(operation["payload"]["design_output"]["resources"][0]["name"], "fixture-image")
        self.assertFalse(any(p.get("name") in {"execute", "confirm_cost", "deliver", "document_write"} for _, p in self.transport.calls))

    def video_contract(self, rules):
        self.transport.contracts = [{"id": "generate_video:reviewed", "operation": "generate_video", "knowledgeCard": "<knowledgeDir>/vendors/fixture.md",
            "paramSchema": {"type": "object", "properties": {
                "mode": {"type": "string", "enum": ["reference", "first-last-frame", "video-edit"], "default": "reference"},
                "aspect_ratio": {"type": "string", "enum": ["adaptive", "16:9", "9:16"], "default": "adaptive"},
                "duration": {"type": "integer", "minimum": 4, "maximum": 15},
            }}, "paramRules": rules, "prompt": {"maxLength": 100},
            "references": {"totalCount": {"min": 0, "max": 12}, "byKind": {"image": {"maxCount": 9}},
                           "modeOverrides": {"first-last-frame": {"totalCount": {"min": 0, "max": 2}}}}}]
        operation = self.manual_operation()
        operation["stage"] = "video"
        operation["payload"].update(capability_id="generate_video:reviewed", params={"duration": 4},
                                    video_prompt="the exact original description")
        return operation

    def test_matching_capability_id_requires_a_matching_explicit_operation(self):
        for stage in ("image", "video"):
            for reported in (None, "generate_video" if stage == "image" else "generate_image", "generate_audio"):
                with self.subTest(stage=stage, reported=reported):
                    operation = self.video_contract([]) if stage == "video" else self.manual_operation()
                    if stage == "image":
                        self.transport.contracts = MCP().contracts
                    contract = self.transport.contracts[0]
                    self.assertEqual(contract["id"], operation["payload"]["capability_id"])
                    if reported is None:
                        contract.pop("operation")
                    else:
                        contract["operation"] = reported
                    for action in (self.provider.prepare, self.provider.submit):
                        result = action(operation)
                        self.assertEqual(result["status"], "needs_setup")
                        self.assertEqual(result["error_code"], "capability_operation_contract_review_required")
        self.assertFalse(any(p.get("name") in {"execute", "confirm_cost", "document_write"} for _, p in self.transport.calls))

    def test_unsupported_stage_settings_block_direct_calls_before_transport(self):
        for stages in ({"image": {"max_cost": "1"}}, {"image": {"budget": {"amount": "1"}}},
                       {"video": {"max_cost": "1"}}, {"image": {"unknown": True}},
                       {"image": []}, {"audio": {}}, None):
            with self.subTest(stages=stages):
                operation = self.manual_operation()
                self.provider.config["stages"] = stages
                before = list(self.transport.calls)
                for action in (self.provider.prepare, self.provider.quote, self.provider.submit):
                    result = action(operation)
                    self.assertEqual(result["status"], "needs_setup")
                    self.assertEqual(result["error_code"], "design_stage_configuration_review_required")
                operation["task_id"] = "existing-read-only-task"
                self.assertEqual(self.provider.submit(operation)["error_code"], "design_stage_configuration_review_required")
                self.assertEqual(self.transport.calls, before)

    def test_known_conditional_rules_validate_without_uploading_or_generating(self):
        rule = {"when": {"param": "mode", "values": ["first-last-frame"]},
                "disable": {"param": "aspect_ratio", "values": ["16:9", "9:16"]}}
        operation = self.video_contract([rule, rule])
        # An omitted mode uses the live rule's declared default, not a guessed key.
        result = self.provider.prepare(operation)
        self.assertEqual(result["status"], "prepared")
        self.assertTrue(result["model_prompt_review_required"])
        self.assertEqual(result["request_preview"]["params"], {"duration": 4})
        operation["payload"]["params"].update(mode="first-last-frame", aspect_ratio="16:9")
        self.assertEqual(self.provider.prepare(operation)["error_code"], "conditional_parameter_forbidden")
        operation["payload"]["params"]["aspect_ratio"] = "adaptive"
        self.assertEqual(self.provider.prepare(operation)["error_code"], "model_reference_contract_review_required")
        operation = self.video_contract([])
        self.transport.contracts[0]["paramSchema"]["properties"]["mode"]["default"] = "first-last-frame"
        self.assertEqual(self.provider.prepare(operation)["error_code"], "model_reference_contract_review_required")
        self.assertFalse(any(p.get("name") in {"execute", "confirm_cost", "deliver"} for _, p in self.transport.calls))

    def test_whole_parameter_disable_and_unknown_rules_fail_closed(self):
        rule = {"when": {"param": "mode", "values": ["video-edit"]}, "disable": {"param": "duration"}}
        operation = self.video_contract([rule])
        operation["payload"]["params"]["mode"] = "video-edit"
        self.assertEqual(self.provider.prepare(operation)["error_code"], "conditional_parameter_forbidden")
        operation["payload"]["params"].pop("duration")
        self.assertEqual(self.provider.prepare(operation)["error_code"], "model_reference_contract_review_required")
        for unsupported in (None, {}, [{"when": {"param": "mode", "values": ["video-edit"]}, "enable": {"param": "duration"}}],
                            [{"when": {"param": "mode", "values": ["video-edit"]}, "disable": {"param": "duration", "unless": True}}],
                            [{"when": {"param": "unknown", "values": ["inactive"]}, "disable": {"param": "duration"}}]):
            with self.subTest(rule=unsupported):
                operation = self.video_contract(unsupported)
                self.assertEqual(self.provider.prepare(operation)["error_code"], "model_parameter_rules_review_required")

    def test_declared_flat_keys_output_and_reference_limits_are_not_assumed(self):
        operation = self.video_contract([])
        operation["payload"]["params"]["undeclared"] = True
        self.assertEqual(self.provider.prepare(operation)["error_code"], "unknown_parameter")
        operation["payload"]["params"].pop("undeclared")
        for key, value in (("input_assets", [{"path": "never-read"}]), ("references", [{"versionId": "never-read"}]),
                           ("references", False)):
            with self.subTest(key=key, value=value):
                operation["payload"][key] = value
                self.assertEqual(self.provider.prepare(operation)["error_code"], "model_reference_contract_review_required")
                operation["payload"].pop(key)
        operation["payload"]["design_output"] = {"resources": []}
        self.assertEqual(self.provider.prepare(operation)["error_code"], "invalid_parameters")
        operation["payload"]["design_output"] = {"resources": [{"mode": "create", "name": "fixture"}]}
        operation["payload"]["design_project_id"] = "unrelated"
        self.assertEqual(self.provider.prepare(operation)["error_code"], "design_project_configuration_changed")

    def test_text_only_preparation_requires_proven_zero_reference_contract(self):
        cases = [None, {}, {"totalCount": {"min": 1, "max": 1}},
                 {"totalCount": {"min": 0, "max": 1}, "byKind": {"image": {"minCount": 1}}},
                 {"totalCount": {"min": 0, "max": 1}, "modeOverrides": {"reference": {"totalCount": {"min": 1}}}},
                 {"totalCount": {"min": 0, "max": 1}, "requiredMask": True},
                 {"totalCount": {"min": False, "max": 1}},
                 {"totalCount": {"min": 0}, "byKind": {"video": {"durationSeconds": {"totalMin": 1}}}},
                 {"totalCount": {"min": 0}, "byKind": {"image": {"size": {"requiredMask": True}}}},
                 {"totalCount": {"min": 0}, "byKind": {"video": {"fps": {"min": "24"}}}},
                 {"totalCount": {"min": 0}, "lastFrameOnly": {"required": True}},
                 {"totalCount": {"min": 0}, "combinedCountLimits": [{"kinds": ["image"], "minCount": 1}]}]
        for references in cases:
            with self.subTest(references=references):
                operation = self.video_contract([])
                self.transport.contracts[0]["references"] = references
                self.assertEqual(self.provider.prepare(operation)["error_code"], "model_reference_contract_review_required")
        operation = self.video_contract([])
        self.transport.contracts[0]["references"]["combinedCountLimits"] = [{"kinds": ["video", "audio"], "maxCount": 3}]
        self.transport.contracts[0]["references"]["byKind"]["video"] = {
            "durationSeconds": {"perItem": {"min": 2, "max": 15}, "totalMax": 15, "totalWithOutputMax": 30},
            "size": {"minWidth": 256, "maxWidth": 5760, "minRatio": 0.4, "maxRatio": 2.5},
            "fps": {"min": 23.5, "max": 60.5}, "maxCount": 3}
        self.assertEqual(self.provider.prepare(operation)["status"], "prepared")
        self.transport.contracts[0]["references"]["byKind"]["video"]["durationSeconds"]["totalWithOutputMax"] = 3
        self.assertEqual(self.provider.prepare(operation)["error_code"], "reference_output_duration_limit")
        self.assertFalse(any(p.get("name") in {"execute", "confirm_cost", "deliver"} for _, p in self.transport.calls))

    def test_real_schema_params_are_validated_not_guessed(self):
        operation = self.manual_operation()
        operation["payload"]["params"]["guessedField"] = True
        result = self.provider.prepare(operation)
        self.assertEqual(result["error_code"], "unknown_parameter")
        self.assertFalse(any(p.get("name") == "execute" for _, p in self.transport.calls))

    def test_unknown_quote_blocks_fresh_execute(self):
        operation = self.manual_operation()
        self.assertIsNone(self.provider.quote(operation)["amount"])
        self.assertEqual(self.provider.submit(operation)["error_code"], "bounded_execute_unavailable")
        self.assertFalse(any(p.get("name") in {"execute", "confirm_cost"} for _, p in self.transport.calls))

    def test_missing_task_id_is_unknown_not_resubmittable(self):
        operation = self.manual_operation()
        self.assertEqual(self.provider.poll(operation)["status"], "unknown")
        self.assertFalse(any(p.get("name") == "execute" for _, p in self.transport.calls))

    def test_session_change_invalidates_prior_manual_scope(self):
        operation = self.manual_operation()
        self.provider.session_nonce = "new-session"
        self.assertEqual(self.provider.poll(operation)["error_code"], "manual_session_authorization_required")

    def test_known_task_waiting_and_completed_require_actual_outputs(self):
        operation = self.manual_operation()
        operation["task_id"] = "server-task"
        self.assertEqual(self.provider.submit(operation)["status"], "running")
        self.transport.task = {"status": "waiting_user", "billing": {"confirmation": {"amount": 7}}}
        self.assertEqual(self.provider.poll(operation)["status"], "needs_approval")
        self.transport.task = {"status": "completed", "outputs": []}
        self.assertEqual(self.provider.poll(operation)["status"], "unknown")
        self.transport.task["outputs"] = [{"versionId": "version-one", "url": "https://temporary/?secret=1"}]
        result = self.provider.poll(operation)
        self.assertEqual(result["status"], "succeeded")
        self.assertNotIn("secret", json.dumps(result))

    def test_no_remote_mcp_or_unknown_cli_provider(self):
        with self.assertRaises(ProviderError):
            LocalMCPTransport("https://remote.example/mcp")
        with self.assertRaises(ProviderError):
            get_provider("guessed-minimax-cli")


class MockTests(unittest.TestCase):
    def test_persistent_ids_and_explicitly_non_playable_output(self):
        provider = get_provider("mock")
        operation = {"operation_id": "mock-one", "stage": "video", "payload": {}}
        self.assertFalse(provider.identity()["live"])
        self.assertEqual(provider.quote(operation)["amount"], "0")
        first = provider.submit(operation)
        second = get_provider("mock").submit(operation)
        self.assertEqual(first["task_id"], second["task_id"])
        with tempfile.TemporaryDirectory() as folder:
            operation["output_dir"] = folder
            result = provider.download(operation)
            self.assertTrue(result["simulated"])
            self.assertFalse(result["playable_media"])
            self.assertEqual(Path(result["path"]).suffix, ".json")
            self.assertFalse(json.loads(Path(result["path"]).read_text())["playable_media"])
            self.assertEqual(provider.download(operation)["sha256"], result["sha256"])


if __name__ == "__main__":
    unittest.main()
