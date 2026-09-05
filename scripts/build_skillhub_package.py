#!/usr/bin/env python3
"""Build a SkillHub-compatible archive without changing Codex SKILL.md."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PATHS = {".gitignore"}
EXCLUDED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pyc"}
GITHUB_ASSET_BASE = (
    "https://raw.githubusercontent.com/jlam00-dev/hardcore-director/"
    "v2.1.0/assets/"
)
SKILLHUB_FIELDS = (
    "slug: hardcore-director\n"
    "version: 2.1.0\n"
    "displayName: 硬核导演\n"
    "summary: 影视与 AI 视频创作总控，覆盖故事、分镜、模型提示词、声音、后期与发布验收。\n"
    "tags:\n"
    "  - video-production\n"
    "  - filmmaking\n"
    "  - ai-video\n"
    "  - storyboard\n"
    "  - screenwriting\n"
)


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    files = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = root / raw.decode("utf-8")
        relative = path.relative_to(root)
        if relative.as_posix() in EXCLUDED_PATHS:
            continue
        if relative.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return files


def skillhub_skill_md(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8")
    marker = "name: hardcore-director\n"
    if marker not in text:
        raise RuntimeError("SKILL.md does not contain the expected canonical name")
    if "\nslug: hardcore-director\n" in text:
        raise RuntimeError("canonical SKILL.md already contains SkillHub-only metadata")
    return text.replace(marker, marker + SKILLHUB_FIELDS, 1).encode("utf-8")


def skillhub_readme(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8")
    return text.replace('src="./assets/', f'src="{GITHUB_ASSET_BASE}').encode("utf-8")


def build(root: Path, output: Path) -> str:
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=root).returncode:
        raise RuntimeError("refusing to package a dirty tracked working tree")
    files = tracked_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(root)
            if relative.as_posix() == "SKILL.md":
                data = skillhub_skill_md(path)
            elif relative.as_posix() == "README.md":
                data = skillhub_readme(path)
            else:
                data = path.read_bytes()
            info = zipfile.ZipInfo(f"hardcore-director/{relative.as_posix()}")
            info.date_time = (2026, 9, 5, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            archive.writestr(info, data)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = build(args.source.resolve(), args.output.resolve())
    print(f"built {args.output.resolve()}")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
