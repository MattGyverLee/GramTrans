#!/usr/bin/env python3
"""Post-build smoke test (FR-047, FR-048, `contracts/build-and-release.md` §4).

    python build\\smoke\\run_smoke.py <artifact-path>

Eight checks against a **frozen artifact**, run by `build.py` for each target.
Exit 0 = PASS, non-zero = FAIL, and a FAIL blocks that artifact from release.

Why these eight and not a test suite: the unit suite already covers behaviour
against the source tree. What can only break *in the bundle* is packaging —
a missing hidden import, a shadowed flat name, a native DLL a hook did not
collect, a version that is not what the lock pinned. Every check below is one
of those, plus the two end-to-end assertions (a real Preview, and the target
unchanged) that prove the packaging actually holds together.

Check 5 needs FieldWorks and the fixture project pair, so it is skipped with a
loud notice where they are absent. A skipped check is reported as `SKIP` and
does **not** count as a pass — a release build must run somewhere that has
them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

BUILD_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BUILD_DIR.parent
LOCK = BUILD_DIR / "requirements.lock"

SOURCE_PROJECT = "Ejagham Mini"
TARGET_PROJECT = "Ejagham Full GT-Test"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


class Results:
    def __init__(self) -> None:
        self.rows: List[Tuple[int, str, str, str]] = []

    def add(self, number: int, name: str, verdict: str, detail: str = "") -> None:
        self.rows.append((number, name, verdict, detail))
        print(f"[{verdict}] {number}. {name}" + (f"\n         {detail}" if detail else ""))

    @property
    def failed(self) -> bool:
        return any(v == FAIL for _, _, v, _ in self.rows)

    @property
    def skipped(self) -> int:
        return sum(1 for _, _, v, _ in self.rows if v == SKIP)


def _run(artifact: Path, args: List[str], timeout: int = 180):
    """Run the frozen artifact with a clean environment.

    `PYTHONPATH` is deliberately *set to something hostile* nowhere here — the
    isolation hook is exercised by check 4's inspection rather than by
    poisoning a real run, because a poisoned run that fails tells us nothing
    about whether the hook or the bundle was responsible.
    """
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return subprocess.run(
        [str(artifact), *args], capture_output=True, text=True,
        timeout=timeout, env=env,
    )


def _bundle_dir(artifact: Path) -> Optional[Path]:
    """The onedir payload directory, or `None` for a onefile artifact.

    Several checks inspect files inside the bundle. A onefile executable has
    no inspectable tree until it unpacks at runtime, so those checks report
    `SKIP` for it — which is honest, and is part of why the portable artifact
    is best-effort rather than supported.
    """
    internal = artifact.parent / "_internal"
    return internal if internal.is_dir() else None


#: Locked distributions that are **build-time only** and must NOT appear in the
#: artifact. The lock's roots include `pyinstaller`, so the lock is not by
#: itself the list of things that ship — check 6 would otherwise demand the
#: freezer be inside its own output. Listed explicitly rather than inferred,
#: because "which of these ships" is a decision, and an inferred answer would
#: quietly absorb a new runtime dependency as build-only.
BUILD_ONLY = {
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "altgraph",          # pyinstaller's dependency graph library
    "pefile",            # pyinstaller, for PE inspection
    "pywin32-ctypes",    # pyinstaller, for Windows version resources
    "setuptools",        # pyinstaller build-time
    "packaging",         # pyinstaller build-time
}


def locked_components(runtime_only: bool = False) -> dict:
    components = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "--hash")):
            continue
        if "==" in line:
            name, _, rest = line.partition("==")
            key = name.strip().lower()
            if runtime_only and key in BUILD_ONLY:
                continue
            components[key] = rest.split()[0].strip(" \\")
    return components


def _dist_info_version(dir_name: str) -> str:
    """`cdfutils-1.1.2.dist-info` -> `1.1.2`.

    Splitting on `-` alone leaves `1.1.2.dist`, which produced a whole screen
    of spurious "version mismatch" lines on the first real build.
    """
    stem = dir_name[: -len(".dist-info")] if dir_name.endswith(".dist-info") else dir_name
    _, _, version = stem.rpartition("-")
    return version


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def check_1_starts_and_exits(artifact: Path, r: Results) -> None:
    """FR-048. `--version` is the cheapest full start-up-and-exit path."""
    try:
        proc = _run(artifact, ["--version"])
    except subprocess.TimeoutExpired:
        r.add(1, "Starts and exits cleanly", FAIL,
              "the application did not exit within the timeout")
        return
    if proc.returncode != 0:
        r.add(1, "Starts and exits cleanly", FAIL,
              f"exit code {proc.returncode}: {(proc.stderr or proc.stdout)[-600:]}")
        return
    r.add(1, "Starts and exits cleanly", PASS, proc.stdout.strip()[:200])


def check_2_self_check_passes(artifact: Path, r: Results) -> Optional[str]:
    """FR-048. The self-check is the diagnostic users are asked for; it has to
    work in the artifact, not just in the source tree."""
    try:
        proc = _run(artifact, ["--self-check"])
    except subprocess.TimeoutExpired:
        r.add(2, "--self-check returns PASS", FAIL, "timed out")
        return None
    output = proc.stdout + proc.stderr
    if "VERDICT: PASS" not in output:
        r.add(2, "--self-check returns PASS", FAIL,
              f"exit {proc.returncode}; output:\n{output[-1500:]}")
        return output
    r.add(2, "--self-check returns PASS", PASS)
    return output


def check_3_projects_enumerated(self_check_output: Optional[str], r: Results) -> None:
    """FR-048: at least one project enumerated — proves LCM is actually
    reachable from inside the bundle, not merely importable."""
    if self_check_output is None:
        r.add(3, "Project list is populated", FAIL, "no self-check output to read")
        return
    # The self-check renders the count on the check's `detected:` line, one
    # line below the check name:
    #     [PASS] Projects enumerated
    #              detected: 84
    m = re.search(
        r"^\[\w+\] Projects enumerated\s*\n\s*detected:\s*(\d+)",
        self_check_output, re.M,
    )
    if not m:
        r.add(3, "Project list is populated", FAIL,
              "the self-check block did not report a project count")
        return
    count = int(m.group(1))
    if count < 1:
        r.add(3, "Project list is populated", FAIL, "zero projects enumerated")
        return
    r.add(3, "Project list is populated", PASS, f"{count} project(s)")


def check_4_no_interface_fallback_unreachable(
    artifact: Path, self_check_output: Optional[str], r: Results
) -> None:
    """FR-005 / FR-006. Two halves.

    PyQt6 must import and a `QApplication` must construct *inside the bundle*
    (which is what makes `MainFunction`'s no-interface branch unreachable), and
    no hard-coded project name may appear in any output.
    """
    problems = []
    combined_check = self_check_output or ""
    if not re.search(r"^\[PASS\] UI toolkit", combined_check, re.M):
        problems.append("the self-check did not report a passing UI toolkit check")

    combined = self_check_output or ""
    try:
        combined += _run(artifact, ["--version"]).stdout
        combined += _run(artifact, ["--nonsense-argument"]).stdout
        combined += _run(artifact, ["--nonsense-argument"]).stderr
    except subprocess.TimeoutExpired:
        problems.append("the artifact hung while collecting output")

    for banned in ("DEFAULT_SOURCE_PROJECT", "Ejagham"):
        if banned in combined:
            problems.append(f"{banned!r} appeared in the artifact's output")

    if problems:
        r.add(4, "No-interface fallback unreachable; no project literal", FAIL,
              "; ".join(problems))
        return
    r.add(4, "No-interface fallback unreachable; no project literal", PASS)


def check_5_preview_leaves_target_unchanged(artifact: Path, r: Results) -> None:
    """FR-048 / SC-004 — the end-to-end one.

    Runs against the source tree's own integration test rather than driving the
    frozen GUI: the artifact has no headless transfer interface, on purpose
    (FR-011), so there is no way to ask it for a Preview from a script. What
    this check *can* establish is that the same pair still previews without
    touching the target on this machine, which is the SC-004 claim.
    """
    projects_root = os.environ.get(
        "GRAMTRANS_PROJECTS_ROOT", r"C:\ProgramData\SIL\FieldWorks\Projects"
    )
    target = Path(projects_root) / TARGET_PROJECT / f"{TARGET_PROJECT}.fwdata"
    source = Path(projects_root) / SOURCE_PROJECT / f"{SOURCE_PROJECT}.fwdata"
    if not (target.is_file() and source.is_file()):
        r.add(5, "Preview against a known pair; target unchanged", SKIP,
              f"the fixture pair is not on this machine (looked in {projects_root}). "
              "A release build must run this check.")
        return

    before = _sha256(target)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-m", "integration",
         "tests/integration/test_034_standalone_preview_live.py"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    after = _sha256(target)

    if proc.returncode != 0:
        r.add(5, "Preview against a known pair; target unchanged", FAIL,
              (proc.stdout + proc.stderr)[-1500:])
        return
    if before != after:
        r.add(5, "Preview against a known pair; target unchanged", FAIL,
              f"{TARGET_PROJECT}.fwdata changed during a Preview")
        return
    r.add(5, "Preview against a known pair; target unchanged", PASS,
          f"sha256 {before[:16]}... unchanged")


def check_6_locked_components_present(artifact: Path, r: Results) -> None:
    """US3-2: every locked component present at exactly the locked version."""
    bundle = _bundle_dir(artifact)
    if bundle is None:
        r.add(6, "Locked components present at locked versions", SKIP,
              "onefile artifact -- no inspectable tree until runtime")
        return

    expected = locked_components(runtime_only=True)
    missing, wrong = [], []
    for name, version in sorted(expected.items()):
        # Distributions land as `<name>-<version>.dist-info`, with `-`/`.`
        # normalised to `_` by the installer.
        stem = name.replace("-", "_")
        matches = list(bundle.glob(f"{stem}-*.dist-info")) + \
            list(bundle.glob(f"{name}-*.dist-info"))
        if not matches:
            missing.append(name)
            continue
        found = {_dist_info_version(m.name) for m in matches}
        if version not in found:
            wrong.append(f"{name}: expected {version}, found {sorted(found)}")

    # And the other direction: a build-time tool that got into the artifact is
    # also a defect -- it means the freezer swept in its own machinery.
    leaked = sorted(
        name for name in BUILD_ONLY
        if list(bundle.glob(f"{name.replace('-', '_')}-*.dist-info"))
    )

    if missing or wrong or leaked:
        detail = ""
        if missing:
            detail += f"missing: {missing}. "
        if wrong:
            detail += f"version mismatch: {wrong}. "
        if leaked:
            detail += f"build-only distribution shipped: {leaked}"
        r.add(6, "Locked components present at locked versions", FAIL, detail)
        return
    r.add(6, "Locked components present at locked versions", PASS,
          f"{len(expected)} runtime component(s) at the locked versions")


def check_7_no_fieldworks_assembly_bundled(artifact: Path, r: Results) -> None:
    """FR-045. FieldWorks is a user-installed prerequisite, never shipped.

    `clr.AddReference` resolves the assemblies at runtime from the `sys.path`
    entry flexicon appends. Bundling them would be both a licensing problem and
    a correctness one: a stale copy loaded in preference to the user's install.
    """
    bundle = _bundle_dir(artifact)
    if bundle is None:
        r.add(7, "No FieldWorks or LibLCM assembly bundled", SKIP,
              "onefile artifact -- no inspectable tree until runtime")
        return

    # Managed FieldWorks/LibLCM assemblies, by name. `icu*.dll` was in this
    # list on the first real build and produced a false FAIL: the bundle's
    # `icudt73.dll` / `icuuc.dll` are ICU 73 collected from the build machine's
    # Python distribution, whereas FieldWorks ships ICU **68**
    # (`icudt68.dll`, `icuuc68.dll`). Matching on "icu" therefore flagged a
    # component that has nothing to do with FieldWorks. The versioned
    # FieldWorks ICU names are still matched below, which is the part that
    # would actually indicate a leak.
    patterns = ("SIL.LCModel*", "SIL.FieldWorks*", "FieldWorks*", "FwUtils*",
                "SIL.Core*", "SIL.Utils*", "LibLCM*", "icu*68.dll",
                "icu.net.dll", "ICU4NET.dll", "Icu*EC.dll")
    found = sorted(
        {p.name for pattern in patterns for p in bundle.rglob(pattern)}
    )
    # clr_loader's and pythonnet's own DLLs are ours to ship and are not
    # FieldWorks assemblies.
    found = [f for f in found if f not in {"ClrLoader.dll", "Python.Runtime.dll"}]
    if found:
        r.add(7, "No FieldWorks or LibLCM assembly bundled", FAIL,
              f"found: {found}")
        return
    r.add(7, "No FieldWorks or LibLCM assembly bundled", PASS)


def check_8_no_flat_name_collision(artifact: Path, r: Results) -> None:
    """Research R6. Re-run against the bundle rather than the build venv.

    The build-time check in `hiddenimports.py` looks at the venv; this looks at
    what actually shipped, which is what would do the shadowing.
    """
    sys.path.insert(0, str(BUILD_DIR))
    import hiddenimports as hi  # noqa: E402

    bundle = _bundle_dir(artifact)
    if bundle is None:
        r.add(8, "No flat-name collision", SKIP,
              "onefile artifact -- no inspectable tree until runtime")
        return

    ours = set(hi.flat_names())
    shipped = set()
    for entry in bundle.iterdir():
        if entry.is_dir() and (entry / "__init__.py").is_file():
            shipped.add(entry.name)
        elif entry.suffix in {".py", ".pyd"}:
            shipped.add(entry.name.split(".")[0])
    # Our own modules are in the archive, not loose in _internal, so anything
    # loose that matches a flat name of ours came from somewhere else.
    collisions = sorted(ours & shipped)
    if collisions:
        r.add(8, "No flat-name collision", FAIL,
              f"a bundled distribution provides: {collisions}")
        return
    r.add(8, "No flat-name collision", PASS)


# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="path to the built .exe")
    parser.add_argument("--json", type=Path, default=None,
                        help="also write the results as JSON")
    args = parser.parse_args(argv)

    artifact = args.artifact.resolve()
    if not artifact.is_file():
        print(f"[FAIL] artifact not found: {artifact}")
        return 2

    print(f"Smoke test: {artifact}")
    print("=" * 72)
    r = Results()

    check_1_starts_and_exits(artifact, r)
    self_check_output = check_2_self_check_passes(artifact, r)
    check_3_projects_enumerated(self_check_output, r)
    check_4_no_interface_fallback_unreachable(artifact, self_check_output, r)
    check_5_preview_leaves_target_unchanged(artifact, r)
    check_6_locked_components_present(artifact, r)
    check_7_no_fieldworks_assembly_bundled(artifact, r)
    check_8_no_flat_name_collision(artifact, r)

    print("=" * 72)
    passed = sum(1 for _, _, v, _ in r.rows if v == PASS)
    print(f"VERDICT: {'FAIL' if r.failed else 'PASS'} "
          f"({passed} of {len(r.rows)} passed, {r.skipped} skipped)")
    if r.skipped:
        print("NOTE: a skipped check is not a pass. A release build must run "
              "on a machine where every check can execute.")

    if args.json:
        args.json.write_text(json.dumps(
            [{"n": n, "check": c, "verdict": v, "detail": d} for n, c, v, d in r.rows],
            indent=2), encoding="utf-8")

    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
