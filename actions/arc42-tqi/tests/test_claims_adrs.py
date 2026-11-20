from __future__ import annotations

from pathlib import Path

from arc42_tqi.adrs import parse_adrs
from arc42_tqi.claims import extract_claims
from arc42_tqi.config import load_config
from arc42_tqi.contracts import ADR, source_ref
from arc42_tqi.documents import DocumentReader
from arc42_tqi.models import DocumentTree
from arc42_tqi.rules import assess


def test_explicit_claim_provenance_and_adr_links(mature: Path) -> None:
    config = load_config(mature, None)
    reader = DocumentReader(mature, config, [mature / "docs/adr"])
    tree = reader.analyze(mature / "docs")
    adrs, errors = parse_adrs(reader, mature / "docs/adr")
    claims, findings = extract_claims(tree, adrs)
    assert not errors + findings
    assert adrs[0]["status"] == "accepted"
    assert 5 in adrs[0]["arc42_sections"]
    assert claims["components"][0]["provenance"]["sources"][0]["section"] == 8
    assert len(claims["constraints_and_adrs"]) == 1


def test_controlled_language_does_not_invent_components(tmp_path: Path) -> None:
    (tmp_path / "arc.md").write_text('## 5. Building Block View\n`API` must not depend on `DB` via `SQL` (sync) because boundaries matter.\n')
    tree = DocumentReader(tmp_path, load_config(tmp_path, None)).analyze(tmp_path)
    claims, findings = extract_claims(tree, [])
    assert not findings
    assert claims["components"] == []
    assert claims["dependencies"][0]["allowed"] is False
    assert claims["dependencies"][0]["target"] == "DB"
    metrics, findings = assess(tree, [], claims, {"status": "unavailable", "reason": "No history", "hotspots": [], "temporal_couplings": []}, load_config(tmp_path, None))
    assert metrics["drift"]["integrity"].satisfied == 0
    assert any(item.rule_id == "CLAIM_INTEGRITY" for item in findings)


def test_bad_claim_types_and_duplicate_ids() -> None:
    tree = DocumentTree(files={"arc.md": "```arc42-claims\ncomponents:\n  - id: api\n    evidence_targets: [code]\n    name: 12\n```\n"})
    claims, findings = extract_claims(tree, [])
    assert not claims["components"]
    assert findings[0].rule_id == "CLAIM_PARSE"
    tree.files["arc.md"] = "```arc42-claims\ncomponents:\n  - id: api\n    evidence_targets: [code]\n  - id: api\n    evidence_targets: [code]\n```\n"
    claims, findings = extract_claims(tree, [])
    assert any(item.rule_id == "CLAIM_PARSE" for item in findings)
    assert len({item["id"] for item in claims["components"]}) == len(claims["components"])


def test_asciidoc_claims_and_accepted_only_adr_extraction() -> None:
    tree = DocumentTree(files={"arc.adoc": "[source,arc42-claims]\n----\ncomponents:\n  - id: api\n    name: API\n    evidence_targets: [code]\n----\n"})
    adrs = [{"id": "ADR-1", "status": "superseded"}, ADR(id="ADR-2", status="accepted", decision="Use a queue", source=source_ref("adr.md", "Use a queue")).dict()]
    claims, findings = extract_claims(tree, adrs)
    assert not findings
    assert claims["components"][0]["name"] == "API"
    assert [item["adr_id"] for item in claims["constraints_and_adrs"]] == ["ADR-2"]


def test_adr_lifecycle_invalid_successor(mature: Path) -> None:
    path = mature / "docs/adr/0001-queue.md"
    path.write_text(path.read_text().replace("status: accepted", "status: superseded").replace("superseded_by: null", "superseded_by: ADR-MISSING"))
    reader = DocumentReader(mature, load_config(mature, None), [mature / "docs/adr"])
    tree = reader.analyze(mature / "docs")
    adrs, _ = parse_adrs(reader, mature / "docs/adr")
    claims, _ = extract_claims(tree, adrs)
    metrics, findings = assess(tree, adrs, claims, {"status": "unavailable", "reason": "No history", "hotspots": [], "temporal_couplings": []}, load_config(mature, None))
    assert metrics["decisions"]["lifecycle"].satisfied == 0
    assert any(item.rule_id == "ADR_LIFECYCLE" for item in findings)


def test_example_blocks_are_not_claims() -> None:
    tree = DocumentTree(files={"example.md": "````markdown\n```arc42-claims\ncomponents:\n  - id: example\n```\n````\n"})
    claims, findings = extract_claims(tree, [])
    assert claims["components"] == []
    assert not findings


def test_unclosed_claim_block_and_nonfinite_cloud_values() -> None:
    tree = DocumentTree(files={"arc.md": "```arc42-claims\ncomponents: []\n"})
    _, findings = extract_claims(tree, [])
    assert findings[0].rule_id == "CLAIM_PARSE"
    assert "Unclosed" in findings[0].evidence
    tree.files["arc.md"] = "```arc42-claims\ncloud_resources:\n  - id: queue\n    evidence_targets: [cloud]\n    configuration: {timeout: .nan}\n```\n"
    claims, findings = extract_claims(tree, [])
    assert not claims["cloud_resources"]
    assert findings[0].rule_id == "CLAIM_PARSE"


def test_invalid_claim_block_is_atomic() -> None:
    tree = DocumentTree(files={"arc.md": "```arc42-claims\ncomponents:\n  - id: valid\n    evidence_targets: [code]\n  - id: invalid\n    evidence_targets: [code]\n    name: 42\n```\n"})
    claims, findings = extract_claims(tree, [])
    assert not claims["components"]
    assert len(findings) == 1
