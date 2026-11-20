from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest
import yaml
from referencing import Registry, Resource

from arc42_tqi.analyzer import analyze_repository
from arc42_tqi.cli import main
from arc42_tqi.config import InputError, load_config
from arc42_tqi.exporters import summary
from arc42_tqi.human_report import human_report


def test_arc42_scope_excludes_volatility_and_claim_gates(mature: Path) -> None:
    report, claims = analyze_repository(mature, review_overrides={"profile": "arc42"}, fail_on_severity="high")
    assert report["scoring_version"] == "2.0"
    assert report["tqi_score"] == 100
    assert report["quality_gate"]["passed"]  # standard review gaps are medium, not high
    for name in ("volatility", "drift"):
        assert report["dimensions"][name]["weight"] == 0
        assert all(metric["status"] == "not_applicable" for metric in report["dimensions"][name]["metrics"].values())
    assert not any(item["dimension"] in {"volatility", "drift"} for item in report["findings"])
    assert report["effective_config"]["history"]["enabled"] is False
    markdown = human_report(report, claims)
    assert "### Readiness for change" not in markdown
    assert "### Readiness for conformance audits" not in markdown
    assert "Completion criteria" in markdown
    assert "evidence needs review" in markdown


@pytest.mark.parametrize("purpose,expected", [
    ("strategic", {"strategic_intent", "target_state"}),
    ("tactical", {"tactical_scope"}),
    ("transition", {"current_state", "target_state", "migration_plan", "rollback"}),
])
def test_depth_and_architecture_purpose(mature: Path, purpose: str, expected: set[str]) -> None:
    report, _ = analyze_repository(mature, review_overrides={
        "profile": "arc42", "architecture_type": purpose, "c4_level": "container", "deployment_view": "not-required",
    })
    assert {check["id"] for check in report["architecture_review"]["checks"]} == {"context", "container"} | expected
    assert all(check["status"] == "unknown" for check in report["architecture_review"]["checks"])


def test_rigor_changes_gate_not_score(mature: Path) -> None:
    reports = [analyze_repository(mature, fail_on_severity="high", review_overrides={"profile": "arc42", "rigor": rigor})[0]
               for rigor in ("advisory", "standard", "strict")]
    assert [report["tqi_score"] for report in reports] == [100, 100, 100]
    assert [report["quality_gate"]["passed"] for report in reports] == [True, True, False]
    assert [{item["severity"] for item in report["findings"]} for report in reports] == [{"low"}, {"medium"}, {"high"}]


def test_evidence_is_scoped_validated_and_not_semantic_certification(mature: Path) -> None:
    path = mature / "docs/review.md"
    path.write_text("The delivery scope includes order placement and excludes financial reconciliation.\n")
    valid = {"file": "docs/review.md", "line": 1, "end_line": 1}
    config = {"review": {"profile": "arc42", "c4_level": "context", "deployment_view": "not-required",
                         "evidence": {"context": [valid], "tactical_scope": [dict(valid)]}}}
    (mature / ".arc42-tqi.yml").write_text(yaml.safe_dump(config))
    report, _ = analyze_repository(mature)
    checks = report["architecture_review"]["checks"]
    assert all(check["status"] == "evidence_available" for check in checks)
    assert report["architecture_review"]["status"] == "review_required"
    assert checks[0]["sources"][0]["evidence_level"] == "declared"
    assert len(checks[0]["sources"][0]["sha256"]) == 64
    for source in ({**valid, "file": "../../outside.md"}, {**valid, "end_line": 50}):
        changed = copy.deepcopy(config)
        changed["review"]["evidence"]["context"] = [source]
        (mature / ".arc42-tqi.yml").write_text(yaml.safe_dump(changed))
        report, _ = analyze_repository(mature)
        assert report["architecture_review"]["checks"][0]["status"] == "unknown"
        assert report["architecture_review"]["checks"][0]["rejected_sources"]
    path.write_text("TODO fill in the architecture\n")
    (mature / ".arc42-tqi.yml").write_text(yaml.safe_dump(config))
    assert analyze_repository(mature)[0]["architecture_review"]["checks"][0]["status"] == "unknown"


@pytest.mark.parametrize("override", [
    "review: {profile: invalid}", "review: {rigor: maximum}", "review: {c4_level: code}",
    "review: {architecture_type: auto}", "review: {deployment_view: true}", "review: []",
    "review: {evidence: {context: [{file: x, line: 3, end_line: 1}]}}",
    "review: {evidence: {context: [{file: x, line: 1, end_line: 201}]}}",
    "weights: {volatility: 10}", "history: {enabled: true}",
])
def test_invalid_review_configuration(tmp_path: Path, override: str) -> None:
    (tmp_path / ".arc42-tqi.yml").write_text(override)
    with pytest.raises(InputError):
        load_config(tmp_path, None)


def test_cli_inputs_override_file_and_summary_keeps_all_findings(mature: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARC42_TQI_REVIEW_PROFILE", "arc42")
    monkeypatch.setenv("ARC42_TQI_REVIEW_RIGOR", "strict")
    monkeypatch.setenv("ARC42_TQI_ARCHITECTURE_TYPE", "transition")
    monkeypatch.setenv("ARC42_TQI_C4_LEVEL", "component")
    monkeypatch.setenv("ARC42_TQI_DEPLOYMENT_VIEW", "required")
    assert main(["--repo-root", str(mature), "--fail-on-severity", "high"]) == 1
    assert (mature / ".arc42-tqi/human-report.html").exists()
    generated = json.loads((mature / ".arc42-tqi/tqi-report.json").read_text())
    schemas = Path(__file__).resolve().parents[1] / "schemas"
    registry = Registry().with_resources((path.name, Resource.from_contents(json.loads(path.read_text())))
                                         for path in schemas.glob("*.schema.json"))
    jsonschema.Draft202012Validator(json.loads((schemas / "tqi-report.schema.json").read_text()), registry=registry).validate(generated)
    assert generated["schema_version"] == "1.1"
    report, claims = analyze_repository(mature, review_overrides={"profile": "arc42", "architecture_type": "transition"})
    rendered = summary(report, "out")
    detailed = human_report(report, claims)
    for item in report["findings"]:
        assert item["rule_id"].replace("_", "\\_") in rendered
        assert item["id"] in detailed
    assert "Rollback and transition risks" in detailed
    assert "Code-level diagrams are not required" in detailed


def test_shipped_repository_configuration_supports_both_profiles() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root, ".arc42-tqi.yml")
    assert config["weights"] == {"structure": 50, "decisions": 50, "volatility": 0, "drift": 0}
    assert config["history"]["enabled"] is False
    legacy = load_config(root, ".arc42-tqi.yml", {"profile": "extended"})
    assert all(weight == 25 for weight in legacy["weights"].values())
    assert legacy["history"]["enabled"] is True
