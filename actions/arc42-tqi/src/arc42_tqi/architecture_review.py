"""Explicit review expectations; referenced evidence is not semantic certification."""
from __future__ import annotations

import hashlib
from typing import Any

from .decision_review import assess_decisions
from .documents import PLACEHOLDER
from .models import DocumentTree, Finding, finding

EXPECTATIONS = {
    "context": (3, "System context", "Identify the system boundary, users, external systems, and relationship purposes."),
    "container": (5, "Containers", "Show applications and data stores, responsibilities, technology choices, and named interfaces."),
    "component": (5, "Components", "For relevant containers, explain internal component responsibilities, interfaces, and dependencies. Code-level diagrams are not required."),
    "deployment": (7, "Deployment view", "Map software instances to deployment nodes and environments; explain network boundaries, replicas, and infrastructure dependencies."),
    "strategic_intent": (4, "Strategic direction", "Explain business drivers, target capabilities, principles, constraints, and the decisions that remain open."),
    "tactical_scope": (4, "Tactical delivery scope", "State the bounded delivery scope, exclusions, accepted trade-offs, and constraints inherited from the strategic direction."),
    "current_state": (3, "Current state", "Describe the existing boundaries, dependencies, and constraints relevant to the migration."),
    "target_state": (4, "Target state", "Describe the desired boundaries and responsibilities, and explain what changes from the current state."),
    "migration_plan": (6, "Transition stages", "Document intermediate states, dependency order, coexistence, data migration, and entry/exit criteria for each stage."),
    "rollback": (11, "Rollback and transition risks", "Record cutover failure conditions, rollback or forward-recovery steps, risk owners, and acceptance criteria."),
}


def assess_review(tree: DocumentTree, config: dict[str, Any], adrs: list[dict[str, Any]]) -> tuple[dict[str, Any], list[Finding]]:
    review = config["review"]
    result: dict[str, Any] = {key: review[key] for key in ("profile", "rigor", "c4_level", "deployment_view")}
    result.update(status="not_evaluated", checks=[], baseline="strategic", decision_assessments=[])
    if review["profile"] == "extended":
        result["reason"] = "Legacy rubric selected; arc42 review expectations are not evaluated."
        return result, []
    levels = ["context", "container", "component"]
    required = levels[:levels.index(review["c4_level"]) + 1]
    if review["deployment_view"] == "required":
        required.append("deployment")
    required.append("strategic_intent")
    findings: list[Finding] = []
    for name in required:
        section, title, guidance = EXPECTATIONS[name]
        sources, rejected = [], []
        for source in review["evidence"][name]:
            content = tree.files.get(source["file"])
            lines = content.splitlines() if content is not None else []
            excerpt = "\n".join(lines[source["line"] - 1:source["end_line"]])
            reason = ("File was not included in the scanned documentation" if content is None
                      else "Line range extends beyond the end of the file" if source["end_line"] > len(lines)
                      else "Selected lines are empty" if not excerpt.strip()
                      else "Selected lines contain unfinished template text" if PLACEHOLDER.search(excerpt) else None)
            if reason:
                rejected.append({**source, "reason": reason})
            else:
                sources.append({**source, "excerpt": excerpt[:4096], "excerpt_truncated": len(excerpt) > 4096,
                                "sha256": hashlib.sha256((content or "").encode()).hexdigest(), "evidence_level": "declared"})
        status = "evidence_available" if sources and not rejected else "unknown"
        severity = {"advisory": "low", "standard": "medium", "strict": "high"}[review["rigor"]]
        result["checks"].append({"id": name, "title": title, "section": section, "status": status,
                                 "expectation": guidance, "sources": sources, "rejected_sources": rejected,
                                 "reason": "Declared source ranges are available; semantic review is still required." if status == "evidence_available"
                                 else "No complete, valid evidence mapping is available; absence of architecture content is not established."})
        if status == "unknown":
            findings.append(finding("structure", severity, "", section, "REVIEW_" + name.upper(),
                                    f"{title}: evidence needs review", f"{len(sources)} valid references; {len(rejected)} rejected references",
                                    guidance + f" Map inspected file/line ranges in review.evidence.{name}; do not add artificial text to satisfy the checker."))
    assessments, decision_findings = assess_decisions(tree, adrs, review["rigor"])
    result["decision_assessments"] = assessments
    findings.extend(decision_findings)
    result["status"] = "review_required"
    result["reason"] = "Checks validate declared source availability only. A reviewer must assess whether the evidence satisfies each expectation."
    return result, findings


def finding_detail(item: dict[str, Any]) -> tuple[str, str, str]:
    """Return a review implication, a concrete review task, and completion criteria."""
    rule = item["rule_id"]
    if rule == "REVIEW_DECISION_EXCEPTION":
        return ("A documented compromise or intermediate state lacks some supporting rationale or follow-up evidence. The choice itself is not a quality defect.",
                item["remediation"],
                "A reviewer confirms the decision's alignment, rationale, consequences, and applicable review, exit, and recovery conditions; readable text alone is not approval.")
    if rule.startswith("REVIEW_"):
        key = rule.removeprefix("REVIEW_").lower()
        expectation = EXPECTATIONS.get(key)
        if expectation:
            return ("The review cannot establish coverage of this agreed architecture expectation from the supplied references.",
                    expectation[2],
                    "A valid source range is mapped and a reviewer confirms its content addresses the expectation; availability alone is not approval.")
    if rule in {"ARC42_EMPTY", "ARC42_DEPTH", "ARC42_PLACEHOLDER"}:
        guidance = {
            1: "State the business problem, stakeholders, measurable goals, and scope exclusions.",
            2: "List binding technical, organizational, and regulatory constraints and their sources.",
            3: EXPECTATIONS["context"][2], 4: "Explain the solution strategy and why it meets the stated goals and constraints.",
            5: EXPECTATIONS["component"][2],
            6: "Trace important success and failure scenarios through named participants, interfaces, and recovery steps.",
            7: EXPECTATIONS["deployment"][2],
            8: "Explain shared security, data, observability, and error-handling concepts and where they apply.",
            9: "Explain decisions, alternatives, consequences, and links to affected views and requirements.",
            10: "Write quality scenarios with stimulus, operating conditions, expected response, and a measurable target.",
            11: "For each risk, record its cause, potential impact, owner, mitigation, and review or acceptance condition.",
            12: "Define domain and technical terms consistently and resolve ambiguous abbreviations.",
        }.get(item["section"] if isinstance(item.get("section"), int) else 0, "Replace the unsupported or missing statement with source-backed architecture evidence.")
        return ("Readers may have to make assumptions about this part of the design; this is a documentation gap, not proof of a runtime defect.",
                guidance,
                "The correct section is recognized, relevant statements replace template text, and a reviewer confirms the content answers the section's questions. Word count alone is not sufficient.")
    if rule.startswith("ADR_"):
        tasks = {
            "ADR_LIFECYCLE": "Record a supported status and valid supersession links; identify which decision currently applies.",
            "ADR_TRADEOFFS": "List viable alternatives, reasons for rejecting them, and positive and negative consequences of the chosen option.",
            "ADR_QUALITY_ATTRIBUTES": "Link the decision to named quality attributes and measurable scenarios in section 10.",
            "ADR_BIDIRECTIONAL_TRACEABILITY": "Add links from the decision to the affected populated arc42 sections and links back to the decision.",
        }
        return ("A future reviewer may be unable to reconstruct the decision rationale or determine which decision governs a change.",
                tasks.get(rule, "Inspect the ADR source and supported fields; record context, decision, alternatives, consequences, status, and affected sections."),
                "The specific ADR check passes, links resolve, and a reviewer confirms the rationale and trade-offs describe the actual decision.")
    return ("The recorded evidence is insufficient for this check; investigate the source before treating it as a design defect.",
            item["remediation"],
            "Re-run the check against corrected evidence and have the responsible reviewer verify the intended meaning; do not suppress the finding without a documented reason.")
