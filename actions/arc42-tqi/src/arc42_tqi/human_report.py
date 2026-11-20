"""Deterministic explanations of recorded evidence, without rescoring or an LLM."""
from __future__ import annotations

import html
from collections import Counter
from typing import Any

from markdown_it import MarkdownIt

from .architecture_review import finding_detail
from .models import DIMENSIONS, SEVERITIES

LABELS = {"structure": "Documentation structure", "decisions": "Architecture decisions",
          "volatility": "Readiness for change", "drift": "Readiness for conformance audits"}
RISKS = {
    "structure": "Gaps in recognized sections or unresolved placeholders can leave reviewers without clear goals, boundaries, or risk ownership.",
    "decisions": "Incomplete decision records make it harder to explain trade-offs, identify the current decision, and assess whether a later change invalidates its rationale.",
    "volatility": "Without explicit change axes, isolation strategies, impacts, and mitigations, reviewers cannot assess how a change might propagate across components.",
    "drift": "Without explicit, traceable, verifiable claims, an implementation audit has fewer reliable statements to compare against code, infrastructure, or diagrams. This is not evidence that drift has occurred.",
}
ACTIONS = {
    "structure": "Check the analyzed paths and recognized headings first. Complete missing sections and replace placeholders with concrete statements, responsible owners, and measurable requirements.",
    "decisions": "Check the ADR input path and supported metadata format. Keep unused templates outside that path. Record real decisions with context, alternatives and rejection reasons, consequences, status, quality attributes, and reciprocal section links.",
    "volatility": "Declare relevant volatility zones: the component, expected change axis, isolation strategy, propagation risk, impact, mitigation, and owner. Do not invent change axes just to increase the score.",
    "drift": "Express relevant design statements as supported structured claims with source references and verification predicates. For genuinely inapplicable categories, record an explicit applicability reason instead of adding artificial evidence.",
}
METRICS = {
    "coverage": "Coverage", "depth": "Substantive detail", "headings": "Heading structure",
    "placeholders": "Sections without placeholders", "references": "Local references",
    "diagrams": "Diagram availability", "completeness": "Evidence completeness",
    "lifecycle": "Decision lifecycle", "tradeoffs": "Alternatives and consequences",
    "quality_attributes": "Quality attributes", "bidirectional_traceability": "Two-way section links",
    "classification": "Change-axis classification", "encapsulation": "Isolation strategy",
    "impact_mitigation": "Impact and mitigation", "evolution": "Git evolution signals",
    "provenance": "Source traceability", "atomic_verifiability": "Verifiable statements",
    "integrity": "Reference integrity",
}
CATEGORIES = {
    "components": "Components", "dependencies": "Dependencies", "flows": "Flows",
    "cloud_resources": "Cloud resources", "volatility_zones": "Volatility zones",
    "constraints_and_adrs": "Constraints and accepted decisions",
}


def text(value: Any) -> str:
    """Keep source evidence inert in both Markdown and the derived HTML."""
    result = html.escape(str(value)).replace("\n", " ").replace("\r", " ")
    for character in ("\\", "`", "*", "_", "[", "]", "|", "#", "!", ">"):
        result = result.replace(character, "\\" + character)
    return result.replace("@", "＠")


def section_name(report: dict[str, Any], identifier: Any) -> str:
    section = next((item for item in report["sections"] if item["id"] == identifier), None)
    return f"Section {identifier}: {section['canonical_name'].capitalize()}" if section else "Repository scope"


def observation(report: dict[str, Any], claims: dict[str, Any], dimension: str) -> str:
    if dimension == "structure":
        missing = [section_name(report, item["id"]) for item in report["sections"] if not item["present"]]
        placeholders = sum(item["placeholder_count"] for item in report["sections"])
        return (f"{sum(bool(item['present']) for item in report['sections'])}/{len(report['sections'])} "
                f"canonical sections recognized as populated; {placeholders} placeholder occurrences. "
                + ("Not recognized as populated: " + "; ".join(missing) + "." if missing else "All canonical sections are populated."))
    if dimension == "decisions":
        records = report["adrs"]
        locations = "; ".join(f"{item['id']} ({item['source']['file']})" for item in records[:3])
        return (f"{len(records)} ADR {'record' if len(records) == 1 else 'records'} parsed. " + ("Examples: " + locations + ". " if locations else "")
                + "Decision metrics inspect typed evidence; a narrative in section 9 alone does not satisfy the ADR contract.")
    if dimension == "volatility":
        history = report["history"]
        return (f"{len(claims.get('volatility_zones', []))} explicit volatility zones extracted. "
                f"Git history status: {history['status']}; {history.get('commits_analyzed', 0)} commits analyzed, "
                f"{len(history.get('hotspots', []))} hotspots and {len(history.get('temporal_couplings', []))} temporal couplings recorded.")
    missing_categories = [label for category, label in CATEGORIES.items()
                          if claims.get("applicability", {}).get(category, {}).get("required", True)
                          and not claims.get(category)]
    count = sum(len(claims.get(category, [])) for category in CATEGORIES)
    return (f"{count} structured claims extracted across the six categories. "
            + ("Required categories without extracted claims: " + ", ".join(missing_categories) + ". " if missing_categories else "")
            + "Prose or diagrams can describe these concepts without satisfying the structured claim contract.")


def counted(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def review_explanation(check: dict[str, Any]) -> tuple[str, str]:
    """Describe reference coverage without claiming that the design is absent or correct."""
    valid, rejected = len(check["sources"]), len(check["rejected_sources"])
    if check["status"] == "evidence_available":
        return ("Ready for human review", f"{counted(valid, 'source reference')} {'is' if valid == 1 else 'are'} readable. A reviewer still needs to confirm what they explain.")
    if rejected:
        return ("Fix evidence links", f"{counted(rejected, 'source reference')} could not be used; {valid} are readable. Correct the rejected file or line ranges before reviewing coverage.")
    return ("Evidence not linked", "No source references have been linked for this check. The documentation may already exist; its absence has not been established.")


def executive_brief(report: dict[str, Any], links: bool = True) -> str:
    """A bounded decision aid, independent of repository size and raw evidence length."""
    gate = report["quality_gate"]
    findings = report["findings"]
    active = [(name, report["dimensions"][name]) for name in DIMENSIONS if report["dimensions"][name]["weight"] > 0]
    counts = Counter(item["severity"] for item in findings)
    lines = ["## At a glance", "", f"Gate: **{'passed' if gate['passed'] else 'failed'}**."]
    if gate["min_tqi"] == 0 and gate["fail_on_severity"] == "none":
        lines.append("Reporting only: this run does not block on score or findings. Passing is not architecture approval.")
    else:
        lines.append(f"Required score: {gate['min_tqi']:g}/100; blocking severity: {text(gate['fail_on_severity'])} or higher. "
                     f"{len(gate['blocking_finding_ids'])} findings block the gate.")
    lines.extend(["", f"**{counted(len(findings), 'finding')}:** " + ", ".join(f"{counts[level]} {level}" for level in SEVERITIES) + ". "
                  "Counts describe documentation checks, not production incidents.", "",
                  "**Why this score:** " + "; ".join(
                      f"{LABELS.get(name, name)} {value['score']:.1f}/100 (contributes {value['weighted_contribution']:.1f} points)"
                      for name, value in active) + ".", "",
                  "## Three priorities", ""])
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in findings:
        rule = item["rule_id"]
        group = ("review" if rule.startswith("REVIEW_") else "decisions" if rule.startswith("ADR_")
                 else "placeholders" if rule == "ARC42_PLACEHOLDER" else "sections" if rule.startswith("ARC42_")
                 else "references" if rule in {"DOC_REFERENCE", "DOC_INCLUDE"} else "other")
        groups.setdefault(group, []).append(item)
    blocking = set(gate["blocking_finding_ids"])
    def order(key: str) -> tuple[bool, int, int, str]:
        items = groups[key]
        return (not any(item["id"] in blocking for item in items),
                min(SEVERITIES.index(item["severity"]) for item in items), -len(items), key)
    guidance = {
        "review": ("Link the architecture evidence", "Point each required view to existing documentation. Missing mappings prevent review; they do not prove that a view is missing."),
        "decisions": ("Make decisions traceable", "Review the ADRs and record the rationale, alternatives, current status, and links to affected sections."),
        "placeholders": ("Replace unfinished template text", "Complete the remaining placeholders with project-specific decisions, requirements, or clearly owned open questions."),
        "sections": ("Complete the section gaps", "Check the scanned headings and paths, then fill the sections that are missing or too thin."),
        "references": ("Repair document links", "Correct broken references so readers can reach the supporting evidence."),
        "other": ("Review the remaining evidence checks", "Use the detailed report to inspect the recorded evidence before deciding which documentation needs correction."),
    }
    ordered = sorted(groups, key=order)
    for index, key in enumerate(ordered[:3], 1):
        items = groups[key]
        title, task = guidance[key]
        files = len({item["file"] for item in items if item["file"]})
        coverage = counted(len(items), "finding") + (f" across {counted(files, 'file')}" if files else " at repository scope")
        if files and any(not item["file"] for item in items):
            coverage += " and repository-wide checks"
        first = min(items, key=lambda item: (SEVERITIES.index(item["severity"]), item.get("section") or 99, item["id"]))
        if first.get("section"):
            task += f" Start with section {first['section']}."
        elif first["file"]:
            location = first["file"]
            task += " Start with " + text(location[:80] + ("…" if len(location) > 80 else "")) + "."
        lines.extend([f"{index}. **{title}** — {coverage}. {task}", ""])
    if not findings:
        lines.extend(["No automated findings. A human architecture review is still required.", ""])
    elif len(ordered) > 3:
        remaining = sum(len(groups[key]) for key in ordered[3:])
        lines.extend([f"Another {remaining} findings in {len(ordered) - 3} groups are covered in the full report.", ""])
    if findings:
        lines.extend(["Groups are ordered by gate blockers, highest severity, then count. Grouping does not change the score or remove findings.", ""])
    review = report.get("architecture_review", {})
    checks = review.get("checks", [])
    if checks:
        unknown = sum(check["status"] != "evidence_available" for check in checks)
        lines.extend(["## Architecture review", "",
                      f"{unknown} of {len(checks)} configured expectations need evidence links or corrections. "
                      "Readable references still require a human content review.", ""])
    deployment = next((check for check in checks if check["id"] == "deployment"), None)
    if deployment:
        status, explanation = review_explanation(deployment)
        lines.extend([f"**Deployment view — {status.lower()}.** {explanation}", "",
                      "Next: identify the view explaining which applications run on which infrastructure, in which environment, "
                      "and how they connect. Link that existing view and its explanation in section 7; then review the mapping together.", ""])
    lines.extend(["TQI measures recognized documentation evidence, not architecture correctness. Missing links are not proof of missing design.", ""])
    if links:
        lines.extend(["[Full human report](human-report.html) · [Markdown details](human-report.md) · [Machine evidence](tqi-report.json)", ""])
    return "\n".join(lines)


def human_summary(report: dict[str, Any]) -> str:
    return ("# Architecture summary\n\n"
            f"**TQI {report['tqi_score']:.2f}/100 · {text(report['maturity_level'])}**\n\n"
            + executive_brief(report))


def human_report(report: dict[str, Any], claims: dict[str, Any]) -> str:
    """Explain existing report values; retain every finding and its evidence."""
    active_dimensions = tuple(name for name in DIMENSIONS if report["dimensions"][name]["weight"] > 0)
    arc42 = report.get("effective_config", {}).get("review", {}).get("profile") == "arc42"
    score, level = report["tqi_score"], report["maturity_level"]
    gate, metadata = report["quality_gate"], report["metadata"]
    counts = Counter(item["severity"] for item in report["findings"])
    lines = ["# Architecture quality report", "", f"**TQI {score:.2f}/100 · {text(level)}**", "",
             f"Repository: {text(metadata.get('repository') or 'Not recorded')} · "
             f"Commit: {text(metadata.get('commit') or 'Not recorded')}", "",
             "## Executive reading", "",
             "TQI measures how much explicit architecture-documentation evidence the analyzer could recognize and validate. "
             "It does not grade the running system's safety, security, or correctness.", "",
             f"The recorded result is **{score:.2f}/100**, classified as **{text(level)}**. "
             "Maturity bands: L1 below 40; L2 from 40 to below 70; L3 from 70 to below 90; L4 from 90 to 100.", "",
             f"There are **{len(report['findings'])} documentation findings**: "
             + ", ".join(f"{counts[severity]} {severity}" for severity in SEVERITIES) + ". "
             "These severities describe evidence gaps, not verified production incidents.", ""]
    positive = [name for name in active_dimensions if report["dimensions"][name]["weighted_contribution"] > 0]
    if len(positive) == 1:
        lines.extend([f"All recorded TQI points come from **{LABELS[positive[0]]}**. "
                      "The other dimensions contribute no points under the configured weights.", ""])
    elif not positive:
        lines.extend(["No dimension contributes points under the configured weights. Verify scan scope and supported "
                      "evidence formats before interpreting this as absence of architecture work.", ""])
    if not arc42 and not claims.get("components") and report["dimensions"]["decisions"]["score"] == 0:
        lines.extend(["A substantial narrative can still score low when the typed ADR and claim contracts are not supplied. "
                      "Verify evidence format and scan coverage before interpreting this score as poor architecture.", ""])
    strengths = [(key, item) for key, item in report["dimensions"]["structure"]["metrics"].items()
                 if item["applicable"] and item["ratio"] == 1]
    if strengths:
        lines.extend(["**Recognized strengths:** " + "; ".join(
            f"{METRICS.get(key, key)} {item['satisfied']}/{item['applicable']} checks passed"
            for key, item in strengths) + ". These checks establish documented availability or consistency, not design correctness.", ""])
    review = report.get("architecture_review")
    if review and review["profile"] == "arc42":
        lines.extend(["## Agreed review scope", "",
                      f"Profile: **arc42** · Rigor: **{text(review['rigor'])}** · Architecture purpose: **{text(review['architecture_type'])}**.", "",
                      f"C4 depth through **{text(review['c4_level'])}**; deployment view: **{text(review['deployment_view'])}**. Code-level diagrams are not required.", "",
                      "Volatility, Git history, and audit-readiness metrics do not contribute to this profile's TQI or gate. "
                      "The score covers document structure and typed decision evidence; view and architecture-purpose checks are reported separately and can block through the severity gate.", "",
                      "Rigor sets the severity of missing or invalid review references: advisory = low, standard = medium, strict = high. "
                      "It does not establish semantic correctness. Thresholds remain explicitly configured.", ""])
        for check in review["checks"]:
            status, explanation = review_explanation(check)
            lines.extend([f"### {text(check['title'])} — {status}", "", text(explanation), "",
                          "**What to review:** " + text(check["expectation"]), ""])
            examples = [(source, "Needs correction") for source in check["rejected_sources"]] + [
                (source, "Readable") for source in check["sources"]]
            for source, label in examples[:3]:
                location = f"{source['file']}:{source['line']}–{source['end_line']}"
                lines.append(f"- {label}: {text(location)}" + (" — " + text(source["reason"]) if label == "Needs correction" else ""))
            if len(examples) > 3:
                lines.append(f"- {len(examples) - 3} more references are in tqi-report.json → architecture_review.checks.")
            if examples:
                lines.extend(["", "Full source ranges, excerpts, and hashes remain in the machine evidence; up to three example locations are shown here.", ""])
    lines.extend(["## Why the quality gate " + ("passed" if gate["passed"] else "failed"), "",
                  f"Configured minimum: **{gate['min_tqi']:g}/100**. Severity blocking: **{text(gate['fail_on_severity'])}**. "
                  f"Score check: {'passed' if gate['score_passed'] else 'failed'}; "
                  f"severity check: {'passed' if gate['severity_passed'] else 'failed'}.", ""])
    if gate["min_tqi"] == 0 and gate["fail_on_severity"] == "none":
        lines.extend(["**The quality gate is non-blocking.** A successful workflow does not mean the documentation "
                      "has reached an agreed quality standard: this configuration accepts any valid score and does not block findings.", ""])
    if gate["blocking_finding_ids"]:
        lines.extend(["Blocking finding IDs: " + ", ".join(text(item) for item in gate["blocking_finding_ids"]) + ".", ""])
    lines.extend(["## How the score was obtained", "",
                  "Each dimension score is multiplied by its normalized dimension weight. The contributions are added "
                  "and the final TQI is rounded half-up to two decimals. Values below come from the recorded analysis; "
                  "display rounding can make a displayed sum differ slightly. Finding counts are not subtracted from the score.", "",
                  "| Dimension | Score / 100 | Share of TQI | Earned TQI points | Unearned TQI points |",
                  "| --- | ---: | ---: | ---: | ---: |"])
    for name in active_dimensions:
        item = report["dimensions"][name]
        budget = 100 * item["normalized_weight"]
        lines.append(f"| {LABELS[name]} | {item['score']:.2f} | {budget:.2f}% | "
                     f"{item['weighted_contribution']:.2f} | {max(0, budget - item['weighted_contribution']):.2f} |")
    formula = " + ".join(f"({report['dimensions'][name]['score']:.2f} × "
                         f"{report['dimensions'][name]['normalized_weight']:.4f})" for name in active_dimensions)
    lines.extend(["", f"Displayed calculation: {formula} ≈ **{score:.2f}**.", "",
                  "## Priorities, review risks, and next steps", "",
                  "Priorities are ordered by unearned weighted points, then finding severity. They describe documentation "
                  "review risks, not measured incident probability. Unearned points are a scoring explanation, not a promise "
                  "that one edit will earn that many points.", ""])
    def priority(name: str) -> tuple[float, int, int]:
        item = report["dimensions"][name]
        severities = [SEVERITIES.index(finding["severity"]) for finding in report["findings"] if finding["dimension"] == name]
        return (-max(0, 100 * item["normalized_weight"] - item["weighted_contribution"]),
                min(severities, default=len(SEVERITIES)), DIMENSIONS.index(name))
    actionable = [name for name in sorted(active_dimensions, key=priority)
                  if report["dimensions"][name]["score"] < 100
                  or any(item["dimension"] == name for item in report["findings"])]
    for index, name in enumerate(actionable, 1):
        measurable = any(item["normalized_weight"] for item in report["dimensions"][name]["metrics"].values())
        observed = observation(report, claims, name) if measurable else (
            "No positive-weight applicable metrics were measured. The rubric records zero for this dimension."
        )
        risk = RISKS[name] if measurable else (
            "This is an assessment coverage limitation, not evidence of failing measured controls."
        )
        action = ACTIONS[name] if measurable else (
            "Review applicability reasons, available evidence, and dimension weights before interpreting the zero. "
            "Do not invent evidence for genuinely inapplicable checks."
        )
        lines.extend([f"### {index}. {LABELS[name]}", "", "**Observed evidence:** " + text(observed), "",
                      "**Review risk:** " + risk, "", "**Next step:** " + action, "",
                      f"Evidence: tqi-report.json → dimensions.{name}; findings filtered by dimension {name}. "
                      "The complete findings below identify exact records and source locations.", ""])
    if not actionable:
        lines.extend(["No deterministic deficiencies were recorded. Preserve the evidence as the system changes and "
                      "perform a separate implementation-conformance review; a perfect documentation score does not replace it.", ""])
    lines.extend(["## Section coverage", "",
                  "“Not recognized” means the analyzer did not find populated evidence in its input. "
                  "Check scanned paths and supported headings before concluding that a section is missing from the project.", "",
                  "| Section | Recognized | Critical | Substantive words | Placeholders | Source locations |",
                  "| --- | --- | --- | ---: | ---: | --- |"])
    for item in report["sections"]:
        sources = list(dict.fromkeys(f"{source['file']}:{source['line']}" for source in item["sources"]))
        locations = "; ".join(sources[:3]) + (f"; +{len(sources) - 3} more in tqi-report.json" if len(sources) > 3 else "")
        lines.append(f"| {text(section_name(report, item['id']))} | {'Yes' if item['present'] else 'Not recognized'} | "
                     f"{'Yes' if item['critical'] else 'No'} | {item['substantive_words']} | {item['placeholder_count']} | "
                     f"{text(locations or 'No recognized source')} |")
    lines.extend(["", f"Critical sections require at least {report['effective_config']['min_section_words']} substantive words "
                  "under this configuration. Code fences, diagrams, claim blocks, headings and placeholder-bearing lines "
                  "do not count as substantive prose.", "", "## Structured evidence coverage", "",
                  "| Category | Extracted records | Applicability |", "| --- | ---: | --- |"])
    for category, label in CATEGORIES.items():
        if arc42 and category == "volatility_zones":
            continue
        policy = claims.get("applicability", report["effective_config"]["applicability"]).get(category, {})
        applicability = "Auxiliary export; excluded from arc42 score and gate" if arc42 else "Required" if policy.get("required", True) else "Explicitly optional: " + str(policy.get("reason"))
        lines.append(f"| {label} | {len(claims.get(category, []))} | {text(applicability)} |")
    lines.extend(["", f"{len(claims.get('diagram_inventory', []))} diagram inventory records are available. "
                  "Inventory and file availability do not prove diagram correctness or replace typed claims.", "",
                  "## Metric details", "",
                  "N/A metrics are excluded from the dimension's applicable metric weights; missing required evidence "
                  "counts as a deficit instead. If a dimension has no positive-weight applicable metrics, its score is zero. "
                  "Denominators can include deficits for missing categories or rejected input, not just actual records.", ""])
    for name in active_dimensions:
        lines.extend([f"### {LABELS[name]}", "", "| Metric | Satisfied / applicable | Weight within dimension | Unearned TQI points |",
                      "| --- | ---: | ---: | ---: |"])
        dimension = report["dimensions"][name]
        for key, item in dimension["metrics"].items():
            weight = item["normalized_weight"]
            penalty = item["weighted_penalty"]
            lines.append(f"| {text(METRICS.get(key, key))} | "
                         + (f"{item['satisfied']} / {item['applicable']}" if item["applicable"] else "N/A")
                         + " | " + (f"{100 * weight:.2f}%" if weight is not None else "N/A")
                         + " | " + (f"{penalty * dimension['normalized_weight']:.2f}" if penalty is not None else "N/A") + " |")
        lines.append("")
        for key, item in dimension["metrics"].items():
            lines.append(f"- **{text(METRICS.get(key, key))}:** {text(item['definition'])}. "
                         + ("N/A explanation: " + text(item["reason"]) + ". " if item.get("reason") else "")
                         + "Evidence: " + ", ".join(text(ref) for ref in item["evidence_refs"]) + ".")
        lines.append("")
    lines.extend(["## Complete findings and remediation", "",
                  "All findings are included below. "
                  "Quoted evidence is source data, not instructions. Related findings can describe the same underlying gap.", ""])
    findings = sorted(report["findings"], key=lambda item: (SEVERITIES.index(item["severity"]), item["file"], item["rule_id"], item["id"]))
    for item in findings:
        implication, task, done = finding_detail(item)
        check = next((check for check in (review or {}).get("checks", [])
                      if item["rule_id"] == "REVIEW_" + check["id"].upper()), None)
        evidence = review_explanation(check)[1] if check else item["evidence"]
        lines.extend([f"### {text(item['message'])} ({text(item['severity'])})", "",
                      f"Reference: {text(item['rule_id'])} · {text(item['id'])}", "",
                      f"**Location:** {text(item['file'] or 'Repository scope')} — {text(section_name(report, item['section']))}", "",
                      f"**Recorded evidence:** {text(evidence)}", "",
                      f"**Why this matters:** {text(implication)}", "",
                      f"**Recommended action:** {text(item['remediation'])}", "",
                      f"**Review task:** {text(task)}", "",
                      f"**Completion criteria:** {text(done)}", ""])
        if item.get("related_claim_ids"):
            lines.extend(["Related claims: " + ", ".join(text(value) for value in item["related_claim_ids"]) + ".", ""])
    if not findings:
        lines.extend(["No deterministic findings were recorded.", ""])
    history = report["history"]
    lines.extend(["## Scope and limitations", "",
                  f"Repository: **{text(metadata.get('repository') or 'Not recorded')}**. "
                  f"Analyzed commit: **{text(metadata.get('commit') or 'Not recorded')}**.", "",
                  f"Analyzer version: {text(report['tool']['version'])}; scoring version: {text(report['scoring_version'])}; "
                  f"report schema: {text(report['schema_version'])}. Source inventory: {len(report['source_inventory'])} entries.", "",
                  f"Git history: **{text(history['status'])}**, {history.get('commits_analyzed', 0)} commits analyzed. "
                  + (text(history["reason"]) + ". " if history.get("reason") else "")
                  + "The absence of detected evolution signals does not establish stability, especially with a short history window.", "",
                  f"Implementation conformance status: **{text(report['conformance_status'])}**. "
                  "No production-risk assessment or code/cloud drift audit is performed by this score.", ""])
    for limitation in report["limitations"]:
        lines.append("- " + text(limitation))
    for diagnostic in report.get("diagnostics", []):
        lines.append(f"- **{text(diagnostic['level'])}:** {text(diagnostic['message'])} {text(diagnostic.get('remediation', ''))}")
    enrichment = report.get("semantic_enrichment", {"status": "disabled", "observations": []})
    lines.extend(["", f"Optional semantic enrichment: **{text(enrichment['status'])}**. "
                  "It does not change the TQI or quality gate. This human report uses deterministic templates and the recorded evidence.", ""])
    for item in enrichment.get("observations", []):
        lines.append("- Unverified semantic observation: " + text(item["message"]))
    lines.extend(["", "## Supporting files", "",
                  "- [Machine-readable score and evidence](tqi-report.json)",
                  "- [Structured claims](claims.json)",
                  "- [Short workflow summary](summary.md)", "",
                  "Use the drift-prompts directory for a separate audit with actual implementation evidence. "
                  "These prompts have not executed an audit. This report explains the saved result without changing or rescoring it.", ""])
    return "\n".join(lines[:4]) + "\n\n" + executive_brief(report, links=False) + "\n" + "\n".join(lines[4:])


def human_html(markdown: str) -> str:
    """Render an offline, script-free, printable report; source HTML stays disabled."""
    renderer = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = renderer.parse(markdown)
    navigation: list[str] = []
    for index, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h2":
            identifier = f"section-{len(navigation) + 1}"
            token.attrSet("id", identifier)
            navigation.append(f'<a href="#{identifier}">{html.escape(tokens[index + 1].content)}</a>')
    content = str(renderer.renderer.render(tokens, renderer.options, {}))
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Architecture quality report · arc42 TQI</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172b3a;background:#f0f4f5}
*{box-sizing:border-box}body{margin:0;line-height:1.65}header{background:#123a46;color:#fff;padding:28px max(24px,calc((100vw - 1280px)/2));letter-spacing:.04em}
header strong{display:block;font-size:21px}header span{color:#c6dce1;font-size:14px}.layout{max-width:1280px;margin:auto;display:grid;grid-template-columns:230px minmax(0,1fr);gap:28px;padding:28px 24px}
nav{position:sticky;top:24px;align-self:start;font-size:13px}nav strong{display:block;color:#52656e;margin-bottom:12px}nav a{display:block;padding:7px 10px;border-left:2px solid #b8ccd0;text-decoration:none;color:#245363}
nav a:hover,nav a:focus{background:#deebed;border-left-color:#19675b}main{background:#fff;border:1px solid #dce5e7;border-radius:12px;padding:36px;min-width:0;overflow-wrap:anywhere}
h1{font-size:32px;line-height:1.2;margin:0 0 18px;color:#123a46}h1+p{font-size:25px;background:#eaf4f2;padding:18px;border-left:5px solid #277669;border-radius:4px}
h2{font-size:23px;margin:40px 0 16px;border-top:1px solid #dce5e7;padding-top:26px;color:#123a46;scroll-margin-top:20px}h3{font-size:17px;margin-top:26px;color:#245363}p{margin:12px 0}a{color:#086f91}strong{font-weight:650}
table{display:block;width:100%;overflow-x:auto;border-collapse:collapse;font-size:13px;margin:20px 0}th{background:#edf3f5;text-align:left;font-weight:650;color:#284b59}th,td{border:1px solid #dce5e7;padding:10px 12px;vertical-align:top}tr:nth-child(even){background:#f8fafb}td{min-width:65px}
li{margin:7px 0}code{background:#eef3f5;border-radius:3px;padding:2px 4px}footer{font-size:12px;color:#52656e;text-align:center;padding:12px 24px 32px}
@media(max-width:850px){.layout{display:block;padding:14px}nav{position:static;margin-bottom:20px;display:flex;flex-wrap:wrap;gap:6px}nav strong{width:100%}nav a{padding:5px 8px}main{padding:22px}h1{font-size:27px}}
@media print{body{background:white;font-size:10pt}.layout{display:block;padding:0;max-width:none}nav,header,footer{display:none}main{border:0;padding:0}h2,h3{break-after:avoid}table{display:table;font-size:8pt}tr{break-inside:avoid}h1+p{font-size:18pt}a{color:inherit;text-decoration:none}}
</style></head><body><header><strong>arc42 · Architecture evidence</strong><span>Human-readable assessment · Offline report</span></header>
<div class="layout"><nav aria-label="Report sections"><strong>IN THIS REPORT</strong>''' + "".join(navigation) + \
        '</nav><main>' + content + '</main></div><footer>Recorded evidence, explained. Documentation quality does not certify implementation conformance.</footer></body></html>\n'
