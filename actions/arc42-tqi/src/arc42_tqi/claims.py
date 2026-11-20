from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from pydantic import ValidationError

from .adrs import lifecycle_valid
from .config import InputError, load_yaml
from .contracts import CLAIM_MODELS, source_ref
from .documents import PLACEHOLDER
from .models import DocumentTree, Finding, finding

CATEGORIES = tuple(CLAIM_MODELS)
AXES = {"business_rules", "external_integrations", "data_schemas", "security_compliance", "infrastructure"}
REQUIRED = {
    "components": ("name", "responsibility", "boundaries"),
    "dependencies": ("source", "target", "protocol", "synchrony", "rationale", "allowed"),
    "flows": ("source", "target", "protocol", "synchrony", "rationale", "interface"),
    "cloud_resources": ("provider", "service", "role", "component_id", "environment", "region", "configuration", "security"),
    "volatility_zones": ("component_id", "axis", "propagation_risk", "encapsulation", "impact", "mitigation", "owner"),
    "constraints_and_adrs": ("constraint", "adr_id", "status", "alternatives", "consequences", "quality_attributes"),
}


def meaningful(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip()) and not PLACEHOLDER.search(value)
    if isinstance(value, (bool, int, float)):
        return math.isfinite(value)
    if isinstance(value, list):
        return bool(value) and all(meaningful(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(meaningful(item) for item in value.values())
    return False


def complete(record: dict[str, Any], category: str) -> bool:
    return all(meaningful(record.get(field)) for field in REQUIRED[category])


def verifiable(record: dict[str, Any]) -> bool:
    check = record.get("verification")
    if not isinstance(check, dict) or not all(meaningful(check.get(key)) for key in ("target", "property", "operator", "method")):
        return False
    operator, expected = check["operator"], check["expected"]
    if operator in {"exists", "not_exists"}:
        return expected is None
    if operator in {"subset_of", "disjoint_from"}:
        return isinstance(expected, list) and meaningful(expected)
    if operator == "matches":
        if not isinstance(expected, str) or not meaningful(expected):
            return False
        try:
            re.compile(expected)
        except re.error:
            return False
    return expected is None or meaningful(expected)


def claim_blocks(text: str) -> list[tuple[int, str | None]]:
    blocks: list[tuple[int, str | None]] = []
    marker = ""
    opening = 0
    is_claim = False
    pending = 0
    content: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if marker:
            if re.fullmatch(re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*", stripped):
                if is_claim:
                    blocks.append((opening, "\n".join(content)))
                marker = ""
                is_claim = False
                content = []
            elif is_claim:
                content.append(line)
            continue
        if stripped == "[source,arc42-claims]":
            pending = number
            continue
        match = re.fullmatch(r"(`{3,}|~{3,}|----|\.\.\.\.)(.*)", stripped)
        if match:
            marker = match.group(1)
            is_claim = match.group(2).strip() == "arc42-claims" or (bool(pending) and marker == "----")
            opening = pending or number
        pending = 0
    if marker and is_claim:
        blocks.append((opening, None))
    return blocks


def extract_claims(tree: DocumentTree, adrs: list[dict[str, Any]],
                   config: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[Finding]]:
    contract: dict[str, Any] = {"schema_version": "1.0", **{category: [] for category in CATEGORIES},
                                "diagram_inventory": tree.diagrams}
    findings: list[Finding] = []
    identifiers: set[str] = set()
    limit = config["limits"]["max_claims"] if config else 10000

    def append(category: str, record: dict[str, Any]) -> None:
        if len(identifiers) >= limit:
            raise InputError("Claim count exceeds configured limit")
        if record["id"] in identifiers:
            raise InputError("Duplicate claim ID")
        identifiers.add(record["id"])
        contract[category].append(record)

    for file, text in sorted(tree.files.items()):
        for opening, content in claim_blocks(text):
            section = tree.locations.get((file, opening))
            try:
                if content is None:
                    raise InputError("Unclosed claims block")
                payload = load_yaml(content)
                if not isinstance(payload, dict) or set(payload) - set(CATEGORIES):
                    raise InputError("Expected a mapping of claim categories")
                if sum(len(items) for items in payload.values() if isinstance(items, list)) + len(identifiers) > limit:
                    raise InputError("Claim count exceeds configured limit")
                pending: list[tuple[str, dict[str, Any]]] = []
                pending_ids: set[str] = set()
                for category, records in payload.items():
                    if not isinstance(records, list):
                        raise InputError("Expected a list of claims")
                    for record in records:
                        if not isinstance(record, dict) or "provenance" in record:
                            raise InputError("Claims must be mappings; provenance is assigned by the parser")
                        end_line = min(len(text.splitlines()), opening + len(content.splitlines()) + (2 if text.splitlines()[opening - 1].startswith("[") else 1))
                        validated = CLAIM_MODELS[category].parse_obj({
                            **record, "provenance": {"method": "explicit", "sources": [
                                source_ref(file, text, opening, end_line, section)]},
                        }).dict()
                        if validated["id"] in identifiers or validated["id"] in pending_ids:
                            raise InputError("Duplicate claim ID")
                        pending_ids.add(validated["id"])
                        pending.append((category, validated))
                for category, record in pending:
                    append(category, record)
            except (InputError, ValidationError) as error:
                if isinstance(error, InputError) and "count exceeds" in str(error):
                    raise
                findings.append(finding("drift", "high", file, section, "CLAIM_PARSE",
                                        "Invalid typed claims block",
                                        f"line {opening}: {str(error) if isinstance(error, InputError) else 'Invalid field types or names'}",
                                        "Supply unique IDs, evidence_targets and schema-compatible fields; omit generated provenance."))
    components = {record["name"]: record["id"] for record in contract["components"] if record["name"]}
    pattern = re.compile(r"^\s*\x60([^\x60]+)\x60 must (not )?depend on \x60([^\x60]+)\x60 via \x60([^\x60]+)\x60 \((sync|async)\) because (.+)\.$")
    for section, lines in tree.sections.items():
        for line in lines:
            match = pattern.fullmatch(line.text)
            if not match:
                continue
            source, forbidden, target, protocol, synchrony, rationale = match.groups()
            identifier = "dependency-" + hashlib.sha256(f"{line.file}:{line.text}".encode()).hexdigest()[:16]
            if identifier in identifiers:
                continue
            append("dependencies", CLAIM_MODELS["dependencies"].parse_obj({
                "id": identifier, "statement": line.text, "source": components.get(source, source),
                "target": components.get(target, target), "protocol": protocol, "synchrony": synchrony,
                "rationale": rationale, "allowed": not bool(forbidden), "evidence_targets": ["code", "diagrams"],
                "verification": {"target": components.get(source, source), "property": "dependencies",
                                 "operator": "not_contains" if forbidden else "contains",
                                 "expected": components.get(target, target), "method": "dependency_graph"},
                "provenance": {"method": "controlled_language", "sources": [
                    source_ref(line.file, tree.files[line.file], line.line, line.line, section)]},
            }).dict())
    for record in adrs:
        if record["status"] != "accepted" or any(item["adr_id"] == record["id"] for item in contract["constraints_and_adrs"]):
            continue
        identifier = "decision-" + hashlib.sha256(record["id"].encode()).hexdigest()[:16]
        if identifier in identifiers:
            findings.append(finding("drift", "high", record["source"]["file"], 9, "CLAIM_ID_COLLISION",
                                    "Generated ADR claim collides with an existing ID", identifier,
                                    "Repair duplicate ADR IDs or rename the conflicting explicit claim."))
            continue
        append("constraints_and_adrs", CLAIM_MODELS["constraints_and_adrs"].parse_obj({
            "id": identifier, "statement": record["decision"], "constraint": record["decision"],
            "adr_id": record["id"], "status": record["status"], "alternatives": record["alternatives"],
            "consequences": record["consequences"], "quality_attributes": record["quality_attributes"],
            "superseded_by": record["superseded_by"], "evidence_targets": ["code", "cloud", "diagrams"],
            "provenance": {"method": "adr", "sources": [record["source"]]},
        }).dict())
    for category in CATEGORIES:
        contract[category].sort(key=lambda record: record["id"])
    return contract, findings


def integrity(record: dict[str, Any], category: str, contract: dict[str, Any], adrs: list[dict[str, Any]]) -> bool:
    component_ids = {item["id"] for item in contract["components"]}
    if category in {"dependencies", "flows"}:
        return record.get("source") in component_ids and record.get("target") in component_ids
    if category in {"volatility_zones", "cloud_resources"}:
        return record.get("component_id") in component_ids
    if category == "constraints_and_adrs":
        return any(item["id"] == record.get("adr_id") and item["status"] == record.get("status")
                   and lifecycle_valid(item, adrs) for item in adrs)
    return True
