from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

DIMENSIONS = ("structure", "decisions", "volatility", "drift")
SEVERITIES = ("critical", "high", "medium", "low")


@dataclass(frozen=True)
class SourceLine:
    file: str
    line: int
    text: str


@dataclass(frozen=True)
class Finding:
    id: str
    dimension: str
    severity: str
    file: str
    section: int | None
    rule_id: str
    message: str
    evidence: str
    remediation: str
    related_claim_ids: list[str] = field(default_factory=list)
    metric_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def finding(
    dimension: str, severity: str, file: str, section: int | None,
    rule: str, message: str, evidence: str, remediation: str,
) -> Finding:
    identity = "\0".join((dimension, file, str(section), rule, evidence))
    identifier = hashlib.sha256(identity.encode()).hexdigest()[:16]
    return Finding(identifier, dimension, severity, file, section, rule, message, evidence, remediation)


@dataclass
class DocumentTree:
    sections: dict[int, list[SourceLine]] = field(default_factory=dict)
    locations: dict[tuple[str, int], int | None] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
    diagrams: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    references_total: int = 0
    references_valid: int = 0
    headings_total: int = 0
    headings_valid: int = 0
    limitations: list[str] = field(default_factory=list)
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    headings: list[dict[str, Any]] = field(default_factory=list)
    traceability_edges: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Metric:
    satisfied: int
    applicable: int
    description: str
    evidence_refs: tuple[str, ...] = ()
    reason: str | None = None

    def ratio(self) -> float | None:
        return self.satisfied / self.applicable if self.applicable else None
