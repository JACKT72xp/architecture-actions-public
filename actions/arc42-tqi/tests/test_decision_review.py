import json
from pathlib import Path

import jsonschema
import pytest

from arc42_tqi.analyzer import analyze_repository
from arc42_tqi.decision_review import declared_sections
from arc42_tqi.human_report import human_report, human_summary

COMPROMISE = """
## Strategic alignment
The order service remains the target owner, as described in section 4.
## Tactical exception
A supplier deadline requires a temporary shared database adapter.
## Transition plan
Introduce the service API, migrate clients, then remove the adapter.
## Review condition
The service owner reviews this decision when the supplier API is available.
## Exit criteria
All clients use the service API and no shared database credentials remain.
## Rollback and recovery
Restore the previous client routing if reconciliation detects missing orders.
"""


def append_decision(mature: Path, text: str) -> Path:
    path = sorted((mature / "docs/adr").glob("*.md"))[0]
    path.write_text(path.read_text() + text)
    return path


def test_mixed_exceptions_preserve_score_and_cite_sources(mature: Path) -> None:
    before, _ = analyze_repository(mature, review_overrides={"profile": "arc42"})
    path = append_decision(mature, COMPROMISE)
    report, claims = analyze_repository(mature, review_overrides={"profile": "arc42"})
    decision = report["architecture_review"]["decision_assessments"][0]
    assert decision["declared_exceptions"] == ["tactical", "transition"]
    assert decision["status"] == "evidence_available"
    assert not decision["missing_evidence"]
    assert report["tqi_score"] == before["tqi_score"]
    for sources in decision["evidence"].values():
        for source in sources:
            assert source["excerpt"] == "\n".join(path.read_text().splitlines()[source["line"] - 1:source["end_line"]]).strip()
            assert len(source["sha256"]) == 64
    assert "1 active ADRs declare tactical exceptions" in human_summary(report)
    assert decision["adr_id"] in human_report(report, claims)
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/tqi-report.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema["properties"]["architecture_review"])
    assert [error.message for error in validator.iter_errors(json.loads(json.dumps(report["architecture_review"])))] == []



@pytest.mark.parametrize("rigor,severity", [("advisory", "low"), ("standard", "medium"), ("strict", "high")])
def test_incomplete_exception_creates_evidence_finding(mature: Path, rigor: str, severity: str) -> None:
    append_decision(mature, "\n## Tactical exception\nSupplier deadline prevents the target implementation.\n")
    report, _ = analyze_repository(mature, review_overrides={"profile": "arc42", "rigor": rigor})
    decision = report["architecture_review"]["decision_assessments"][0]
    assert decision["missing_evidence"] == ["Strategic alignment", "Review condition"]
    findings = [item for item in report["findings"] if item["rule_id"] == "REVIEW_DECISION_EXCEPTION"]
    assert len(findings) == 1
    assert findings[0]["severity"] == severity
    assert decision["adr_id"] in findings[0]["remediation"]


def test_ambiguous_prose_does_not_infer_exception_or_alignment(mature: Path) -> None:
    append_decision(mature, "\nWe discussed tactical alternatives and transition risks but did not select them.\n")
    report, _ = analyze_repository(mature, review_overrides={"profile": "arc42"})
    assert all(not item["declared_exceptions"] and item["status"] == "unknown"
               for item in report["architecture_review"]["decision_assessments"])
    assert not any(item["rule_id"] == "REVIEW_DECISION_EXCEPTION" for item in report["findings"])


def test_historical_exceptions_are_visible_without_new_findings(mature: Path) -> None:
    path = append_decision(mature, "\n## Tactical exception\nTemporary supplier integration.\n")
    path.write_text(path.read_text().replace("status: accepted", "status: deprecated"))
    report, _ = analyze_repository(mature, review_overrides={"profile": "arc42"})
    assert report["architecture_review"]["decision_assessments"][0]["status"] == "historical"
    assert not any(item["rule_id"] == "REVIEW_DECISION_EXCEPTION" for item in report["findings"])


def test_declarations_ignore_examples_and_preserve_incomplete_ranges() -> None:
    content = "---\ntitle: example\n---\n```md\n## Tactical exception\nExample only\n```\n## Excepción táctica\nTODO\n## Review condition\n"
    evidence = declared_sections("adr.md", content)
    assert len(evidence["tactical"]) == 1
    assert evidence["tactical"][0]["status"] == "unknown"
    assert evidence["review"][0]["status"] == "unknown"
    assert evidence["review"][0]["end_line"] <= len(content.splitlines())


def test_repeated_and_empty_declarations_do_not_get_silently_approved() -> None:
    evidence = declared_sections("adr.adoc", "= ADR\n== Tactical exception\nDeadline\n== Tactical exception\nTODO\n")
    assert [item["status"] for item in evidence["tactical"]] == ["evidence_available", "unknown"]


def test_summary_stays_bounded_for_many_decisions_and_old_reports(mature: Path) -> None:
    report, claims = analyze_repository(mature, review_overrides={"profile": "arc42"})
    review = report["architecture_review"]
    review["decision_assessments"] *= 10000
    assert len(human_summary(report)) < 6000
    review.pop("decision_assessments")
    review.pop("baseline")
    review["architecture_type"] = "tactical"
    report["schema_version"] = "1.1"
    assert "Legacy declared purpose: tactical" in human_report(report, claims)
    assert "Strategic baseline" not in human_report(report, claims)
