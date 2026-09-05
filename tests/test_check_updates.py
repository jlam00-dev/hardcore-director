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


if __name__ == "__main__":
    unittest.main()
