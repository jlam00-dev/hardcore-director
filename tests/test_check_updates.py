from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_updates.py"
SPEC = importlib.util.spec_from_file_location("check_updates", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class UpdateCheckerTests(unittest.TestCase):
    def make_fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "references").mkdir()
        bundled = root / "references" / "sample.md"
        bundled.write_text("sample\n", encoding="utf-8")
        digest = MODULE.sha256_file(bundled)
        component = {
            "id": "sample",
            "bundled_path": "references/sample.md",
            "sha256": digest,
            "bundled_version": "1.0.0",
            "upstream": {"kind": "clawhub", "ref": "@demo/sample"},
        }
        return temporary, root, component

    def test_offline_integrity_clean(self):
        temporary, root, component = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        result = MODULE.check_component(component, root=root, offline=True)
        self.assertEqual(result["local"], "ok")
        self.assertEqual(result["upstream"], "skipped")
        self.assertEqual(result["source_mode"], "tracked")

    def test_offline_integrity_detects_drift(self):
        temporary, root, component = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        (root / component["bundled_path"]).write_text("changed\n", encoding="utf-8")
        result = MODULE.check_component(component, root=root, offline=True)
        self.assertEqual(result["local"], "drift")

    @mock.patch.object(MODULE, "inspect_clawhub", return_value="1.0.1")
    def test_online_update_detected(self, _inspect):
        temporary, root, component = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        result = MODULE.check_component(component, root=root, offline=False)
        self.assertEqual(result["upstream"], "update_available")

    def test_local_only_component_is_counted_offline(self):
        temporary, root, component = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        component["upstream"] = {"kind": "local_only"}
        result = MODULE.check_component(component, root=root, offline=True)
        summary = MODULE.summarize([result])
        self.assertEqual(result["upstream"], "skipped")
        self.assertEqual(result["source_mode"], "local_only")
        self.assertEqual(summary["source_tracked"], 0)
        self.assertEqual(summary["local_only"], 1)

    def test_local_only_component_is_not_queried_online(self):
        temporary, root, component = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        component["upstream"] = {"kind": "local_only"}
        result = MODULE.check_component(component, root=root, offline=False)
        self.assertEqual(result["upstream"], "not_applicable")

    @mock.patch.object(MODULE, "latest_github_path_commit", return_value="new-commit")
    def test_source_watch_requires_review_instead_of_sync(self, _inspect):
        temporary, root, component = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        component["update_policy"] = "source_watch"
        component["upstream"] = {
            "kind": "github_path",
            "repo": "demo/repo",
            "path": "SKILL.md",
            "pinned_commit": "old-commit",
        }
        result = MODULE.check_component(component, root=root, offline=False)
        self.assertEqual(result["upstream"], "review_available")

    @mock.patch.object(MODULE, "latest_github_path_commit", side_effect=["primary", "secondary-new"])
    def test_additional_upstream_is_checked(self, _inspect):
        temporary, root, component = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        component["upstream"] = {
            "kind": "github_path",
            "repo": "demo/primary",
            "path": "SKILL.md",
            "pinned_commit": "primary",
        }
        component["additional_upstreams"] = [
            {
                "kind": "github_path",
                "repo": "demo/secondary",
                "path": "SKILL.md",
                "pinned_commit": "secondary-old",
            }
        ]
        result = MODULE.check_component(component, root=root, offline=False)
        self.assertEqual(result["upstream"], "update_available")
        self.assertEqual(len(result["sources"]), 2)

    def test_manifest_validation(self):
        temporary, root, component = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps({"schema_version": 2, "components": [component]}),
            encoding="utf-8",
        )
        loaded = MODULE.load_manifest(manifest)
        self.assertEqual(loaded["components"][0]["id"], "sample")

    @mock.patch.object(MODULE, "http_text")
    def test_clawhub_uses_read_only_http_and_checks_owner(self, http):
        http.return_value = json.dumps({"owner": {"handle": "cellcog"}, "latestVersion": {"version": "2.0.21"}})
        self.assertEqual(MODULE.inspect_clawhub("@cellcog/cellcog"), "2.0.21")
        self.assertEqual(http.call_args.args[0], "https://clawhub.ai/api/v1/skills/cellcog")
        with self.assertRaisesRegex(RuntimeError, "owner mismatch"):
            MODULE.inspect_clawhub("@other/cellcog")

    @mock.patch.object(MODULE, "latest_github_path_commit", side_effect=["new-commit", RuntimeError("not found")])
    def test_secondary_failure_retains_primary_update_evidence(self, _inspect):
        temporary, root, component = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        component["upstream"] = {"kind": "github_path", "repo": "demo/primary", "path": "SKILL.md", "pinned_commit": "old"}
        component["additional_upstreams"] = [{"kind": "github_path", "repo": "demo/missing", "path": "rules.md", "pinned_commit": "old"}]
        result = MODULE.check_component(component, root=root, offline=False)
        self.assertEqual(result["upstream"], "error")
        self.assertTrue(result["has_changes"])
        self.assertEqual(result["sources"][0]["latest"], "new-commit")
        self.assertEqual(len(result["source_errors"]), 1)

    @mock.patch.dict(MODULE.os.environ, {}, clear=True)
    @mock.patch.object(MODULE.shutil, "which", return_value="/usr/bin/gh")
    @mock.patch.object(MODULE.subprocess, "run")
    def test_github_uses_existing_gh_auth_without_exposing_credentials(self, run, _which):
        run.return_value = mock.Mock(returncode=0, stdout='{"ok":true}')
        self.assertEqual(MODULE.http_text("https://api.github.com/repos/demo/repo/commits?per_page=1"), '{"ok":true}')
        command = run.call_args.args[0]
        self.assertIn("GET", command)
        self.assertEqual(command[-1], "repos/demo/repo/commits?per_page=1")
        self.assertFalse(any("Authorization" in item for item in command))

    @mock.patch.object(MODULE.time, "sleep")
    @mock.patch.object(MODULE, "_http_text_once")
    def test_transient_connection_error_retries_once(self, fetch, sleep):
        fetch.side_effect = [MODULE.urllib.error.URLError("TLS EOF"), "ok"]
        self.assertEqual(MODULE.http_text("https://clawhub.ai/api/v1/skills/cellcog"), "ok")
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(0.4)


if __name__ == "__main__":
    unittest.main()
