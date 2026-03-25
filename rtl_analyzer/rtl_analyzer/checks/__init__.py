"""
checks/__init__.py — registry of all deterministic checks.

Each check is a function:
    def check_XYZ(pf: ParsedFile) -> List[Finding]: ...

Checks must be:
  • Pure functions — no side effects, no global state.
  • Fast — O(lines) or O(lines²) at worst. No subprocess calls.
  • Conservative — a false negative (miss) is better than a false positive.
  • Documented with the reference standard / commercial-tool equivalent.
"""

from .blocking_in_ff import check_blocking_in_ff
from .nonblocking_in_comb import check_nonblocking_in_comb
from .latch_inference import check_latch_inference
from .missing_default import check_missing_default
from .width_mismatch import check_width_mismatch
from .sensitivity_list import check_sensitivity_list
from .missing_reset import check_missing_reset
from .sim_synth_mismatch import check_sim_synth_mismatch
from .multi_driver import check_multi_driver
from .unused_signals import check_unused_signals
from .combinational_loop import check_combinational_loop
from .empty_always import check_empty_always
from .fsm_extractor import check_fsm
from .cdc_checker import check_cdc

ALL_CHECKS = [
    check_blocking_in_ff,
    check_nonblocking_in_comb,
    check_latch_inference,
    check_missing_default,
    check_width_mismatch,
    check_sensitivity_list,
    check_missing_reset,
    check_sim_synth_mismatch,
    check_multi_driver,
    check_unused_signals,
    check_combinational_loop,
    check_empty_always,
    check_fsm,
    check_cdc,
]

__all__ = ["ALL_CHECKS"] + [c.__name__ for c in ALL_CHECKS]
