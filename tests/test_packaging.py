from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SPEC = importlib.util.spec_from_file_location("packaging", Path(__file__).resolve().parents[1] / "scripts/build_skillhub_package.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class PackagingTests(unittest.TestCase):
    def test_skillhub_version_comes_from_requested_version(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "SKILL.md"
            original = "---\nname: hardcore-director\ndescription: test\n---\n"
            path.write_text(original, encoding="utf-8")
            adapted = MODULE.skillhub_skill_md(path, "2.2.0").decode()
            self.assertIn("\nversion: 2.2.0\n", adapted)
            self.assertIn("\nslug: hardcore-director\n", adapted)
            self.assertEqual(path.read_text(), original)

    @mock.patch.object(MODULE.subprocess, "run")
    def test_draft_includes_new_sources_but_skillhub_excludes_rejected_files(self, run):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("SKILL.md", "LICENSE", "LICENSE.md", "new.py", "asset.png", ".gitignore", "VERSION"):
                (root / name).write_text("sample", encoding="utf-8")
            run.return_value = mock.Mock(stdout=b"SKILL.md\0LICENSE\0LICENSE.md\0new.py\0asset.png\0.gitignore\0VERSION\0new.py\0")
            paths = MODULE.tracked_files(root, draft=True)
            self.assertEqual({path.name for path in paths}, {"SKILL.md", "LICENSE.md", "new.py"})
            self.assertIn("--others", run.call_args.args[0])
            self.assertEqual(len(paths), 3)
            codex = MODULE.tracked_files(root, draft=True, package_format="codex")
            self.assertEqual(len(codex), 7)

    def test_existing_archive_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "existing.zip"
            path.write_bytes(b"original")
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                MODULE.build(Path(temp), path, draft=True)
            self.assertEqual(path.read_bytes(), b"original")

    def test_skillhub_images_are_pinned_to_the_packaged_release(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "README.md"
            original = '<img src="./assets/hero.png" />'
            path.write_text(original, encoding="utf-8")
            adapted = MODULE.skillhub_readme(path, "2.2.0").decode()
            self.assertIn("/v2.2.0/assets/hero.png", adapted)
            self.assertEqual(path.read_text(), original)


if __name__ == "__main__":
    unittest.main()
