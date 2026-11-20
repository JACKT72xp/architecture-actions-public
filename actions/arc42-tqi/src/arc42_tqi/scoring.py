from __future__ import annotations

from fractions import Fraction
from typing import Any

from .models import DIMENSIONS, Metric


def rounded(value: Fraction) -> float:
    scaled = value * 100
    return ((2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator)) / 100


def maturity(score: float) -> str:
    return "L4" if score >= 90 else "L3" if score >= 70 else "L2" if score >= 40 else "L1"


def calculate(metrics: dict[str, dict[str, Metric]], config: dict[str, Any]) -> dict[str, Any]:
    dimensions: dict[str, Any] = {}
    total = Fraction(0)
    total_weight = sum(Fraction(str(weight)) for weight in config["weights"].values())
    if total_weight <= 0:
        raise ValueError("Dimension weights must have a positive sum")
    for dimension in DIMENSIONS:
        if set(metrics[dimension]) != set(config["metrics"][dimension]):
            raise ValueError(f"Metric contract mismatch: {dimension}")
        weights = {name: Fraction(str(value)) for name, value in config["metrics"][dimension].items()}
        applicable_weight = sum(weights[name] for name, metric in metrics[dimension].items() if metric.applicable)
        details: dict[str, Any] = {}
        score = Fraction(0)
        for name, metric in metrics[dimension].items():
            if not 0 <= metric.satisfied <= metric.applicable:
                raise ValueError("Metric numerator is outside its denominator")
            ratio = Fraction(metric.satisfied, metric.applicable) if metric.applicable else None
            normalized = weights[name] / applicable_weight if applicable_weight and ratio is not None else None
            if ratio is not None and normalized is not None:
                score += 100 * normalized * ratio
            details[name] = {
                "satisfied": metric.satisfied, "applicable": metric.applicable,
                "ratio": float(ratio) if ratio is not None else None,
                "deficit_ratio": float(1 - ratio) if ratio is not None else None,
                "weight": float(weights[name]), "normalized_weight": float(normalized) if normalized is not None else None,
                "weighted_penalty": float(100 * normalized * (1 - ratio)) if normalized is not None and ratio is not None else None,
                "status": "measured" if ratio is not None else "not_applicable",
                "definition": metric.description, "reason": metric.reason,
                "evidence_refs": [
                    "claims.json#" + reference.removeprefix("/claims") if reference.startswith("/claims")
                    else "tqi-report.json#" + reference for reference in metric.evidence_refs
                ],
            }
        weight = Fraction(str(config["weights"][dimension]))
        contribution = weight * score / total_weight
        dimensions[dimension] = {"score": float(score), "weight": float(weight),
                                 "normalized_weight": float(weight / total_weight),
                                 "weighted_contribution": float(contribution), "metrics": details}
        total += contribution
    final = rounded(total)
    return {"tqi_score": final, "maturity_level": maturity(final), "dimensions": dimensions}
