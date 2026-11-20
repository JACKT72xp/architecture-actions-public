from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def mature(tmp_path: Path) -> Path:
    source = Path(__file__).parent / "fixtures" / "mature"
    shutil.copytree(source, tmp_path, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".arc42-tqi"))
    # Existing mature contract tests exercise the published four-dimension rubric.
    (tmp_path / ".arc42-tqi.yml").write_text("review: {profile: extended}\n")
    return tmp_path


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    for key in list(os.environ):
        if key.startswith("INPUT_") or key.startswith("GITHUB_") or key.startswith("ARC42_TQI_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("arc42_tqi.analyzer.metadata", lambda root: {
        "commit": None, "repository": None, "tracked_worktree_dirty": None,
        "shallow_clone": None, "git_available": False, "head_commit_time": None,
    })
    monkeypatch.setattr("arc42_tqi.analyzer.evolution", lambda *args: {
        "status": "unavailable", "reason": "Fixture history unavailable", "hotspots": [],
        "temporal_couplings": [], "commits_analyzed": 0,
        "window_oldest_commit": None, "window_newest_commit": None,
    })
