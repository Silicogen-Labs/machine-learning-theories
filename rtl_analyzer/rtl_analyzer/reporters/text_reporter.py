"""Rich-formatted text reporter."""

from __future__ import annotations

import sys
from typing import IO

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

from ..engine import AnalysisResult, FileResult
from ..models import Severity


_SEVERITY_STYLE = {
    Severity.ERROR:   "bold red",
    Severity.WARNING: "bold yellow",
    Severity.INFO:    "dim cyan",
}

_SEVERITY_ICON = {
    Severity.ERROR:   "✖",
    Severity.WARNING: "▲",
    Severity.INFO:    "●",
}


class TextReporter:
    def __init__(self, stream: IO = None, no_color: bool = False):
        self._console = Console(
            file=stream or sys.stdout,
            no_color=no_color,
            highlight=False,
        )

    def report(self, result: AnalysisResult) -> None:
        c = self._console

        for fr in result.file_results:
            if not fr.findings:
                c.print(f"[green]✔[/]  {fr.path}  [dim]({fr.elapsed_ms:.1f} ms, no issues)[/]")
                continue

            c.print(f"\n[bold]{fr.path}[/]  [dim]({fr.elapsed_ms:.1f} ms)[/]")
            for f in fr.findings:
                style = _SEVERITY_STYLE[f.severity]
                icon = _SEVERITY_ICON[f.severity]
                col = f":{f.location.column}" if f.location.column else ""
                loc = f"[dim]{f.location.line}{col}[/]"
                c.print(
                    f"  [{style}]{icon} {f.check_id.value}[/]  "
                    f"{loc}  {f.message}"
                )
                if f.fix_hint:
                    c.print(f"  [dim]  Hint: {f.fix_hint}[/]")

        # Summary bar
        c.print()
        e = result.error_count
        w = result.warning_count
        i = result.info_count
        total = e + w + i
        files = len(result.file_results)
        ms = result.total_elapsed_ms

        if total == 0:
            c.print(
                f"[bold green]✔ No issues found[/] in {files} file(s) "
                f"[dim]({ms:.1f} ms)[/]"
            )
        else:
            parts = []
            if e:
                parts.append(f"[bold red]{e} error(s)[/]")
            if w:
                parts.append(f"[bold yellow]{w} warning(s)[/]")
            if i:
                parts.append(f"[dim]{i} info[/]")
            c.print(
                f"[bold]Found {', '.join(parts)}[/] in {files} file(s) "
                f"[dim]({ms:.1f} ms)[/]"
            )
