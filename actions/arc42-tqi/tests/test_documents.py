from __future__ import annotations

from pathlib import Path

import pytest

from arc42_tqi.config import InputError, load_config, safe_path
from arc42_tqi.documents import DocumentReader, section_number


@pytest.mark.parametrize("title,expected", [("05 Building Block View", 5), ("5. Vista de bloques de construcción", 5), ("Einführung und Ziele", 1), ("10 Qualitätsanforderungen", 10), ("Risiken und technische Schulden", 11), ("5. Something else", None)])
def test_section_aliases(title: str, expected: int | None) -> None:
    assert section_number(title) == expected


def test_include_graph_anchors_and_fences(tmp_path: Path) -> None:
    (tmp_path / "architecture.adoc").write_text("= Architecture\n\ninclude::part.md[]\n\n== 6. Runtime View\nCalls are asynchronous.\n")
    (tmp_path / "part.md").write_text("## 5. Building Block View\nAn isolated service.\n[valid](part.md#5-building-block-view)\n```text\n## 10. Quality Requirements\ninclude::missing.adoc[]\n```\n")
    tree = DocumentReader(tmp_path, load_config(tmp_path, None)).analyze(tmp_path)
    assert set(tree.sections) == {5, 6}
    assert tree.references_total == 2
    assert tree.references_valid == 2
    assert not tree.findings
    assert sum(line.text == "An isolated service." for line in tree.sections[5]) == 1


def test_broken_references_and_cycles(tmp_path: Path) -> None:
    (tmp_path / "a.adoc").write_text("== 5. Building Block View\ninclude::b.adoc[]\nimage::lost.png[]\nxref:a.adoc#absent[missing]\n")
    (tmp_path / "b.adoc").write_text("include::a.adoc[]\ninclude::outside.adoc[tag=example]\n")
    tree = DocumentReader(tmp_path, load_config(tmp_path, None)).analyze(tmp_path)
    assert any(item.rule_id == "DOC_INCLUDE" for item in tree.findings)
    assert sum(item.rule_id == "DOC_REFERENCE" for item in tree.findings) == 2
    assert tree.references_valid < tree.references_total


def test_repository_boundary_and_symlink(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    outside = tmp_path / "private.md"
    outside.write_text("private architecture")
    (repository / "link.md").symlink_to(outside)
    with pytest.raises(InputError):
        safe_path(repository, "../private.md")
    with pytest.raises(InputError):
        safe_path(repository, "link.md")
    with pytest.raises(InputError):
        safe_path(repository, ".git/config")


def test_limits_and_binary_inputs(tmp_path: Path) -> None:
    (tmp_path / "large.md").write_text("x" * 100)
    (tmp_path / "binary.md").write_bytes(b"\xff\xfe\xff")
    config = load_config(tmp_path, None)
    config["limits"]["max_file_bytes"] = 50
    tree = DocumentReader(tmp_path, config).analyze(tmp_path)
    assert {item.file for item in tree.findings if item.rule_id == "DOC_UNREADABLE"} == {"large.md", "binary.md"}


def test_entry_document_follows_relative_links(tmp_path: Path) -> None:
    (tmp_path / "index.md").write_text("# Architecture\n[Blocks](blocks.md)\n")
    (tmp_path / "blocks.md").write_text("## 5. Building Block View\nAn isolated service.\n[Index](index.md)\n")
    tree = DocumentReader(tmp_path, load_config(tmp_path, None)).analyze(tmp_path / "index.md")
    assert 5 in tree.sections
    assert tree.references_valid == 2
    assert len(tree.files) == 2


def test_malformed_urls_and_undefined_reference_labels(tmp_path: Path) -> None:
    (tmp_path / "arc.md").write_text("## 5. Building Block View\n[broken](https://[bad)\n[Undefined][no-definition]\n")
    tree = DocumentReader(tmp_path, load_config(tmp_path, None)).analyze(tmp_path)
    assert tree.references_total == 2
    assert tree.references_valid == 0
    assert len([item for item in tree.findings if item.rule_id == "DOC_REFERENCE"]) == 2


def test_repeated_include_expansion_is_bounded(tmp_path: Path) -> None:
    (tmp_path / "root.adoc").write_text("include::part.adoc[]\n" * 50)
    (tmp_path / "part.adoc").write_text("Meaningful text " * 20)
    config = load_config(tmp_path, None)
    config["limits"]["max_total_bytes"] = 2000
    config["limits"]["max_expanded_bytes"] = 2000
    reader = DocumentReader(tmp_path, config)
    tree = reader.analyze(tmp_path)
    assert reader.expanded_bytes < 2100
    assert any(item.rule_id == "DOC_INCLUDE" for item in tree.findings)


def test_sources_preserve_raw_bytes_for_hashes(tmp_path: Path) -> None:
    raw = b"## 5. Building Block View\r\nAn isolated service.\r\n"
    (tmp_path / "arc.md").write_bytes(raw)
    tree = DocumentReader(tmp_path, load_config(tmp_path, None)).analyze(tmp_path)
    assert tree.files["arc.md"].encode() == raw
