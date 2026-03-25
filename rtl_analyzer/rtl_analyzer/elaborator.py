"""
rtl_analyzer/elaborator.py — pyslang elaboration wrapper.

Wraps pyslang.Compilation to produce an ElaboratedModule: a clean,
check-friendly view of a fully elaborated Verilog/SV module.

Phase 2 checks (FSM, CDC) operate on ElaboratedModule rather than the
raw line model used by Phase 1 checks.

Design rules:
  - Never raises: returns None if elaboration has fatal errors.
  - build_elaborated(pf) is O(1) if pf.elaborated is already set.
  - All pyslang API calls are isolated here; checks never import pyslang.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

import pyslang

from .parser import ParsedFile


@dataclass
class SignalInfo:
    """Lightweight descriptor for a net or variable."""
    name: str
    line: int           # 1-based source line
    width: int          # bit width, 1 if unknown
    clock_domain: Optional[str] = None   # inferred clock name, None if unknown


@dataclass
class ElaboratedModule:
    """
    Check-friendly view of a single elaborated module.

    Built once per ParsedFile by build_elaborated(); cached on pf.elaborated.
    All Phase 2 checks receive this object alongside the ParsedFile.
    """
    module_names: List[str] = field(default_factory=list)
    signals: List[SignalInfo] = field(default_factory=list)
    # clock signals inferred from posedge/negedge sensitivity lists
    clock_signals: Set[str] = field(default_factory=set)
    elaboration_errors: List[str] = field(default_factory=list)


def build_elaborated(pf: ParsedFile) -> Optional[ElaboratedModule]:
    """
    Build an ElaboratedModule from a ParsedFile.

    Returns None if pyslang cannot elaborate the file at all (e.g. missing
    imports that we cannot resolve).  Partial elaboration errors are
    recorded in ElaboratedModule.elaboration_errors but do not return None.

    Caches result on pf.elaborated: subsequent calls are O(1).
    """
    # Return cached result if already built
    if pf.elaborated is not None:
        return pf.elaborated

    if pf.syntax_tree is None or pf.parse_errors:
        return None

    em = ElaboratedModule(module_names=list(pf.modules))

    try:
        compilation = pyslang.Compilation()
        compilation.addSyntaxTree(pf.syntax_tree)
        diags = compilation.getAllDiagnostics()
        for d in diags:
            try:
                if d.isError():
                    em.elaboration_errors.append(
                        f"{d.code}: {' '.join(str(a) for a in d.args)}"
                    )
            except Exception:
                em.elaboration_errors.append(str(d))

        root = compilation.getRoot()
        _walk_instance(root, em)

    except Exception as exc:
        # Fatal pyslang error — return empty rather than crash
        em.elaboration_errors.append(f"[fatal] {exc}")

    # Infer clock signals from parser's always-block data
    for ab in pf.always_blocks:
        sens = ab.sensitivity.lower()
        for m in re.finditer(r"\b(?:posedge|negedge)\s+(\w+)", sens):
            em.clock_signals.add(m.group(1))

    # Cache for subsequent calls
    pf.elaborated = em
    return em


def _walk_instance(
    symbol: "pyslang.Symbol",
    em: ElaboratedModule,
) -> None:
    """Recursively walk an elaborated instance and collect signal info."""
    try:
        members = list(symbol.members)
    except Exception:
        return

    for member in members:
        try:
            kind = member.kind
            if kind in (pyslang.SymbolKind.Variable, pyslang.SymbolKind.Net):
                _collect_signal(member, em)
            elif kind in (
                pyslang.SymbolKind.Instance,
                pyslang.SymbolKind.InstanceBody,
            ):
                _walk_instance(member, em)
        except Exception:
            continue


def _collect_signal(sym: "pyslang.Symbol", em: ElaboratedModule) -> None:
    """Collect a variable or net symbol into em.signals."""
    try:
        line = 1
        try:
            syntax = sym.getSyntax()
            if syntax is not None:
                loc = syntax.sourceRange().start()
                line = int(loc.line()) if callable(getattr(loc, "line", None)) else 1
        except Exception:
            pass
        width = 1
        try:
            width = int(sym.type.bitstreamWidth())
        except Exception:
            pass
        em.signals.append(SignalInfo(name=sym.name, line=line, width=width))
    except Exception:
        pass


# Keep old names as thin aliases so any future callers aren't broken.
_collect_variable = _collect_signal
_collect_net = _collect_signal
