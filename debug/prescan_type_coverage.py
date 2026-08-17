"""READ-ONLY object-type coverage prescan across every FLEx project on this machine.

Purpose (feature 035): decide the ORDER in which the fullsweep admits projects.
The user's rule is "maximize the number of object types hit in the first rounds",
and this measures that rather than guessing it from project names or sizes.
Name-based guessing has already failed twice in this project (`Sichuan Yi` and
`Mbugwe Lizzie HCPractice` are empty shells whose real counterparts are
`Yi Sichuan` and `Mbugwe LizzieHC practice`), and the first hand-built project
table already omitted a real project (`Spiti Sumi`, 9.39 MB) -- so enumeration
here is DERIVED AT RUNTIME, never read from a list.

WHAT IT DOES, per project: open read-only, walk
`ICmObjectRepository.AllInstances()`, count objects per LCM class name, close.
That yields a per-project type profile, and `--order` turns the profiles into a
greedy set-cover ordering: the project covering the most not-yet-covered types
first, then whichever adds the most new types, and so on.

SAFETY -- this script never writes to a FLEx project:
  * every open is `writeEnabled=False`;
  * any project whose name matches ^Target[0-9]*$ is REFUSED outright (those are
    the sweep's disposable write targets; nothing here should touch them);
  * no restore, no delete, no lock-file manipulation of any kind;
  * each project's data-file size+mtime is recorded before AND after its scan,
    and a change is reported as a loud finding rather than ignored.

NO SILENT OMISSION. Every project is either scanned, or recorded with an
explicit reason (no data file, refused by name, open failed, walk failed). A
project that errors keeps its traceback. The driver exits non-zero if any
project failed, so "it printed a lot of rows" can never be mistaken for success.

Isolation: by default each project is scanned in its own SUBPROCESS, so peak
memory is attributable per project and a crash or a hang in one project cannot
poison the rest. `--in-process` overrides that for debugging.

ASCII-only output (Windows-terminal safe).

USAGE
    python debug/prescan_type_coverage.py --list
    python debug/prescan_type_coverage.py                 # scan all (resumable)
    python debug/prescan_type_coverage.py --project "Sena 3"
    python debug/prescan_type_coverage.py --order
Env: GRAMTRANS_PROJECTS_ROOT overrides the projects root for ENUMERATION only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT / "src", _ROOT / "tests" / "integration"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Anchored, full-match only. A prefix/glob check here would sweep in the
# archived `Target.pre025bak` / `Target.pre029bak` evidence directories.
_TARGET_RE = re.compile(r"Target[0-9]*\Z")

_DEFAULT_ROOT = r"C:\ProgramData\SIL\FieldWorks\Projects"
_OUT_DIR = _ROOT / "scratchpad" / "prescan_results"

# The user's anchor projects: they know things about these that object counts
# do not show, so they lead the ordering and set-cover fills in around them.
# Names corrected against disk 2026-08-17 (two of the five as given were shells).
ANCHORS = [
    "Yi Sichuan",                # given as "Sichuan Yi" -- that is a shell
    "Sena 3",
    "Mbugwe LizzieHC practice",  # given as "Mbugwe HC practice"
    "Spiti Sumi",
    "French-FLExTrans-Demo2025",  # a FLExTrans representative
]


def _projects_root() -> str:
    return os.environ.get("GRAMTRANS_PROJECTS_ROOT", _DEFAULT_ROOT)


def _enumerate() -> list[dict]:
    """Every candidate directory under the projects root, with a disposition.

    Reuses the engine's own definition of "a project on disk" (a directory
    containing a same-named .fwdata) rather than re-inventing a glob.
    """
    root = _projects_root()
    rows: list[dict] = []
    try:
        from gramtrans.Lib import api
        walked = dict(api._walk_flex_projects(root))
    except Exception:  # noqa: BLE001 -- fall back, but say so
        walked = {}
        print("[WARN] engine enumeration unavailable; falling back to a "
              "directory scan with the same rule")
        for d in sorted(Path(root).iterdir()):
            if d.is_dir() and (d / (d.name + ".fwdata")).is_file():
                walked[d.name] = str(d)

    seen = set(walked)
    for name in sorted(walked):
        path = Path(walked[name])
        fw = path / (name + ".fwdata")
        lock = path / (name + ".fwdata.lock")
        row = {
            "project": name,
            "path": str(path),
            "fwdata_mb": round(fw.stat().st_size / (1024 * 1024), 2),
            "lock_present": lock.is_file(),
            "disposition": "scan",
            "reason": "",
        }
        if _TARGET_RE.fullmatch(name):
            row["disposition"] = "refused"
            row["reason"] = ("name matches the sweep's disposable write-target "
                             "pattern; never opened by this prescan")
        rows.append(row)

    # Record the directories we are NOT scanning, with the reason, so the
    # corpus count is auditable rather than merely asserted.
    try:
        for d in sorted(Path(root).iterdir()):
            if d.is_dir() and d.name not in seen:
                rows.append({
                    "project": d.name, "path": str(d), "fwdata_mb": 0.0,
                    "lock_present": False, "disposition": "skipped",
                    "reason": "no same-named .fwdata (empty shell directory)",
                })
    except Exception as exc:  # noqa: BLE001
        print("[WARN] could not enumerate shells: %s" % exc)
    return rows


def _fingerprint(path: Path, name: str) -> dict:
    fw = path / (name + ".fwdata")
    try:
        st = fw.stat()
        return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
    except Exception:  # noqa: BLE001
        return {"size": None, "mtime_ns": None}


def _peak_rss_mb() -> float | None:
    try:
        import ctypes
        from ctypes import wintypes

        class _PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        pmc = _PMC()
        pmc.cb = ctypes.sizeof(_PMC)
        # GetCurrentProcess returns (HANDLE)-1. With the default restype of
        # c_int that pseudo-handle is truncated on 64-bit and the subsequent
        # call fails, which is why an earlier version of this silently reported
        # 0.0 MB. Declare the types explicitly.
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.GetCurrentProcess.argtypes = []
        handle = k32.GetCurrentProcess()
        # psapi first, then the kernel32 re-export; both are BOOL-returning, so
        # check the result instead of trusting a zero-filled struct (an ignored
        # failure here reports 0.0 MB, which reads as a measurement rather than
        # as the absence of one).
        ok = 0
        for dll in ("psapi", "kernel32"):
            try:
                lib = getattr(ctypes.windll, dll)
                fn = getattr(lib, "GetProcessMemoryInfo", None) or \
                    getattr(lib, "K32GetProcessMemoryInfo", None)
                if fn is None:
                    continue
                fn.restype = wintypes.BOOL
                fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC),
                               wintypes.DWORD]
                ok = fn(handle, ctypes.byref(pmc), pmc.cb)
                if ok:
                    break
            except Exception:  # noqa: BLE001
                continue
        if not ok:
            return None
        return round(pmc.PeakWorkingSetSize / (1024 * 1024), 1)
    except Exception:  # noqa: BLE001
        return None


def _flex_init() -> None:
    import clr  # noqa: F401  -- pythonnet must load first
    from flexicon import FLExInitialize
    FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr
        if not Sldr.IsInitialized:
            Sldr.Initialize(True)
    except Exception:  # noqa: BLE001
        pass


def scan_one(name: str) -> dict:
    """Open `name` READ-ONLY, count objects per class, close. Never writes."""
    if _TARGET_RE.fullmatch(name):
        raise SystemExit("[REFUSED] %r matches the disposable write-target "
                         "pattern; this prescan never opens it." % name)

    path = Path(_projects_root()) / name
    result = {
        "project": name,
        "fwdata_mb": round((path / (name + ".fwdata")).stat().st_size
                           / (1024 * 1024), 2),
        "status": "error",
        "reason": "",
        "class_counts": {},
        "writing_systems": {},
        "nesting_depth": {},
        "n_classes": 0,
        "n_objects": 0,
        "open_seconds": None,
        "walk_seconds": None,
        "peak_rss_mb": None,
        "fingerprint_before": _fingerprint(path, name),
        "fingerprint_after": None,
        "source_touched": None,
        "traceback": "",
    }

    proj = None
    try:
        _flex_init()
        from flexicon import FLExProject
        from SIL.LCModel import ICmObjectRepository

        t0 = time.time()
        proj = FLExProject()
        proj.OpenProject(projectName=name, writeEnabled=False)
        result["open_seconds"] = round(time.time() - t0, 2)

        # Writing-system breadth. Class counts are blind to this, and the
        # sweep's WS-mapped fidelity requirement can only be exercised by a
        # project carrying several -- so it is captured explicitly.
        ws = {"total": None, "vernacular": None, "analysis": None,
              "tags": [], "error": ""}
        try:
            wso = proj.WritingSystems
            allws = list(wso.GetAll() or [])
            ws["total"] = len(allws)
            ws["vernacular"] = len(list(wso.GetVernacular() or []))
            ws["analysis"] = len(list(wso.GetAnalysis() or []))
            tags = []
            for w in allws:
                try:
                    tags.append(str(wso.GetLanguageTag(w)))
                except Exception:  # noqa: BLE001
                    tags.append("<unreadable>")
            ws["tags"] = sorted(tags)
        except Exception as exc:  # noqa: BLE001 -- recorded, never silent
            ws["error"] = "%s: %s" % (type(exc).__name__, exc)
        result["writing_systems"] = ws

        t1 = time.time()
        sl = proj.project.ServiceLocator
        repo = (sl.GetInstance[ICmObjectRepository]()
                if hasattr(sl, "GetInstance")
                else sl.GetService(ICmObjectRepository))
        counts: dict[str, int] = {}
        total = 0
        # Structural depth, via the owner chain only (ClassName + Owner are the
        # two members already proven reachable). Set-cover over class PRESENCE
        # cannot see nesting -- a project with reversals-inside-reversals and one
        # with a flat reversal list look identical to it, yet only the former
        # exercises both the top-level and sub-entry creation paths, which are
        # known to disagree about identity.
        depth = {"reversal_entry": 0, "sense": 0, "possibility": 0}

        def _owner_depth(o, stop_classes, cap=24):
            d = 0
            cur = o
            while d < cap:
                try:
                    cur = cur.Owner
                except Exception:  # noqa: BLE001
                    return d
                if cur is None:
                    return d
                try:
                    cn2 = cur.ClassName
                except Exception:  # noqa: BLE001
                    return d
                if cn2 in stop_classes:
                    return d
                d += 1
            return d

        for obj in repo.AllInstances():
            try:
                cn = obj.ClassName
            except Exception:  # noqa: BLE001
                cn = "<unreadable-class>"
            counts[cn] = counts.get(cn, 0) + 1
            total += 1
            if cn == "ReversalIndexEntry":
                depth["reversal_entry"] = max(
                    depth["reversal_entry"], _owner_depth(obj, {"ReversalIndex"}))
            elif cn == "LexSense":
                depth["sense"] = max(
                    depth["sense"], _owner_depth(obj, {"LexEntry"}))
            elif cn in ("CmPossibility", "CmSemanticDomain", "CmAnthroItem"):
                depth["possibility"] = max(
                    depth["possibility"], _owner_depth(obj, {"CmPossibilityList"}))
        result["nesting_depth"] = depth
        result["walk_seconds"] = round(time.time() - t1, 2)
        result["class_counts"] = dict(sorted(counts.items()))
        result["n_classes"] = len(counts)
        result["n_objects"] = total
        result["status"] = "ok"
    except Exception as exc:  # noqa: BLE001 -- recorded loudly, never swallowed
        result["reason"] = "%s: %s" % (type(exc).__name__, exc)
        result["traceback"] = traceback.format_exc()[-3000:]
    finally:
        if proj is not None:
            try:
                proj.CloseProject()
            except Exception as exc:  # noqa: BLE001
                result["reason"] = (result["reason"] + " | close: %s" % exc).strip(" |")
        result["peak_rss_mb"] = _peak_rss_mb()
        result["fingerprint_after"] = _fingerprint(path, name)
        result["source_touched"] = (
            result["fingerprint_before"] != result["fingerprint_after"])
    return result


def _result_path(name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    return _OUT_DIR / ("%s.json" % safe)


def drive(args) -> int:
    rows = _enumerate()
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    (_OUT_DIR / "_enumeration.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8")

    todo = [r for r in rows if r["disposition"] == "scan"]
    print("[INFO] projects root : %s" % _projects_root())
    print("[INFO] to scan       : %d" % len(todo))
    print("[INFO] refused       : %d"
          % len([r for r in rows if r["disposition"] == "refused"]))
    print("[INFO] shells skipped: %d"
          % len([r for r in rows if r["disposition"] == "skipped"]))

    failures, touched, scanned = [], [], 0
    for i, row in enumerate(todo, 1):
        name = row["project"]
        out = _result_path(name)
        if out.is_file() and not args.force:
            print("[SKIP] %3d/%d %-38s (already scanned)" % (i, len(todo), name))
            continue
        print("[SCAN] %3d/%d %-38s %8.2f MB" % (i, len(todo), name,
                                                row["fwdata_mb"]), flush=True)
        if args.in_process:
            res = scan_one(name)
        else:
            cp = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()),
                 "--project", name, "--json-only"],
                capture_output=True, text=True, timeout=args.timeout)
            try:
                res = json.loads(cp.stdout.strip().splitlines()[-1])
            except Exception:  # noqa: BLE001
                res = {"project": name, "status": "error",
                       "reason": "worker produced no parseable result "
                                 "(exit %s)" % cp.returncode,
                       "traceback": (cp.stderr or "")[-3000:],
                       "class_counts": {}, "n_classes": 0, "n_objects": 0}
        out.write_text(json.dumps(res, indent=2), encoding="utf-8")
        scanned += 1
        if res.get("status") != "ok":
            failures.append((name, res.get("reason", "")))
            print("       [FAIL] %s" % res.get("reason", ""))
        else:
            print("       %d classes / %d objects / open %ss walk %ss / peak %s MB"
                  % (res["n_classes"], res["n_objects"], res["open_seconds"],
                     res["walk_seconds"], res["peak_rss_mb"]))
        if res.get("source_touched"):
            touched.append(name)
            print("       [LOUD] SOURCE DATA FILE CHANGED during a read-only "
                  "scan -- investigate before sweeping")

    print("\n[SUMMARY] scanned=%d failed=%d source-touched=%d"
          % (scanned, len(failures), len(touched)))
    for n, why in failures:
        print("  [FAIL] %-38s %s" % (n, why))
    for n in touched:
        print("  [LOUD] %-38s data file changed" % n)
    if failures or touched:
        print("\nExiting non-zero: a prescan with failures or a touched source "
              "is not a usable coverage baseline.")
        return 1
    return 0


def order(args) -> int:
    """Greedy set-cover ordering over the collected profiles."""
    profiles = {}
    for f in sorted(_OUT_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if d.get("status") == "ok":
            profiles[d["project"]] = set(d.get("class_counts", {}))
    if not profiles:
        print("[ERROR] no successful profiles in %s -- run the scan first"
              % _OUT_DIR)
        return 2

    universe = set().union(*profiles.values())
    covered: set[str] = set()
    picked: list[tuple[str, int, int]] = []
    remaining = dict(profiles)

    for a in args.anchors:
        if a in remaining:
            new = remaining[a] - covered
            picked.append((a, len(new), len(covered | new)))
            covered |= remaining.pop(a)
        else:
            print("[WARN] anchor %r has no successful profile; skipped" % a)

    while remaining:
        best = max(remaining, key=lambda p: (len(remaining[p] - covered),
                                             len(remaining[p])))
        new = remaining[best] - covered
        picked.append((best, len(new), len(covered | new)))
        covered |= remaining.pop(best)

    lines = ["# Prescan type-coverage ordering", "",
             "%d projects profiled, %d distinct object classes across the corpus."
             % (len(profiles), len(universe)), "",
             "| # | project | new types | cumulative | % of corpus types |",
             "|---|---|---|---|---|"]
    for i, (p, new, cum) in enumerate(picked, 1):
        lines.append("| %d | %s | %d | %d | %.1f%% |"
                     % (i, p, new, cum, 100.0 * cum / len(universe)))
    hit90 = next((i for i, (_, _, c) in enumerate(picked, 1)
                  if c >= 0.9 * len(universe)), None)
    if hit90:
        lines += ["", "**%d projects reach 90%% of all object types.**" % hit90]
    out = _OUT_DIR / "ordering.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:16]))
    print("\n[INFO] full ordering written to %s" % out)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true",
                    help="enumerate projects and dispositions; open nothing")
    ap.add_argument("--project", help="scan exactly one project (worker mode)")
    ap.add_argument("--json-only", action="store_true",
                    help="worker mode: print only the result JSON")
    ap.add_argument("--order", action="store_true",
                    help="compute the greedy set-cover ordering")
    ap.add_argument("--anchors", nargs="*", default=ANCHORS,
                    help="projects to lead the ordering")
    ap.add_argument("--force", action="store_true",
                    help="re-scan projects that already have a result file")
    ap.add_argument("--in-process", action="store_true",
                    help="do not isolate each project in a subprocess")
    ap.add_argument("--timeout", type=int, default=1800,
                    help="per-project subprocess timeout in seconds")
    args = ap.parse_args()

    if args.list:
        for r in _enumerate():
            print("%-9s %-38s %8.2f MB %s%s"
                  % (r["disposition"], r["project"], r["fwdata_mb"],
                     "LOCK " if r["lock_present"] else "",
                     r["reason"]))
        return 0
    if args.project:
        res = scan_one(args.project)
        if args.json_only:
            print(json.dumps(res))
        else:
            print(json.dumps(res, indent=2))
        return 0 if res["status"] == "ok" else 1
    if args.order:
        return order(args)
    return drive(args)


if __name__ == "__main__":
    raise SystemExit(main())
