"""
RTL source parser.

Uses pyslang (IEEE 1800-2023 grammar) to validate syntax and capture parse
errors.  All check logic operates on a lightweight regex-based line/block
model built from the comment-stripped source — this is fast (O(lines)),
avoids pyslang elaboration overhead, and is sufficient for the pattern-based
checks in Phase 1.

Phase 2 will wire pyslang's SyntaxTree into checks that require accurate
expression-width reasoning and cross-module signal tracking.

Design principles:
  • One ParsedFile per source file.  Never global state.
  • All checks receive a ParsedFile and return List[Finding].
  • Parser errors are surfaced as findings, not exceptions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional

import pyslang

from ..models import CheckID, Finding, Location, Severity


# ---------------------------------------------------------------------------
# Token-level line model (no pyslang required, used by regex-based checks)
# ---------------------------------------------------------------------------

@dataclass
class LineInfo:
    """Enriched per-line data extracted by the lightweight tokeniser."""
    number: int           # 1-based
    text: str             # raw text, tabs expanded
    stripped: str         # text with comments removed, whitespace normalised
    in_block_comment: bool = False


def _strip_comments(source: str) -> List[LineInfo]:
    """
    Remove // and /* */ comments, preserving line numbers.
    Returns a LineInfo per source line.
    """
    lines: List[LineInfo] = []
    in_block = False
    for lineno, raw in enumerate(source.splitlines(), start=1):
        text = raw.expandtabs(4)
        stripped = text

        if in_block:
            end = stripped.find("*/")
            if end != -1:
                stripped = stripped[end + 2:]
                in_block = False
            else:
                lines.append(LineInfo(lineno, text, "", in_block_comment=True))
                continue

        # Remove /* … */ on same line (multiple possible)
        while True:
            m = re.search(r"/\*", stripped)
            if not m:
                break
            end = stripped.find("*/", m.end())
            if end != -1:
                stripped = stripped[: m.start()] + " " + stripped[end + 2:]
            else:
                stripped = stripped[: m.start()]
                in_block = True
                break

        # Remove // comment
        sl = stripped.find("//")
        if sl != -1:
            stripped = stripped[:sl]

        lines.append(LineInfo(lineno, text, stripped.strip(), in_block_comment=False))

    return lines


# ---------------------------------------------------------------------------
# Always-block model
# ---------------------------------------------------------------------------

class AlwaysKind(str):
    COMB = "comb"         # always_comb / always @(*)
    FF   = "ff"           # always_ff
    LATCH = "latch"       # always_latch (explicit)
    GENERIC = "generic"   # always @(something specific) — ambiguous


@dataclass
class AlwaysBlock:
    kind: str
    start_line: int
    end_line: int
    sensitivity: str          # raw sensitivity list text
    signals_assigned: List[str] = field(default_factory=list)
    has_blocking: bool = False
    has_nonblocking: bool = False
    has_posedge: bool = False
    has_negedge: bool = False
    has_reset: bool = False


# ---------------------------------------------------------------------------
# Main ParsedFile
# ---------------------------------------------------------------------------

@dataclass
class ParsedFile:
    path: Path
    source: str
    lines: List[LineInfo] = field(default_factory=list)
    # pyslang syntax tree (None if parse failed)
    syntax_tree: Optional[pyslang.SyntaxTree] = field(default=None, repr=False)
    parse_errors: List[str] = field(default_factory=list)
    # Phase 2: populated lazily by elaborator.build_elaborated()
    elaborated: Optional["ElaboratedModule"] = field(default=None, repr=False)
    modules: List[str] = field(default_factory=list)
    always_blocks: List[AlwaysBlock] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Helpers for checks                                                   #
    # ------------------------------------------------------------------ #

    def iter_lines(self) -> Iterator[LineInfo]:
        yield from self.lines

    def line(self, number: int) -> Optional[LineInfo]:
        """1-based line lookup."""
        if 1 <= number <= len(self.lines):
            return self.lines[number - 1]
        return None

    def location(self, line: int, col: Optional[int] = None) -> Location:
        return Location(file=self.path, line=line, column=col)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_RE_MODULE = re.compile(r"\bmodule\s+(\w+)\b")
_RE_ALWAYS_HDR = re.compile(
    r"\balways(?:_comb|_ff|_latch)?\s*(?:@\s*\(([^)]*)\))?"
)
_RE_POSEDGE = re.compile(r"\bposedge\b")
_RE_NEGEDGE = re.compile(r"\bnegedge\b")
_RE_RESET = re.compile(r"\b(?:rst|reset|arst|srst|n_rst|rst_n|resetn|aresetn)\b", re.I)
_RE_BLOCKING = re.compile(r"(?<![<>!])\s*=\s*(?!=)")   # = but not <=, >=, !=, ==
_RE_NONBLOCKING = re.compile(r"<=\s*")


def _classify_always(header: str, sensitivity: str) -> str:
    h = header.strip()
    if "always_comb" in h:
        return AlwaysKind.COMB
    if "always_ff" in h:
        return AlwaysKind.FF
    if "always_latch" in h:
        return AlwaysKind.LATCH
    s = sensitivity.lower()
    if "*" in s or "always_comb" in h:
        return AlwaysKind.COMB
    if _RE_POSEDGE.search(s) or _RE_NEGEDGE.search(s):
        return AlwaysKind.FF
    return AlwaysKind.GENERIC


def parse_file(path: Path) -> ParsedFile:
    """
    Parse a single Verilog/SystemVerilog file.
    Returns a ParsedFile regardless of errors (errors are recorded inside).
    """
    source = path.read_text(encoding="utf-8", errors="replace")
    pf = ParsedFile(path=path, source=source)

    # ── Line model ─────────────────────────────────────────────────────────
    pf.lines = _strip_comments(source)

    # ── pyslang parse ───────────────────────────────────────────────────────
    try:
        pf.syntax_tree = pyslang.SyntaxTree.fromFile(str(path))
        # Collect any parse-level diagnostics (e.g. missing endmodule)
        for diag in pf.syntax_tree.diagnostics:
            try:
                if diag.isError():
                    pf.parse_errors.append(
                        f"{diag.code}: {' '.join(str(a) for a in diag.args)}"
                    )
            except Exception:
                pf.parse_errors.append(str(diag))
    except Exception as exc:  # pyslang can throw on catastrophic files
        pf.parse_errors.append(str(exc))

    # ── Module names ────────────────────────────────────────────────────────
    for li in pf.lines:
        for m in _RE_MODULE.finditer(li.stripped):
            name = m.group(1)
            if name not in ("endmodule",):
                pf.modules.append(name)

    # ── Always blocks ───────────────────────────────────────────────────────
    pf.always_blocks = _extract_always_blocks(pf)

    return pf


def _extract_always_blocks(pf: ParsedFile) -> List[AlwaysBlock]:
    """
    Lightweight always-block extractor using brace/keyword tracking.
    Handles nested begin/end and multi-line sensitivity lists.
    """
    blocks: List[AlwaysBlock] = []
    lines = pf.lines
    i = 0
    n = len(lines)

    while i < n:
        li = lines[i]
        m = _RE_ALWAYS_HDR.search(li.stripped)
        if not m:
            i += 1
            continue

        header_text = li.stripped[m.start():]
        raw_sens = m.group(1) or ""

        # Collect sensitivity list if it spans multiple lines
        if "always_comb" in header_text or "always_latch" in header_text:
            pass  # no sensitivity list
        elif raw_sens == "":
            # Maybe @( on next lines
            sens_buf = ""
            j = i
            while j < n and ")" not in sens_buf:
                chunk = lines[j].stripped
                at = chunk.find("@")
                if at != -1:
                    chunk = chunk[at + 1:]
                paren_open = chunk.find("(")
                if paren_open != -1:
                    chunk = chunk[paren_open + 1:]
                paren_close = chunk.find(")")
                if paren_close != -1:
                    sens_buf += chunk[:paren_close]
                    break
                sens_buf += chunk + " "
                j += 1
            raw_sens = sens_buf.strip()

        kind = _classify_always(header_text, raw_sens)
        start = li.number

        # Walk forward to collect the block body (begin/end or single stmt)
        body_lines: List[LineInfo] = []
        depth = 0
        found_begin = False
        j = i
        while j < n:
            body = lines[j].stripped
            if re.search(r"\bbegin\b", body):
                found_begin = True
                depth += body.count("begin") - body.count("end")
            elif found_begin:
                # count begin/end without the initial line
                opens = len(re.findall(r"\bbegin\b", body))
                closes = len(re.findall(r"\bend\b", body))
                depth += opens - closes
            body_lines.append(lines[j])
            if found_begin and depth <= 0:
                break
            if not found_begin and j > i:
                # Single-statement block ends at first non-empty line after header
                if body and not _RE_ALWAYS_HDR.search(body):
                    break
            j += 1

        end = lines[min(j, n - 1)].number
        body_text = "\n".join(l.stripped for l in body_lines)

        ab = AlwaysBlock(
            kind=kind,
            start_line=start,
            end_line=end,
            sensitivity=raw_sens,
            has_posedge=bool(_RE_POSEDGE.search(raw_sens)),
            has_negedge=bool(_RE_NEGEDGE.search(raw_sens)),
            has_reset=bool(_RE_RESET.search(body_text)),
        )

        # Detect blocking / non-blocking usage in body
        for bl in body_lines:
            s = bl.stripped
            if _RE_NONBLOCKING.search(s):
                ab.has_nonblocking = True
            # blocking: = but not <= or == or !=
            clean = re.sub(r"[<>!]=", "  ", s)  # remove <=, >=, !=, ==
            clean = re.sub(r"==", "  ", clean)
            if re.search(r"(?<![<>!])\s*=\s*(?!=)", clean):
                ab.has_blocking = True

        # Collect assigned signal names (LHS of assignments)
        for bl in body_lines:
            for m2 in re.finditer(r"(\w+)\s*(?:\[.*?\])?\s*<=?", bl.stripped):
                name = m2.group(1)
                if name not in (
                    "if", "else", "case", "casez", "casex",
                    "begin", "end", "for", "while", "repeat",
                ):
                    ab.signals_assigned.append(name)

        blocks.append(ab)
        i = j + 1

    return blocks
