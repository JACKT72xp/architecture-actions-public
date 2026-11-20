from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

from .config import InputError, load_yaml, safe_path
from .contracts import source_ref
from .models import DocumentTree, SourceLine, finding

EXTENSIONS = {".md", ".markdown", ".adoc", ".asciidoc"}
DIAGRAM_FORMATS = {".mmd": "mermaid", ".puml": "plantuml", ".plantuml": "plantuml",
                   ".dsl": "structurizr", ".drawio": "drawio", ".png": "png",
                   ".jpg": "jpg", ".jpeg": "jpeg", ".svg": "svg"}
ALIASES = {
    1: ("introduction and goals", "introduccion y objetivos", "einfuhrung und ziele"),
    2: ("architecture constraints", "constraints", "restricciones de arquitectura", "restricciones", "randbedingungen"),
    3: ("context and scope", "system scope and context", "contexto y alcance", "alcance y contexto", "kontextabgrenzung"),
    4: ("solution strategy", "estrategia de solucion", "losungsstrategie"),
    5: ("building block view", "vista de bloques", "vista de bloques de construccion", "bausteinsicht"),
    6: ("runtime view", "vista de ejecucion", "vista de tiempo de ejecucion", "laufzeitsicht"),
    7: ("deployment view", "vista de despliegue", "verteilungssicht"),
    8: ("crosscutting concepts", "cross cutting concepts", "conceptos transversales", "querschnittliche konzepte"),
    9: ("architecture decisions", "architectural decisions", "decisions", "decisiones de arquitectura", "decisiones arquitectonicas", "architekturentscheidungen"),
    10: ("quality requirements", "quality scenarios", "requisitos de calidad", "qualitatsanforderungen"),
    11: ("risks and technical debt", "riesgos y deuda tecnica", "risiken und technische schulden"),
    12: ("glossary", "glosario", "glossar"),
}
HEADING = re.compile(r"^(#{1,6}|={1,6})\s+(.+?)\s*#*\s*$")
INCLUDE = re.compile(r"^\s*include::([^\[]+)\[([^\]]*)\]\s*$")
PLACEHOLDER = re.compile(r"\b(?:TBD|TODO|FIXME|XXX|lorem ipsum|insert (?:text|description)|to be (?:defined|completed)|por definir|pendiente de completar|hier beschreiben|this section describes relevant requirements|the following table contains the top three|describe the building blocks of your system|describe the technical infrastructure used to execute your system)\b|<\s*(?:describe|insert)[^>]*>", re.I)


def normalize(text: str) -> str:
    ascii_text = "".join(char for char in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def section_number(title: str) -> int | None:
    normalized = re.sub(r"^\d+\s*", "", normalize(title))
    for number, aliases in ALIASES.items():
        if normalized in aliases:
            return number
    return None


def substantive(lines: list[SourceLine]) -> str:
    return "\n".join(line.text for line in lines if not PLACEHOLDER.search(line.text) and not HEADING.match(line.text))


def slug(text: str) -> str:
    return re.sub(r"[^\w\- ]", "", text.casefold()).replace(" ", "-")


class DocumentReader:
    def __init__(self, root: Path, config: dict[str, Any], excluded: list[Path] | None = None):
        self.root = root.resolve()
        self.limits = config["limits"]
        self.tree = DocumentTree()
        self.excluded = excluded or []
        self.total_bytes = 0
        self.expanded_bytes = 0
        self.markdown = MarkdownIt("commonmark")
        self.asset_hashes: dict[str, str] = {}

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def read(self, path: Path) -> str:
        path = safe_path(self.root, path)
        relative = self.relative(path)
        if relative in self.tree.files:
            return self.tree.files[relative]
        if len(self.tree.files) >= self.limits["max_files"]:
            raise InputError("Document file limit exceeded")
        size = path.stat().st_size
        if size > self.limits["max_file_bytes"] or self.total_bytes + size > self.limits["max_total_bytes"]:
            raise InputError("Document byte limit exceeded")
        with path.open("rb") as stream:
            raw = stream.read(self.limits["max_file_bytes"] + 1)
        if len(raw) > self.limits["max_file_bytes"] or self.total_bytes + len(raw) > self.limits["max_total_bytes"]:
            raise InputError("Document byte limit exceeded while reading")
        content = raw.decode("utf-8")
        self.total_bytes += len(raw)
        self.tree.files[relative] = content
        return content

    def candidates(self, path: Path, exclude: bool = True) -> list[Path]:
        if path.is_file():
            return [path] if path.suffix.lower() in EXTENSIONS else []
        if not path.exists():
            return []
        result = []
        for candidate in sorted(path.rglob("*")):
            if any(part.startswith(".") for part in candidate.relative_to(path).parts):
                continue
            if exclude and any(candidate == excluded or excluded in candidate.parents for excluded in self.excluded):
                continue
            if candidate.is_file() and candidate.suffix.lower() in EXTENSIONS:
                result.append(safe_path(self.root, candidate))
                if len(result) > self.limits["max_files"]:
                    raise InputError("Document file limit exceeded")
        return result

    def issue(self, file: str, rule: str, message: str, evidence: str, section: int | None = None) -> None:
        self.tree.findings.append(finding("structure", "high", file, section, rule, message, evidence,
                                          "Repair the local reference or provide complete, readable source documentation."))

    def expand(self, path: Path, stack: tuple[Path, ...] = ()) -> list[SourceLine]:
        relative = self.relative(path)
        if path in stack or len(stack) >= self.limits["max_include_depth"]:
            self.issue(relative, "DOC_INCLUDE_CYCLE", "Cyclic or excessively deep include", relative)
            return []
        try:
            content = self.read(path)
        except (OSError, UnicodeError, InputError):
            self.issue(relative, "DOC_UNREADABLE", "Document is absent, unsafe, unreadable, or exceeds limits", relative)
            return []
        result = []
        fence: str | None = None
        for number, text in enumerate(content.splitlines(), 1):
            stripped = text.strip()
            marker = re.match(r"^(`{3,}|~{3,}|----|\.\.\.\.)", stripped)
            if marker:
                token = marker.group(1)
                fence = None if fence and token[0] == fence[0] and len(token) >= len(fence) else (fence or token)
            match = INCLUDE.match(text) if not fence else None
            if match:
                self.tree.references_total += 1
                try:
                    if match.group(2).strip():
                        raise InputError("Include attributes require preprocessing")
                    target = safe_path(self.root, path.parent / unquote(match.group(1)))
                    if target.suffix.lower() not in EXTENSIONS or not target.is_file():
                        raise InputError("Unsupported include target")
                    if target in (*stack, path):
                        raise InputError("Cyclic include")
                    nested = self.expand(target, (*stack, path))
                    if nested:
                        self.tree.references_valid += 1
                        result.extend(nested)
                except (InputError, OSError):
                    self.issue(relative, "DOC_INCLUDE", "Unresolved, unsafe, cyclic, or unsupported include", f"line {number}: {text}")
            else:
                size = len(text.encode()) + 1
                if self.expanded_bytes + size > self.limits["max_expanded_bytes"]:
                    raise InputError("Expanded document byte limit exceeded")
                self.expanded_bytes += size
                result.append(SourceLine(relative, number, text))
        return result

    def analyze(self, docs: Path, diagrams: Path | None = None) -> DocumentTree:
        candidates = self.candidates(docs)
        if not candidates:
            self.issue(self.relative(docs), "DOC_MISSING", "No architecture documents found", self.relative(docs))
        included: set[Path] = set()
        for candidate in candidates:
            try:
                content = self.read(candidate)
                targets: list[str] = []
                if candidate.suffix.lower() in {".md", ".markdown"}:
                    for token in self.markdown.parse(content):
                        for child in token.children or []:
                            if child.type == "link_open":
                                targets.append(str(child.attrGet("href")))
                else:
                    targets += re.findall(r"(?:xref:|link:)([^\s\[]+)\[", content)
                for text in content.splitlines():
                    match = INCLUDE.match(text)
                    if match and not match.group(2):
                        try:
                            included.add(safe_path(self.root, candidate.parent / unquote(match.group(1))))
                        except InputError:
                            pass
                for target_url in targets:
                    parsed = urlsplit(target_url)
                    if parsed.scheme or parsed.netloc or not parsed.path:
                        continue
                    target = safe_path(self.root, candidate.parent / unquote(parsed.path))
                    excluded = any(target == item or item in target.parents for item in self.excluded)
                    if target not in candidates and not excluded and target.is_file() and target.suffix.lower() in EXTENSIONS:
                        candidates.append(target)
                        if len(candidates) > self.limits["max_files"]:
                            raise InputError("Document graph exceeds file limit")
            except (OSError, UnicodeError, InputError, ValueError):
                self.issue(self.relative(candidate), "DOC_UNREADABLE", "Cannot resolve document graph", self.relative(candidate))
        seen: set[tuple[str, int]] = set()
        roots = [candidate for candidate in candidates if candidate not in included]
        for candidate in roots + candidates:
            if any(file == self.relative(candidate) for file, _ in seen):
                continue
            self.scan(self.expand(candidate), candidate, seen)
        if diagrams:
            if not diagrams.exists():
                self.issue(self.relative(diagrams), "DOC_DIAGRAM_PATH", "Configured diagrams path is absent", self.relative(diagrams))
            else:
                assets = [diagrams] if diagrams.is_file() else diagrams.rglob("*")
                for asset in assets:
                    if asset.is_file() and asset.suffix.lower() in DIAGRAM_FORMATS:
                        self.diagram(asset, None)
        self.tree.diagrams.sort(key=lambda item: item["id"])
        self.tree.limitations.extend([
            "Remote links and diagrams are never fetched; local references are checked.",
            "AsciiDoc executable preprocessing, attributes in includes, and substitutions are unsupported and reported.",
            "Diagrams are inventoried and hashed, not rendered or interpreted as verified architecture.",
        ])
        return self.tree

    def scan(self, lines: list[SourceLine], candidate: Path, seen: set[tuple[str, int]]) -> None:
        headings: dict[int, tuple[int, str]] = {}
        ignored: set[int] = set()
        links: dict[int, list[str]] = {}
        diagram_blocks: dict[int, tuple[str, int]] = {}
        markdown_lines = {index for index, line in enumerate(lines) if Path(line.file).suffix.lower() in {".md", ".markdown"}}
        texts = [line.text for line in lines]
        if texts and texts[0] == "---":
            end = next((index for index in range(1, len(texts)) if texts[index] == "---"), None)
            if end is not None:
                try:
                    metadata = load_yaml("\n".join(texts[1:end]))
                    if not isinstance(metadata, dict):
                        raise InputError("Document metadata must be a mapping")
                    self.tree.metadata[self.relative(candidate)] = metadata
                except InputError:
                    self.issue(self.relative(candidate), "DOC_METADATA", "Invalid document metadata", "frontmatter")
                ignored.update(range(end + 1))
        if markdown_lines:
            content = "\n".join("" if index in ignored or index not in markdown_lines else text for index, text in enumerate(texts))
            tokens = self.markdown.parse(content)
            for index, token in enumerate(tokens):
                if token.map is None:
                    continue
                start, end = token.map
                if token.type == "heading_open":
                    headings[start] = (int(token.tag[1:]), tokens[index + 1].content)
                    ignored.update(range(start + 1, end))
                if token.type in {"fence", "code_block", "html_block"}:
                    ignored.update(range(start, end))
                    if token.type == "fence" and token.info.strip().lower() in {"mermaid", "plantuml", "structurizr"}:
                        diagram_blocks[start] = (token.info.strip().lower(), end)
                if token.type == "inline":
                    for child in token.children or []:
                        attribute = "href" if child.type == "link_open" else "src" if child.type == "image" else None
                        if attribute:
                            links.setdefault(start, []).append(str(child.attrGet(attribute)))
        if len(markdown_lines) < len(lines):
            fence: str | None = None
            pending: str | None = None
            for index, text in enumerate(texts):
                if index in markdown_lines:
                    continue
                block = re.fullmatch(r"\[(?:source,)?(mermaid|plantuml|structurizr)\]", text.strip())
                if block:
                    pending = block.group(1)
                    ignored.add(index)
                    continue
                if text.strip() in {"----", "....", "////"}:
                    marker = text.strip()
                    if fence is None:
                        fence = marker
                        if pending:
                            end = next((position + 1 for position in range(index + 1, len(texts))
                                        if texts[position].strip() == marker), index + 1)
                            diagram_blocks[index] = (pending, end)
                    elif fence == marker:
                        fence = None
                    ignored.add(index)
                    pending = None
                    continue
                if fence or text.startswith("//"):
                    ignored.add(index)
                else:
                    adoc_heading = HEADING.match(text)
                    if adoc_heading:
                        headings[index] = (len(adoc_heading.group(1)), adoc_heading.group(2))
                    adoc_attribute = re.fullmatch(r":([a-zA-Z0-9_-]+):\s*(.*)", text)
                    if adoc_attribute:
                        self.tree.metadata.setdefault(self.relative(candidate), {})[adoc_attribute.group(1)] = adoc_attribute.group(2)
                        ignored.add(index)
        section = section_number(candidate.stem)
        canonical_level = 0 if section is not None else 99
        previous_level = 0
        parents: list[tuple[int, str]] = []
        for index, line in enumerate(lines):
            key = (line.file, line.line)
            if key in seen:
                continue
            seen.add(key)
            if index in headings:
                level, title = headings[index]
                recognized = section_number(title)
                if recognized is not None:
                    section, canonical_level = recognized, level
                    self.tree.sections.setdefault(section, [])
                elif level <= canonical_level:
                    section = None
                valid = not previous_level or level <= previous_level + 1
                self.tree.headings_total += 1
                self.tree.headings_valid += int(valid)
                if not valid:
                    self.issue(line.file, "DOC_HEADING", "Heading skips a hierarchy level", f"line {line.line}", section)
                previous_level = level
                while parents and parents[-1][0] >= level:
                    parents.pop()
                identifier = f"{line.file}:{line.line}"
                self.tree.headings.append({"id": identifier, "parent": parents[-1][1] if parents else None,
                                           "level": level, "title": title, "section": section,
                                           "source": source_ref(line.file, self.tree.files[line.file], line.line, line.line, section)})
                parents.append((level, identifier))
            self.tree.locations[key] = section
            if index in diagram_blocks:
                kind, end = diagram_blocks[index]
                last = lines[min(end, len(lines)) - 1]
                end_line = last.line if last.file == line.file else line.line
                self.diagram(self.root / line.file, line, kind, section, end_line)
            if index in ignored or index in headings:
                continue
            if index in markdown_lines and re.match(r"^#{1,6}[^#\s]", line.text):
                self.tree.headings_total += 1
                self.issue(line.file, "DOC_HEADING", "Markdown heading needs a space", f"line {line.line}", section)
            if section:
                self.tree.sections.setdefault(section, []).append(line)
            self.references(line, section, links.get(index, []) if index in markdown_lines else None)

    def diagram(self, path: Path, origin: SourceLine | None, inline: str | None = None,
                section: int | None = None, end_line: int | None = None) -> None:
        path = safe_path(self.root, path)
        file = self.relative(path)
        source_file = origin.file if origin else file
        source_text = self.tree.files.get(source_file, "")
        source = source_ref(source_file, source_text, origin.line if origin else 1,
                            end_line if end_line is not None else (origin.line if origin else 1), section)
        kind = "inline" if inline else "local_file"
        identifier = "diagram-" + hashlib.sha256(f"{file}:{source_file}:{source['line']}:{kind}".encode()).hexdigest()[:16]
        if any(item["id"] == identifier for item in self.tree.diagrams):
            return
        if len(self.tree.diagrams) >= self.limits["max_files"]:
            raise InputError("Diagram count limit exceeded")
        digest = None
        status = "missing"
        if path.is_file():
            size = path.stat().st_size
            if file in self.asset_hashes:
                digest, status = self.asset_hashes[file], "available"
            elif size > self.limits["max_file_bytes"]:
                status = "unsupported"
            elif file not in self.tree.files and self.total_bytes + size > self.limits["max_total_bytes"]:
                raise InputError("Combined document and diagram byte limit exceeded")
            else:
                with path.open("rb") as stream:
                    raw = stream.read(self.limits["max_file_bytes"] + 1)
                if len(raw) > self.limits["max_file_bytes"]:
                    raise InputError("Diagram size limit exceeded")
                digest = hashlib.sha256(raw).hexdigest()
                status = "available"
                self.asset_hashes[file] = digest
                if file not in self.tree.files:
                    self.total_bytes += len(raw)
            if origin is None and digest is not None:
                source["sha256"] = digest
        self.tree.diagrams.append({"id": identifier, "file": file, "format": inline or DIAGRAM_FORMATS.get(path.suffix.lower(), "other"),
                                   "kind": kind, "source": source, "sha256": digest,
                                   "status": status, "related_claim_ids": []})

    def references(self, line: SourceLine, section: int | None, parsed_targets: list[str] | None = None) -> None:
        targets = re.findall(r"!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)", line.text)
        targets += re.findall(r"(?:image::?|xref:|link:)([^\s\[]+)\[", line.text)
        targets += re.findall(r"^\s*\[[^\]]+\]:\s*(\S+)", line.text)
        targets += [f"#{anchor}" for anchor in re.findall(r"<<([^,>]+)(?:,[^>]*)?>>", line.text)]
        definitions = {label.casefold().strip() for label in re.findall(r"(?m)^\s*\[([^\]]+)\]:", self.tree.files.get(line.file, ""))}
        for label, reference in re.findall(r"!?\[([^\]]+)\]\[([^\]]*)\]", line.text):
            if (reference or label).casefold().strip() not in definitions:
                self.tree.references_total += 1
                self.issue(line.file, "DOC_REFERENCE", "Undefined Markdown reference label", f"line {line.line}: {reference or label}", section)
        if parsed_targets is not None:
            for target in targets:
                try:
                    urlsplit(target.strip("<>"))
                except ValueError:
                    if target not in parsed_targets:
                        parsed_targets.append(target)
        for target in parsed_targets if parsed_targets is not None else targets:
            try:
                parsed = urlsplit(target.strip("<>"))
            except ValueError:
                self.tree.references_total += 1
                self.issue(line.file, "DOC_REFERENCE", "Malformed link URL", f"line {line.line}: {target}", section)
                continue
            if parsed.scheme in {"http", "https", "mailto"}:
                if Path(parsed.path).suffix.lower() in DIAGRAM_FORMATS:
                    identifier = "diagram-" + hashlib.sha256(f"{line.file}:{line.line}:{target}".encode()).hexdigest()[:16]
                    if len(self.tree.diagrams) >= self.limits["max_files"]:
                        raise InputError("Diagram count limit exceeded")
                    self.tree.diagrams.append({
                        "id": identifier, "file": target, "format": DIAGRAM_FORMATS[Path(parsed.path).suffix.lower()],
                        "kind": "remote_reference", "source": source_ref(line.file, self.tree.files[line.file],
                                                                        line.line, line.line, section),
                        "sha256": None, "status": "not_fetched", "related_claim_ids": [],
                    })
                continue
            self.tree.references_total += 1
            try:
                if parsed.scheme or parsed.netloc or "{" in target:
                    raise InputError("Unsupported reference")
                path = safe_path(self.root, (self.root / line.file).parent / unquote(parsed.path)) if parsed.path else self.root / line.file
                if path.suffix.lower() in DIAGRAM_FORMATS:
                    self.diagram(path, line, section=section)
                if not path.is_file():
                    raise InputError("Missing reference")
                if parsed.fragment and path.suffix.lower() in EXTENSIONS:
                    content = self.read(path)
                    anchors = set(re.findall(r"\[\[([^,\]]+)", content)) | set(re.findall(r"\{#([^}]+)\}", content))
                    counts: dict[str, int] = {}
                    if path.suffix.lower() in {".md", ".markdown"}:
                        tokens = self.markdown.parse(content)
                        titles = [tokens[index + 1].content for index, token in enumerate(tokens) if token.type == "heading_open"]
                    else:
                        titles = [match.group(2) for text in content.splitlines() if (match := HEADING.match(text))]
                    for title in titles:
                        anchor = slug(title)
                        occurrence = counts.get(anchor, 0)
                        anchors.add(anchor if not occurrence else f"{anchor}-{occurrence}")
                        anchors.add("_" + re.sub(r"[^\w ]", "", title.casefold()).replace(" ", "_"))
                        counts[anchor] = occurrence + 1
                    if unquote(parsed.fragment) not in anchors:
                        raise InputError("Missing anchor")
                self.tree.references_valid += 1
            except (InputError, OSError, UnicodeError, ValueError):
                self.issue(line.file, "DOC_REFERENCE", "Broken, unsafe, or unresolved local reference", f"line {line.line}: {target}", section)
