#!/usr/bin/env python3
"""
Smart-Educator Presentation Test Runner
════════════════════════════════════════
Interactive CLI runner for the 18-test presentation suite.
Run from project root:  python presentation_tester.py
Options:
  --no-pause     Auto-advance (no waiting for Enter between tests)
  --delay N      Seconds to wait between tests in no-pause mode (default: 2)
  --test N       Run only test number N
  --phase N      Run only phase N (1, 2, or 3)
  --layer LAYER  Run only tests for a layer (P1, P2, P3)
"""

import sys
import os
import asyncio
import argparse
import time
import json

# ── ANSI Colors ─────────────────────────────────────────────────────────────

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"
BG_BLUE    = "\033[44m"
BG_GREEN   = "\033[42m"
BG_RED     = "\033[41m"
BG_YELLOW  = "\033[43m"
BG_MAGENTA = "\033[45m"
BG_CYAN    = "\033[46m"

# Layer colors
LAYER_COLORS = {
    "P1":       BLUE,
    "P2":       GREEN,
    "P3":       YELLOW,
    "P1+P2+P3": MAGENTA,
    "P3+P1":    CYAN,
}

LAYER_ICONS = {
    "P1":       "🟦",
    "P2":       "🟩",
    "P3":       "🟧",
    "P1+P2+P3": "⭐",
    "P3+P1":    "🟧🟦",
}

STATUS_DISPLAY = {
    "PASS":  f"{GREEN}{BOLD}✅ PASS{RESET}",
    "FAIL":  f"{RED}{BOLD}❌ FAIL{RESET}",
    "ERROR": f"{RED}{BOLD}💥 ERROR{RESET}",
}


def layer_color(layer: str) -> str:
    return LAYER_COLORS.get(layer, WHITE)


def layer_icon(layer: str) -> str:
    return LAYER_ICONS.get(layer, "")


# ── Formatting ──────────────────────────────────────────────────────────────

def print_banner():
    """Print the opening presentation banner."""
    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   🧠  Smart-Educator — Presentation Test Suite                       ║
║                                                                      ║
║   18 Live Tests • P1 (API & Data) • P2 (AI Pipeline) • P3 (Infra)   ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝{RESET}
""")


def print_phase_header(phase_num: int, phase_name: str, test_range: str):
    """Print a phase section header."""
    labels = {
        1: "🧱 CORE COMPONENT TESTS",
        2: "🔗 INTEGRATION TESTS",
        3: "🚀 END-TO-END PROJECT USAGE TESTS",
    }
    label = labels.get(phase_num, "")
    print(f"""
{BOLD}{CYAN}{'━' * 70}
  PHASE {phase_num}: {label} ({test_range})
{'━' * 70}{RESET}
""")


def print_test_header(test_num: int, total: int, name: str, layer: str, layer_name: str, files: list):
    """Print the boxed header for a single test."""
    lc = layer_color(layer)
    icon = layer_icon(layer)
    files_str = ", ".join(files)

    print(f"""
{lc}{BOLD}╔══════════════════════════════════════════════════════════════════════╗
║  TEST {test_num}/{total} — {icon} {layer}: {name:<48}║
║  Team: {layer_name:<60}║
║  Files: {files_str:<59}║
╚══════════════════════════════════════════════════════════════════════╝{RESET}
""")


def print_test_output(lines: list):
    """Print the test output lines with indentation."""
    for line in lines:
        print(f"  {line}")


def print_test_footer(status: str, duration: float, error: str = ""):
    """Print the test result footer."""
    print()
    print(f"  {'─' * 50}")
    print(f"  ⏱️  Duration: {duration:.2f}s")
    print(f"  {STATUS_DISPLAY.get(status, status)}")
    if error:
        print(f"  {RED}Error: {error[:200]}{RESET}")
    print()


def print_summary(results: list):
    """Print the final summary table."""
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    errors = sum(1 for r in results if r.status == "ERROR")
    total = len(results)
    total_time = sum(r.duration for r in results)

    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════════════╗
║                    📊  FINAL SUMMARY                                 ║
╠══════════════════════════════════════════════════════════════════════╣{RESET}""")

    for r in results:
        status_icon = {"PASS": f"{GREEN}✅{RESET}", "FAIL": f"{RED}❌{RESET}", "ERROR": f"{RED}💥{RESET}"}.get(r.status, "?")
        lc = layer_color(r.layer)
        li = layer_icon(r.layer)
        print(f"  {status_icon} {lc}{li} {r.layer:10s}{RESET} Test {r.test_number:2d}: {r.name:<45s} {DIM}{r.duration:.2f}s{RESET}")

    print(f"""
{BOLD}{CYAN}╠══════════════════════════════════════════════════════════════════════╣
║  Results: {GREEN}{passed} passed{RESET}{CYAN}  •  {RED}{failed} failed{RESET}{CYAN}  •  {RED}{errors} errors{RESET}{CYAN}  •  Total: {total}     ║
║  Time:    {total_time:.2f}s                                                   ║
╠══════════════════════════════════════════════════════════════════════╣{RESET}""")

    # Layer breakdown
    layer_stats = {}
    for r in results:
        for layer in r.layer.split("+"):
            if layer not in layer_stats:
                layer_stats[layer] = {"pass": 0, "fail": 0, "error": 0}
            layer_stats[layer][r.status.lower()] = layer_stats[layer].get(r.status.lower(), 0) + 1

    print(f"  {BOLD}Layer Coverage:{RESET}")
    for layer in ["P1", "P2", "P3"]:
        stats = layer_stats.get(layer, {"pass": 0, "fail": 0, "error": 0})
        lc = layer_color(layer)
        li = layer_icon(layer)
        total_l = stats["pass"] + stats.get("fail", 0) + stats.get("error", 0)
        print(f"    {lc}{li} {layer}: {stats['pass']}/{total_l} passed{RESET}")

    print(f"""
{BOLD}{CYAN}╚══════════════════════════════════════════════════════════════════════╝{RESET}
""")


# ── Main Runner ─────────────────────────────────────────────────────────────

def get_phase(test_num: int) -> int:
    if test_num <= 5:
        return 1
    elif test_num <= 10:
        return 2
    else:
        return 3


async def main():
    parser = argparse.ArgumentParser(description="Smart-Educator Presentation Test Runner")
    parser.add_argument("--no-pause", action="store_true", help="Auto-advance without waiting for Enter")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between tests in no-pause mode (seconds)")
    parser.add_argument("--test", type=int, help="Run only a specific test number (1-18)")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3], help="Run only a specific phase")
    parser.add_argument("--layer", type=str, choices=["P1", "P2", "P3"], help="Run only tests for a specific layer")
    args = parser.parse_args()

    # Import suite
    from presentation_suite import SmartEducatorPresentationTester, TEST_REGISTRY

    tester = SmartEducatorPresentationTester()

    # Determine which tests to run
    test_nums = list(range(1, 19))

    if args.test:
        test_nums = [args.test]
    elif args.phase:
        phase_ranges = {1: range(1, 6), 2: range(6, 11), 3: range(11, 19)}
        test_nums = list(phase_ranges[args.phase])
    elif args.layer:
        test_nums = [
            t["num"] for t in TEST_REGISTRY
            if args.layer in t["layer"]
        ]

    total = len(test_nums)

    print_banner()

    if args.no_pause:
        print(f"  {DIM}Mode: Auto-advance ({args.delay}s delay between tests){RESET}")
    else:
        print(f"  {DIM}Mode: Interactive (press Enter to advance between tests){RESET}")
    print(f"  {DIM}Tests to run: {total}{RESET}")
    print()

    results = []
    current_phase = 0

    for i, test_num in enumerate(test_nums, 1):
        meta = TEST_REGISTRY[test_num - 1]
        phase = get_phase(test_num)

        # Print phase header on phase change
        if phase != current_phase:
            current_phase = phase
            phase_names = {1: "Core Component Tests", 2: "Integration Tests", 3: "End-to-End Project Usage Tests"}
            phase_ranges = {1: "Tests 1-5", 2: "Tests 6-10", 3: "Tests 11-18"}
            print_phase_header(phase, phase_names[phase], phase_ranges[phase])

        # Print test header
        print_test_header(
            test_num=test_num,
            total=18,
            name=meta["name"],
            layer=meta["layer"],
            layer_name=meta["layer_name"],
            files=meta["files"],
        )

        # Run the test
        result = await tester.run_test(test_num)
        results.append(result)

        # Print output
        print_test_output(result.output_lines)
        print_test_footer(result.status, result.duration, result.error)

        # Wait for user or auto-advance
        if i < total:
            if args.no_pause:
                print(f"  {DIM}[Auto-advancing in {args.delay}s...]{RESET}")
                await asyncio.sleep(args.delay)
            else:
                try:
                    input(f"  {DIM}[Press Enter to continue to next test...]{RESET}")
                except (EOFError, KeyboardInterrupt):
                    print(f"\n  {YELLOW}Interrupted. Printing summary...{RESET}")
                    break

    # Print summary
    print_summary(results)

    # Save results as JSON for dashboard generation
    results_data = []
    for r in results:
        results_data.append({
            "test_number": r.test_number,
            "name": r.name,
            "layer": r.layer,
            "layer_name": r.layer_name,
            "files_tested": r.files_tested,
            "status": r.status,
            "output_lines": r.output_lines,
            "duration": r.duration,
            "error": r.error,
        })

    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presentation_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, ensure_ascii=False, indent=2)
    print(f"  {DIM}Results saved to: {results_path}{RESET}")
    print(f"  {DIM}Generate HTML dashboard: python generate_presentation_dashboard.py{RESET}")
    print()

    # Exit code
    failed = sum(1 for r in results if r.status in ("FAIL", "ERROR"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
