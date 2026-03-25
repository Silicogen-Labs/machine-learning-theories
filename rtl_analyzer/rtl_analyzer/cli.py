"""
CLI entry point — `rtl-check` command.

Usage:
    rtl-check path/to/design.v
    rtl-check src/rtl/ --recursive
    rtl-check *.sv --format json
    rtl-check design.sv --suppress RTL_I001,RTL_I002
    rtl-check design.sv --severity error,warning   # skip INFO
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from .engine import AnalysisEngine
from .models import CheckID, Severity
from .reporters import TextReporter, JsonReporter, SarifReporter


def _parse_suppress(value: Optional[str]) -> set:
    if not value:
        return set()
    result = set()
    for token in value.split(","):
        token = token.strip().upper()
        try:
            result.add(CheckID(token))
        except ValueError:
            click.echo(f"[warn] Unknown check ID to suppress: {token}", err=True)
    return result


def _parse_severity(value: Optional[str]) -> Optional[set]:
    if not value:
        return None
    result = set()
    for token in value.split(","):
        token = token.strip().upper()
        try:
            result.add(Severity(token))
        except ValueError:
            click.echo(f"[warn] Unknown severity: {token}", err=True)
    return result or None


def _parse_enabled_ml_checks(value: Optional[str]) -> Optional[set[str]]:
    if not value:
        return None
    return {
        token.strip().lower()
        for token in value.split(",")
        if token.strip()
    } or None


@click.command(name="rtl-check")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--recursive/--no-recursive", "-r",
    default=True,
    show_default=True,
    help="Recurse into directories.",
)
@click.option(
    "--format", "fmt",
    type=click.Choice(["text", "json", "sarif"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--suppress",
    metavar="IDS",
    default=None,
    help="Comma-separated check IDs to suppress (e.g. RTL_I001,RTL_I002).",
)
@click.option(
    "--severity",
    metavar="LEVELS",
    default=None,
    help="Only report these severity levels (e.g. error,warning).",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable colour output (text format only).",
)
@click.option(
    "--exit-zero",
    is_flag=True,
    default=False,
    help="Always exit with code 0 (useful in informational CI steps).",
)
@click.option(
    "--phase3-enabled/--no-phase3-enabled",
    default=False,
    hidden=True,
)
@click.option(
    "--enabled-ml-checks",
    default=None,
    hidden=True,
)
@click.option(
    "--model-dir",
    type=click.Path(path_type=Path),
    default=None,
    hidden=True,
)
def main(
    paths: tuple,
    recursive: bool,
    fmt: str,
    suppress: Optional[str],
    severity: Optional[str],
    no_color: bool,
    exit_zero: bool,
    phase3_enabled: bool,
    enabled_ml_checks: Optional[str],
    model_dir: Optional[Path],
) -> None:
    """
    General-purpose RTL static analyser for Verilog/SystemVerilog.

    Detects: latch inference, blocking/non-blocking misuse, width mismatch,
    missing reset, CDC risks, sim/synth mismatch, multi-driver, unused signals.

    Works on any project — FPGA, ASIC, academic, or commercial RTL.
    """
    suppress_set = _parse_suppress(suppress)
    severity_set = _parse_severity(severity)

    ml_checks = _parse_enabled_ml_checks(enabled_ml_checks)

    engine = AnalysisEngine(
        suppress=suppress_set,
        severity_filter=severity_set,
        phase3_enabled=phase3_enabled,
        enabled_ml_checks=ml_checks,
        model_dir=model_dir,
    )

    # Expand paths (files + directories)
    files = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.glob("**/*.v") if recursive else p.glob("*.v")))
            files.extend(sorted(p.glob("**/*.sv") if recursive else p.glob("*.sv")))
        elif p.suffix in (".v", ".sv"):
            files.append(p)
        else:
            click.echo(f"[warn] Skipping non-Verilog file: {p}", err=True)

    if not files:
        click.echo("No Verilog/SystemVerilog files found.", err=True)
        sys.exit(1)

    result = engine.analyze_files(files)

    # Output
    fmt_lower = fmt.lower()
    if fmt_lower == "json":
        JsonReporter().report(result)
    elif fmt_lower == "sarif":
        SarifReporter().report(result)
    else:
        TextReporter(no_color=no_color).report(result)

    # Exit code: non-zero if any errors (unless --exit-zero)
    if not exit_zero and result.error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
