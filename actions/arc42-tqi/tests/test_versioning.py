from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import pytest

from arc42_tqi import __version__

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_metadata", ROOT / "scripts/release_metadata.py")
assert SPEC is not None and SPEC.loader is not None
METADATA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(METADATA)


def test_installed_version_and_release_notes_match_source() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert __version__ == version
    assert METADATA.release_notes(ROOT, "v" + version).strip()


@pytest.mark.parametrize("version", ["v9.9.9", "0.1.0", "v01.1.0", "v0.1.0;echo bad"])
def test_release_rejects_invalid_or_mismatched_versions(version: str) -> None:
    with pytest.raises(ValueError):
        METADATA.release_notes(ROOT, version)


def test_release_requires_nonempty_unique_changelog_entry(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
    for text in ("# Changelog", "## 0.1.0\n", "## 0.1.0\nFirst\n## 0.1.0\nSecond\n"):
        (tmp_path / "CHANGELOG.md").write_text(text)
        with pytest.raises(ValueError):
            METADATA.release_notes(tmp_path, "v0.1.0")
