from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt, StrictStr, validator

Axis = Literal["business_rules", "external_integrations", "data_schemas", "security_compliance", "infrastructure"]
Status = Literal["proposed", "accepted", "deprecated", "superseded"]
Scalar = StrictStr | StrictBool | StrictInt | StrictFloat | None


class Contract(BaseModel):
    class Config:
        extra = "forbid"
        allow_inf_nan = False
        validate_all = True
        smart_union = True

    @validator("*")
    def valid_collections(cls, value: Any, field: Any) -> Any:
        if isinstance(value, list):
            if any(isinstance(item, str) and not item.strip() for item in value):
                raise ValueError("Text collections cannot contain empty entries")
            if field.name in {"declared_volatility", "quality_attributes", "supersedes", "related"}:
                if len({repr(item) for item in value}) != len(value):
                    raise ValueError("Collection entries must be unique")
        return value


class Source(Contract):
    file: StrictStr
    line: StrictInt = 1
    end_line: StrictInt = 1
    section: StrictInt | None = None
    sha256: StrictStr

    @validator("end_line")
    def valid_range(cls, value: int, values: dict[str, Any]) -> int:
        if values.get("line", 1) < 1 or value < values.get("line", 1):
            raise ValueError("Invalid source line range")
        return value

    @validator("section")
    def valid_section(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 12:
            raise ValueError("Section must be in 1..12")
        return value

    @validator("sha256")
    def valid_hash(cls, value: str) -> str:
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("Expected SHA-256")
        return value


class Provenance(Contract):
    method: Literal["explicit", "controlled_language", "adr"]
    sources: list[Source] = Field(min_items=1)


class Verification(Contract):
    target: StrictStr = Field(min_length=1)
    property: StrictStr = Field(min_length=1)
    operator: Literal["exists", "not_exists", "equals", "not_equals", "contains", "not_contains",
                      "subset_of", "disjoint_from", "matches"]
    expected: Scalar | list[Scalar] = Field(...)
    method: Literal["ast", "dependency_graph", "iac", "cloud_inventory", "diagram_graph", "manual"]

    @validator("expected")
    def valid_expected(cls, value: Any) -> Any:
        if isinstance(value, list) and (not value or len({repr(item) for item in value}) != len(value)):
            raise ValueError("Expected values must be nonempty and unique")
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Expected values must be finite")
        return value


class SemanticObservation(Contract):
    claim_ids: list[StrictStr] = Field(default_factory=list)
    source_refs: list[Source] = Field(default_factory=list)
    message: StrictStr = Field(min_length=1, max_length=4000)
    kind: Literal["contradiction", "ambiguity", "claim_refinement", "other"] = "other"


class Claim(Contract):
    id: StrictStr
    statement: StrictStr | None = None
    provenance: Provenance
    evidence_targets: list[Literal["code", "cloud", "diagrams"]] = Field(min_items=1)
    verification: Verification | None = None

    @validator("id")
    def valid_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}", value):
            raise ValueError("Invalid claim ID")
        return value

    @validator("evidence_targets")
    def unique_targets(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Evidence targets must be unique")
        return value


class Component(Claim):
    name: StrictStr | None = None
    responsibility: StrictStr | None = None
    boundaries: list[StrictStr] = Field(default_factory=list)
    declared_volatility: list[Axis] = Field(default_factory=list)


class Dependency(Claim):
    source: StrictStr | None = None
    target: StrictStr | None = None
    protocol: StrictStr | None = None
    synchrony: Literal["sync", "async"] | None = None
    rationale: StrictStr | None = None
    allowed: StrictBool | None = None


class Flow(Claim):
    source: StrictStr | None = None
    target: StrictStr | None = None
    protocol: StrictStr | None = None
    synchrony: Literal["sync", "async"] | None = None
    rationale: StrictStr | None = None
    interface: StrictStr | None = None


class CloudResource(Claim):
    provider: Literal["aws", "gcp", "azure", "other"] | None = None
    service: StrictStr | None = None
    role: StrictStr | None = None
    component_id: StrictStr | None = None
    environment: StrictStr | None = None
    region: StrictStr | None = None
    configuration: dict[StrictStr, Scalar] = Field(default_factory=dict)
    security: dict[StrictStr, Scalar] = Field(default_factory=dict)


class VolatilityZone(Claim):
    component_id: StrictStr | None = None
    axis: Axis | None = None
    propagation_risk: StrictStr | None = None
    encapsulation: StrictStr | None = None
    impact: StrictStr | None = None
    mitigation: StrictStr | None = None
    owner: StrictStr | None = None


class Alternative(Contract):
    name: StrictStr = Field(min_length=1)
    rejection_reason: StrictStr | None = None


class Consequences(Contract):
    positive: list[StrictStr] = Field(default_factory=list)
    negative: list[StrictStr] = Field(default_factory=list)


class Constraint(Claim):
    adr_id: StrictStr | None = None
    status: Status | None = None
    constraint: StrictStr | None = None
    alternatives: list[Alternative] = Field(default_factory=list)
    consequences: Consequences = Field(default_factory=Consequences)
    quality_attributes: list[StrictStr] = Field(default_factory=list)
    superseded_by: StrictStr | None = None


class ADR(Contract):
    id: StrictStr = Field(min_length=1)
    title: StrictStr | None = None
    status: Status | None = None
    source: Source
    context: StrictStr | None = None
    decision: StrictStr | None = None
    alternatives: list[Alternative] = Field(default_factory=list)
    consequences: Consequences = Field(default_factory=Consequences)
    quality_attributes: list[StrictStr] = Field(default_factory=list)
    arc42_sections: list[StrictInt] = Field(default_factory=list)
    supersedes: list[StrictStr] = Field(default_factory=list)
    superseded_by: StrictStr | None = None
    related: list[StrictStr] = Field(default_factory=list)
    reviewed_against: list[StrictStr] = Field(default_factory=list)

    @validator("arc42_sections")
    def section_ids(cls, value: list[int]) -> list[int]:
        if any(not 1 <= item <= 12 for item in value) or len(set(value)) != len(value):
            raise ValueError("Expected unique arc42 section IDs")
        return value

    @validator("reviewed_against")
    def commits(cls, value: list[str]) -> list[str]:
        if any(not re.fullmatch(r"[a-f0-9]{40}(?:[a-f0-9]{24})?", item) for item in value):
            raise ValueError("Expected full commit IDs")
        return sorted(set(value))


CLAIM_MODELS: dict[str, type[Claim]] = {
    "components": Component, "dependencies": Dependency, "flows": Flow,
    "cloud_resources": CloudResource, "volatility_zones": VolatilityZone, "constraints_and_adrs": Constraint,
}


def source_ref(file: str, text: str, line: int = 1, end_line: int | None = None,
               section: int | None = None) -> dict[str, Any]:
    return Source(file=file, line=line, end_line=end_line if end_line is not None else max(1, len(text.splitlines())),
                  section=section, sha256=hashlib.sha256(text.encode()).hexdigest()).dict()
