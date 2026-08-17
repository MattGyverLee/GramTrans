#!/usr/bin/env python3
"""Build the standalone Windows artifacts (`contracts/build-and-release.md` §1).

    python build\\build.py                 both artifacts
    python build\\build.py --installer     onedir + Inno Setup only
    python build\\build.py --portable      onefile only
    python build\\build.py --lock          regenerate requirements.lock

Seven ordered steps, and the order is the point:

1. **Fresh venv** under `build\\.venv-build`, deleting any prior one. Reusing
   it would let yesterday's resolution leak into today's artifact, which is
   exactly what SC-008 ("identical dependency set across two builds of one
   commit") is checking for.
2. `PYTHONNOUSERSITE=1`, `PYTHONPATH`/`PYTHONHOME` cleared for **every** child.
3. `pip install --require-hashes --no-cache-dir -r build\\requirements.lock`.
   No other source, no `-e`, **no fallback** (FR-042). A build that cannot be
   satisfied from the lock alone fails. Falling back to the build machine's
   environment would produce an artifact nobody can reproduce, and would do it
   silently.
4. Stamp `src\\gramtrans\\_buildinfo.py` (FR-049). Gitignored.
5. Freeze via `build\\gramtrans.spec` — one Analysis, both targets (FR-046).
6. Smoke-test each artifact (FR-047/FR-048).
7. Emit a manifest per artifact, and apply the release rule: a `FAIL` verdict
   blocks that artifact, and a failing `portable` MUST NOT block the
   `installer` (SC-010).

The build machine needs Python and git. Inno Setup (`ISCC.exe`, major 6 or 7 --
whichever is installed, newest wins) is needed for the installer; without it the
onedir tree is still produced and the installer step reports why it was skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

BUILD_DIR = Path(__file__).resolve().parent
REPO_ROOT = BUILD_DIR.parent
SRC = REPO_ROOT / "src"
VENV = BUILD_DIR / ".venv-build"
LOCK = BUILD_DIR / "requirements.lock"
LOCK_IN = BUILD_DIR / "requirements.in"
SPEC = BUILD_DIR / "gramtrans.spec"
DIST = BUILD_DIR / "dist"
WORK = BUILD_DIR / "build"
BUILDINFO = SRC / "gramtrans" / "_buildinfo.py"
INSTALLER_ISS = BUILD_DIR / "installer.iss"

APP_NAME = "GramTrans"


# ---------------------------------------------------------------------------
# Process plumbing
# ---------------------------------------------------------------------------

def child_env() -> Dict[str, str]:
    """A clean environment for every child process (step 2).

    `PYTHONNOUSERSITE` stops `%APPDATA%\\Python\\...\\site-packages` joining
    the venv's path, which is the quiet way a build machine's own packages get
    into an artifact.
    """
    env = dict(os.environ)
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONSTARTUP", None)
    return env


def run(cmd: List[str], *, cwd: Path = REPO_ROOT,
        check: bool = True) -> subprocess.CompletedProcess:
    printable = " ".join(str(c) for c in cmd)
    print(f"[RUN] {printable}")
    proc = subprocess.run(
        [str(c) for c in cmd], cwd=str(cwd), env=child_env(), text=True
    )
    if check and proc.returncode != 0:
        raise SystemExit(f"[FAIL] command failed ({proc.returncode}): {printable}")
    return proc


def capture(cmd: List[str], *, cwd: Path = REPO_ROOT) -> str:
    proc = subprocess.run(
        [str(c) for c in cmd], cwd=str(cwd), env=child_env(),
        capture_output=True, text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def venv_python() -> Path:
    return VENV / "Scripts" / "python.exe"


# ---------------------------------------------------------------------------
# Steps 1-3
# ---------------------------------------------------------------------------

def make_fresh_venv() -> None:
    if VENV.exists():
        print(f"[INFO] removing the previous build venv: {VENV}")
        shutil.rmtree(VENV)
    run([sys.executable, "-m", "venv", str(VENV)])
    run([str(venv_python()), "-m", "pip", "install", "--upgrade", "pip", "-q"])


def install_from_lock() -> None:
    if not LOCK.is_file():
        raise SystemExit(
            f"[FAIL] {LOCK} is missing. Regenerate it with "
            "`python build/build.py --lock`."
        )
    # --require-hashes makes every pin verified rather than merely written
    # down; --no-cache-dir stops a poisoned or stale wheel cache satisfying it.
    run([
        str(venv_python()), "-m", "pip", "install",
        "--require-hashes", "--no-cache-dir", "-r", str(LOCK),
    ])


def regenerate_lock() -> int:
    """`--lock`: recompile `requirements.lock` from `requirements.in`."""
    if shutil.which("uv") is None:
        print("[FAIL] `uv` is not on PATH. Install it "
              "(https://docs.astral.sh/uv/) or compile the lock with "
              "`pip-compile --generate-hashes`.")
        return 2
    run([
        "uv", "pip", "compile", str(LOCK_IN),
        "--generate-hashes", "--python-version", "3.12",
        "--output-file", str(LOCK),
    ])
    print(f"[PASS] regenerated {LOCK}")
    print("[NOTE] the explanatory header is not regenerated -- re-add it by "
          "hand if uv replaced it. It records why flexlibs1 and cdfutils are "
          "in the lock (FR-052/FR-053), which is not information uv has.")
    return 0


# ---------------------------------------------------------------------------
# Step 4 — version stamping (FR-049, research R10)
# ---------------------------------------------------------------------------

def describe_version() -> Dict[str, str]:
    described = capture(["git", "describe", "--tags", "--always", "--dirty"])
    sha = capture(["git", "rev-parse", "--short", "HEAD"])
    branch = capture(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    import datetime

    return {
        "version": described or "0.0.0-unknown",
        "commit": sha or "unknown",
        "branch": branch or "unknown",
        "built_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }


def stamp_buildinfo(info: Dict[str, str]) -> None:
    """Write the generated `_buildinfo.py` the shell reads.

    A generated module is the only mechanism that works identically frozen and
    unfrozen without shipping git metadata. It is gitignored, and the shell
    falls back to `gramtrans.__version__` plus "(source checkout)" when it is
    absent — so a developer run needs no build step.
    """
    BUILDINFO.write_text(
        '"""Generated by build/build.py. Not checked in (see .gitignore).\n\n'
        "Read by `standalone/prereq.py` for the self-check block and by the\n"
        "application's version display (FR-049). Absent on a source checkout,\n"
        "which is why every reader has a fallback.\n"
        '"""\n'
        f'VERSION = {info["version"]!r}\n'
        f'COMMIT = {info["commit"]!r}\n'
        f'BRANCH = {info["branch"]!r}\n'
        f'BUILT_AT = {info["built_at"]!r}\n',
        encoding="utf-8",
    )
    print(f"[INFO] stamped {BUILDINFO.relative_to(REPO_ROOT)}: "
          f"{info['version']} ({info['commit']}) {info['built_at']}")
    if info["version"].endswith("-dirty"):
        print("[WARN] the working tree is dirty. The artifact's stamped "
              "version records that, but it cannot be reproduced from the "
              "commit alone -- do not release this build.")


# ---------------------------------------------------------------------------
# Step 5 — freeze
# ---------------------------------------------------------------------------

def freeze(targets: List[str]) -> None:
    for path in (DIST, WORK):
        if not path.exists():
            continue
        try:
            shutil.rmtree(path)
        except PermissionError as exc:
            # Almost always a previously built artifact still running: the
            # onefile bootloader holds its unpacked temp tree, and flextoolslib
            # writes `flextools.log` into the working directory, which for a
            # double-clicked artifact is `dist\` itself. The raw traceback
            # names shutil and a log file, so it reads as a build bug rather
            # than "close the application you left open" -- which is the entire
            # fix, and takes two seconds once you know.
            raise SystemExit(
                f"[FAIL] cannot clear {path}: {exc.filename or path} is in use.\n"
                "       A previously built GramTrans is probably still running. "
                "Close it and build again.\n"
                "       Check with:  Get-Process GramTrans*, GramTrans-portable*"
            ) from exc
    cmd = [
        str(venv_python()), "-m", "PyInstaller", str(SPEC),
        "--noconfirm",
        "--distpath", str(DIST),
        "--workpath", str(WORK),
    ]
    if len(targets) == 1:
        cmd += ["--", f"--{targets[0]}"]
    run(cmd, cwd=BUILD_DIR)


# ---------------------------------------------------------------------------
# Installer (T044)
# ---------------------------------------------------------------------------

def _iscc_rank(exe: Path):
    """Sort key for a discovered `ISCC.exe`: newer major wins, then 64-bit.

    Directory names look like `Inno Setup 6` / `Inno Setup 7`. An unparsable
    tail sorts last rather than crashing the build -- a compiler we cannot
    rank is still better than no compiler at all.
    """
    tail = exe.parent.name.rsplit(" ", 1)[-1]
    major = int(tail) if tail.isdigit() else -1
    is_64bit = 0 if "(x86)" in str(exe) else 1
    return (major, is_64bit)


def find_iscc() -> Optional[str]:
    """Locate the Inno Setup compiler: PATH first, then the default installs.

    The install directory is versioned (`Inno Setup 6`, `Inno Setup 7`, ...)
    and Inno Setup supports installing majors side by side, so the directories
    are globbed rather than listed and the highest version wins. Hardcoding a
    major is how this build quietly stops producing the SUPPORTED artifact the
    day the build machine upgrades: `build_installer` only warns, so the run
    still exits 0 with the installer missing.

    Inno Setup does not put itself on PATH, so the PATH probe is really an
    escape hatch for a build machine with a non-default install.
    """
    found = shutil.which("ISCC") or shutil.which("iscc")
    if found:
        return found
    candidates = [
        exe
        for root in (r"C:\Program Files", r"C:\Program Files (x86)")
        if Path(root).is_dir()
        for exe in Path(root).glob("Inno Setup */ISCC.exe")
        if exe.is_file()
    ]
    if not candidates:
        return None
    return str(max(candidates, key=_iscc_rank))


def build_installer(info: Dict[str, str]) -> Optional[Path]:
    iscc = find_iscc()
    if iscc is None:
        print(r"[WARN] Inno Setup (ISCC.exe) not found on PATH or under "
              r"'C:\Program Files[ (x86)]\Inno Setup <n>\' -- the onedir tree "
              "was produced but the installer was not. The installer is the "
              "SUPPORTED artifact, so a release build must have it. Install "
              "Inno Setup from https://jrsoftware.org/isdl.php.")
        return None
    print(f"[INFO] Inno Setup compiler: {iscc}")
    run([iscc, f"/DAppVersion={info['version']}", f"/DRepoRoot={REPO_ROOT}",
         str(INSTALLER_ISS)], cwd=BUILD_DIR)
    produced = DIST / f"{APP_NAME}-Setup-{info['version']}.exe"
    return produced if produced.is_file() else None


# ---------------------------------------------------------------------------
# Steps 6-7 — smoke and manifest
# ---------------------------------------------------------------------------

def locked_components() -> Dict[str, str]:
    """Parse `name==version` out of the lock, ignoring hashes and comments."""
    components: Dict[str, str] = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "--hash")):
            continue
        if "==" in line:
            name, _, rest = line.partition("==")
            components[name.strip().lower()] = rest.split()[0].strip(" \\")
    return components


def smoke(artifact: Path) -> str:
    """Run the smoke test with the **outer** interpreter, not the build venv.

    The build venv contains exactly what `requirements.lock` pins and nothing
    else — no pytest, and deliberately so: adding a test runner to it would
    put a package in the resolution set that has no business being in a
    shipped artifact. The smoke test is a harness for the repository, so it
    runs with the repository's interpreter. What it *inspects* is the frozen
    artifact, which is the part that has to be isolated.
    """
    smoke_script = BUILD_DIR / "smoke" / "run_smoke.py"
    proc = subprocess.run(
        [sys.executable, str(smoke_script), str(artifact)],
        cwd=str(REPO_ROOT), env=child_env(), text=True,
    )
    return "PASS" if proc.returncode == 0 else "FAIL"


def write_manifest(kind: str, support: str, artifact: Optional[Path],
                   info: Dict[str, str], verdict: str) -> Dict[str, object]:
    manifest = {
        "kind": kind,
        "support_status": support,
        "artifact": str(artifact) if artifact else None,
        "source_commit": info["commit"],
        "version": info["version"],
        "branch": info["branch"],
        "built_at": info["built_at"],
        "smoke_verdict": verdict,
        "components": locked_components(),
    }
    if artifact is not None:
        out = artifact.with_suffix(artifact.suffix + ".manifest.json")
    else:
        out = DIST / f"{kind}.manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[INFO] manifest -> {out}")
    return manifest


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--installer", action="store_true",
                       help="onedir + Inno Setup only")
    group.add_argument("--portable", action="store_true", help="onefile only")
    group.add_argument("--lock", action="store_true",
                       help="regenerate requirements.lock and exit")
    args = parser.parse_args(argv)

    if args.lock:
        return regenerate_lock()

    targets = []
    if args.installer:
        targets = ["onedir"]
    elif args.portable:
        targets = ["onefile"]
    else:
        targets = ["onedir", "onefile"]

    print(f"[INFO] building: {', '.join(targets)}")
    make_fresh_venv()                       # 1
    install_from_lock()                     # 2, 3
    info = describe_version()
    stamp_buildinfo(info)                   # 4
    freeze(targets)                         # 5

    manifests = []
    installer_failed = False
    portable_failed = False

    if "onedir" in targets:
        onedir = DIST / APP_NAME / f"{APP_NAME}.exe"
        if not onedir.is_file():
            raise SystemExit(f"[FAIL] onedir target missing: {onedir}")
        installer = build_installer(info)
        # The smoke test runs against the onedir executable whether or not
        # Inno Setup wrapped it: the installer is a container, and what has to
        # be verified is the program inside it.
        verdict = smoke(onedir)             # 6
        manifests.append(
            write_manifest("installer", "supported", installer or onedir, info, verdict)
        )
        installer_failed = verdict == "FAIL"

    if "onefile" in targets:
        onefile = DIST / f"{APP_NAME}-portable.exe"
        if not onefile.is_file():
            raise SystemExit(f"[FAIL] onefile target missing: {onefile}")
        verdict = smoke(onefile)
        manifests.append(
            write_manifest("portable", "best_effort", onefile, info, verdict)
        )
        portable_failed = verdict == "FAIL"

    # Step 7 -- the release rule (FR-047, SC-010).
    print()
    for m in manifests:
        print(f"[{m['smoke_verdict']}] {m['kind']:<10} ({m['support_status']}) "
              f"{m['artifact']}")

    if portable_failed and not installer_failed:
        # SC-010 stated as behaviour: the best-effort artifact failing must not
        # take the supported one down with it. It is simply not released.
        print("\n[WARN] the portable artifact failed its smoke test and will "
              "NOT be released. The installer is unaffected and is releasable.")
        return 0
    if installer_failed:
        print("\n[FAIL] the installer failed its smoke test. Nothing ships.")
        return 1
    print("\n[PASS] every produced artifact passed its smoke test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
