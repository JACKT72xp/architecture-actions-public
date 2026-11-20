"""Review explicitly documented ADR compromises without inferring design quality."""
from __future__ import annotations

import re
from typing import Any

from .contracts import source_ref
from .documents import HEADING, PLACEHOLDER, normalize
from .models import DocumentTree, Finding, finding

# These headings declare intent; mentions in arbitrary prose do not classify a decision.
HEADINGS = {
    "alignment": ("strategic alignment", "alineacion estrategica"),
    "tactical": ("tactical exception", "excepcion tactica"),
    "transition": ("transition plan", "plan de transicion"),
    "review": ("review condition", "condicion de revision"),
    "exit": ("exit criteria", "criterios de salida"),
    "recovery": ("rollback and recovery", "reversion y recuperacion"),
}
LABELS = {"alignment": "Strategic alignment", "tactical": "Tactical exception rationale",
          "transition": "Transition plan", "review": "Review condition", "exit": "Exit criteria",
          "recovery": "Rollback or recovery", "consequences": "Consequences"}


def declared_sections(file: str, content: str) -> dict[str, list[dict[str, Any]]]:
    """Capture exact source ranges, including repeated declarations, outside code blocks."""
    result: dict[str, list[dict[str, Any]]] = {}
    lines = content.splitlines()
    current: str | None = None
    start = 0
    fence: str | None = None
    frontmatter = bool(lines and lines[0].strip() == "---")

    def finish(end: int) -> None:
        if current is None:
            return
        excerpt = "\n".join(lines[start:end]).strip()
        result.setdefault(current, []).append({
            **source_ref(file, content, min(start + 1, len(lines)), max(start, end), 9),
            "excerpt": excerpt[:4096], "excerpt_truncated": len(excerpt) > 4096,
            "status": "evidence_available" if excerpt and not PLACEHOLDER.search(excerpt) else "unknown",
            "evidence_level": "declared",
        })

    for index, line in enumerate(lines):
        if frontmatter:
            if index and line.strip() == "---":
                frontmatter = False
            continue
        marker = re.match(r"^\s*(`{3,}|~{3,}|----|\.\.\.\.)\s*", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence:
            continue
        heading = HEADING.match(line)
        if heading:
            finish(index)
            label = normalize(heading.group(2))
            current = next((key for key, aliases in HEADINGS.items() if label in aliases), None)
            start = index + 1
    finish(len(lines))
    return result


def assess_decisions(tree: DocumentTree, adrs: list[dict[str, Any]], rigor: str) -> tuple[list[dict[str, Any]], list[Finding]]:
    assessments, findings = [], []
    severity = {"advisory": "low", "standard": "medium", "strict": "high"}[rigor]
    for adr in adrs:
        file = adr["source"]["file"]
        evidence = declared_sections(file, tree.files.get(file, ""))
        roles = [role for role in ("tactical", "transition") if role in evidence]
        active = adr["status"] not in {"deprecated", "superseded"}
        required = {"alignment"} if roles else set()
        if "tactical" in roles:
            required.update(("tactical", "review", "consequences"))
        if "transition" in roles:
            required.update(("transition", "exit", "recovery", "consequences"))
        missing = []
        for field in sorted(required):
            if field == "consequences":
                values = [value for group in adr["consequences"].values() for value in group]
                available = bool(values) and all(value.strip() and not PLACEHOLDER.search(value) for value in values)
            else:
                available = bool(evidence.get(field)) and all(
                    source["status"] == "evidence_available" for source in evidence[field])
            if not available:
                missing.append(LABELS[field])
        status = "historical" if not active else "unknown" if not roles or missing else "evidence_available"
        assessments.append({"adr_id": adr["id"], "title": adr["title"], "lifecycle": adr["status"],
                            "source": adr["source"], "declared_exceptions": roles, "status": status,
                            "missing_evidence": missing, "evidence": evidence,
                            "reason": "Only explicit ADR headings are recognized. No declaration does not prove strategic alignment or absence of compromises. Readable evidence still requires human review."})
        if active and roles and missing:
            findings.append(finding("decisions", severity, file, 9, "REVIEW_DECISION_EXCEPTION",
                                    "Document the rationale and follow-up for this decision", adr["id"],
                                    "Review " + adr["id"] + ": " + ", ".join(missing) +
                                    ". Link the solution strategy (section 4) and any risks or debt (section 11). "
                                    "A tactical choice is not itself a quality defect; review the supporting evidence."))
    return assessments, findings
