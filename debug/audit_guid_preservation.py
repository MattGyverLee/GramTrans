"""Project-wide GUID-preservation audit for a full transfer.

INVARIANT UNDER TEST (general, not MSA-specific): every object created in the
target by a transfer must carry its SOURCE GUID. A target object that already
holds a source GUID is the same object and must be linked/deduped, never
duplicated under a new identity.

Method -- empirical, class-by-class, no reliance on reading creation paths:

  1. restore TARGET clean, inventory EVERY object (class -> {guid})   [BEFORE]
  2. inventory SOURCE the same way
  3. full-selection Move SOURCE -> TARGET
  4. inventory TARGET again                                          [AFTER]
  5. new_objects = AFTER - BEFORE, bucketed by class. For each class:
       preserved = new GUIDs that ARE source GUIDs
       minted    = new GUIDs that are NOT source GUIDs   <-- the defect
     Any class with minted > 0 created objects under fresh identities.

`minted` is not automatically a bug: an object with no source counterpart
(a container the target genuinely lacked, a residue/tag artifact) legitimately
gets a new GUID. The report therefore pairs each class's minted count with the
number of SOURCE objects of that class that went MISSING from the target -- a
class showing `minted == missing` is the regeneration signature (n objects in,
n fresh identities out, n source identities unaccounted for).

Enumerates via ICmObjectRepository.AllInstances() so nothing is missed.
Read-only except for the Move itself; TARGET is restored clean first.

    python scratchpad/audit_guid_preservation.py
Env: GT_SOURCE (default "Ejagham Mini"), GT_TARGET (default "Target"),
     GT_BACKUP, GT_OUT.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT / "src", _ROOT / "tests" / "integration"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SOURCE = os.environ.get("GT_SOURCE", "Ejagham Mini")
TARGET = os.environ.get("GT_TARGET", "Target")
TARGET_PATH = os.environ.get(
    "GT_TARGET_PATH", r"C:\ProgramData\SIL\FieldWorks\Projects\Target")
BACKUP = Path(os.environ.get(
    "GT_BACKUP", str(_ROOT / "backups" / "Target 2026-07-06 0218.fwbackup")))
OUT_JSON = Path(os.environ.get(
    "GT_OUT", str(_ROOT / "scratchpad" / "guid_audit.json")))


def _banner(msg):
    print("\n" + "=" * 72)
    print("== " + msg)
    print("=" * 72)


def inventory_all(project_name, *, counters=None, oplog=None, scope=None):
    """{class_name: set(guid)} over EVERY object in the project (read-only).

    ``counters`` (feature 035 T045b / FR-103)
        An optional ``fullsweep.instrument.AccessorCounters``. Every per-object
        read failure below used to be swallowed by a bare
        ``except Exception: continue`` -- the object simply vanished from the
        inventory and the inventory reported a smaller, cleaner number with no
        trace that anything had been dropped. The swallow is KEPT (aborting a
        half-million-object enumeration over one unreadable object trades a
        partial measurement for none); what changes is that the drop is now
        COUNTED, at the exact point it happens, when a counter is supplied.

        ``None`` -- the default, and what every pre-existing caller passes --
        behaves byte-identically to before.

    ``oplog`` (FR-104 / FR-108)
        An optional ``fullsweep.instrument.OperationLog``. Records the open and
        the close with their outcomes and durations. The close below is inside
        a bare ``except`` for the same reason as always -- a failed close must
        not lose an inventory that succeeded -- but the failure is now on the
        record instead of being discarded with the exception.

    ``scope``
        The label counter increments are attributed to. Defaults to the project
        name; the sweep passes ``"<project>:<step>"`` because one run
        enumerates the target three times and the source once, and a counter
        that cannot say which of the four dropped objects cannot be acted on.
    """
    import flexicon

    where = scope or project_name
    if counters is not None:
        counters.open_scope(where)

    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr
        if not Sldr.IsInitialized:
            Sldr.Initialize(True)
    except Exception:  # noqa: BLE001
        pass
    from flexicon import FLExProject
    from SIL.LCModel import ICmObjectRepository

    proj = FLExProject()
    if oplog is not None:
        with oplog.watch("OpenProject(writeEnabled=False)", project_name,
                         kind="open"):
            proj.OpenProject(projectName=project_name, writeEnabled=False)
    else:
        proj.OpenProject(projectName=project_name, writeEnabled=False)
    out = defaultdict(set)
    try:
        try:
            repo = proj.project.ServiceLocator.GetInstance[ICmObjectRepository]() \
                if hasattr(proj.project.ServiceLocator, "GetInstance") \
                else proj.project.ServiceLocator.GetService(ICmObjectRepository)
            instances = repo.AllInstances()
        except Exception as exc:  # noqa: BLE001 -- counted, then re-raised
            # FR-103: a failure to ENUMERATE is categorically worse than a
            # failure to read one object -- it means the inventory is not
            # merely incomplete but unbounded-unknown. It is counted and then
            # raised, because continuing would report an empty project.
            if counters is not None:
                counters.record("enumeration_failures", scope=where,
                                accessor="ICmObjectRepository.AllInstances",
                                error=exc)
            raise
        for obj in instances:
            try:
                class_name = obj.ClassName
            except Exception as exc:  # noqa: BLE001
                # The object could not even say what it is. Counted against
                # `unreadable_names`, since ClassName is the name accessor.
                if counters is not None:
                    counters.record("unreadable_names", scope=where,
                                    accessor="ICmObject.ClassName", error=exc)
                    counters.record("skipped_source_objects", scope=where,
                                    accessor="ICmObject.ClassName", error=exc)
                continue
            try:
                out[class_name].add(str(obj.Guid).lower())
            except Exception as exc:  # noqa: BLE001
                if counters is not None:
                    counters.record("unreadable_identifiers", scope=where,
                                    accessor="ICmObject.Guid (%s)" % class_name,
                                    error=exc)
                    counters.record("skipped_source_objects", scope=where,
                                    accessor="ICmObject.Guid (%s)" % class_name,
                                    error=exc)
                continue
    finally:
        if oplog is not None:
            try:
                with oplog.watch("CloseProject", project_name, kind="close"):
                    proj.CloseProject()
            except Exception:  # noqa: BLE001 -- recorded by the watch above
                pass
        else:
            try:
                proj.CloseProject()
            except Exception:  # noqa: BLE001
                pass
    return {k: v for k, v in out.items()}


def run_full_move():
    from collections import Counter
    from gramtrans.Lib import api
    from gramtrans.Lib.debuglog import DEBUG_ENV
    from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
    from harness import full_run

    os.environ[DEBUG_ENV] = "0"
    source_handle = full_run._open_source_readonly(SOURCE)
    context = None
    try:
        stub = api.initialize_run(
            source_handle, source_project_name=SOURCE, source_project_path="")
        choice = api.TargetCandidate(project_name=TARGET, project_path=TARGET_PATH)
        context = api.bind_target(stub, choice)
        selection = full_run.build_full_selection()
        src_vern = source_handle.GetDefaultVernacularWS()[0]
        tgt_vern = context.target_handle.GetDefaultVernacularWS()[0]
        ws_mapping = WSMapping(entries=(WSMappingEntry(
            source_ws_id=src_vern, source_ws_kind=WSKind.VERNACULAR,
            target_ws_id=tgt_vern, create_in_target=False),))
        state, plan = api.compute_preview(context, selection, ws_mapping=ws_mapping)
        if state is not api.PreviewState.PREVIEW_READY:
            raise RuntimeError("compute_preview returned %r" % (state,))
        report = api.execute_move(context, plan)
        return {
            "actions": len(plan.actions),
            "added": sum(r.added for r in report.per_category.values()),
            "dropped_items": len(report.dropped_items),
        }
    finally:
        if context is not None:
            try:
                api._close_project_watchdog(
                    context.target_handle, api._SCHEMA_CLOSE_TIMEOUT_S, "target")
            except Exception as exc:  # noqa: BLE001
                print("[WARN] target close: %s" % exc)
        try:
            source_handle.CloseProject()
        except Exception:  # noqa: BLE001
            pass


def main():
    from harness import restore

    _banner("SOURCE inventory (all classes): %s" % SOURCE)
    src = inventory_all(SOURCE)
    src_all = set().union(*src.values()) if src else set()
    print("  %d classes, %d objects" % (len(src), len(src_all)))

    _banner("RESTORE %s" % TARGET)
    restore.restore_target(TARGET, backup_path=str(BACKUP))
    before = inventory_all(TARGET)
    before_all = set().union(*before.values()) if before else set()
    print("  baseline: %d classes, %d objects" % (len(before), len(before_all)))

    _banner("FULL MOVE %s -> %s" % (SOURCE, TARGET))
    move = run_full_move()
    print("[MOVE] %s" % json.dumps(move))

    _banner("TARGET inventory after Move")
    after = inventory_all(TARGET)
    after_all = set().union(*after.values()) if after else set()
    print("  after: %d classes, %d objects" % (len(after), len(after_all)))

    rows = []
    for cls in sorted(set(after) | set(src)):
        new_guids = after.get(cls, set()) - before.get(cls, set())
        src_guids = src.get(cls, set())
        preserved = new_guids & src_guids
        minted = new_guids - src_guids
        # source objects of this class that never reached the target at all
        missing = src_guids - after.get(cls, set())
        if not new_guids and not missing:
            continue
        rows.append({
            "class": cls,
            "source": len(src_guids),
            "new_in_target": len(new_guids),
            "preserved": len(preserved),
            "minted": len(minted),
            "source_missing": len(missing),
            "regeneration_signature": bool(minted) and len(minted) == len(missing),
            "sample_minted": sorted(minted)[:3],
        })

    offenders = [r for r in rows if r["minted"]]
    offenders.sort(key=lambda r: (-r["minted"], r["class"]))

    _banner("GUID PRESERVATION BY CLASS (classes with newly created objects)")
    print("  %-32s %7s %7s %9s %7s %8s  %s"
          % ("class", "source", "new", "preserved", "minted", "missing", "flag"))
    for r in sorted(rows, key=lambda r: (-r["minted"], -r["new_in_target"])):
        flag = ""
        if r["regeneration_signature"]:
            flag = "**REGENERATED**"
        elif r["minted"]:
            flag = "minted (check)"
        print("  %-32s %7d %7d %9d %7d %8d  %s"
              % (r["class"][:32], r["source"], r["new_in_target"],
                 r["preserved"], r["minted"], r["source_missing"], flag))

    _banner("SUMMARY")
    total_minted = sum(r["minted"] for r in rows)
    print("  classes creating objects : %d" % len([r for r in rows if r["new_in_target"]]))
    print("  classes minting new GUIDs: %d" % len(offenders))
    print("  total minted GUIDs       : %d" % total_minted)
    for r in offenders:
        print("    %-32s minted=%-5d missing=%-5d %s"
              % (r["class"][:32], r["minted"], r["source_missing"],
                 "REGENERATION" if r["regeneration_signature"] else ""))

    OUT_JSON.write_text(json.dumps(
        {"source": SOURCE, "target": TARGET, "move": move, "rows": rows},
        indent=2), encoding="utf-8")
    print("\n[RESULT_FILE] %s" % OUT_JSON)
    print("[%s] GUID preservation audit"
          % ("PASS" if not offenders else "FAIL"))
    return 0 if not offenders else 1


if __name__ == "__main__":
    raise SystemExit(main())
