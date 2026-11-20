"""Add human reports to an existing artifact bundle without changing its evidence."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from arc42_tqi.human_report import human_html, human_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, help="Defaults to the existing artifact directory")
    args = parser.parse_args()
    report = json.loads((args.artifacts / "tqi-report.json").read_text(encoding="utf-8"))
    claims = json.loads((args.artifacts / "claims.json").read_text(encoding="utf-8"))
    if report.get("schema_version") not in {"1.0", "1.1"} or claims.get("schema_version") != "1.0":
        parser.error("This renderer requires report schema 1.0/1.1 and claims schema 1.0")
    if report.get("metadata") != claims.get("metadata"):
        parser.error("The report and claims must belong to the same analyzed snapshot")
    markdown = human_report(report, claims)
    destination = (args.output_dir or args.artifacts).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in (("human-report.md", markdown), ("human-report.html", human_html(markdown))):
        target = destination / name
        if target.is_symlink():
            parser.error("Human-report outputs must not be symbolic links")
        descriptor, temporary_name = tempfile.mkstemp(prefix=".human-report-", dir=destination)
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o644)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        print(target)


if __name__ == "__main__":
    main()
