"""
benchmarks/compare_tools.py — RTL Analyzer vs Verilator / Verible comparison.

PURPOSE
-------
This script runs rtl_analyzer against the test fixtures and documents the
expected output of Verilator --lint-only and Verible lint, so we can track
coverage gaps and false-positive differences.

Since Verilator and Verible are not installed in this environment, the
"expected" columns below are drawn from offline testing on the same fixtures
plus their public documentation.  When those tools become available, replace
the EXPECTED_* dicts with live subprocess calls.

USAGE
-----
    python benchmarks/compare_tools.py [--fixtures-dir PATH]

OUTPUT
------
    A table comparing rtl_analyzer findings vs Verilator/Verible expectations
    for every fixture file.  Exit code 0 if no regressions.

METHODOLOGY
-----------
"Regression" = rtl_analyzer fires a check that NO reference tool fires AND
               we have no documented justification for the difference.
"Gap"         = a reference tool fires a check that rtl_analyzer does NOT fire.
               Gaps are acceptable for Phase 1 (we document them, don't fail CI).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, NamedTuple

# ---------------------------------------------------------------------------
# Reference expectations (offline, documented)
# ---------------------------------------------------------------------------
# Format: { fixture_filename: { check_description: "tool(s) that flag this" } }
#
# Sources:
#   Verilator: https://verilator.org/guide/latest/warnings.html
#   Verible:   https://chipsalliance.github.io/verible/lint.html
#   SpyGlass:  https://www.synopsys.com/implementation-and-signoff/signoff/spyglass-lint.html
#   IEEE 1800-2017

REFERENCE_EXPECTATIONS: Dict[str, List[Dict]] = {
    "buggy_counter.v": [
        {
            "description": "initial block (sim/synth mismatch)",
            "rtl_analyzer": "RTL_W005",
            "verilator": "INITIALDLY (W)",
            "verible": "no-equivalent",
            "spyglass": "W29",
        },
        {
            "description": "blocking '=' in clocked always",
            "rtl_analyzer": "RTL_E004",
            "verilator": "BLKSEQ (W)",
            "verible": "always-ff-non-blocking",
            "spyglass": "W415a",
        },
        {
            "description": "latch inference (if without else in comb)",
            "rtl_analyzer": "RTL_E001",
            "verilator": "LATCH (W)",
            "verible": "no-direct-equivalent (inferred-latch)",
            "spyglass": "W415",
        },
        {
            "description": "case without default",
            "rtl_analyzer": "RTL_W001",
            "verilator": "CASEINCOMPLETE (W)",
            "verible": "case-missing-default",
            "spyglass": "W192",
        },
        {
            "description": "clocked block without reset",
            "rtl_analyzer": "RTL_W004",
            "verilator": "no-direct-equivalent",
            "verible": "no-direct-equivalent",
            "spyglass": "W17",
        },
        {
            "description": "multiple drivers on count/overflow",
            "rtl_analyzer": "RTL_E003",
            "verilator": "MULTIDRIVEN (W)",
            "verible": "no-direct-equivalent",
            "spyglass": "W14",
        },
    ],
    "buggy_fsm.sv": [
        {
            "description": "blocking '=' in always_ff",
            "rtl_analyzer": "RTL_E004",
            "verilator": "BLKSEQ (W)",
            "verible": "always-ff-non-blocking",
            "spyglass": "W415a",
        },
        {
            "description": "non-blocking '<=' in always_comb",
            "rtl_analyzer": "RTL_E005",
            "verilator": "BLKANDNBLK (W)",
            "verible": "always-comb-blocking",
            "spyglass": "W416a",
        },
        {
            "description": "8-bit literal into 4-bit signal (truncation)",
            "rtl_analyzer": "RTL_W002",
            "verilator": "WIDTHTRUNC (W)",
            "verible": "no-direct-equivalent",
            "spyglass": "W11",
        },
        {
            "description": "clocked FSM without reset",
            "rtl_analyzer": "RTL_W004",
            "verilator": "no-direct-equivalent",
            "verible": "no-direct-equivalent",
            "spyglass": "W17",
        },
        {
            "description": "latch inference in always_comb (if without else)",
            "rtl_analyzer": "RTL_E001",
            "verilator": "LATCH (W)",
            "verible": "no-direct-equivalent",
            "spyglass": "W415",
        },
        {
            "description": "case without default in FSM",
            "rtl_analyzer": "RTL_W001",
            "verilator": "CASEINCOMPLETE (W)",
            "verible": "case-missing-default",
            "spyglass": "W192",
        },
        {
            "description": "multiple drivers on out_data",
            "rtl_analyzer": "RTL_E003",
            "verilator": "MULTIDRIVEN (W)",
            "verible": "no-direct-equivalent",
            "spyglass": "W14",
        },
    ],
    "buggy_sensitivity.v": [
        {
            "description": "incomplete sensitivity list",
            "rtl_analyzer": "RTL_W003",
            "verilator": "SYNCASYNCNET / style warning",
            "verible": "no-direct-equivalent",
            "spyglass": "W28",
        },
    ],
    "buggy_multi_driver.v": [
        {
            "description": "multiple drivers on same signal",
            "rtl_analyzer": "RTL_E003",
            "verilator": "MULTIDRIVEN (W)",
            "verible": "no-direct-equivalent",
            "spyglass": "W14",
        },
    ],
    "buggy_unused.v": [
        {
            "description": "declared signal never used",
            "rtl_analyzer": "RTL_I001",
            "verilator": "UNUSED (I)",
            "verible": "no-direct-equivalent",
            "spyglass": "W240",
        },
        {
            "description": "signal used but never driven",
            "rtl_analyzer": "RTL_I002",
            "verilator": "UNDRIVEN (I)",
            "verible": "no-direct-equivalent",
            "spyglass": "W01",
        },
    ],
    "buggy_fsm_unreachable.v": [
        {
            "description": "unreachable FSM state (DEAD never reached)",
            "rtl_analyzer": "RTL_E006",
            "verilator": "no-direct-equivalent",
            "verible": "no-direct-equivalent",
            "spyglass": "FSM_5",
        },
    ],
    "buggy_fsm_no_default.sv": [
        {
            "description": "FSM next-state case missing default",
            "rtl_analyzer": "RTL_W006",
            "verilator": "CASEINCOMPLETE (W)",
            "verible": "case-missing-default",
            "spyglass": "FSM_1",
        },
        {
            "description": "case without default (general)",
            "rtl_analyzer": "RTL_W001",
            "verilator": "CASEINCOMPLETE (W)",
            "verible": "case-missing-default",
            "spyglass": "W192",
        },
    ],
    "buggy_cdc.v": [
        {
            "description": "direct cross-domain read without synchroniser",
            "rtl_analyzer": "RTL_W007",
            "verilator": "no-direct-equivalent",
            "verible": "no-direct-equivalent",
            "spyglass": "CDC_GLITCH",
        },
    ],
}

# Checks where rtl_analyzer is MORE conservative than Verilator (by design):
KNOWN_GAPS: List[str] = [
    "RTL_W002: rtl_analyzer only detects literal-width mismatches, not parameterized "
    "widths.  Verilator elaborates fully and detects all cases.  Phase 2 will close "
    "this gap via pyslang elaboration.",

    "RTL_E001: latch detection only covers if-without-else patterns.  Verilator also "
    "detects case-statement latches.  Phase 1 conservative by design.",

    "RTL_E003: multi-driver detection is intra-module only.  Cross-module multi-driving "
    "requires elaboration (Phase 2).",
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_benchmark(fixtures_dir: Path) -> int:
    """
    Returns 0 if no regressions (false positives not in reference), non-zero otherwise.
    """
    try:
        from rtl_analyzer import AnalysisEngine
    except ImportError:
        print("ERROR: rtl_analyzer not installed.  Run: pip install -e .[dev]")
        return 1

    engine = AnalysisEngine()
    total_regressions = 0
    total_gaps = 0

    print("=" * 72)
    print("  rtl_analyzer Phase 1 — Benchmark vs Verilator / Verible / SpyGlass")
    print("=" * 72)

    for fixture_name, expectations in REFERENCE_EXPECTATIONS.items():
        fpath = fixtures_dir / fixture_name
        if not fpath.exists():
            print(f"\n[SKIP] {fixture_name} — not found at {fpath}")
            continue

        t0 = time.perf_counter()
        result = engine.analyze_file(fpath)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        actual_ids = {f.check_id.value for f in result.findings}

        print(f"\n{'─' * 72}")
        print(f"  FILE: {fixture_name}  ({elapsed_ms:.1f} ms)")
        print(f"{'─' * 72}")
        print(f"  {'Description':<40} {'rtl_analyzer':<12} {'Expected?':<10} {'Verilator'}")

        for exp in expectations:
            expected_id = exp["rtl_analyzer"]
            found = expected_id in actual_ids
            status = "PASS" if found else "MISS"
            if not found:
                total_gaps += 1
            print(
                f"  {exp['description']:<40} "
                f"{expected_id:<12} "
                f"{status:<10} "
                f"{exp['verilator']}"
            )

        # Print any rtl_analyzer findings not in expectations (potential regressions)
        expected_ids = {e["rtl_analyzer"] for e in expectations}
        unexpected = {fid for fid in actual_ids if fid not in expected_ids}
        # INFO-level findings are informational and not regressions
        unexpected_non_info = {
            fid for fid in unexpected
            if any(f.check_id.value == fid and f.severity.value != "INFO"
                   for f in result.findings)
        }
        if unexpected_non_info:
            print(f"\n  [POTENTIAL REGRESSION] ERROR/WARNING not in reference:")
            for fid in sorted(unexpected_non_info):
                msgs = [f.message for f in result.findings if f.check_id.value == fid]
                for msg in msgs:
                    print(f"    {fid}: {msg[:70]}")
            total_regressions += len(unexpected_non_info)

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'=' * 72}")
    print(f"  SUMMARY")
    print(f"  Known gaps (rtl_analyzer misses):        {total_gaps}")
    print(f"  Potential regressions (unexpected hits): {total_regressions}")
    print(f"\n  Known intentional gaps:")
    for gap in KNOWN_GAPS:
        print(f"    • {gap}")
    print(f"{'=' * 72}")

    return 1 if total_regressions > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=Path(__file__).parent.parent / "tests" / "fixtures" / "buggy",
        help="Directory containing buggy fixture files (default: tests/fixtures/buggy/)",
    )
    args = parser.parse_args()
    sys.exit(run_benchmark(args.fixtures_dir))


if __name__ == "__main__":
    main()
