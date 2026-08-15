"""Read-only: does the Move's identity_remap map the msa_slot_bindings MSA guids
so the consumer _run_171_subpass could resolve target MSAs? Decides whether the
sub-pass is functional (remap has MSAs) or inert (copy path does the wiring).
"""
from __future__ import annotations
import os, sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT / "src", _ROOT / "tests" / "integration"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

SOURCE = os.environ.get("GT_SOURCE", "Ejagham Mini")
TARGET = os.environ.get("GT_TARGET", "Target")
TARGET_PATH = r"C:\ProgramData\SIL\FieldWorks\Projects\Target"


def main() -> int:
    from gramtrans.Lib import api, categories
    from harness import full_run

    source_handle = full_run._open_source_readonly(SOURCE)
    context = None
    try:
        stub = api.initialize_run(source_handle, source_project_name=SOURCE,
                                  source_project_path="")
        choice = api.TargetCandidate(project_name=TARGET, project_path=TARGET_PATH)
        context = api.bind_target(stub, choice)
        selection = full_run.build_full_selection(exclude=frozenset())
        src_vern = source_handle.GetDefaultVernacularWS()[0]
        tgt_vern = context.target_handle.GetDefaultVernacularWS()[0]
        from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
        wsm = WSMapping(entries=(WSMappingEntry(
            source_ws_id=src_vern, source_ws_kind=WSKind.VERNACULAR,
            target_ws_id=tgt_vern, create_in_target=False),))
        state, plan = api.compute_preview(context, selection, ws_mapping=wsm)
        bindings = dict(getattr(plan, "msa_slot_bindings", {}) or {})
        remap = dict(getattr(plan, "identity_remap", {}) or {})
        target = context.target_handle
        resolve = categories._resolve_target_by_guid
        cast = categories._cast_lcm

        n = len(bindings)
        in_remap = sum(1 for k in bindings if k in remap)
        resolves_via_remap = 0
        resolves_direct = 0
        for k in bindings:
            tg = remap.get(k, k)
            if cast(resolve(target, tg), "IMoInflAffMsa") is not None:
                resolves_via_remap += 1
            if cast(resolve(target, k), "IMoInflAffMsa") is not None:
                resolves_direct += 1
        print("== identity_remap vs msa_slot_bindings (live, in bound session) ==")
        print("  bound MSA guids                    : %d" % n)
        print("  present as KEYS in identity_remap   : %d" % in_remap)
        print("  resolve on target via remap.get()   : %d" % resolves_via_remap)
        print("  resolve on target by SOURCE guid    : %d" % resolves_direct)
        print("  identity_remap total entries        : %d" % len(remap))
        print("-" * 60)
        if resolves_via_remap == n and n > 0:
            print("  => consumer CAN resolve all target MSAs: sub-pass is FUNCTIONAL")
        elif resolves_via_remap == 0:
            print("  => consumer resolves NONE: _run_171_subpass is INERT on live;")
            print("     SlotsRC wiring (79/79 on target) comes from the owned-child")
            print("     copy path, NOT this producer/consumer machinery.")
        else:
            print("  => consumer resolves %d/%d: PARTIAL" % (resolves_via_remap, n))
        return 0
    finally:
        if context is not None:
            try:
                api._close_project_watchdog(
                    context.target_handle, api._SCHEMA_CLOSE_TIMEOUT_S, "target")
            except Exception:  # noqa: BLE001
                pass
        try:
            source_handle.CloseProject()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())
