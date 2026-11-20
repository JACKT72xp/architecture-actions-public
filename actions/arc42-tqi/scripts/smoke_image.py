"""Validate a local image offline without publishing or changing fixture sources."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import jsonschema
import yaml
from referencing import Registry, Resource


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--platform", choices=["linux/arm64", "linux/amd64"], required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    registry = Registry().with_resources(
        (path.name, Resource.from_contents(json.loads(path.read_text())))
        for path in (root / "schemas").glob("*.schema.json")
    )
    schema = json.loads((root / "schemas/tqi-report.schema.json").read_text())
    with tempfile.TemporaryDirectory(prefix="arc42-image-smoke-") as temporary:
        for fixture, expected_exit in (("mature", 0), ("poor", 1)):
            target = Path(temporary) / fixture
            shutil.copytree(root / "tests/fixtures" / fixture, target,
                            ignore=shutil.ignore_patterns(".arc42-tqi"))
            command = [
                "docker", "run", "--rm", "--network", "none", "--platform", args.platform,
                # Keep fixture artifacts owned by the test runner so Linux cleanup can remove them.
                # The separate action-smoke CI job exercises GitHub's default root Docker invocation.
                "--user", f"{os.getuid()}:{os.getgid()}",
                "-v", f"{target}:/github/workspace",
                "-e", "GITHUB_OUTPUT=/github/workspace/github-output",
                "-e", "GITHUB_STEP_SUMMARY=/github/workspace/github-summary",
                "-e", "ARC42_TQI_MIN_TQI=90", "-e", "ARC42_TQI_COMMENT_PR=false", args.image,
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            assert result.returncode == expected_exit, result.stderr
            destination = target / ".arc42-tqi"
            report = json.loads((destination / "tqi-report.json").read_text())
            jsonschema.Draft202012Validator(schema, registry=registry).validate(report)
            assert "Architecture quality report" in (destination / "human-report.md").read_text()
            assert "<!doctype html>" in (destination / "human-report.html").read_text()
            assert "human-report-html-path=.arc42-tqi/human-report.html" in (target / "github-output").read_text()
            claims = json.loads((destination / "claims.json").read_text())
            assert yaml.safe_load((destination / "claims.yaml").read_text()) == claims
            assert report["semantic_enrichment"]["status"] == "disabled"
            assert report["maturity_level"] == ("L4" if fixture == "mature" else "L1")
            for entry in report["prompt_manifest"]:
                assert (target / entry["path"]).is_file()
            assert "report-path=.arc42-tqi/tqi-report.json" in (target / "github-output").read_text()
            assert "Architecture Technical Quality Index" in (target / "github-summary").read_text()
            before = {path.relative_to(destination): path.read_bytes()
                      for path in destination.rglob("*") if path.is_file()}
            for path in destination.rglob("*"):
                if path.is_file():
                    assert path.stat().st_mode & 0o777 == 0o644
            repeated = subprocess.run(command, capture_output=True, text=True, check=False)
            assert repeated.returncode == expected_exit, repeated.stderr
            assert before == {path.relative_to(destination): path.read_bytes()
                              for path in destination.rglob("*") if path.is_file()}
            invalid = subprocess.run(command + ["--output-dir", "docs"], capture_output=True, text=True, check=False)
            assert invalid.returncode == 2, invalid.stderr
            print(f"{args.platform} {fixture}: {report['tqi_score']}/{report['maturity_level']}, "
                  f"exit {expected_exit}; schemas, outputs, permissions and repeatability pass")


if __name__ == "__main__":
    main()
