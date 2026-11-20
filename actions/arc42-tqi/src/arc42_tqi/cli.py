from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Annotated

import typer
from click import ClickException

from . import __version__
from .analyzer import analyze_repository
from .config import InputError, safe_path
from .exporters import github_files, summary, write_artifacts
from .integrations import comment_pr as publish_comment
from .integrations import enrich

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


@app.command()
def analyze(
    repo_root: Annotated[Path, typer.Option(envvar="GITHUB_WORKSPACE")] = Path("."),
    docs_path: Annotated[str, typer.Option(envvar="ARC42_TQI_DOCS_PATH")] = "docs",
    adr_path: Annotated[str, typer.Option(envvar="ARC42_TQI_ADR_PATH")] = "docs/adr",
    diagrams_path: Annotated[str, typer.Option(envvar="ARC42_TQI_DIAGRAMS_PATH")] = "",
    config_path: Annotated[str, typer.Option(envvar="ARC42_TQI_CONFIG_PATH")] = "",
    output_dir: Annotated[str, typer.Option(envvar="ARC42_TQI_OUTPUT_DIR")] = ".arc42-tqi",
    min_tqi: Annotated[float | None, typer.Option(envvar="ARC42_TQI_MIN_TQI")] = None,
    fail_on_severity: Annotated[str | None, typer.Option(envvar="ARC42_TQI_FAIL_ON_SEVERITY")] = None,
    llm_provider: Annotated[str, typer.Option(envvar="ARC42_TQI_LLM_PROVIDER")] = "none",
    llm_model: Annotated[str, typer.Option(envvar="ARC42_TQI_LLM_MODEL")] = "",
    llm_endpoint: Annotated[str, typer.Option(envvar="ARC42_TQI_LLM_ENDPOINT")] = "",
    comment_pr: Annotated[bool, typer.Option(envvar="ARC42_TQI_COMMENT_PR")] = False,
) -> None:
    try:
        root = repo_root.resolve()
        report, claims = analyze_repository(root, docs_path, adr_path, diagrams_path, config_path,
                                            output_dir, min_tqi, fail_on_severity)
        report["semantic_enrichment"] = enrich(
            llm_provider, llm_endpoint, llm_model, os.environ.get("ARC42_TQI_LLM_API_KEY", ""), report, claims,
        )
        outputs = write_artifacts(root, safe_path(root, output_dir), report, claims)
        summary_text = summary(report, safe_path(root, output_dir).relative_to(root).as_posix())
        github_files(outputs, summary_text)
        if comment_pr:
            status = publish_comment(summary_text, os.environ.get("ARC42_TQI_GITHUB_TOKEN", ""))
            typer.echo("PR comment: " + status, err=True)
        for diagnostic in report["diagnostics"]:
            typer.echo(f"{diagnostic['level']}: {diagnostic['message']}", err=True)
        typer.echo(json.dumps({"tqi_score": report["tqi_score"], "maturity_level": report["maturity_level"],
                               "quality_gate": report["quality_gate"], "output_dir": output_dir}, sort_keys=True))
        raise typer.Exit(0 if report["quality_gate"]["passed"] else 1)
    except (InputError, OSError, UnicodeError) as error:
        typer.echo(f"arc42-tqi: {type(error).__name__}: {error}", err=True)
        raise typer.Exit(2) from error


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments == ["--version"]:
        typer.echo(__version__)
        return 0
    try:
        result = app(args=arguments, standalone_mode=False)
        return int(result) if isinstance(result, int) else 0
    except typer.Exit as error:
        return int(error.exit_code)
    except ClickException as error:
        typer.echo(str(error), err=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
