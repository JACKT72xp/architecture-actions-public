from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from urllib.error import URLError

import jsonschema
import pytest

from arc42_tqi.config import InputError, load_config
from arc42_tqi.history import evolution
from arc42_tqi.integrations import NoRedirect, comment_pr, enrich, request_json


def run_git(root: Path, *args: str, day: int = 1) -> str:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                       GIT_AUTHOR_DATE=f"2026-01-{day:02d}T12:00:00+00:00",
                       GIT_COMMITTER_DATE=f"2026-01-{day:02d}T12:00:00+00:00")
    return subprocess.check_output(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args],
        env=environment, text=True, stderr=subprocess.DEVNULL,
    ).strip()


def test_history_requires_related_recent_evidence(tmp_path: Path) -> None:
    run_git(tmp_path, "init")
    config = load_config(tmp_path, None)["history"]
    config.update(hotspot_changes=3, coupling_min_support=2,
                  associations={"view.md": ["related.md"]})
    for day, names in enumerate([
        ["view.md", "related.md", "unrelated.md"],
        ["view.md", "related.md"], ["view.md"],
    ], 1):
        for name in names:
            with (tmp_path / name).open("a") as stream:
                stream.write(f"Change {day}\n")
        run_git(tmp_path, "add", ".")
        run_git(tmp_path, "commit", "-m", "Update evidence", day=day)
    args = (tmp_path, {"view.md"}, {"related.md", "unrelated.md"}, config)
    result = evolution(*args)
    assert result["status"] == "available"
    hotspot = result["hotspots"][0]
    assert not hotspot["aligned"]
    assert hotspot["commit_frequency"] == 1
    assert hotspot["staleness_days"] == 1
    assert hotspot["last_change"] == run_git(tmp_path, "rev-parse", "HEAD")
    assert hotspot["last_associated_change"] == run_git(tmp_path, "rev-parse", "HEAD~1")
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/tqi-report.schema.json").read_text())
    jsonschema.validate(result, schema["properties"]["history"])
    coupling = result["temporal_couplings"][0]
    assert coupling["target_file"] == "related.md"
    assert coupling["directed_ratio"] == pytest.approx(2 / 3)
    assert coupling["jaccard"] == pytest.approx(2 / 3)
    for day, name in [(4, "unrelated.md"), (5, "related.md")]:
        (tmp_path / name).write_text(f"Review {day}\n")
        run_git(tmp_path, "add", ".")
        run_git(tmp_path, "commit", "-m", "Review evidence", day=day)
        assert evolution(*args)["hotspots"][0]["aligned"] == (day == 5)
    assert evolution(*args) == evolution(*args)
    bounded = evolution(*args[:-1], {**config, "max_commits": 2})
    assert bounded["status"] == "truncated"
    assert bounded["commits_analyzed"] == 2
    limited = evolution(*args[:-1], {**config, "max_git_output_bytes": 1})
    assert limited["status"] == "unavailable"
    assert limited["hotspots"] == []


def test_shallow_history_is_unavailable(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    run_git(source, "init")
    run_git(source, "commit", "--allow-empty", "-m", "Initial")
    clone = tmp_path / "clone"
    run_git(tmp_path, "clone", "--depth", "1", source.as_uri(), str(clone))
    result = evolution(clone, set(), set(), load_config(clone, None)["history"])
    assert result["status"] == "shallow"
    assert result["hotspots"] == []
    assert "Shallow" in result["reason"]


def test_semantic_failures_and_secret_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise URLError("sensitive response text")

    monkeypatch.setattr("arc42_tqi.integrations.request_json", fail)
    result = enrich("http-json", "https://example.invalid", "model", "secret", {}, {})
    assert result["status"] == "unavailable"
    assert "sensitive" not in str(result)
    monkeypatch.setattr("arc42_tqi.integrations.request_json", lambda *args: {"observations": ["secret leaked"]})
    result = enrich("http-json", "https://example.invalid", "model", "secret", {}, {})
    assert result["observations"][0]["message"] == "[REDACTED] leaked"


@pytest.mark.parametrize("url", ["http://example.invalid", "file:///etc/passwd", "https://user:password@example.invalid"])
def test_endpoint_restrictions(url: str) -> None:
    with pytest.raises(InputError):
        request_json(url, "secret")


def test_redirects_rejected() -> None:
    with pytest.raises(InputError):
        NoRedirect().redirect_request(None, None, 302, "redirect", None, "https://elsewhere.invalid")


def test_pr_comment_skip_and_upsert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert comment_pr("body", "") == "skipped: no GitHub token"
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    event = {"number": 1, "repository": {"full_name": "owner/repo"}, "pull_request": {"head": {"repo": {"full_name": "fork/repo"}}}}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    assert comment_pr("body", "token") == "skipped: fork pull request"
    event["pull_request"]["head"]["repo"]["full_name"] = "owner/repo"
    event_path.write_text(json.dumps(event))
    calls = []

    def response(*args: object) -> object:
        calls.append(args)
        if len(args) == 2:
            return [{"id": 5, "user": {"login": "github-actions[bot]"}, "body": "<!-- arc42-tqi-action --> old"}]
        return {}

    monkeypatch.setattr("arc42_tqi.integrations.request_json", response)
    assert comment_pr("body", "token") == "updated"
    assert calls[-1][-1] == "PATCH"
    assert str(calls[-1][0]).endswith("/issues/comments/5")
