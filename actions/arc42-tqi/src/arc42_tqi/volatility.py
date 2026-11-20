from __future__ import annotations

import re
from typing import Any

from .claims import AXES, integrity, meaningful
from .documents import substantive
from .models import DocumentTree, Finding, Metric, finding


def assess_volatility(tree: DocumentTree, claims: dict[str, Any], adrs: list[dict[str, Any]],
                      history: dict[str, Any], required: bool) -> tuple[dict[str, Metric], list[Finding]]:
    zones = claims["volatility_zones"]
    findings: list[Finding] = []
    declared = {(item["component_id"], item["axis"]) for item in zones}
    missing_axes = {(component["id"], axis) for component in claims["components"]
                    for axis in component["declared_volatility"]} - declared
    represented_sections = {source["section"] for zone in zones for source in zone["provenance"]["sources"]}
    unclassified = {section for section, lines in tree.sections.items() if section not in represented_sections
                    and re.search(r"\b(?:volatile|volatility|volatilidad|volatil|volatilitat)\b",
                                  substantive(lines), re.I)}
    for component, axis in sorted(missing_axes):
        findings.append(finding("volatility", "high", "", None, "VOL_AXIS_UNMAPPED",
                                "Declared component volatility has no corresponding zone", f"{component}:{axis}",
                                "Document a zone for this component and axis with encapsulation and mitigation."))
    for section in sorted(unclassified):
        findings.append(finding("volatility", "medium", "", section, "VOL_UNCLASSIFIED",
                                "Volatility prose lacks a structured zone", str(section),
                                "Link an explicit volatility zone to this section."))
    denominator = max(len(zones) + len(missing_axes) + len(unclassified), int(required))
    counts = {"classification": 0, "encapsulation": 0, "impact_mitigation": 0}
    for zone in zones:
        checks = {
            "classification": zone["axis"] in AXES and integrity(zone, "volatility_zones", claims, adrs),
            "encapsulation": meaningful(zone["encapsulation"]),
            "impact_mitigation": all(meaningful(zone[key]) for key in ("propagation_risk", "impact", "mitigation")),
        }
        for key, passed in checks.items():
            counts[key] += int(passed)
            if not passed:
                source = zone["provenance"]["sources"][0]
                findings.append(finding("volatility", "high", source["file"], source["section"],
                                        "VOL_" + key.upper(), f"Zone fails {key} evidence check", zone["id"],
                                        "Specify the change axis, information-hiding boundary, impact and mitigation."))
    if not zones and required:
        findings.append(finding("volatility", "high", "", None, "VOL_MISSING", "No volatility zones declared",
                                "0 zones", "Document likely change axes and their isolation strategies."))
    metrics = {key: Metric(value, denominator, f"Zones satisfying {key}; missing declared axes and unclassified sections count as deficits",
                           ("/claims/volatility_zones", "/claims/components", "/sections"),
                           None if denominator else "Volatility zones explicitly not applicable")
               for key, value in counts.items()}
    hotspots = history["hotspots"]
    couplings = history["temporal_couplings"]
    available = history["status"] in {"available", "truncated"}
    for hotspot in hotspots:
        if not hotspot["aligned"]:
            findings.append(finding("volatility", "medium", hotspot["file"], None, "VOL_HOTSPOT",
                                    "Frequently changed design lacks a current associated decision or risk review",
                                    f"{hotspot['changes']} changes; staleness={hotspot['staleness_days']}",
                                    "Update the associated ADR/risk document and its reviewed_against commit evidence."))
    for coupling in couplings:
        if not coupling["association_declared"]:
            findings.append(finding("volatility", "low", coupling["source_file"], None, "VOL_TEMPORAL_COUPLING",
                                    "Repeated co-changes have no documented association", coupling["target_file"],
                                    "Review whether the co-change pattern reveals an undocumented change-propagation risk."))
    total = len(hotspots) + len(couplings) if available else 0
    satisfied = sum(item["aligned"] for item in hotspots) + sum(item["association_declared"] for item in couplings)
    metrics["evolution"] = Metric(satisfied if available else 0, total,
                                  "Aligned hotspots and declared temporal couplings / detected evolutionary signals",
                                  ("/history/hotspots", "/history/temporal_couplings"),
                                  None if total else history["reason"] or "No evolutionary signals in the analyzed window")
    return metrics, findings
