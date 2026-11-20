"""Keep public Action metadata within GitHub Marketplace limits."""
from pathlib import Path

import yaml


def test_marketplace_description_limit() -> None:
    metadata = yaml.safe_load((Path(__file__).resolve().parents[1] / "action.yml").read_text())
    assert isinstance(metadata["description"], str)
    assert 0 < len(metadata["description"]) < 125
