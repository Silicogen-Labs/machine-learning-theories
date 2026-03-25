from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from rtl_analyzer.dataflow import build_dataflow_graph, find_cycles


_RE_ASSIGN = re.compile(r"\bassign\b")


@dataclass(frozen=True)
class DataflowFeatureSummary:
    node_count: float
    cycle_count: float
    error: float


def summarize_dataflow_features(parsed_file: Any) -> DataflowFeatureSummary:
    try:
        graph = build_dataflow_graph(parsed_file)
        return DataflowFeatureSummary(
            node_count=float(len(graph.dependencies)),
            cycle_count=float(len(find_cycles(graph))),
            error=0.0,
        )
    except Exception:
        return DataflowFeatureSummary(node_count=0.0, cycle_count=0.0, error=1.0)


def extract_ast_features(parsed_file: Any) -> dict[str, float]:
    dataflow = summarize_dataflow_features(parsed_file)

    return {
        "always_block_count": float(len(parsed_file.always_blocks)),
        "always_ff_count": float(sum(block.kind == "ff" for block in parsed_file.always_blocks)),
        "always_comb_count": float(sum(block.kind == "comb" for block in parsed_file.always_blocks)),
        "assign_count": float(len(_RE_ASSIGN.findall(parsed_file.source))),
        "module_count": float(len(parsed_file.modules)),
        "line_count": float(len(parsed_file.lines)),
        "parse_error_count": float(len(parsed_file.parse_errors)),
        "dataflow_node_count": dataflow.node_count,
        "dataflow_cycle_count": dataflow.cycle_count,
        "dataflow_error": dataflow.error,
    }
