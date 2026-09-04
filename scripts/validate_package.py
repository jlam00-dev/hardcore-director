#!/usr/bin/env python3
"""Deterministic local validation for the packaged skill."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_FRONTMATTER = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_frontmatter(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return ["SKILL.md must begin with YAML frontmatter"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return ["SKILL.md frontmatter has no closing delimiter"]
    keys = []
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z0-9_-]+):", line)
        if match:
            keys.append(match.group(1))
    errors = []
    for required in ("name", "description"):
        if required not in keys:
            errors.append(f"frontmatter missing {required}")
    unknown = sorted(set(keys) - ALLOWED_FRONTMATTER)
    if unknown:
        errors.append(f"frontmatter has unsupported top-level keys: {', '.join(unknown)}")
    if "name: hardcore-director" not in "\n".join(lines[1:end]):
        errors.append("frontmatter name must be hardcore-director")
    return errors


def validate_links() -> list[str]:
    errors = []
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for raw in LINK_RE.findall(text):
            target = raw.strip().split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            target = target.split("?", 1)[0]
            if not (
                target.endswith((".md", ".png", ".jpg", ".jpeg", ".gif", ".json", ".yaml", ".yml"))
                or target.startswith(("./", "../", "references/", "assets/", "audits/", "manifests/"))
            ):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"broken link in {path.relative_to(ROOT)}: {raw}")
    return errors


def validate_manifest() -> list[str]:
    errors = []
    manifest_path = ROOT / "manifests" / "dependencies.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot parse dependency manifest: {exc}"]
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if manifest.get("package", {}).get("version") != version:
        errors.append("VERSION and dependency manifest version differ")
    seen = set()
    for item in manifest.get("components", []):
        component_id = item.get("id")
        if not component_id:
            errors.append("manifest component has no id")
            continue
        if component_id in seen:
            errors.append(f"duplicate component id: {component_id}")
        seen.add(component_id)
        local_path = ROOT / item.get("bundled_path", "")
        if not local_path.is_file():
            errors.append(f"manifest path missing for {component_id}: {item.get('bundled_path')}")
            continue
        actual = sha256_file(local_path)
        if actual != item.get("sha256"):
            errors.append(f"manifest hash mismatch for {component_id}")
    return errors


def validate_portability() -> list[str]:
    errors = []
    private_patterns = ("/Users/" + "lam/", "/Users/" + "baimengke/")
    for path in sorted(ROOT.rglob("*")):
        if (
            not path.is_file()
            or ".git" in path.parts
            or "__pycache__" in path.parts
            or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pyc"}
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in private_patterns:
            if pattern in text:
                errors.append(f"private absolute path {pattern} in {path.relative_to(ROOT)}")
    return errors


def main() -> int:
    errors = []
    errors.extend(validate_frontmatter(ROOT / "SKILL.md"))
    errors.extend(validate_links())
    errors.extend(validate_manifest())
    errors.extend(validate_portability())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"validation failed: {len(errors)} issue(s)")
        return 1
    print("validation passed: frontmatter, links, manifest hashes, and portability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
