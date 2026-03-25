"""
rtl_analyzer — General-purpose RTL static analysis engine.

Phase 1: Deterministic bug detection (no ML, no GPU required).
Works on any Verilog/SystemVerilog project at any scale.
"""

from .engine import AnalysisEngine
from .models import Finding, Severity, CheckID

__all__ = ["AnalysisEngine", "Finding", "Severity", "CheckID"]
__version__ = "0.1.0"
