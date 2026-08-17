#!/usr/bin/env python3
"""SC-011 — the unit suite does not regress on this branch.

Runs `pytest -m "not integration"` and compares the set of failing node IDs
against `.github/known-failures.txt`. Fails on either kind of drift:

* **New failure** — a test failed that is not in the baseline. This branch
  broke something.
* **Stale baseline entry** — a listed test now passes. The list has to shrink
  in the commit that fixes the test, or it rots into a permanent excuse.

The plain `pytest` step this replaces would have been red from the feature's
first commit: 27 tests under features 026/029 already fail on `main`, none of
them related to the standalone host. A permanently-red gate is one nobody
reads, which is the exact failure FR-021 ("continuously during development,
not once at release") exists to prevent. See the baseline file's header.

Usage:
    python .github/scripts/check_suite_baseline.py [-- <extra pytest args>]

Exit codes: 0 no drift, 1 drift, 2 the check could not run.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / ".github" / "known-failures.txt"

# pytest's short summary lines: `FAILED tests/x.py::test_y - AssertionError: ...`
# and `ERROR tests/x.py::test_y`. The node ID stops at the first " - ".
_SUMMARY = re.compile(r"^(?:FAILED|ERROR)\s+(\S+?)(?:\s+-\s+.*)?$")


def load_baseline() -> set[str]:
    if not BASELINE.is_file():
        raise RuntimeError(f"baseline not found: {BASELINE}")
    entries = set()
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            entries.add(line.replace("\\", "/"))
    return entries


def run_suite(extra: list[str]) -> tuple[set[str], int, str]:
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", "not integration",
        "-q", "--tb=no", "-p", "no:cacheprovider",
        *extra,
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    failing = set()
    for line in output.splitlines():
        m = _SUMMARY.match(line.strip())
        if m:
            failing.add(m.group(1).replace("\\", "/"))
    return failing, proc.returncode, output


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--":
        argv = argv[1:]

    try:
        baseline = load_baseline()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 2

    failing, returncode, output = run_suite(argv)

    # An exit code that is neither "all passed" (0) nor "tests failed" (1)
    # means the run itself broke — collection error, internal error, no tests.
    # Comparing sets in that case would report a comfortable green.
    if returncode not in (0, 1):
        print(output[-4000:])
        print(f"[ERROR] pytest exited {returncode}; the suite did not run to completion.")
        return 2

    new_failures = sorted(failing - baseline)
    now_passing = sorted(baseline - failing)

    print(f"[INFO] failing now      : {len(failing)}")
    print(f"[INFO] baseline entries : {len(baseline)}")

    if new_failures:
        print()
        print("[FAIL] New test failures on this branch (SC-011):")
        for node in new_failures:
            print(f"         {node}")

    if now_passing:
        print()
        print("[FAIL] Baseline entries that now PASS — delete these lines from "
              f"{BASELINE.relative_to(REPO_ROOT).as_posix()}:")
        for node in now_passing:
            print(f"         {node}")

    if new_failures or now_passing:
        if new_failures:
            print()
            print(output[-6000:])
        return 1

    print()
    print(f"[PASS] No new failures; all {len(baseline)} baseline entries still "
          "fail for their own pre-existing reasons.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
