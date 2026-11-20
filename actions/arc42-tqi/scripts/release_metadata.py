"""Validate a release version and extract its reviewed upstream changelog entry."""
from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path


def release_notes(root: Path, version: str) -> str:
    if not re.fullmatch(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise ValueError("Expected a stable vMAJOR.MINOR.PATCH version")
    package = tomllib.loads((root / "pyproject.toml").read_text())
    if version != "v" + package["project"]["version"]:
        raise ValueError("Release version must match pyproject.toml")
    changelog = (root / "CHANGELOG.md").read_text()
    headings = list(re.finditer(r"(?m)^## (\S+)\s*$", changelog))
    matches = [index for index, match in enumerate(headings) if match[1] == version[1:]]
    if len(matches) != 1:
        raise ValueError("Changelog must contain exactly one entry for the release")
    index = matches[0]
    end = headings[index + 1].start() if index + 1 < len(headings) else len(changelog)
    notes = changelog[headings[index].end():end].strip()
    if not notes:
        raise ValueError("Release notes must not be empty")
    return notes + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(release_notes(Path(__file__).resolve().parents[1], args.version), end="")


if __name__ == "__main__":
    main()
