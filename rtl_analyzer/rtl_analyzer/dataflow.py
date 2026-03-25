from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parser import AlwaysKind, ParsedFile


@dataclass
class DataflowGraph:
    dependencies: dict[str, set[str]] = field(default_factory=dict)
    assignment_lines: dict[str, int] = field(default_factory=dict)


_KEYWORDS = frozenset(
    {
        "always",
        "always_comb",
        "always_ff",
        "always_latch",
        "assign",
        "begin",
        "case",
        "casex",
        "casez",
        "default",
        "else",
        "end",
        "endcase",
        "for",
        "if",
        "module",
        "posedge",
        "repeat",
        "while",
    }
)
_RE_IDENTIFIER = re.compile(r"\b[A-Za-z_]\w*\b")
_RE_MODULE = re.compile(r"\bmodule\s+(\w+)\b")
_RE_ENDMODULE = re.compile(r"\bendmodule\b")
_RE_ASSIGN = re.compile(r"^assign\b\s+(?P<lhs>.+?)\s*=\s*(?P<rhs>.+?);?$")
_RE_PROC_ASSIGN = re.compile(
    r"^(?P<lhs>[A-Za-z_]\w*)(?:\s*\[[^\]]+\])?\s*(?:<=|=)\s*(?P<rhs>.+?);?$"
)
_RE_VERILOG_LITERAL = re.compile(r"\b\d+\s*'\s*[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+\b|'\s*[01xXzZ]\b")
_RE_CONTROL_FLOW = re.compile(r"\b(?:if|else|case|casex|casez|for|while|repeat)\b")
_PREFIX_PATTERNS = (
    re.compile(r"^always(?:_comb|_ff|_latch)?\s*(?:@\s*\([^)]*\))?\s*"),
    re.compile(r"^begin\b\s*"),
    re.compile(r"^end\b\s*"),
    re.compile(r"^else\s+if\s*\([^)]*\)\s*"),
    re.compile(r"^if\s*\([^)]*\)\s*"),
    re.compile(r"^else\b\s*"),
    re.compile(r"^default\s*:\s*"),
)


def build_dataflow_graph(parsed_file: ParsedFile) -> DataflowGraph:
    graph = DataflowGraph()
    module_by_line = _build_module_by_line(parsed_file)
    use_module_scope = len(set(module_by_line.values())) > 1

    for line in parsed_file.lines:
        target, deps = _parse_continuous_assignment(line.stripped)
        if target is None:
            continue
        module_name = module_by_line.get(line.number)
        scoped_target = _scope_signal(module_name, target, use_module_scope)
        scoped_deps = {
            _scope_signal(module_name, dep, use_module_scope)
            for dep in deps
        }
        _record_dependencies(graph, scoped_target, scoped_deps, line.number)

    for block in parsed_file.always_blocks:
        if block.kind != AlwaysKind.COMB:
            continue

        block_lines = parsed_file.lines[block.start_line - 1 : block.end_line]
        if _block_has_ambiguous_control_flow(block_lines):
            continue

        module_name = module_by_line.get(block.start_line)

        for line in block_lines:
            target, deps = _parse_combinational_assignment(line.stripped)
            if target is None:
                continue
            scoped_target = _scope_signal(module_name, target, use_module_scope)
            scoped_deps = {
                _scope_signal(module_name, dep, use_module_scope)
                for dep in deps
            }
            _record_dependencies(graph, scoped_target, scoped_deps, line.number)

    return graph


def find_cycles(graph: DataflowGraph) -> list[list[str]]:
    adjacency = {
        node: sorted(deps)
        for node, deps in graph.dependencies.items()
    }
    all_nodes = sorted(set(adjacency) | {dep for deps in adjacency.values() for dep in deps})
    cycles: set[tuple[str, ...]] = set()

    for start in all_nodes:
        _dfs_cycles(start, start, adjacency, [start], {start}, cycles)

    return [list(cycle) for cycle in sorted(cycles)]


def _dfs_cycles(
    start: str,
    current: str,
    adjacency: dict[str, list[str]],
    path: list[str],
    seen: set[str],
    cycles: set[tuple[str, ...]],
) -> None:
    for neighbor in adjacency.get(current, []):
        if neighbor == start:
            cycles.add(tuple(path))
            continue

        if neighbor in seen or neighbor < start:
            continue

        _dfs_cycles(start, neighbor, adjacency, path + [neighbor], seen | {neighbor}, cycles)


def _parse_continuous_assignment(text: str) -> tuple[str | None, set[str]]:
    match = _RE_ASSIGN.match(text)
    if not match:
        return None, set()

    target = _extract_signal_name(match.group("lhs"))
    if target is None:
        return None, set()

    return target, _extract_dependencies(match.group("rhs"))


def _parse_combinational_assignment(text: str) -> tuple[str | None, set[str]]:
    statement = _strip_prefixes(text)
    match = _RE_PROC_ASSIGN.match(statement)
    if not match:
        return None, set()

    target = match.group("lhs")
    if target in _KEYWORDS:
        return None, set()

    return target, _extract_dependencies(match.group("rhs"))


def _strip_prefixes(text: str) -> str:
    statement = text.strip()

    while True:
        updated = _strip_case_label(statement)
        changed = updated != statement
        statement = updated

        for pattern in _PREFIX_PATTERNS:
            updated = pattern.sub("", statement, count=1).strip()
            if updated != statement:
                statement = updated
                changed = True

        if not changed:
            return statement


def _strip_case_label(text: str) -> str:
    colon_index = text.find(":")
    if colon_index == -1:
        return text

    eq_index = text.find("=")
    le_index = text.find("<=")
    assignment_index = min(
        [index for index in (eq_index, le_index) if index != -1],
        default=-1,
    )

    if assignment_index == -1 or colon_index < assignment_index:
        return text[colon_index + 1 :].strip()

    return text


def _extract_signal_name(lhs: str) -> str | None:
    match = re.match(r"([A-Za-z_]\w*)", lhs.strip())
    if not match:
        return None

    signal = match.group(1)
    if signal in _KEYWORDS:
        return None

    return signal


def _extract_dependencies(rhs: str) -> set[str]:
    deps = set()
    for token in _RE_IDENTIFIER.findall(_strip_verilog_literals(rhs)):
        if token in _KEYWORDS:
            continue
        deps.add(token)
    return deps


def _build_module_by_line(parsed_file: ParsedFile) -> dict[int, str]:
    module_by_line: dict[int, str] = {}
    current_module: str | None = None

    for line in parsed_file.lines:
        module_match = _RE_MODULE.search(line.stripped)
        if module_match:
            current_module = module_match.group(1)

        if current_module is not None:
            module_by_line[line.number] = current_module

        if _RE_ENDMODULE.search(line.stripped):
            current_module = None

    return module_by_line


def _scope_signal(module_name: str | None, signal: str, use_module_scope: bool) -> str:
    if use_module_scope and module_name is not None:
        return f"{module_name}::{signal}"
    return signal


def _block_has_ambiguous_control_flow(block_lines) -> bool:
    return any(_RE_CONTROL_FLOW.search(line.stripped) for line in block_lines)


def _strip_verilog_literals(rhs: str) -> str:
    return _RE_VERILOG_LITERAL.sub(" ", rhs)


def _record_dependencies(
    graph: DataflowGraph,
    target: str,
    dependencies: set[str],
    line_number: int,
) -> None:
    graph.dependencies.setdefault(target, set()).update(dependencies)
    current = graph.assignment_lines.get(target)
    if current is None or line_number < current:
        graph.assignment_lines[target] = line_number
