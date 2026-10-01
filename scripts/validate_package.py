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
SKILLHUB_FRONTMATTER = {"slug", "version", "displayName", "summary", "tags"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
REQUIRED_COMPONENT_FIELDS = {
    "id",
    "role",
    "update_policy",
    "bundled_path",
    "sha256",
    "bundled_version",
    "license",
    "upstream",
}


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
    allowed = ALLOWED_FRONTMATTER
    if "slug: hardcore-director" in lines[1:end]:
        allowed = allowed | SKILLHUB_FRONTMATTER
    unknown = sorted(set(keys) - allowed)
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
    version_path = ROOT / "VERSION"
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    header = skill_text.split("---", 2)[1] if skill_text.startswith("---") else ""
    declared_versions = re.findall(r'^(?:  )?version:\s*["\']?([^"\'\r\n]+)', header, re.MULTILINE)
    if version_path.is_file():
        version = version_path.read_text(encoding="utf-8").strip()
    elif re.search(r"^slug:\s*hardcore-director\s*$", header, re.MULTILINE) and declared_versions:
        version = declared_versions[0].strip()
    else:
        return ["VERSION missing outside a SkillHub package"]
    if any(item.strip() != version for item in declared_versions):
        errors.append("SKILL.md version and package version differ")
    if manifest.get("schema_version") != 2:
        errors.append("dependency manifest schema_version must be 2")
    if manifest.get("package", {}).get("version") != version:
        errors.append("VERSION and dependency manifest version differ")
    components = manifest.get("components", [])
    if not isinstance(components, list):
        return [*errors, "dependency manifest components must be a list"]

    seen_ids = set()
    seen_paths = set()
    for item in components:
        missing_fields = sorted(REQUIRED_COMPONENT_FIELDS - set(item))
        if missing_fields:
            errors.append(
                f"manifest component {item.get('id', '<unknown>')} missing fields: "
                + ", ".join(missing_fields)
            )
        component_id = item.get("id")
        if not component_id:
            errors.append("manifest component has no id")
            continue
        if component_id in seen_ids:
            errors.append(f"duplicate component id: {component_id}")
        seen_ids.add(component_id)
        bundled_path = item.get("bundled_path", "")
        if bundled_path in seen_paths:
            errors.append(f"duplicate manifest path: {bundled_path}")
        seen_paths.add(bundled_path)
        local_path = ROOT / bundled_path
        if not local_path.is_file():
            errors.append(f"manifest path missing for {component_id}: {bundled_path}")
            continue
        actual = sha256_file(local_path)
        if actual != item.get("sha256"):
            errors.append(f"manifest hash mismatch for {component_id}")

    discovered_paths = {
        str(path.relative_to(ROOT))
        for pattern in ("references/*.md", "references/prompt-tools/*.md", "references/integrations/*.md")
        for path in ROOT.glob(pattern)
        if path.is_file()
    }
    missing_from_manifest = sorted(discovered_paths - seen_paths)
    extra_in_manifest = sorted(seen_paths - discovered_paths)
    for path in missing_from_manifest:
        errors.append(f"top-level module missing from manifest: {path}")
    for path in extra_in_manifest:
        errors.append(f"manifest component is not a top-level module: {path}")

    summary = manifest.get("inventory_summary", {})
    declared_total = summary.get("top_level_modules", summary.get("v2_1_top_level_modules"))
    if declared_total != len(discovered_paths):
        errors.append(
            "inventory_summary top_level_modules does not match discovered top-level modules"
        )
    if len(components) != len(discovered_paths):
        errors.append("manifest component count does not match discovered top-level modules")
    v2_1_total = summary.get("v2_1_top_level_modules")
    if summary.get("v1_top_level_modules", 0) + summary.get("v2_1_new_top_level_modules", 0) != v2_1_total:
        errors.append("inventory summary does not reconcile v1 modules plus v2.1 additions")
    if v2_1_total + summary.get("new_modules_since_v2_1", 0) != declared_total:
        errors.append("inventory summary does not reconcile v2.1 modules plus later additions")
    if summary.get("v1_public_source_trackable", 0) + summary.get("v1_local_or_internal", 0) != summary.get("v1_top_level_modules"):
        errors.append("inventory summary does not reconcile the v1 source categories")
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
    manifest = json.loads((ROOT / "manifests" / "dependencies.json").read_text(encoding="utf-8"))
    print(f"validation passed: frontmatter, links, {len(manifest['components'])}-module ledger, manifest hashes, and portability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
