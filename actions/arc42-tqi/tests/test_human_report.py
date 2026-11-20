from __future__ import annotations

import copy
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from arc42_tqi.analyzer import analyze_repository
from arc42_tqi.human_report import human_html, human_report


class Markup(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.attributes: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self.attributes.extend(attrs)


def sample(mature: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    return analyze_repository(mature, review_overrides={"profile": "extended"})


def test_explains_weighted_score_gate_and_all_findings_without_mutation(mature: Path) -> None:
    report, claims = sample(mature)
    report["tqi_score"] = 21.04
    report["maturity_level"] = "L1"
    for name, dimension in report["dimensions"].items():
        dimension["score"] = 84.16666666666667 if name == "structure" else 0
        dimension["weighted_contribution"] = dimension["score"] * dimension["normalized_weight"]
    report["findings"] = [
        {"id": f"finding-{index}", "severity": "high", "dimension": "structure", "section": 11,
         "file": "docs/risks.md", "message": "Missing evidence", "rule_id": "ARC42_EMPTY",
         "evidence": f"evidence-{index}", "remediation": "Record the evidence."}
        for index in range(15)
    ]
    before = copy.deepcopy((report, claims))
    markdown = human_report(report, claims)
    assert "TQI 21.04/100" in markdown
    assert "84.17" in markdown and "21.04" in markdown
    assert "All recorded TQI points come from **Documentation structure**" in markdown
    assert "quality gate is non-blocking" in markdown
    assert "15 high" in markdown
    for index in range(15):
        assert f"finding-{index}" in markdown and f"evidence-{index}" in markdown
    assert "not a promise" in markdown
    assert "not verified production incidents" in markdown
    assert "Not recognized" in markdown
    assert (report, claims) == before
    assert human_report(report, claims) == markdown
    assert human_html(markdown) == human_html(markdown)


def test_custom_weights_and_not_applicable_metrics(mature: Path) -> None:
    (mature / ".arc42-tqi.yml").write_text("weights:\n  structure: 100\n  decisions: 0\n  volatility: 0\n  drift: 0\n")
    report, claims = sample(mature)
    markdown = human_report(report, claims)
    assert "| Documentation structure | 100.00 | 100.00% | 100.00 | 0.00 |" in markdown
    assert "| Architecture decisions |" not in markdown
    assert "Readiness for change" not in markdown
    assert "excluded from the dimension" in markdown
    assert "No deterministic findings were recorded" in markdown
    assert "a perfect documentation score does not replace" in markdown


def test_source_evidence_stays_inert_in_html(mature: Path) -> None:
    report, claims = sample(mature)
    payload = '<script>alert(1)</script> ![x](https://invalid.example/image) [click](javascript:alert(1))'
    report["metadata"]["repository"] = payload
    report["findings"] = [{"id": "unsafe", "severity": "high", "dimension": "structure", "section": None,
                           "file": payload, "message": payload, "rule_id": payload, "evidence": payload,
                           "remediation": payload}]
    report["semantic_enrichment"] = {"status": "complete", "observations": [{"message": payload}]}
    document = human_html(human_report(report, claims))
    parsed = Markup()
    parsed.feed(document)
    assert "script" not in parsed.tags and "img" not in parsed.tags
    assert not any(name.lower().startswith("on") for name, _ in parsed.attributes)
    assert all(value and (value.startswith("#") or value in {"tqi-report.json", "claims.json", "summary.md"})
               for name, value in parsed.attributes if name == "href")
    assert "&lt;script&gt;" in document
    assert "Content-Security-Policy" in document
    assert "<table>" in document
    assert "Unverified semantic observation" in document


def test_missing_inputs_and_failed_gate_remain_explainable(tmp_path: Path) -> None:
    report, claims = analyze_repository(tmp_path, min_tqi=70, fail_on_severity="high", review_overrides={"profile": "extended"})
    markdown = human_report(report, claims)
    assert "TQI 0.00/100" in markdown
    assert "Why the quality gate failed" in markdown
    assert "Blocking finding IDs" in markdown
    assert "No dimension contributes points" in markdown
    assert "Required categories without extracted claims" in markdown
    assert "implementation" in markdown
    assert "0 ADR records parsed" in markdown


def test_saved_bundle_renderer_preserves_evidence(mature: Path, monkeypatch: Any, tmp_path: Path) -> None:
    import importlib.util
    import json
    import sys

    from arc42_tqi.exporters import write_artifacts

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("render_human_report", root / "scripts/render_human_report.py")
    assert spec is not None and spec.loader is not None
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    report, claims = sample(mature)
    output = mature / ".arc42-tqi"
    write_artifacts(mature, output, report, claims)
    for name in ("human-report.md", "human-report.html"):
        (output / name).unlink()
    before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    monkeypatch.setattr(sys, "argv", ["render_human_report", "--artifacts", str(output)])
    renderer.main()
    assert (output / "human-report.html").is_file()
    assert all((output / name).read_bytes() == content for name, content in before.items())
    claims["metadata"]["commit"] = "different-snapshot"
    (output / "claims.json").write_text(json.dumps(claims))
    monkeypatch.setattr(sys, "argv", ["render_human_report", "--artifacts", str(output), "--output-dir", str(tmp_path / "invalid")])
    import pytest
    with pytest.raises(SystemExit):
        renderer.main()
    assert not (tmp_path / "invalid").exists()


def test_all_na_dimension_is_a_coverage_limit_not_a_measured_failure(mature: Path) -> None:
    report, claims = sample(mature)
    report["tqi_score"] = 75.0
    report["maturity_level"] = "L3"
    dimension = report["dimensions"]["volatility"]
    dimension.update(score=0, weighted_contribution=0)
    for metric in dimension["metrics"].values():
        metric.update(applicable=0, satisfied=0, ratio=None, normalized_weight=None,
                      weighted_penalty=None, reason="Explicitly inapplicable", status="not_applicable")
    markdown = human_report(report, claims)
    assert "assessment coverage limitation" in markdown
    assert "not evidence of failing measured controls" in markdown
    assert "Without explicit change axes" not in markdown
