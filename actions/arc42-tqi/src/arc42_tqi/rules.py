from __future__ import annotations

import hashlib
import re
from typing import Any

from .adrs import lifecycle_valid
from .claims import CATEGORIES, complete, integrity, meaningful, verifiable
from .documents import ALIASES, PLACEHOLDER, substantive
from .models import DocumentTree, Finding, Metric, finding
from .volatility import assess_volatility


def section_results(tree: DocumentTree, config: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for section in range(1, 13):
        lines = tree.sections.get(section, [])
        words = len(re.findall(r"\b\w+\b", substantive(lines)))
        sources = [heading["source"] for heading in tree.headings if heading["section"] == section]
        results.append({"id": section, "canonical_name": ALIASES[section][0], "sources": sources,
                        "substantive_words": words, "placeholder_count": sum(bool(PLACEHOLDER.search(line.text)) for line in lines),
                        "critical": section in config["critical_sections"], "present": words > 0})
    return results


def assess(tree: DocumentTree, adrs: list[dict[str, Any]], claims: dict[str, Any],
           history: dict[str, Any], config: dict[str, Any]) -> tuple[dict[str, dict[str, Metric]], list[Finding]]:
    findings: list[Finding] = []
    sections = section_results(tree, config)
    for section in sections:
        file = section["sources"][0]["file"] if section["sources"] else ""
        if not section["present"]:
            findings.append(finding("structure", "high", file, section["id"], "ARC42_EMPTY",
                                    "Canonical section is missing or empty", str(section["id"]),
                                    "Write substantive architecture documentation for this section."))
        if section["critical"] and section["substantive_words"] < config["min_section_words"]:
            findings.append(finding("structure", "medium", file, section["id"], "ARC42_DEPTH",
                                    "Critical section lacks substantive depth", str(section["substantive_words"]),
                                    f"Provide at least {config['min_section_words']} substantive words."))
        for line in tree.sections.get(section["id"], []):
            if PLACEHOLDER.search(line.text):
                findings.append(finding("structure", "medium", line.file, section["id"], "ARC42_PLACEHOLDER",
                                        "Unresolved placeholder or template text", f"line {line.line}: {line.text}",
                                        "Replace the template with a concrete architectural statement."))
    structure = {
        "coverage": Metric(sum(item["present"] for item in sections), 12, "Populated canonical sections / 12", ("/sections",)),
        "depth": Metric(sum(item["critical"] and item["substantive_words"] >= config["min_section_words"] for item in sections),
                        len(config["critical_sections"]), "Critical sections meeting minimum substantive word count", ("/sections",)),
        "placeholders": Metric(sum(item["present"] and item["placeholder_count"] == 0 for item in sections), 12,
                               "Populated sections without placeholders / 12", ("/sections",)),
        "references": Metric(tree.references_valid, tree.references_total, "Resolvable local references / local references",
                             ("/source_inventory",), None if tree.references_total else "No local references"),
        "headings": Metric(tree.headings_valid, max(tree.headings_total, 1), "Valid headings / headings; missing headings score zero",
                           ("/sections",)),
        "diagrams": Metric(sum(item["status"] == "available" for item in tree.diagrams
                               if item["kind"] != "remote_reference"),
                           sum(item["kind"] != "remote_reference" for item in tree.diagrams),
                           "Available local or inline diagrams / local or inline diagrams",
                           ("/claims/diagram_inventory",), None if tree.diagrams else "No diagrams declared"),
    }
    counts = {key: 0 for key in ("completeness", "lifecycle", "tradeoffs", "quality_attributes", "bidirectional_traceability")}
    if not adrs:
        findings.append(finding("decisions", "high", "", 9, "ADR_MISSING", "No readable ADRs found", "0 ADRs",
                                "Document lifecycle, context, decision, alternatives, consequences and section links."))
    for record in adrs:
        edges = [edge for edge in tree.traceability_edges if edge["adr_id"] == record["id"]]
        checks = {
            "completeness": all(meaningful(record[key]) for key in ("id", "title", "context", "decision"))
                            and any(meaningful(items) for items in record["consequences"].values()),
            "lifecycle": lifecycle_valid(record, adrs),
            "tradeoffs": meaningful(record["alternatives"]) and meaningful(record["consequences"]),
            "quality_attributes": meaningful(record["quality_attributes"]),
            "bidirectional_traceability": bool(edges) and all(edge["from_adr"] and edge["from_section"]
                and sections[edge["section_id"] - 1]["present"] for edge in edges),
        }
        for name, valid in checks.items():
            counts[name] += int(valid)
            if not valid:
                findings.append(finding("decisions", "high" if name == "lifecycle" else "medium",
                                        record["source"]["file"], 9, "ADR_" + name.upper(),
                                        f"ADR fails {name} check", record["id"],
                                        "Complete typed ADR evidence and reciprocal links to populated sections."))
    decisions = {name: Metric(count, max(len(adrs), 1), f"ADRs satisfying {name} / ADRs; absence scores zero",
                              ("/adrs", "/traceability_edges")) for name, count in counts.items()}
    volatility, volatility_findings = assess_volatility(tree, claims, adrs, history,
                                                        config["applicability"]["volatility_zones"]["required"])
    findings.extend(volatility_findings)
    required = {category for category in CATEGORIES if config["applicability"][category]["required"]}
    active = required | {category for category in CATEGORIES if claims[category]}
    total = sum(len(claims[category]) for category in active)
    missing = sum(not claims[category] for category in required)
    counters = {name: 0 for name in ("completeness", "provenance", "atomic_verifiability", "integrity")}
    for category in CATEGORIES:
        for record in claims[category]:
            sources = record["provenance"]["sources"]
            provenance = bool(sources) and all(
                source["file"] in tree.files
                and 1 <= source["line"] <= source["end_line"] <= len(tree.files[source["file"]].splitlines())
                and source["sha256"] == hashlib.sha256(tree.files[source["file"]].encode()).hexdigest()
                for source in sources)
            checks = {"completeness": complete(record, category), "provenance": provenance,
                      "atomic_verifiability": verifiable(record),
                      "integrity": integrity(record, category, claims, adrs)}
            for name, valid in checks.items():
                counters[name] += int(valid)
                if not valid:
                    source = sources[0]
                    findings.append(finding("drift", "high" if name == "integrity" else "medium",
                                            source["file"], source["section"], "CLAIM_" + name.upper(),
                                            f"Claim fails {name}", record["id"],
                                            "Supply complete fields, resolvable IDs, and one typed verification predicate."))
    for category in sorted(required):
        if not claims[category]:
            findings.append(finding("drift", "high", "", None, "CLAIM_CATEGORY_MISSING",
                                    "Required claim category is empty", category,
                                    "Declare claims or document an explicit non-applicability reason in configuration."))
    drift = {"coverage": Metric(sum(bool(claims[category]) for category in active), len(active),
                                "Nonempty applicable categories / applicable categories", ("/claims",))}
    drift.update({name: Metric(value, total + missing, f"Claims satisfying {name}; each missing required category adds one deficit",
                               ("/claims",), None if total + missing else "All claim categories explicitly not applicable")
                  for name, value in counters.items()})
    return {"structure": structure, "decisions": decisions, "volatility": volatility, "drift": drift}, findings
