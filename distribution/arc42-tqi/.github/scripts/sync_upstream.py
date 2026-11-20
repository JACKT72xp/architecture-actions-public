"""Export a committed upstream subtree; never execute code from the source checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

UPSTREAM = "https://github.com/JACKT72xp/architecture-actions-public"
PREFIX = "actions/arc42-tqi/"
TARGET = "JACKT72xp/arc42-tqi-action"
TEMPLATE_PREFIX = "distribution/arc42-tqi/"
DESTINATION = Path(__file__).resolve().parents[2]


def git(source: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(source), *args])


def exported(source: Path, revision: str) -> dict[str, bytes]:
    result = {}
    listing = git(source, "ls-tree", "-rz", revision, "--", PREFIX)
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, object_id = metadata.decode().split()
        relative = raw_path.decode().removeprefix(PREFIX)
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Unsafe upstream path")
        if path.parts[0] == "design" or relative == "scripts/prepare_release.py":
            continue
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError(f"Unsupported upstream entry: {relative}")
        if path.parts[0] == ".github" or relative in {"UPSTREAM.json", "DISTRIBUTION.md", ".gitignore"}:
            raise ValueError(f"Upstream collides with distribution-owned file: {relative}")
        content = git(source, "cat-file", "blob", object_id)
        if relative == "README.md":
            text = content.decode()
            start = text.index("Replace `COMMIT_SHA` below")
            end = text.index("```yaml", start)
            text = text[:start] + (
                "Replace `COMMIT_SHA` below with a reviewed full commit SHA from this\n"
                "distribution repository. The Docker Action requires a Linux runner and\n"
                "builds its bundled Dockerfile; no GHCR credentials are needed.\n\n"
            ) + text[end:]
            text = text.replace("JACKT72xp/architecture-actions-public/actions/arc42-tqi@", TARGET + "@")
            text = text.replace("../../README.md", UPSTREAM + "#readme")
            notice = (
                "\n> **Marketplace distribution repository.** Development, issues and pull requests\n"
                f"> belong in [{UPSTREAM.removeprefix('https://github.com/')}]({UPSTREAM}).\n"
                "> The analyzer is synchronized from `actions/arc42-tqi/`; do not edit generated files here.\n"
                "> See [distribution and release instructions](DISTRIBUTION.md) and [source provenance](UPSTREAM.json).\n\n"
            )
            layout = text.index("## Repository layout")
            text = text[:layout] + (
                "## Repository layout\n\n"
                "This repository contains the exported Action at its root. Run validation\n"
                "commands here; submit analyzer changes to `actions/arc42-tqi/` upstream.\n"
                "Workflows live in `.github/workflows/`; release tags use `vMAJOR.MINOR.PATCH`.\n"
                "See [DISTRIBUTION.md](DISTRIBUTION.md) for synchronization and Marketplace publication.\n"
            )
            first, rest = text.split("\n", 1)
            content = (first + "\n" + notice + rest).encode()
        elif relative == "CONTRIBUTING.md":
            content = (
                "# Contributing\n\n"
                f"Submit code changes and issues to [{UPSTREAM}]({UPSTREAM}).\n"
                "Change `actions/arc42-tqi/` there. Maintainers review, merge and test changes\n"
                "upstream before synchronizing this repository. Direct analyzer changes here\n"
                "will fail the source verification check and can be overwritten by synchronization.\n\n"
                "Distribution workflow changes also belong upstream, under `distribution/arc42-tqi/`.\n\n"
                f"[Upstream contribution guide]({UPSTREAM}/blob/main/actions/arc42-tqi/CONTRIBUTING.md).\n"
            ).encode()
        elif relative == "docs/releasing.md":
            content = (
                "# Releasing this distribution\n\n"
                "Follow [the distribution release guide](../DISTRIBUTION.md).\n"
                "All release changes are reviewed upstream before synchronizing this distribution.\n"
            ).encode()
        elif relative in {"docs/phase-2.md", "docs/phase-3.md", "docs/architecture.md"}:
            content = (
                "> **Upstream design/history document.** Packaging and GHCR release references\n"
                "> describe the monorepo. This distribution builds its root Dockerfile and uses\n"
                "> [its own release process](../DISTRIBUTION.md).\n\n"
            ).encode() + content
        elif relative == "examples/architecture-quality.yml":
            content = content.replace(b"JACKT72xp/architecture-actions-public/actions/arc42-tqi@", (TARGET + "@").encode())
        result[relative] = content
    if not {"action.yml", "Dockerfile", "LICENSE", "src/arc42_tqi/cli.py"} <= result.keys():
        raise ValueError("The selected revision does not contain a complete Action")
    templates = git(source, "ls-tree", "-rz", revision, "--", TEMPLATE_PREFIX)
    if not templates:
        raise ValueError("Source revision has no canonical distribution configuration")
    for entry in templates.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, object_id = metadata.decode().split()
        relative = raw_path.decode().removeprefix(TEMPLATE_PREFIX)
        target_path(relative)
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError(f"Unsupported template entry: {relative}")
        if relative in result or relative == "UPSTREAM.json":
            raise ValueError(f"Template collides with analyzer file: {relative}")
        result[relative] = git(source, "cat-file", "blob", object_id)
    return result


def target_path(relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or ".git" in path.parts:
        raise ValueError("Unsafe managed path")
    target = DESTINATION / path
    if target.resolve() != target.absolute():
        raise ValueError(f"Managed paths cannot traverse symlinks: {relative}")
    return target


def main() -> None:
    global DESTINATION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--ref", help="Full upstream commit SHA; defaults to recorded provenance")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--destination", type=Path, default=DESTINATION)
    args = parser.parse_args()
    DESTINATION = args.destination.resolve()
    if DESTINATION == args.source.resolve():
        parser.error("Destination must be separate from source")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest_path = DESTINATION / "UPSTREAM.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    revision = args.ref or previous.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        parser.error("A full upstream commit SHA is required")
    resolved = git(args.source, "rev-parse", revision + "^{commit}").decode().strip()
    if resolved != revision:
        parser.error("Source must identify a commit")
    files = exported(args.source, revision)
    manifest = {
        "repository": UPSTREAM, "commit": revision, "subdirectory": PREFIX.rstrip("/"),
        "export_format": 2, "distribution_subdirectory": TEMPLATE_PREFIX.rstrip("/"),
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())},
    }
    serialized = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        mismatches = [name for name, content in files.items()
                      if not target_path(name).is_file() or target_path(name).read_bytes() != content]
        # Reject tracked additions to the distributed code as well as modifications/deletions.
        if (DESTINATION / ".git").exists():
            tracked = git(DESTINATION, "ls-files", "-z").decode().split("\0")
            mismatches.extend(name for name in tracked if name and name not in files and name != "UPSTREAM.json"
                              and target_path(name).exists())
        if not manifest_path.exists() or manifest_path.read_bytes() != serialized:
            mismatches.append("UPSTREAM.json")
        if mismatches:
            raise SystemExit("Distribution differs from upstream export: " + ", ".join(sorted(set(mismatches))))
        print(f"Verified {len(files)} files from {revision}")
        return
    for name in previous.get("files", {}):
        if name not in files:
            target_path(name).unlink(missing_ok=True)
    for name, content in files.items():
        destination = target_path(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    manifest_path.write_bytes(serialized)
    print(f"Exported {len(files)} files from {revision}")


if __name__ == "__main__":
    main()
