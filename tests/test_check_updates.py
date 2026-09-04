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

    def test_manifest_validation(self):
        temporary, root, component = self.make_fixture()
        self.addCleanup(temporary.cleanup)
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps({"schema_version": 1, "components": [component]}),
            encoding="utf-8",
        )
        loaded = MODULE.load_manifest(manifest)
        self.assertEqual(loaded["components"][0]["id"], "sample")


if __name__ == "__main__":
    unittest.main()
