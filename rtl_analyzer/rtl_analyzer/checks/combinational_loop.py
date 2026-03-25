"""
RTL_E002 - Combinational loop (combinational feedback).
"""

from __future__ import annotations

from typing import List

from ..dataflow import build_dataflow_graph, find_cycles
from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile


def check_combinational_loop(pf: ParsedFile) -> List[Finding]:
    graph = build_dataflow_graph(pf)
    findings: List[Finding] = []

    for cycle in find_cycles(graph):
        cycle_set = set(cycle)
        line_number = min(
            graph.assignment_lines.get(signal, 1)
            for signal in cycle_set
        )
        ordered_cycle = sorted(cycle_set)
        findings.append(
            Finding(
                check_id=CheckID.RTL_E002,
                severity=Severity.ERROR,
                message=(
                    "Combinational loop detected across signals "
                    f"{ordered_cycle}. The feedback path has no sequential break "
                    "and can oscillate or settle to an indeterminate value."
                ),
                location=pf.location(line_number),
                fix_hint=(
                    "Break the feedback path with registered logic or restructure "
                    "the combinational assignments to remove the cycle."
                ),
                metadata={"cycle": ordered_cycle},
            )
        )

    return findings
