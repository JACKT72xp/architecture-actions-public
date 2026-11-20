from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Pin a release Action to a verified GHCR image digest")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--version", required=True)
    arguments = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*/[a-z0-9][a-z0-9_.-]*", arguments.repository):
        parser.error("Expected a lowercase owner/repository")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", arguments.digest):
        parser.error("Expected an immutable SHA-256 image digest")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", arguments.version):
        parser.error("Expected a stable vMAJOR.MINOR.PATCH release")
    with Path("pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    if arguments.version != "v" + version:
        parser.error("Release version must match package metadata")
    path = Path("action.yml")
    manifest = yaml.safe_load(path.read_text())
    manifest["runs"]["image"] = f"docker://ghcr.io/{arguments.repository}@{arguments.digest}"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    main()
