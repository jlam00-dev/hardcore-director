from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SPEC = importlib.util.spec_from_file_location("package_validator", Path(__file__).resolve().parents[1] / "scripts/validate_package.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class PackageValidationTests(unittest.TestCase):
    def test_skillhub_without_extensionless_version_is_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "manifests").mkdir()
            (root / "SKILL.md").write_text("---\nname: hardcore-director\nslug: hardcore-director\nversion: 2.2.0\ndescription: test\ndisplayName: test\nsummary: test\ntags: []\n---\n", encoding="utf-8")
            manifest = {"schema_version": 2, "package": {"version": "2.2.0"}, "components": [], "inventory_summary": {"v1_top_level_modules": 0, "v1_public_source_trackable": 0, "v1_local_or_internal": 0, "v2_1_new_top_level_modules": 0, "v2_1_top_level_modules": 0, "top_level_modules": 0}}
            (root / "manifests/dependencies.json").write_text(json.dumps(manifest), encoding="utf-8")
            with mock.patch.object(MODULE, "ROOT", root):
                self.assertEqual(MODULE.validate_frontmatter(root / "SKILL.md"), [])
                self.assertEqual(MODULE.validate_manifest(), [])
            manifest["package"]["version"] = "2.1.0"
            (root / "manifests/dependencies.json").write_text(json.dumps(manifest), encoding="utf-8")
            with mock.patch.object(MODULE, "ROOT", root):
                self.assertTrue(MODULE.validate_manifest())


if __name__ == "__main__":
    unittest.main()
