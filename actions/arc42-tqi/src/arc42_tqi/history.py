from __future__ import annotations

import json
import os
import re
import selectors
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class GitLimitError(RuntimeError):
    pass


def git(root: Path, *arguments: str, timeout: int = 5, max_bytes: int = 8_388_608) -> str:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    command = ["git", "-c", f"safe.directory={root.resolve()}", "-c", "core.fsmonitor=false",
               "-c", "core.hooksPath=/dev/null", "-c", "core.excludesFile=/dev/null",
               "-c", "core.quotePath=false", "-C", str(root), *arguments]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment) as process:
        assert process.stdout is not None
        deadline = time.monotonic() + timeout
        chunks: list[bytes] = []
        size = 0
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise subprocess.TimeoutExpired(command, timeout)
                    chunk = os.read(process.stdout.fileno(), min(65536, max_bytes - size + 1))
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise GitLimitError("Git output exceeded configured byte limit")
                    chunks.append(chunk)
                process.wait(timeout=max(0.001, deadline - time.monotonic()))
                if process.returncode:
                    raise subprocess.CalledProcessError(process.returncode, command)
            except BaseException:
                process.kill()
                process.wait()
                raise
        return b"".join(chunks).decode("utf-8", errors="replace")


def iso_time(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def is_checkout(root: Path) -> bool:
    return any((path / ".git").exists() for path in (root, *root.parents))


def metadata(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"repository": os.environ.get("GITHUB_REPOSITORY"), "commit": None,
                              "shallow_clone": None, "git_available": False,
                              "tracked_worktree_dirty": None, "head_commit_time": None}
    if not is_checkout(root):
        return result
    try:
        result["shallow_clone"] = git(root, "rev-parse", "--is-shallow-repository").strip() == "true"
        result["git_available"] = True
        commit, timestamp = git(root, "show", "-s", "--format=%H%n%ct", "HEAD").strip().splitlines()
        result["commit"], result["head_commit_time"] = commit, iso_time(int(timestamp))
        result["tracked_worktree_dirty"] = bool(git(root, "status", "--porcelain", "--untracked-files=no").strip())
    except (OSError, ValueError, GitLimitError, subprocess.SubprocessError):
        pass
    return result


def evolution(root: Path, files: set[str], supporting_files: set[str], config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "disabled", "reason": "Git history disabled", "hotspots": [],
                              "temporal_couplings": [], "commits_analyzed": 0,
                              "window_oldest_commit": None, "window_newest_commit": None}
    if not config["enabled"]:
        return result
    if not is_checkout(root):
        result.update(status="unavailable", reason="No Git checkout found; evolutionary metrics are not applicable.")
        return result
    options = {"timeout": config["timeout_seconds"], "max_bytes": config.get("max_git_output_bytes", 8_388_608)}
    try:
        if git(root, "rev-parse", "--is-shallow-repository", **options).strip() == "true":
            result.update(status="shallow", reason="Shallow clone: configure actions/checkout@v4 with fetch-depth: 0.")
            return result
        head_time = int(git(root, "show", "-s", "--format=%ct", "HEAD", **options).strip())
        raw = git(root, "log", f"-{config['max_commits'] + 1}", "--no-merges", "--no-renames",
                  "--no-ext-diff", "--no-textconv", "--root", "--format=%x00TQI-COMMIT%x00%H%x00%ct%x00",
                  "--raw", "-z", "HEAD", "--", **options)
        commits: list[tuple[str, int, set[str]]] = []
        tokens = iter(raw.split("\0"))
        for token in tokens:
            marker = token.lstrip("\n")
            if not marker:
                continue
            if marker == "TQI-COMMIT":
                identifier, timestamp = next(tokens), next(tokens)
                if not re.fullmatch(r"[a-f0-9]{40}(?:[a-f0-9]{24})?", identifier):
                    raise ValueError("Malformed Git commit record")
                commits.append((identifier, int(timestamp), set()))
            elif marker.startswith(":") and commits:
                commits[-1][2].add(next(tokens))
            else:
                raise ValueError("Malformed Git raw change record")
        truncated = len(commits) > config["max_commits"]
        commits = commits[:config["max_commits"]]
        result["commits_analyzed"] = len(commits)
        if len(commits) < 2:
            result.update(status="insufficient_history", reason="At least two non-merge commits are required.")
            return result
        result.update(status="truncated" if truncated else "available",
                      reason="Analysis uses the configured bounded commit window." if truncated else None,
                      window_newest_commit=commits[0][0], window_oldest_commit=commits[-1][0])
        relevant = files | supporting_files
        changes = {file: {index for index, (_, _, touched) in enumerate(commits) if file in touched}
                   for file in sorted(relevant)}
        associations = config.get("associations", {})
        for file in sorted(files):
            revisions = changes[file]
            if len(revisions) < config["hotspot_changes"]:
                continue
            latest = min(revisions)
            related = sorted((set(associations.get(file, [])) & supporting_files) - {file})
            evidence_indices = set().union(*(changes[support] for support in related)) if related else set()
            last_support = min(evidence_indices) if evidence_indices else None
            reviews = config.get("reviewed_against", {})
            reviewed = [support for support in related if commits[latest][0] in reviews.get(support, [])]
            aligned = last_support is not None and last_support <= latest
            staleness = None if last_support is None else max(0, head_time - commits[last_support][1]) / 86400
            if not aligned and reviewed and staleness is not None:
                aligned = staleness <= config["stale_after_days"]
            result["hotspots"].append({
                "file": file, "section_ids": sorted(config.get("section_ids", {}).get(file, [])),
                "changes": len(revisions), "commit_frequency": len(revisions) / len(commits),
                "last_change": commits[latest][0], "associated_files": related,
                "last_associated_change": commits[last_support][0] if last_support is not None else None,
                "staleness_days": staleness, "aligned": aligned,
                "alignment_evidence": sorted(set(reviewed + [
                    support for support in related if any(index <= latest for index in changes[support])
                ])) if aligned else [],
            })
        masks = {file: sum(1 << index for index in revisions) for file, revisions in changes.items()}
        coupling_bytes = 0
        eligible = {file for file in relevant if len(changes[file]) >= config["coupling_min_support"]}
        for source in sorted(files & eligible):
            source_changes = changes[source]
            if len(source_changes) < config["coupling_min_support"]:
                continue
            for target in sorted(eligible - {source}):
                target_changes = changes[target]
                cochanges = (masks[source] & masks[target]).bit_count()
                ratio = cochanges / len(source_changes)
                if cochanges < config["coupling_min_support"] or ratio < config["coupling_threshold"]:
                    continue
                coupling = {
                    "source_file": source, "target_file": target, "source_changes": len(source_changes),
                    "target_changes": len(target_changes), "cochanges": cochanges, "directed_ratio": ratio,
                    "jaccard": cochanges / (len(source_changes) + len(target_changes) - cochanges),
                    "association_declared": target in associations.get(source, []),
                }
                coupling_bytes += len(json.dumps(coupling, ensure_ascii=False).encode())
                if coupling_bytes > options["max_bytes"]:
                    raise GitLimitError("Temporal coupling output exceeds configured Git byte limit")
                result["temporal_couplings"].append(coupling)
    except (OSError, ValueError, StopIteration, GitLimitError, subprocess.SubprocessError):
        result.update(status="unavailable", reason="Git history unavailable, unsafe, over budget, or timed out.",
                      hotspots=[], temporal_couplings=[])
    return result
