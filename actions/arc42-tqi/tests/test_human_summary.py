from __future__ import annotations

import copy
import json
from pathlib import Path

from arc42_tqi.analyzer import analyze_repository
from arc42_tqi.exporters import summary, write_artifacts
from arc42_tqi.human_report import human_report, human_summary


def test_large_repository_has_bounded_summary_without_changing_evidence(mature: Path) -> None:
    report, claims = analyze_repository(mature, review_overrides={"profile": "arc42"})
    finding = report["findings"][0]
    report["findings"] = [{**finding, "id": f"finding-{index}", "file": f"docs/area-{index}.md",
                           "evidence": "untrusted long evidence " * 1000} for index in range(10000)]
    before = copy.deepcopy(report)
    brief = human_summary(report)
    assert len(brief) < 5000
    assert "10000 findings across 10000 files" in brief
    assert "finding-9999" not in brief
    assert "untrusted long evidence" not in brief
    assert "Link the architecture evidence" in brief
    assert report == before
    assert human_summary(json.loads(json.dumps(report, sort_keys=True))) == brief
    assert len(summary(report, "out")) < 5500
    assert claims  # No source content is needed to summarize recorded results.


def test_deployment_is_explained_without_internal_rule_codes(mature: Path) -> None:
    report, claims = analyze_repository(mature, review_overrides={"profile": "arc42"})
    brief = human_summary(report)
    assert "Deployment view — evidence not linked" in brief
    assert "documentation may already exist" in brief
    assert "which applications run on which infrastructure" in brief
    assert "REVIEW_DEPLOYMENT" not in brief
    assert "review.evidence" not in brief
    full = human_report(report, claims)
    assert full.index("## At a glance") < full.index("## Executive reading")
    assert "**Recorded evidence:** 0 valid references" not in full
    assert "Reference: REVIEW\\_DEPLOYMENT" in full


def test_many_review_sources_show_only_three_locations(mature: Path) -> None:
    report, claims = analyze_repository(mature, review_overrides={"profile": "arc42"})
    deployment = next(check for check in report["architecture_review"]["checks"] if check["id"] == "deployment")
    deployment["status"] = "evidence_available"
    deployment["sources"] = [{"file": f"deployment-evidence-{i}.md", "line": 1, "end_line": 20,
                              "excerpt": "Long source excerpt " * 100, "sha256": "a" * 64} for i in range(100)]
    full = human_report(report, claims)
    assert "100 source references are readable" in full
    assert "97 more references" in full
    assert "deployment-evidence-2.md" in full
    assert "deployment-evidence-3.md" not in full
    assert "Long source excerpt" not in full
    assert "a" * 64 not in full
    assert len(deployment["sources"]) == 100
    deployment["status"] = "unknown"
    deployment["rejected_sources"] = [{"file": "missing.md", "line": 1, "end_line": 2, "reason": "File was not scanned"}]
    assert "Deployment view — fix evidence links" in human_summary(report)
    assert "1 source reference could not be used; 100 are readable" in human_summary(report)


def test_blocking_group_is_first_and_other_groups_accounted_for(mature: Path) -> None:
    report, _ = analyze_repository(mature)
    base = {"dimension": "structure", "severity": "medium", "file": "doc.md", "section": 7,
            "message": "Check", "evidence": "value", "remediation": "Inspect"}
    rules = ["ARC42_PLACEHOLDER", "ADR_MISSING", "DOC_REFERENCE", "ARC42_DEPTH", "REVIEW_DEPLOYMENT"]
    report["findings"] = [{**base, "id": rule, "rule_id": rule} for rule in rules]
    report["quality_gate"].update(passed=False, min_tqi=70, fail_on_severity="medium", blocking_finding_ids=["DOC_REFERENCE"])
    brief = human_summary(report)
    assert "1. **Repair document links**" in brief
    assert "Another 2 findings in 2 groups" in brief
    assert brief.count("1. **") == brief.count("2. **") == brief.count("3. **") == 1


def test_short_artifacts_are_generated_and_reproducible(mature: Path) -> None:
    report, claims = analyze_repository(mature, review_overrides={"profile": "arc42"})
    outputs = write_artifacts(mature, mature / "out", report, claims)
    assert outputs["human-summary-path"] == "out/human-summary.md"
    assert outputs["human-summary-html-path"] == "out/human-summary.html"
    html = (mature / outputs["human-summary-html-path"]).read_text()
    assert "Three priorities" in html
    assert "<script" not in html
    assert "Full human report" in html
    saved = json.loads((mature / "out/tqi-report.json").read_text())
    assert human_summary(saved) == (mature / "out/human-summary.md").read_text()
    assert len(saved["findings"]) == len(report["findings"])
