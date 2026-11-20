from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from pydantic import ValidationError

from .config import InputError, load_yaml, safe_path
from .contracts import ADR, source_ref
from .documents import HEADING, DocumentReader, normalize
from .models import Finding, finding

STATUSES = {"proposed", "accepted", "deprecated", "superseded"}
STATUS_ALIASES = {"propuesto": "proposed", "aceptado": "accepted", "obsoleto": "deprecated",
                  "reemplazado": "superseded", "vorgeschlagen": "proposed", "angenommen": "accepted",
                  "veraltet": "deprecated", "ersetzt": "superseded"}
FIELD_ALIASES = {
    "context": ("context", "contexto", "kontext"),
    "decision": ("decision", "entscheidung"),
    "consequences": ("consequences", "consecuencias", "konsequenzen", "trade offs", "tradeoffs"),
    "alternatives": ("alternatives", "alternatives considered", "considered options", "alternativas", "alternativen"),
    "quality_attributes": ("quality attributes", "atributos de calidad", "qualitatsmerkmale"),
    "positive": ("positive consequences", "benefits", "consecuencias positivas", "positive konsequenzen"),
    "negative": ("negative consequences", "costs", "consecuencias negativas", "negative konsequenzen"),
}


def _paragraphs(value: str) -> list[str]:
    return [re.sub(r"^\s*[-*]\s+", "", line).strip() for line in value.splitlines() if line.strip()]


def parse_adrs(reader: DocumentReader, path: Path) -> tuple[list[dict[str, Any]], list[Finding]]:
    records: list[dict[str, Any]] = []
    findings: list[Finding] = []
    for candidate in reader.candidates(path, exclude=False):
        relative = reader.relative(candidate)
        try:
            original = reader.read(candidate)
            text = original
            metadata: dict[str, Any] = {}
            frontmatter = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
            if frontmatter:
                metadata = load_yaml(frontmatter.group(1))
                if not isinstance(metadata, dict):
                    raise InputError("ADR metadata must be a mapping")
                text = text[frontmatter.end():]
            number = re.search(r"(?:ADR[-_ ]?)?(\d+)", candidate.stem, re.I)
            title = next((match.group(2) for line in text.splitlines() if (match := HEADING.match(line))), None)
            if title is None and not metadata:
                continue
            fields = {key: "" for key in FIELD_ALIASES}
            current = None
            fence = None
            for line in text.splitlines():
                marker = re.match(r"^(\x60{3,}|~{3,}|----|\.\.\.\.)", line)
                if marker:
                    fence = None if fence == marker.group(1) else marker.group(1)
                    continue
                if fence:
                    continue
                heading = HEADING.match(line)
                if heading:
                    label = normalize(heading.group(2))
                    current = next((key for key, aliases in FIELD_ALIASES.items() if label in aliases), None)
                elif current:
                    fields[current] += line + "\n"
            status = metadata.get("status")
            if status is None:
                match = re.search(r"(?:^|\n)\s*[-*]?\s*\*{0,2}(?:status|estado)\*{0,2}\s*:\s*\*{0,2}([^\n*]+)", text, re.I)
                if match is None:
                    match = re.search(r"^(?:#{1,6}|={1,6})\s+(?:status|estado)\s*\n+([^\n]+)", text, re.I | re.M)
                status = match.group(1).strip() if match else None
            if isinstance(status, str):
                status = STATUS_ALIASES.get(status.casefold(), status.casefold())
            alternatives = metadata.get("alternatives")
            if alternatives is None:
                alternatives = []
                for item in _paragraphs(fields["alternatives"]):
                    match = re.fullmatch(r"(.+?)\s+(?:rejected because|descartada porque|abgelehnt weil)\s+(.+)", item, re.I)
                    alternatives.append({"name": match.group(1) if match else item,
                                         "rejection_reason": match.group(2) if match else None})
            consequences = metadata.get("consequences", {
                "positive": _paragraphs(fields["positive"]), "negative": _paragraphs(fields["negative"]),
            })
            if fields["consequences"].strip() and not fields["positive"].strip() and not fields["negative"].strip():
                findings.append(finding("decisions", "medium", relative, 9, "ADR_UNCLASSIFIED_CONSEQUENCES",
                                        "Consequences are not classified as benefits and costs", relative,
                                        "Use positive/negative consequences headings or structured frontmatter."))
            record = ADR.parse_obj({
                "id": metadata.get("id", f"ADR-{int(number.group(1)):04d}" if number else candidate.stem),
                "title": metadata.get("title", title), "status": status,
                "source": source_ref(relative, original, section=9),
                "context": metadata.get("context", fields["context"].strip() or None),
                "decision": metadata.get("decision", fields["decision"].strip() or None),
                "alternatives": alternatives, "consequences": consequences,
                "quality_attributes": metadata.get("quality_attributes", _paragraphs(fields["quality_attributes"])),
                **{key: metadata.get(key, []) for key in ("arc42_sections", "supersedes", "related", "reviewed_against")},
                "superseded_by": metadata.get("superseded_by"),
            }).dict()
            records.append(record)
        except (InputError, ValidationError, OSError, UnicodeError) as error:
            findings.append(finding("decisions", "high", relative, 9, "ADR_PARSE",
                                    "ADR does not satisfy the typed contract", type(error).__name__,
                                    "Use typed metadata, structured alternatives and consequences, and valid lifecycle status."))
    records.sort(key=lambda item: (item["id"], item["source"]["file"]))
    reader.tree.traceability_edges = traceability(reader, records)
    for record in records:
        if not lifecycle_valid(record, records):
            findings.append(finding("decisions", "high", record["source"]["file"], 9, "ADR_LIFECYCLE",
                                    "Duplicate, cyclic, inconsistent, or unresolved ADR lifecycle", record["id"],
                                    "Use unique IDs and reciprocal, acyclic supersession links ending at an accepted decision."))
    return records, findings


def traceability(reader: DocumentReader, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for record in records:
        for section in range(1, 13):
            evidence: list[dict[str, Any]] = []
            for line in reader.tree.sections.get(section, []):
                targets: list[str] = []
                for token in reader.markdown.parse(line.text):
                    for child in token.children or []:
                        if child.type == "link_open":
                            targets.append(str(child.attrGet("href")))
                targets.extend(re.findall(r"(?:xref:|link:)([^\s\[]+)\[", line.text))
                for target in targets:
                    try:
                        parsed = urlsplit(target)
                        if parsed.scheme or parsed.netloc:
                            continue
                        linked = safe_path(reader.root, (reader.root / line.file).parent / unquote(parsed.path))
                        if reader.relative(linked) == record["source"]["file"]:
                            evidence.append(source_ref(line.file, reader.tree.files[line.file], line.line, line.line, section))
                    except (ValueError, InputError):
                        continue
            declared = section in record["arc42_sections"]
            if declared or evidence:
                edges.append({"adr_id": record["id"], "section_id": section, "from_adr": declared,
                              "from_section": bool(evidence), "adr_evidence": [record["source"]] if declared else [],
                              "section_evidence": evidence})
    return edges


def lifecycle_valid(record: dict[str, Any], records: list[dict[str, Any]]) -> bool:
    by_id = {item["id"]: item for item in records}
    if sum(item["id"] == record["id"] for item in records) != 1 or record["status"] not in STATUSES:
        return False
    if any(identifier not in by_id or identifier == record["id"] for identifier in record["related"]):
        return False
    for previous in record["supersedes"]:
        if previous not in by_id or by_id[previous]["superseded_by"] != record["id"]:
            return False
    if record["status"] != "superseded":
        return record["superseded_by"] is None
    visited: set[str] = set()
    current = record
    while current["status"] == "superseded":
        if current["id"] in visited:
            return False
        visited.add(current["id"])
        successor = by_id.get(current["superseded_by"])
        if successor is None or current["id"] not in successor["supersedes"]:
            return False
        current = successor
    return current["status"] == "accepted" and current["superseded_by"] is None
