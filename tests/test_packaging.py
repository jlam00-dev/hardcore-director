from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from zipfile import ZipFile


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
            original = (
                '<img src="./assets/hero.png" />\n'
                "![硬仔](./assets/hardzai.png)\n"
                "[下载海报](assets/poster.png)\n"
                "<a href='assets/icon.png'>Icon</a>\n"
                "[安装指南](references/support/user-guide.md)\n"
            )
            path.write_text(original, encoding="utf-8")
            adapted = MODULE.skillhub_readme(path, "2.2.0").decode()
            base = "https://raw.githubusercontent.com/jlam00-dev/hardcore-director/v2.2.0/assets/"
            self.assertEqual(adapted, original.replace("./assets/", "assets/").replace("assets/", base))
            self.assertEqual(path.read_text(), original)

    @mock.patch.object(MODULE.subprocess, "run")
    def test_only_skillhub_archive_removes_icons_it_does_not_bundle(self, run):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            metadata = (
                'interface:\n  display_name: "硬核导演"\n'
                '  icon_small: "./assets/icon.png"\n'
                "  icon_large: 'assets/hero.jpg' # release artwork\n"
                '  default_prompt: "使用 $hardcore-director"\n'
            )
            files = {
                "VERSION": b"3.0.0\n",
                "agents/openai.yaml": metadata.encode(),
                "assets/icon.png": b"icon",
                "assets/hero.jpg": b"hero",
            }
            for name, data in files.items():
                path = root / name
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(data)
            run.return_value = mock.Mock(returncode=0, stdout=b"\0".join(name.encode() for name in files))
            for package_format in ("skillhub", "codex"):
                output = root / f"{package_format}.zip"
                MODULE.build(root, output, draft=True, package_format=package_format)
                with ZipFile(output) as archive:
                    adapted = archive.read("hardcore-director/agents/openai.yaml").decode()
                    if package_format == "skillhub":
                        self.assertEqual(adapted, 'interface:\n  display_name: "硬核导演"\n  default_prompt: "使用 $hardcore-director"\n')
                        self.assertNotIn("hardcore-director/assets/icon.png", archive.namelist())
                        self.assertNotIn("hardcore-director/assets/hero.jpg", archive.namelist())
                    else:
                        self.assertEqual(adapted, metadata)
                        self.assertEqual(archive.read("hardcore-director/assets/icon.png"), b"icon")
                        self.assertEqual(archive.read("hardcore-director/assets/hero.jpg"), b"hero")
            self.assertEqual((root / "agents/openai.yaml").read_text(), metadata)


if __name__ == "__main__":
    unittest.main()
