#!/usr/bin/env python3
"""Read-only update and integrity checker for hardcore-director v2.1."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "manifests" / "dependencies.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("schema_version") != 1 or not isinstance(data.get("components"), list):
        raise ValueError("unsupported or malformed dependency manifest")
    return data


def http_text(url: str, *, accept: str = "application/json") -> str:
    headers = {
        "Accept": accept,
        "User-Agent": "hardcore-director-update-check/2.1",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def latest_github_path_commit(upstream: dict[str, Any]) -> str:
    repo = upstream["repo"]
    path = urllib.parse.quote(upstream["path"], safe="")
    ref = urllib.parse.quote(upstream.get("ref", "main"), safe="")
    url = f"https://api.github.com/repos/{repo}/commits?path={path}&sha={ref}&per_page=1"
    payload = json.loads(http_text(url))
    if not payload:
        raise RuntimeError(f"GitHub returned no commits for {repo}:{upstream['path']}")
    return payload[0]["sha"]


def inspect_clawhub(skill_ref: str) -> str:
    if not shutil.which("npx"):
        raise RuntimeError("npx is required for ClawHub checks")
    result = subprocess.run(
        ["npx", "-y", "clawhub@latest", "inspect", skill_ref, "--json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"ClawHub inspect failed: {detail}")
    start = result.stdout.find("{")
    if start < 0:
        raise RuntimeError("ClawHub did not return JSON")
    payload = json.loads(result.stdout[start:])
    version = payload.get("latestVersion", {}).get("version")
    if not version:
        raise RuntimeError("ClawHub response has no latest version")
    return str(version)


def inspect_web_pattern(upstream: dict[str, Any]) -> str:
    page = http_text(upstream["url"], accept="text/html,*/*")
    match = re.search(upstream["pattern"], page)
    if not match:
        raise RuntimeError("configured pattern was not found in the upstream page")
    return match.group(1)


def check_component(
    component: dict[str, Any], *, root: Path, offline: bool
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": component["id"],
        "local": "ok",
        "upstream": "skipped" if offline else "unknown",
        "details": [],
    }
    local_path = root / component["bundled_path"]
    if not local_path.is_file():
        result["local"] = "missing"
        result["details"].append(f"missing {component['bundled_path']}")
    else:
        actual_hash = sha256_file(local_path)
        result["actual_sha256"] = actual_hash
        if actual_hash != component["sha256"]:
            result["local"] = "drift"
            result["details"].append("local SHA-256 differs from manifest")

    if offline:
        return result

    upstream = component.get("upstream", {})
    kind = upstream.get("kind")
    try:
        if kind == "clawhub":
            latest = inspect_clawhub(upstream["ref"])
            expected = str(component["bundled_version"])
        elif kind == "github_path":
            latest = latest_github_path_commit(upstream)
            expected = upstream["pinned_commit"]
        elif kind == "web_pattern":
            latest = inspect_web_pattern(upstream)
            expected = upstream["pinned_value"]
        else:
            result["upstream"] = "skipped"
            result["details"].append(f"unsupported upstream kind: {kind!r}")
            return result
        result["latest"] = latest
        result["expected"] = expected
        if latest == expected:
            result["upstream"] = "current"
        else:
            result["upstream"] = "update_available"
            result["details"].append(f"pinned {expected}, latest {latest}")
    except Exception as exc:  # network and registry failures must remain visible
        result["upstream"] = "error"
        result["details"].append(str(exc))
    return result


def summarize(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "checked": len(results),
        "local_issues": sum(item["local"] != "ok" for item in results),
        "updates": sum(item["upstream"] == "update_available" for item in results),
        "errors": sum(item["upstream"] == "error" for item in results),
    }


def exit_code(summary: dict[str, int]) -> int:
    if summary["errors"]:
        return 2
    if summary["local_issues"] or summary["updates"]:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check bundled hashes and optional GitHub/ClawHub/Web updates without changing files."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--offline", action="store_true", help="Only verify local integrity")
    parser.add_argument("--only", action="append", default=[], help="Check one component id; repeatable")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    manifest_path = args.manifest.resolve()
    root = manifest_path.parents[1]
    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    selected = manifest["components"]
    if args.only:
        wanted = set(args.only)
        selected = [item for item in selected if item["id"] in wanted]
        missing = wanted - {item["id"] for item in selected}
        if missing:
            print(f"ERROR: unknown component(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 2

    results = [check_component(item, root=root, offline=args.offline) for item in selected]
    summary = summarize(results)
    payload = {"package": manifest["package"], "offline": args.offline, "summary": summary, "results": results}

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in results:
            print(f"{item['id']}: local={item['local']} upstream={item['upstream']}")
            for detail in item["details"]:
                print(f"  - {detail}")
        print(
            "summary: "
            f"checked={summary['checked']} local_issues={summary['local_issues']} "
            f"updates={summary['updates']} errors={summary['errors']}"
        )
    return exit_code(summary)


if __name__ == "__main__":
    raise SystemExit(main())
