from __future__ import annotations

import math
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol, cast

import yaml

from .models import SEVERITIES


class InputError(ValueError):
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


class NodeLoader(Protocol):
    def construct_object(self, node: yaml.Node, deep: bool = False) -> Any: ...


def _mapping(loader: UniqueLoader, node: yaml.MappingNode) -> dict[str, Any]:
    result: dict[str, Any] = {}
    typed_loader = cast(NodeLoader, loader)
    for key_node, value_node in node.value:
        key = typed_loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise InputError("YAML keys must be unique strings")
        result[key] = typed_loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_yaml(text: str) -> Any:
    if len(text.encode()) > 2_097_152:
        raise InputError("YAML exceeds the 2 MiB limit")
    try:
        depth = 0
        for event in yaml.parse(text):
            if isinstance(event, yaml.AliasEvent):
                raise InputError("YAML aliases are not supported")
            if isinstance(event, (yaml.SequenceStartEvent, yaml.MappingStartEvent)):
                depth += 1
                if depth > 30:
                    raise InputError("YAML nesting exceeds 30 levels")
            if isinstance(event, (yaml.SequenceEndEvent, yaml.MappingEndEvent)):
                depth -= 1
        return yaml.load(text, Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise InputError("Invalid YAML syntax") from error


def safe_path(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as error:
        raise InputError("Path cannot be safely resolved") from error
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise InputError("Path escapes repository boundary") from error
    if any(part in {".git", ".ssh", ".aws", ".azure", ".config"} for part in resolved.relative_to(root.resolve()).parts):
        raise InputError("Protected directory is not an analysis input")
    return resolved


def _merge(default: dict[str, Any], override: dict[str, Any], prefix: str = "") -> None:
    for key, value in override.items():
        if key not in default:
            raise InputError(f"Unknown configuration key: {prefix}{key}")
        if isinstance(default[key], dict):
            if not isinstance(value, dict):
                raise InputError(f"Expected mapping: {prefix}{key}")
            _merge(default[key], value, f"{prefix}{key}.")
        else:
            default[key] = value


def _number(value: Any, name: str, maximum: float = 1_000_000) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{name} must be numeric")
    if not math.isfinite(value) or not 0 <= value <= maximum:
        raise InputError(f"{name} is out of range")


def validate(config: dict[str, Any]) -> None:
    if type(config["version"]) is not int or config["version"] != 1:
        raise InputError("Only configuration version 1 is supported")
    for weights in [config["weights"], *config["metrics"].values()]:
        for name, value in weights.items():
            _number(value, name)
        if sum(weights.values()) <= 0:
            raise InputError("Each weight group must have a positive sum")
    _number(config["min_tqi"], "min_tqi", 100)
    if config["fail_on_severity"] not in (*SEVERITIES, "none"):
        raise InputError("Invalid fail_on_severity")
    review = config["review"]
    choices = {
        "profile": ("arc42", "extended"), "rigor": ("advisory", "standard", "strict"),
        "c4_level": ("context", "container", "component"), "deployment_view": ("required", "not-required"),
    }
    for key, allowed in choices.items():
        if review[key] not in allowed:
            raise InputError(f"review.{key} must be one of {', '.join(allowed)}")
    if review["profile"] == "arc42":
        if config["weights"]["volatility"] or config["weights"]["drift"] or config["history"]["enabled"]:
            raise InputError("The arc42 profile excludes volatility, drift scoring, and Git history; use extended for those checks")
    for name, sources in review["evidence"].items():
        if not isinstance(sources, list) or len(sources) > 100:
            raise InputError(f"review.evidence.{name} must be a list of at most 100 sources")
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"file", "line", "end_line"}:
                raise InputError("Review evidence requires file, line, and end_line")
            if not isinstance(source["file"], str) or not source["file"].strip():
                raise InputError("Review evidence file must be nonempty text")
            if any(type(source[key]) is not int for key in ("line", "end_line")) or not 1 <= source["line"] <= source["end_line"]:
                raise InputError("Review evidence requires a positive, ordered line range")
            if source["end_line"] - source["line"] >= 200:
                raise InputError("Review evidence ranges may contain at most 200 lines")
    sections = config["critical_sections"]
    if not isinstance(sections, list) or not sections or any(type(item) is not int or not 1 <= item <= 12 for item in sections):
        raise InputError("critical_sections must contain section numbers 1–12")
    if len(set(sections)) != len(sections):
        raise InputError("critical_sections must be unique")
    if type(config["history"]["enabled"]) is not bool:
        raise InputError("history.enabled must be boolean")
    for category, policy in config["applicability"].items():
        if type(policy["required"]) is not bool:
            raise InputError(f"{category}.required must be boolean")
        reason = policy["reason"]
        if reason is not None and (not isinstance(reason, str) or not reason.strip()):
            raise InputError(f"{category}.reason must be null or nonempty text")
        if not policy["required"] and reason is None:
            raise InputError(f"{category} requires an explicit non-applicability reason")
    _number(config["history"]["coupling_threshold"], "coupling_threshold", 1)
    bounds = {"min_section_words": (1, 10000)}
    for name in config["limits"]:
        bounds["limits." + name] = (1, 64 if name == "max_include_depth" else 1073741824)
    bounds.update({
        "history.max_commits": (2, 10000), "history.hotspot_changes": (2, 10000),
        "history.coupling_min_support": (2, 10000), "history.stale_after_days": (0, 36500),
        "history.timeout_seconds": (1, 60), "prompts.max_claims_per_prompt": (1, 1000),
        "prompts.max_embedded_chars": (4096, 1000000), "prompts.max_findings_per_prompt": (0, 100),
    })
    for name, (minimum, maximum) in bounds.items():
        value = config
        for part in name.split("."):
            value = value[part]
        if type(value) is not int or not minimum <= value <= maximum:
            raise InputError(f"{name} must be an integer in {minimum}..{maximum}")


def load_config(root: Path, path: str | None, review_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    config: dict[str, Any] = load_yaml(files("arc42_tqi").joinpath("default-config.yml").read_text())
    override: dict[str, Any] = {}
    candidate = safe_path(root, path or ".arc42-tqi.yml")
    if candidate.is_file():
        if candidate.stat().st_size > 2_097_152:
            raise InputError("Configuration exceeds the 2 MiB limit")
        override = load_yaml(candidate.read_text(encoding="utf-8"))
        if not isinstance(override, dict):
            raise InputError("Configuration must be a mapping")
    elif path:
        raise InputError("Explicit configuration file does not exist")
    if "review" in override and not isinstance(override["review"], dict):
        raise InputError("review must be a mapping")
    requested = {**override.get("review", {}), **(review_overrides or {})}
    if requested.get("profile", config["review"]["profile"]) == "arc42":
        config["weights"].update(structure=50, decisions=50, volatility=0, drift=0)
        config["history"]["enabled"] = False
        config["applicability"]["volatility_zones"] = {
            "required": False, "reason": "Outside the arc42 documentation assessment scope",
        }
    else:
        config["weights"].update(structure=25, decisions=25, volatility=25, drift=25)
        config["history"]["enabled"] = True
        config["applicability"]["volatility_zones"] = {"required": True, "reason": None}
    _merge(config, override)
    _merge(config["review"], review_overrides or {}, "review.")
    validate(config)
    return config
