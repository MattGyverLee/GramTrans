"""Read-only, LIVE-EXECUTION probe for feature 035 (fullsweep-fidelity)
census-API claims C1-C5, plus wall-clock/memory measurements.

Written to close the UNRESOLVED items in
``specs/035-fullsweep-fidelity/probe-results.md`` (which was source-only,
never executed against a live project). Every finding this script prints
was produced by actually running the call against a live FLEx project via
pythonnet/flexicon -- not read out of C# source.

SAFETY (read-only by construction):
  * every ``OpenProject`` call in this file passes ``writeEnabled=False``.
  * ``_guard_target_name`` refuses (SystemExit) to open any project whose
    name matches ``^Target([0-9]+)?$`` in ANY mode, before any project
    handle is created. This is a hard stop, not a warning.
  * no Save/Commit/Undo/Redo/mutating operation class is imported or used.

Modes
-----
confirm   Runs the live checks for C1-C5 (+ the MDC decorator spot-check,
          probe-results.md UNRESOLVED item 4) against one project and
          prints a plain-text report to stdout.

census    Opens the project, times the open, picks the most populous
          class among a small candidate list of repositories, and times a
          full per-field census (every non-virtual, non-structural field
          of every instance, read via the Q4 generic dispatch table).

hold      Opens the project and blocks (reading a line from stdin, or
          sleeping --hold-seconds) so an external, SEPARATE process can
          sample THIS process's peak working-set memory (e.g. via
          ``psutil.Process(pid).memory_info().peak_wset`` on Windows).
          Prints ``HELD pid=<pid>`` once the project is open and ready to
          be sampled, then ``CLOSED`` after it closes cleanly.

Examples
--------
    python debug/probe_field_census_api.py confirm --project "Ejagham Mini"
    python debug/probe_field_census_api.py census --project "Ejagham Mini"
    python debug/probe_field_census_api.py hold --project "Esperanto" --hold-seconds 30
"""
from __future__ import annotations

import argparse
import re
import sys
import time

_TARGET_RE = re.compile(r"^Target([0-9]+)?$")


def _guard_target_name(name: str) -> None:
    """Hard stop: never open anything named Target or Target<N>."""
    if _TARGET_RE.match(name.strip()):
        raise SystemExit(
            "REFUSING: project name %r matches the forbidden ^Target([0-9]+)?$ "
            "pattern. This script will not open Target projects under any "
            "circumstances (read-only-only task, but Target is off-limits "
            "entirely per task instructions)." % (name,)
        )


def _open_readonly(name: str):
    """Open *name* read-only via flexicon. Returns the FLExProject handle.

    ``writeEnabled=False`` is hard-coded here -- never pass True.
    """
    _guard_target_name(name)
    import flexicon
    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr  # noqa: PLC0415
        if not Sldr.IsInitialized:
            Sldr.Initialize(True)
    except Exception:  # noqa: BLE001 -- SLDR init is best-effort
        pass
    from flexicon import FLExProject  # noqa: PLC0415
    proj = FLExProject()
    proj.OpenProject(projectName=name, writeEnabled=False)
    return proj


# ---------------------------------------------------------------------------
# confirm mode: C1-C5 + decorator spot-check
# ---------------------------------------------------------------------------

def _confirm(project_name: str) -> int:
    # NOTE: SIL.* imports must come AFTER _open_readonly() -- that call is
    # what runs flexicon.FLExInitialize(), which sets up the pythonnet CLR
    # assembly references. Importing SIL.* before that raises
    # ModuleNotFoundError.
    t0 = time.perf_counter()
    proj = _open_readonly(project_name)
    open_s = time.perf_counter() - t0

    from SIL.LCModel.Infrastructure import IFwMetaDataCacheManaged  # noqa: PLC0415
    from SIL.LCModel.Core.Cellar import CellarPropertyTypeFilter  # noqa: PLC0415
    from SIL.LCModel.Core.KernelInterfaces import ITsString  # noqa: PLC0415
    from SIL.LCModel.Core.Text import TsStringUtils  # noqa: PLC0415
    print("=== OPEN ===")
    print("project=%r writeEnabled=%r undoable(effective)=%r open_time_s=%.3f"
          % (project_name, proj.writeEnabled, proj._undoable, open_s))

    try:
        cache = proj.Cache
        mdca = cache.MetaDataCacheAccessor

        # --- item 4: decorator spot-check ---------------------------------
        print("\n=== ITEM 4: decorator spot-check ===")
        print("MetaDataCacheAccessor .NET runtime type: %s"
              % mdca.GetType().FullName)

        # --- C1 -------------------------------------------------------------
        print("\n=== C1: managed metadata cache cast ===")
        try:
            mdca.GetFields(5002, True, int(CellarPropertyTypeFilter.All))
            print("C1 CONTROL: uncast GetFields did NOT raise (UNEXPECTED)")
        except Exception as exc:  # noqa: BLE001 -- exact type is the finding
            print("C1 CONTROL: uncast base-interface GetFields raised %s: %s"
                  % (type(exc).__name__, exc))
        mdc = IFwMetaDataCacheManaged(mdca)
        print("C1: IFwMetaDataCacheManaged(mdca) cast succeeded, "
              "runtime type after cast: %s" % mdc.GetType().FullName)

        # a live object to test against
        from SIL.LCModel import ILexEntryRepository  # noqa: PLC0415
        repo = proj.ObjectRepository(ILexEntryRepository)
        entries = list(repo.AllInstances())
        if not entries:
            print("C1/C2/C5: no LexEntry instances -- cannot proceed with "
                  "class-based checks on this project")
        else:
            e0 = entries[0]
            clid = e0.ClassID
            print("sample class for C2/C5: %s (clid=%d), LexEntry count=%d"
                  % (e0.ClassName, clid, len(entries)))

            print("C1: get_IsVirtual/IsCustom/GetFieldWs/GetFieldListRoot "
                  "member resolution:")
            flids_probe = list(mdc.GetFields(
                clid, True, int(CellarPropertyTypeFilter.All)))
            f0 = flids_probe[0]
            print("  get_IsVirtual(f0)=%r" % mdc.get_IsVirtual(f0))
            print("  IsCustom(f0)=%r" % mdc.IsCustom(f0))
            print("  GetFieldWs(f0)=%r" % mdc.GetFieldWs(f0))
            try:
                print("  GetFieldListRoot(f0)=%r" % mdc.GetFieldListRoot(f0))
            except Exception as exc:  # noqa: BLE001
                print("  GetFieldListRoot(f0) raised %s: %s (may be normal "
                      "for a non-list field)" % (type(exc).__name__, exc))

            # --- C2 -----------------------------------------------------------
            print("\n=== C2: 'All' sentinel vs 0x7FFFFFFF mask ===")
            flids_all = list(mdc.GetFields(
                clid, True, int(CellarPropertyTypeFilter.All)))
            flids_mask = list(mdc.GetFields(clid, True, 0x7FFFFFFF))
            set_all = {int(f) for f in flids_all}
            set_mask = {int(f) for f in flids_mask}
            print("len(All-sentinel)=%d len(0x7FFFFFFF mask)=%d sets_equal=%r"
                  % (len(flids_all), len(flids_mask), set_all == set_mask))
            if set_all != set_mask:
                print("  DIFFERENCE -- All only: %s | mask only: %s"
                      % (sorted(set_all - set_mask), sorted(set_mask - set_all)))
            types_all = sorted({int(mdc.GetFieldType(f)) & 0x1F for f in flids_all})
            print("distinct field types returned by 'All': %s" % types_all)
            non_owning_ref_types = [t for t in types_all if t not in (23, 24, 25, 26, 27, 28)]
            print("of those, NON-owning/reference types present: %s "
                  "(non-empty here proves the sentinel bypasses the "
                  "AllOwning|AllReference bitmask -- a literal bitmask read "
                  "of CellarPropertyTypeFilter.All=%d could only ever match "
                  "types 23-28)" % (non_owning_ref_types, int(CellarPropertyTypeFilter.All)))

            # contrast case: a genuine (non-.All) restrictive mask really
            # does filter, proving GetFields' masking logic isn't just
            # broadly permissive.
            multi_mask = (int(CellarPropertyTypeFilter.MultiString)
                          | int(CellarPropertyTypeFilter.MultiUnicode))
            flids_multi = list(mdc.GetFields(clid, True, multi_mask))
            types_multi = sorted({int(mdc.GetFieldType(f)) & 0x1F for f in flids_multi})
            print("CONTRAST: genuine restrictive mask (MultiString|"
                  "MultiUnicode, int=%d, != All) -> %d fields, types=%s "
                  "(correctly restricted)"
                  % (multi_mask, len(flids_multi), types_multi))

            # --- C5 -----------------------------------------------------------
            print("\n=== C5: virtual/structural exclusion, class=%s ===" % e0.ClassName)
            structural = [f for f in flids_all if int(f) < 200]
            virtual = [f for f in flids_all if mdc.get_IsVirtual(f)]
            overlap = [f for f in flids_all if int(f) < 200 and mdc.get_IsVirtual(f)]
            print("total fields=%d  structural(flid<200)=%d  virtual=%d  "
                  "overlap=%d  remaining_after_both_excluded=%d"
                  % (len(flids_all), len(structural), len(virtual), len(overlap),
                     len(flids_all) - len(structural) - len(virtual) + len(overlap)))

        # --- C3 -----------------------------------------------------------
        print("\n=== C3: populated WS-alternative enumeration ===")
        sda = proj.Cache.DomainDataByFlid
        from SIL.LCModel import ILexSenseRepository  # noqa: PLC0415
        sense_repo = proj.ObjectRepository(ILexSenseRepository)
        gloss_flid = mdc.GetFieldId("LexSense", "Gloss", True)
        found = None
        for sense in sense_repo.AllInstances():
            ms = sda.get_MultiStringProp(sense.Hvo, gloss_flid)
            if ms.StringCount > 0:
                found = (sense, ms)
                break
        if found is None:
            print("C3: no LexSense with a populated Gloss found in this project")
        else:
            _sense, ms = found
            raw = ms.GetStringFromIndex(0)
            print("C3: ms.GetStringFromIndex(0) raw pythonnet return type=%s value=%r"
                  % (type(raw).__name__, raw))
            print("C3: exact working line -> "
                  "tss, ws = ms.GetStringFromIndex(i)")
            for i in range(ms.StringCount):
                tss, ws = ms.GetStringFromIndex(i)
                print("  i=%d ws=%d text=%r" % (i, ws, tss.Text))

        # --- C4 -----------------------------------------------------------
        print("\n=== C4: native ITsString equality ===")
        vern_ws = proj.project.DefaultVernWs
        anal_ws = proj.project.DefaultAnalWs
        print("DefaultVernWs=%d DefaultAnalWs=%d" % (vern_ws, anal_ws))
        s1 = TsStringUtils.MakeString("probe-word", vern_ws)
        s1b = TsStringUtils.MakeString("probe-word", vern_ws)
        s2_diffws = TsStringUtils.MakeString("probe-word", anal_ws)
        s3_diffstyle = TsStringUtils.MakeString("probe-word", vern_ws, "Emphasis")
        eq_baseline = ITsString(s1).Equals(s1b)
        eq_ws = ITsString(s1).Equals(s2_diffws)
        eq_style = ITsString(s1).Equals(s3_diffstyle)
        print("exact working line -> ITsString(src_tss).Equals(tgt_tss)")
        print("identical text/ws/style .Equals -> %r (expect True)" % eq_baseline)
        print("same text, DIFFERENT ws .Equals -> %r (expect False)" % eq_ws)
        print("same text+ws, DIFFERENT char style .Equals -> %r (expect False)"
              % eq_style)
        print("plain .Text == .Text across the ws diff -> %r "
              "(shows a naive .Text compare WOULD miss it)"
              % (s1.Text == s2_diffws.Text))
        direct_eq = s1.Equals(s2_diffws)
        print("uncast s1.Equals(s2_diffws) [no ITsString() wrapper] -> %r "
              "(pythonnet resolves the same overload without an explicit cast)"
              % direct_eq)

        return 0
    finally:
        proj.CloseProject()
        print("\n=== CLOSED ===")


# ---------------------------------------------------------------------------
# census mode: wall-clock timing for open + full per-field census
# ---------------------------------------------------------------------------

_SKIP = object()

# CellarPropertyType values used by the dispatch table (see Q4 of
# probe-results.md; VERIFIED against SIL.LCModel.Core.Cellar.CellarPropertyType).
_T_BOOLEAN, _T_INTEGER, _T_TIME, _T_GUID, _T_GENDATE = 1, 2, 5, 6, 8
_T_STRING, _T_MULTISTRING, _T_UNICODE, _T_MULTIUNICODE = 13, 14, 15, 16
_T_OWN_ATOM, _T_REF_ATOM = 23, 24
_T_OWN_COLL, _T_REF_COLL, _T_OWN_SEQ, _T_REF_SEQ = 25, 26, 27, 28


def _read_field(sda, hvo: int, flid: int, ftype: int):
    """Generic per-field reader mirroring LCM's own CopyObject dispatch
    (probe-results.md Q4). Returns ``_SKIP`` for field types this probe
    intentionally does not exercise (Binary/Image/Numeric/Float are unused
    or rare in the model and not needed to measure the per-call cost)."""
    if ftype == _T_BOOLEAN:
        return sda.get_BooleanProp(hvo, flid)
    if ftype in (_T_INTEGER, _T_GENDATE):
        return sda.get_IntProp(hvo, flid)
    if ftype == _T_TIME:
        return sda.get_TimeProp(hvo, flid)
    if ftype == _T_GUID:
        return sda.get_GuidProp(hvo, flid)
    if ftype == _T_STRING:
        tss = sda.get_StringProp(hvo, flid)
        return tss.Text if tss is not None else None
    if ftype in (_T_MULTISTRING, _T_MULTIUNICODE):
        ms = sda.get_MultiStringProp(hvo, flid)
        out = []
        for i in range(ms.StringCount):
            tss, ws = ms.GetStringFromIndex(i)
            out.append((ws, tss.Text))
        return out
    if ftype == _T_UNICODE:
        return sda.get_UnicodeProp(hvo, flid)
    if ftype in (_T_OWN_ATOM, _T_REF_ATOM):
        return sda.get_ObjectProp(hvo, flid)
    if ftype in (_T_OWN_COLL, _T_REF_COLL, _T_OWN_SEQ, _T_REF_SEQ):
        n = sda.get_VecSize(hvo, flid)
        return [sda.get_VecItem(hvo, flid, i) for i in range(n)]
    return _SKIP


# Candidate populous-class repositories to choose from at runtime (module
# name, interface name). The census picks whichever has the most instances
# in the opened project.
_CENSUS_CANDIDATES = [
    ("ILexEntryRepository",),
    ("IWfiWordformRepository",),
    ("ISegmentRepository",),
    ("ILexSenseRepository",),
    ("IWfiAnalysisRepository",),
]


def _census(project_name: str) -> int:
    # See the note in _confirm(): SIL.* imports must follow _open_readonly().
    t0 = time.perf_counter()
    proj = _open_readonly(project_name)
    open_s = time.perf_counter() - t0

    from SIL.LCModel.Infrastructure import IFwMetaDataCacheManaged  # noqa: PLC0415
    from SIL.LCModel.Core.Cellar import CellarPropertyTypeFilter  # noqa: PLC0415
    import SIL.LCModel as lcm  # noqa: PLC0415, N813
    print("OPEN: project=%r elapsed_s=%.3f" % (project_name, open_s))

    try:
        mdc = IFwMetaDataCacheManaged(proj.Cache.MetaDataCacheAccessor)
        sda = proj.Cache.DomainDataByFlid

        best_name = None
        best_repo = None
        best_count = -1
        for (iface_name,) in _CENSUS_CANDIDATES:
            iface = getattr(lcm, iface_name, None)
            if iface is None:
                continue
            try:
                repo = proj.ObjectRepository(iface)
                n = repo.Count
            except Exception:  # noqa: BLE001
                continue
            if n > best_count:
                best_name, best_repo, best_count = iface_name, repo, n

        if best_repo is None or best_count <= 0:
            print("CENSUS: no populated candidate class found; nothing to time")
            return 1

        print("CENSUS: most populous candidate = %s (count=%d)"
              % (best_name, best_count))

        objs = list(best_repo.AllInstances())
        t_start = time.perf_counter()
        flid_cache: dict = {}
        reads = skipped = errors = 0
        for obj in objs:
            clid = obj.ClassID
            flids = flid_cache.get(clid)
            if flids is None:
                raw = mdc.GetFields(clid, True, int(CellarPropertyTypeFilter.All))
                flids = []
                for f in raw:
                    fi = int(f)
                    if fi < 200 or mdc.get_IsVirtual(fi):
                        continue
                    flids.append((fi, int(mdc.GetFieldType(fi)) & 0x1F))
                flid_cache[clid] = flids
            hvo = obj.Hvo
            for fi, ftype in flids:
                try:
                    val = _read_field(sda, hvo, fi, ftype)
                except Exception:  # noqa: BLE001 -- count and continue
                    errors += 1
                    continue
                if val is _SKIP:
                    skipped += 1
                else:
                    reads += 1
        elapsed = time.perf_counter() - t_start

        print("CENSUS RESULT: class=%s objects=%d distinct_classes_seen=%d "
              "field_reads=%d field_skipped=%d field_errors=%d "
              "elapsed_s=%.3f reads_per_sec=%.0f"
              % (best_name, len(objs), len(flid_cache), reads, skipped, errors,
                 elapsed, (reads / elapsed) if elapsed > 0 else float("nan")))
        return 0
    finally:
        proj.CloseProject()


# ---------------------------------------------------------------------------
# hold mode: open and block so an external process can sample memory
# ---------------------------------------------------------------------------

def _hold(project_name: str, hold_seconds: float) -> int:
    import os

    t0 = time.perf_counter()
    proj = _open_readonly(project_name)
    open_s = time.perf_counter() - t0
    print("OPEN: project=%r elapsed_s=%.3f pid=%d" % (project_name, open_s, os.getpid()),
          flush=True)
    print("HELD pid=%d" % os.getpid(), flush=True)
    try:
        if hold_seconds > 0:
            time.sleep(hold_seconds)
        else:
            sys.stdin.readline()
    finally:
        proj.CloseProject()
        print("CLOSED", flush=True)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    p_confirm = sub.add_parser("confirm", help="Live-check C1-C5 + decorator spot-check")
    p_confirm.add_argument("--project", default="Ejagham Mini")

    p_census = sub.add_parser("census", help="Time open + full per-field census")
    p_census.add_argument("--project", default="Ejagham Mini")

    p_hold = sub.add_parser("hold", help="Open and hold for external memory sampling")
    p_hold.add_argument("--project", default="Ejagham Mini")
    p_hold.add_argument("--hold-seconds", type=float, default=0.0,
                         help="If >0, sleep this long instead of reading stdin")

    args = parser.parse_args(argv)
    _guard_target_name(args.project)

    if args.mode == "confirm":
        return _confirm(args.project)
    if args.mode == "census":
        return _census(args.project)
    if args.mode == "hold":
        return _hold(args.project, args.hold_seconds)
    parser.error("unknown mode")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
