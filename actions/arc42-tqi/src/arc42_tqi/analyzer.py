from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from . import __version__
from .adrs import parse_adrs
from .architecture_review import assess_review
from .claims import extract_claims
from .config import InputError, load_config, safe_path, validate
from .documents import DIAGRAM_FORMATS, DocumentReader
from .history import GitLimitError, evolution, git, metadata
from .models import SEVERITIES
from .rules import assess, section_results
from .scoring import calculate


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def analyze_repository(root: Path, docs_path: str = "docs", adr_path: str = "docs/adr",
                       diagrams_path: str = "", config_path: str = "", output_dir: str = ".arc42-tqi",
                       min_tqi: float | None = None, fail_on_severity: str | None = None,
                       review_overrides: dict[str, str] | None = None
                       ) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    if not root.is_dir():
        raise InputError("Repository root does not exist")
    config = load_config(root, config_path or None, review_overrides)
    if min_tqi is not None:
        config["min_tqi"] = min_tqi
    if fail_on_severity is not None:
        config["fail_on_severity"] = fail_on_severity
    validate(config)
    docs, adr, output = (safe_path(root, value) for value in (docs_path, adr_path, output_dir))
    diagrams = safe_path(root, diagrams_path) if diagrams_path else None
    if any(character in output_dir for character in "\r\n") or output == root:
        raise InputError("Output must be a single-line repository subdirectory")
    if any(output == source or output in source.parents for source in [docs, adr, *([diagrams] if diagrams else [])]):
        raise InputError("Output must not contain or replace source inputs")
    reader = DocumentReader(root, config, excluded=[output, adr])
    tree = reader.analyze(docs, diagrams)
    adrs, adr_findings = parse_adrs(reader, adr)
    claims, claim_findings = extract_claims(tree, adrs, config)
    section_files = {section: {line.file for line in lines} for section, lines in tree.sections.items()}
    files = set().union(*section_files.values()) if section_files else set()
    supporting = {record["source"]["file"] for record in adrs} | section_files.get(11, set())
    associations: dict[str, list[str]] = {}
    section_ids = {file: sorted(section for section, paths in section_files.items() if file in paths) for file in files}
    for section, paths in section_files.items():
        linked_adrs = {edge["adr_id"] for edge in tree.traceability_edges
                       if edge["section_id"] == section and edge["from_adr"] and edge["from_section"]}
        related = {record["source"]["file"] for record in adrs if record["id"] in linked_adrs}
        for line in tree.sections[section]:
            targets = []
            for token in reader.markdown.parse(line.text):
                for child in token.children or []:
                    if child.type == "link_open":
                        targets.append(str(child.attrGet("href")))
            targets.extend(re.findall(r"(?:xref:|link:)([^\s\[]+)\[", line.text))
            for target in targets:
                try:
                    parsed = urlsplit(target)
                    if not parsed.scheme and not parsed.netloc and parsed.path:
                        path = safe_path(root, (root / line.file).parent / unquote(parsed.path))
                        relative = path.relative_to(root).as_posix()
                        if relative in section_files.get(11, set()):
                            related.add(relative)
                except (ValueError, InputError):
                    continue
        for file in paths:
            associations[file] = sorted(set(associations.get(file, [])) | related)
    history = evolution(root, files, supporting, {
        **config["history"], "max_git_output_bytes": config["limits"]["max_git_output_bytes"],
        "associations": associations, "section_ids": section_ids,
        "reviewed_against": {record["source"]["file"]: record["reviewed_against"] for record in adrs},
    })
    metrics, rule_findings = assess(tree, adrs, claims, history, config)
    parse_deficits = {
        "decisions": sum(item.rule_id == "ADR_PARSE" for item in adr_findings),
        "drift": sum(item.rule_id == "CLAIM_PARSE" for item in claim_findings),
    }
    for dimension, deficit in parse_deficits.items():
        if deficit and not (dimension == "drift" and config["review"]["profile"] == "arc42"):
            for name, metric in metrics[dimension].items():
                if name != "coverage":
                    metrics[dimension][name] = replace(
                        metric, applicable=metric.applicable + deficit,
                        description=metric.description + "; each rejected input document/block adds one deficit",
                    )
    review, review_findings = assess_review(tree, config)
    scoped_findings = tree.findings + adr_findings + claim_findings + rule_findings
    if config["review"]["profile"] == "arc42":
        scoped_findings = [item for item in scoped_findings if item.dimension not in {"volatility", "drift"}]
    all_findings = {item.id: item for item in scoped_findings + review_findings}
    findings = sorted(all_findings.values(), key=lambda item: (SEVERITIES.index(item.severity), item.file, item.rule_id, item.id))
    inventory: list[dict[str, Any]] = [{"file": file, "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode()),
                  "format": "markdown" if Path(file).suffix.lower() in {".md", ".markdown"} else "asciidoc"}
                 for file, text in sorted(tree.files.items())]
    known = set(tree.files)
    for diagram in tree.diagrams:
        if diagram["file"] not in known and diagram["status"] == "available":
            path = safe_path(root, diagram["file"])
            inventory.append({"file": diagram["file"], "sha256": diagram["sha256"],
                              "bytes": path.stat().st_size, "format": DIAGRAM_FORMATS.get(path.suffix.lower(), "other")})
            known.add(diagram["file"])
    inventory.sort(key=lambda item: item["file"])
    repo_metadata = {**metadata(root), "source_tree_sha256": hashlib.sha256(canonical_json(inventory).encode()).hexdigest(),
                     "config_sha256": hashlib.sha256(canonical_json(config).encode()).hexdigest()}
    git_version = None
    if repo_metadata["git_available"]:
        try:
            git_version = git(root, "--version").strip()
        except (OSError, GitLimitError, subprocess.SubprocessError):
            pass
    claims.update(metadata=repo_metadata, applicability=config["applicability"])
    report: dict[str, Any] = {
        "schema_version": "1.1", "scoring_version": "2.0" if config["review"]["profile"] == "arc42" else "1.0",
        "architecture_review": review,
        "tool": {"name": "arc42-tqi-action", "version": __version__, "python_version": platform.python_version(),
                 "git_version": git_version},
        "metadata": repo_metadata, **calculate(metrics, config), "conformance_status": "not_evaluated",
        "effective_config": config, "sections": section_results(tree, config), "adrs": adrs,
        "traceability_edges": tree.traceability_edges, "history": history, "source_inventory": inventory,
        "findings": [item.to_dict() for item in findings], "diagnostics": [], "limitations": tree.limitations + [
            "TQI measures explicit documentation evidence, not implementation conformance.",
            "Volatility and temporal coupling are review signals, not causal proof.",
            "Git signals are file-level; edits within a combined arc42 file cannot prove that its risk section was reviewed.",
        ],
    }
    if config["review"]["profile"] == "arc42":
        report["limitations"] = tree.limitations + [
            "TQI measures documentation evidence, not architecture correctness or implementation conformance.",
            "Volatility, Git evolution, and structured audit claims are excluded from this profile's score and gate.",
            "Review evidence references establish availability, not semantic correctness or diagram topology.",
        ]
    if history["status"] not in {"available", "disabled"}:
        report["diagnostics"].append({"code": "HISTORY_" + history["status"].upper(), "level": "warning",
                                      "message": history["reason"], "remediation": "Use actions/checkout@v4 with fetch-depth: 0."
                                      if history["status"] == "shallow" else "Inspect Git availability and configured history limits."})
    for dimension, details in report["dimensions"].items():
        if details["weight"] and not any(item["normalized_weight"] for item in details["metrics"].values()):
            report["diagnostics"].append({"code": "NO_APPLICABLE_METRICS", "level": "warning",
                                          "message": f"{dimension} has no positive-weight applicable metrics; score is zero.",
                                          "remediation": "Review applicability and metric weights."})
    threshold = config["fail_on_severity"]
    blocking = [item.id for item in findings if threshold != "none"
                and SEVERITIES.index(item.severity) <= SEVERITIES.index(threshold)]
    score_passed = report["tqi_score"] >= config["min_tqi"]
    report["quality_gate"] = {"min_tqi": config["min_tqi"], "fail_on_severity": threshold, "score_passed": score_passed,
                              "severity_passed": not blocking, "passed": score_passed and not blocking,
                              "blocking_finding_ids": blocking}
    return report, claims
