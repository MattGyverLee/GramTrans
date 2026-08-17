#!/usr/bin/env python3
"""SC-014 / FR-020 — no unlisted shared-code change on this branch.

Feature 034's whole safety argument is that the FlexTools path is untouched
except at a handful of enumerated, individually justified points. `plan.md`
holds that enumeration; this script is what makes it binding rather than
aspirational.

It diffs the branch against its merge base with `main`, collects every changed
file under `src/gramtrans/Lib/` plus `src/gramtrans/gramtrans.py`, and fails
unless that set is a **subset** of the plan's exception table. Additions count
as changes — a new shared-code file is exactly as much of a shared-code change
as an edit to an old one, which is why `Lib/gate.py` had to be added to the
table (row 6) before this check could run green.

Usage:
    python .github/scripts/check_shared_exceptions.py [--base REF] [--plan PATH]

Exit codes: 0 clean, 1 unlisted change found, 2 the check could not run.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PLAN = "specs/034-standalone-windows-app/plan.md"

# The shared surface this feature promises not to disturb. Anything changed
# inside it must appear in the plan's exception table.
SHARED_PREFIXES = ("src/gramtrans/Lib/",)
SHARED_FILES = ("src/gramtrans/gramtrans.py",)

# `| 6 | `src/gramtrans/Lib/gate.py` | ... |` — the row number in cell 1 and a
# backticked repo-relative path in cell 2. Anchored on the numeric first cell
# so prose tables elsewhere in the plan cannot leak entries in.
_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|")


def _run(args: list[str]) -> str:
    proc = subprocess.run(
        args, cwd=str(REPO_ROOT), capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"`{' '.join(args)}` failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def parse_exceptions(plan_path: Path) -> set[str]:
    """The set of shared files the plan sanctions changing."""
    if not plan_path.is_file():
        raise RuntimeError(f"plan not found: {plan_path}")
    allowed: set[str] = set()
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        m = _ROW.match(line.strip())
        if m:
            allowed.add(m.group(2).strip().replace("\\", "/"))
    if not allowed:
        raise RuntimeError(
            f"no exception rows parsed out of {plan_path} — the table format "
            "changed, and a silently-empty allow-list would fail every change "
            "rather than checking anything"
        )
    return allowed


def resolve_base(requested: str | None) -> str:
    """Pick a base ref that actually exists in this checkout.

    A shallow CI clone often has `origin/main` but not `main`; a developer's
    worktree usually has both. Trying in order beats hard-coding either.
    """
    candidates = [requested] if requested else ["origin/main", "main"]
    for ref in candidates:
        if ref is None:
            continue
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return ref
    raise RuntimeError(
        f"none of {candidates} resolves to a commit — fetch the base branch "
        "(actions/checkout needs fetch-depth: 0) or pass --base"
    )


def changed_shared_files(base: str) -> list[str]:
    """Shared-surface paths touched between the merge base and HEAD.

    Three-dot so a base branch that has moved on does not turn every commit
    made on `main` since the branch point into a finding against this branch.
    """
    out = _run(["git", "diff", "--name-only", f"{base}...HEAD"])
    changed = [p.strip().replace("\\", "/") for p in out.splitlines() if p.strip()]
    return sorted(
        p
        for p in changed
        if p in SHARED_FILES or any(p.startswith(x) for x in SHARED_PREFIXES)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None,
                        help="base ref (default: origin/main, then main)")
    parser.add_argument("--plan", default=DEFAULT_PLAN,
                        help=f"plan file holding the exception table (default: {DEFAULT_PLAN})")
    args = parser.parse_args(argv)

    try:
        base = resolve_base(args.base)
        allowed = parse_exceptions(REPO_ROOT / args.plan)
        touched = changed_shared_files(base)
    except RuntimeError as exc:
        print(f"[ERROR] shared-code exception check could not run: {exc}")
        return 2

    print(f"[INFO] base ref            : {base}")
    print(f"[INFO] exception table     : {args.plan} ({len(allowed)} row(s))")
    for path in sorted(allowed):
        print(f"         allowed: {path}")
    print(f"[INFO] shared files changed: {len(touched)}")
    for path in touched:
        print(f"         changed: {path}")

    unlisted = [p for p in touched if p not in allowed]
    if unlisted:
        print()
        print("[FAIL] Unlisted shared-code change (SC-014, FR-020):")
        for path in unlisted:
            print(f"         {path}")
        print()
        print("       Either revert the change, or add a row to the exception "
              f"table in {args.plan} justifying it and explaining why the "
              "FlexTools path is unaffected. An unlisted shared-code change is "
              "a defect, not a review comment.")
        return 1

    print()
    print(f"[PASS] {len(touched)} shared-code change(s), all enumerated in the plan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
