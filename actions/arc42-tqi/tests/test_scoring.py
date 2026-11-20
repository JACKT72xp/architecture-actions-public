from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from arc42_tqi.config import InputError, load_config, load_yaml, validate
from arc42_tqi.models import Metric
from arc42_tqi.scoring import calculate, maturity


@pytest.mark.parametrize("score,expected", [(0, "L1"), (39.99, "L1"), (40, "L2"), (69.99, "L2"), (70, "L3"), (89.99, "L3"), (90, "L4"), (100, "L4")])
def test_maturity_boundaries(score: float, expected: str) -> None:
    assert maturity(score) == expected


def test_weighted_formula_and_na(tmp_path: Path) -> None:
    config = load_config(tmp_path, None, {"profile": "extended"})
    metrics = {dimension: {name: Metric(1, 2, "half") for name in weights} for dimension, weights in config["metrics"].items()}
    metrics["structure"]["coverage"] = Metric(1, 1, "full")
    metrics["volatility"]["evolution"] = Metric(0, 0, "unavailable")
    result = calculate(metrics, config)
    assert result["dimensions"]["structure"]["score"] == 62.5
    assert result["dimensions"]["volatility"]["score"] == 50
    assert result["dimensions"]["volatility"]["metrics"]["evolution"]["ratio"] is None
    assert result["tqi_score"] == 53.13
    config["weights"].update(structure=100, decisions=0, volatility=0, drift=0)
    assert calculate(metrics, config)["tqi_score"] == 62.5


def test_report_can_reconstruct_score(tmp_path: Path) -> None:
    config = load_config(tmp_path, None)
    metrics = {dimension: {name: Metric(2, 3, "two thirds") for name in weights} for dimension, weights in config["metrics"].items()}
    result = calculate(metrics, config)
    reconstructed = Decimal(0)
    for dimension in result["dimensions"].values():
        numerator = sum(Decimal(str(item["weight"])) * Decimal(item["satisfied"]) / Decimal(item["applicable"]) for item in dimension["metrics"].values())
        denominator = sum(Decimal(str(item["weight"])) for item in dimension["metrics"].values())
        reconstructed += numerator / denominator * Decimal(100) * Decimal(dimension["weight"])
    assert float((reconstructed / Decimal(100)).quantize(Decimal("0.01"))) == result["tqi_score"]


@pytest.mark.parametrize("override", ["weights: {structure: -1}", "weights: {structure: .nan}", "weights: {structure: true}", "unknown: 1", "min_tqi: 101", "fail_on_severity: urgent", "critical_sections: [5, 5]", "history: {enabled: yesplease}", "limits: {max_include_depth: 1000}"])
def test_config_rejects_bad_overrides(tmp_path: Path, override: str) -> None:
    (tmp_path / ".arc42-tqi.yml").write_text(override)
    with pytest.raises(InputError):
        load_config(tmp_path, None)


def test_deep_merge_and_missing_config(tmp_path: Path) -> None:
    (tmp_path / ".arc42-tqi.yml").write_text("metrics:\n  structure:\n    depth: 60\n")
    config = load_config(tmp_path, None)
    assert config["metrics"]["structure"]["depth"] == 60
    assert config["metrics"]["structure"]["coverage"] == 25
    with pytest.raises(InputError):
        load_config(tmp_path, "missing.yml")
    config["weights"] = dict.fromkeys(config["weights"], 0)
    with pytest.raises(InputError):
        validate(config)


@pytest.mark.parametrize("payload", ["a: 1\na: 2", "a: &a [*a]", "a: !!python/object/apply:os.system ['false']", "[" * 32 + "]" * 32])
def test_unsafe_yaml(payload: str) -> None:
    with pytest.raises(InputError):
        load_yaml(payload)
