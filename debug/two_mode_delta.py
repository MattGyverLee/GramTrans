"""T024c/T024e -- LIVE two-mode full-copy delta driver (standalone CLI).

    restore blank -> inventory -> MOVE -> inventory,  once per mode.

Modes
-----
forceall  Selection with every GrammarCategory True and EVERY pick-set empty.
          `collapse_phonology` records leaf_item_picks only when a category is
          TRIMMED, so empty pick-sets mean transfer-all: the preselection
          heuristics (orphan NCs, AS-NEEDED slot/template/POS closure) are
          bypassed. This is the "force all" mode.

filtered  What the GUI produces: build the phonology inventory, keep the rows
          whose `preselected` flag is True, fold through `collapse_phonology`.
          Orphan natural classes and unreached deps stay UNCHECKED.

Delta, per LCM class, by GUID set (never by count -- counts cannot tell a
reused starter object from a created one):

    missing   = source - after            did not arrive
    arrived   = source & after            arrived, identity preserved
    invented  = after - before - source   created with a NEW guid
    survivor  = before & after            starter objects still standing

WRITE SAFETY: the destination name is checked against an explicit anchored
allowlist before the restore AND again before the write-enabled open, and the
destination may never equal the source. Only the destination is ever opened
write-enabled; the source is opened read-only.

ASCII-only output (Windows terminal safe).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from pathlib import Path

_UNSAFE_NAME_CHARS = set('/\\:*?"<>|')


def _bootstrap(repo: Path) -> None:
    # Mirror debug/run_fullcopy_sweep.py: debug/ and tests/integration/ go on
    # sys.path directly -- neither `tests` nor `tests.integration` is a package.
    for p in (repo / "src", repo, repo / "debug", repo / "tests" / "integration"):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


class WriteSafetyError(RuntimeError):
    pass


def assert_destination_safe(name, *, source_name, allowlist) -> None:
    """Deny-by-default, anchored FULL-match only. Mirrors 035 FR-011/FR-012."""
    if not allowlist:
        raise WriteSafetyError("[FR-011] empty allowlist -- refusing any destination")
    if not name or name.strip() != name or (set(name) & _UNSAFE_NAME_CHARS):
        raise WriteSafetyError("[FR-012] unsafe destination name %r" % (name,))
    if name == source_name:
        raise WriteSafetyError(
            "[FR-016] destination %r equals its source -- refusing" % (name,))
    for pattern in allowlist:
        if re.fullmatch(pattern, name):
            return
    raise WriteSafetyError(
        "[FR-011] destination %r matches no allowlist entry %r"
        % (name, list(allowlist)))


# ---------------------------------------------------------------------------

def inventory(project_name: str) -> dict:
    import audit_guid_preservation as guid_audit
    return {k: set(v) for k, v in guid_audit.inventory_all(project_name).items()}


def build_selection(mode, source_handle, target_handle):
    """-> Selection for `mode`, or (Selection, unchecked_map) for filtered."""
    from dataclasses import replace as dc_replace

    from harness.full_run import build_full_selection

    # Force-all: every category, every pick-set empty => transfer-all.
    sel = build_full_selection(exclude=frozenset())
    if mode == "forceall":
        return sel

    # Filtered: fold the inventory's PRESELECTED rows through collapse_phonology.
    from gramtrans.Lib import selection as selmod
    inv = selmod.build_phonology_inventory(source_handle, target_handle)
    checked = {
        g.category: {r.guid for r in g.rows if getattr(r, "preselected", True)}
        for g in inv.groups
    }
    frag = selmod.collapse_phonology(inv, checked)
    cats = dict(sel.categories)
    cats.update(frag["categories"])
    unchecked = {
        str(g.category): sorted(
            {r.guid for r in g.rows if not getattr(r, "preselected", True)})
        for g in inv.groups
        if any(not getattr(r, "preselected", True) for r in g.rows)
    }
    new_sel = dc_replace(sel, categories=cats,
                         leaf_item_picks=dict(frag["leaf_item_picks"]))
    return new_sel, unchecked


def transfer(source_name, target_name, target_path, mode):
    """Open source RO, bind target, preview, move.

    -> (report, unchecked_map, plan). The PLAN is returned as well because
    `match_basis` is a property of the planned action (T024h reads it to tell
    "the natural-key path found nothing" from "the natural-key path never
    ran"); the report carries only the substitution TALLY.
    """
    from gramtrans.Lib import api
    from gramtrans.Lib.debuglog import DEBUG_ENV
    from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
    from harness.full_run import _open_source_readonly

    os.environ.setdefault(DEBUG_ENV, "1")
    context = None
    unchecked = {}
    src = _open_source_readonly(source_name)
    try:
        stub = api.initialize_run(src, source_project_name=source_name,
                                  source_project_path="")
        context = api.bind_target(
            stub, api.TargetCandidate(project_name=target_name,
                                      project_path=target_path))
        built = build_selection(mode, src, context.target_handle)
        if isinstance(built, tuple):
            sel, unchecked = built
        else:
            sel = built

        src_vern = src.GetDefaultVernacularWS()[0]
        tgt_vern = context.target_handle.GetDefaultVernacularWS()[0]
        if os.environ.get("GT_WS_FULL") == "1":
            # FULL mapping: every source WS gets an entry. A tag the target
            # already has maps to itself; a tag it lacks is created there.
            # WS HANDLES ARE PER-PROJECT AND NOT PORTABLE (measured: 999000002
            # is `en` in Ngoreme FLEx and `ngq` in Ngoreme Target), so an
            # unmapped alternative carries a handle the target's
            # WritingSystemManager cannot resolve.
            tgt_ids = {w.Id for w in context.target_handle.WritingSystems.GetAll()}
            entries = []
            for w in src.WritingSystems.GetAll():
                wid = w.Id
                kind = (WSKind.VERNACULAR if wid == src_vern else WSKind.ANALYSIS)
                entries.append(WSMappingEntry(
                    source_ws_id=wid, source_ws_kind=kind,
                    target_ws_id=wid,
                    create_in_target=(wid not in tgt_ids)))
            ws_mapping = WSMapping(entries=tuple(entries))
            print("[INFO] FULL ws mapping: %s"
                  % ([(e.source_ws_id, e.target_ws_id, e.create_in_target)
                      for e in entries],))
        else:
            ws_mapping = WSMapping(entries=(WSMappingEntry(
                source_ws_id=src_vern, source_ws_kind=WSKind.VERNACULAR,
                target_ws_id=tgt_vern, create_in_target=False),))

        state, plan = api.compute_preview(context, sel, ws_mapping=ws_mapping)
        if state is not api.PreviewState.PREVIEW_READY:
            raise RuntimeError("compute_preview -> %r (not PREVIEW_READY)" % (state,))
        report = api.execute_move(context, plan)
        return report, unchecked, plan
    finally:
        if context is not None:
            try:
                api._close_project_watchdog(context.target_handle,
                                            api._SCHEMA_CLOSE_TIMEOUT_S,
                                            "two-mode target handle")
            except Exception as exc:  # noqa: BLE001
                # CloseProject() is the ONLY disk-write on this path, so a
                # raise here means NOTHING PERSISTED. Record it, never bury it.
                globals()["_LAST_PERSIST_ERROR"] = "%s: %s" % (type(exc).__name__, exc)
                print("[ERROR] PERSIST FAILED (CloseProject raised) -- "
                      "nothing was written: %s" % (exc,))
        try:
            src.CloseProject()
        except Exception:  # noqa: BLE001
            pass


def breakdown(report, plan) -> dict:
    """T024h -- turn the two bare tallies into attributable breakdowns.

    `dropped_items: 10,749` and `identity_substituted: 0` are both single
    integers in the run summary, and neither can be read as expected or
    unexpected without knowing what it is made of. Three questions, three
    breakdowns:

    (a) WHAT is being dropped -- by (owner_kind, reason), the two fields
        `DroppedItemRecord` carries for exactly this purpose. A large number
        against a 205,979-object source may be entirely ordinary (one record
        per out-of-scope reference) or may be a defect; the pair tells them
        apart, and the count alone cannot.
    (b) WHETHER the natural-key match path engaged AT ALL -- read off the
        PLAN's `match_basis`, not off the report. `identity_substituted`
        counts SUBSTITUTIONS; `MatchBasis.IDENTITY` vs `NATURAL_KEY` vs `NONE`
        says which arm each planned action took. Zero substitutions beside
        zero `NATURAL_KEY` bases means the path never ran (FR-006 unreachable
        on this pair); zero substitutions beside non-zero `NATURAL_KEY` would
        mean it ran and found nothing to substitute. Opposite conclusions.
    (c) WHICH leaf failed -- 037's `LeafExecutionFailure` records, so the
        filtered-mode `leaf_failed: 1` that force-all did not report is
        attributable instead of merely counted.
    """
    from collections import Counter

    out = {}

    dropped = list(getattr(report, "dropped_items", ()) or ())
    pairs = Counter((getattr(r, "owner_kind", "?"), getattr(r, "reason", "?"))
                    for r in dropped)
    out["dropped_total"] = len(dropped)
    out["dropped_by_owner_kind"] = dict(
        Counter(getattr(r, "owner_kind", "?") for r in dropped).most_common())
    out["dropped_by_reason"] = dict(
        Counter(getattr(r, "reason", "?") for r in dropped).most_common())
    out["dropped_by_owner_kind_and_reason"] = [
        {"owner_kind": k, "reason": rsn, "count": n}
        for (k, rsn), n in pairs.most_common()
    ]
    out["dropped_by_field"] = dict(
        Counter(getattr(r, "field_name", "?") for r in dropped).most_common(40))
    out["dropped_examples"] = [
        {"owner_kind": r.owner_kind, "owner_label": r.owner_label,
         "field_name": r.field_name, "item_name": r.item_name,
         "item_guid": r.item_guid, "reason": r.reason}
        for r in dropped[:20]
    ]

    bases = Counter()
    by_class = Counter()
    for action in list(getattr(plan, "actions", ()) or ()):
        mb = getattr(action, "match_basis", None)
        name = getattr(getattr(mb, "basis", None), "name", None)
        if name is None:
            name = "<no match_basis>"
        bases[name] += 1
        if name == "NATURAL_KEY":
            by_class[getattr(mb, "object_class", "?")] += 1
    out["plan_match_basis"] = dict(bases.most_common())
    out["plan_natural_key_by_class"] = dict(by_class.most_common())
    out["report_identity_substituted"] = getattr(
        report, "identity_substituted", None)
    out["report_matched_by_class"] = dict(
        getattr(report, "matched_by_class", {}) or {})
    out["report_matches_unattributed"] = {
        str(k): v for k, v in
        (getattr(report, "matches_unattributed", {}) or {}).items()}

    out["leaf_failures"] = [
        {f: str(getattr(lf, f, None))
         for f in ("category", "source_guid", "exception_type", "message")}
        for lf in (getattr(report, "leaf_execution_failures", ()) or ())
    ]
    return out


def delta(source_inv, before, after) -> dict:
    out = {}
    for cls in sorted(set(source_inv) | set(before) | set(after)):
        s = source_inv.get(cls, set())
        b = before.get(cls, set())
        a = after.get(cls, set())
        if not (s or b or a):
            continue
        row = {
            "source": len(s), "before": len(b), "after": len(a),
            "missing": len(s - a),
            "arrived": len(s & a),
            "invented": len(a - b - s),
            "survivor": len(b & a),
        }
        row["missing_guids"] = sorted(s - a)[:2000]
        out[cls] = row
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--destination", required=True)
    ap.add_argument("--backup", required=True, type=Path)
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--allowlist", nargs="+", required=True)
    ap.add_argument("--modes", nargs="+", default=["forceall", "filtered"])
    ap.add_argument("--projects-root",
                    default=r"C:\ProgramData\SIL\FieldWorks\Projects")
    args = ap.parse_args()

    _bootstrap(args.repo)
    from harness.restore import restore_target

    assert_destination_safe(args.destination, source_name=args.source,
                            allowlist=args.allowlist)
    tgt_path = str(Path(args.projects_root) / args.destination)

    print("[INFO] source      : %s" % args.source)
    print("[INFO] destination : %s  (allowlisted)" % args.destination)
    print("[INFO] backup      : %s" % args.backup)

    print("[INFO] inventorying SOURCE (read-only) ...")
    source_inv = inventory(args.source)
    print("[INFO]   source classes=%d objects=%d"
          % (len(source_inv), sum(len(v) for v in source_inv.values())))

    results = {
        "source": args.source, "destination": args.destination,
        "backup": str(args.backup),
        "source_totals": {"classes": len(source_inv),
                          "objects": sum(len(v) for v in source_inv.values())},
        "modes": {},
    }

    for mode in args.modes:
        print("")
        print("=" * 68)
        print("[INFO] MODE: %s" % mode)
        print("=" * 68)
        assert_destination_safe(args.destination, source_name=args.source,
                                allowlist=args.allowlist)
        print("[INFO] restoring %s from backup ..." % args.destination)
        restore_target(args.destination, backup_path=args.backup,
                       projects_root=args.projects_root)
        before = inventory(args.destination)
        print("[INFO]   before: classes=%d objects=%d"
              % (len(before), sum(len(v) for v in before.values())))

        entry = {"before_objects": sum(len(v) for v in before.values())}
        try:
            report, unchecked, plan = transfer(args.source, args.destination,
                                               tgt_path, mode)
            entry["unchecked_preselection"] = {k: len(v)
                                               for k, v in unchecked.items()}
            entry["unchecked_guids"] = unchecked
            # NOTE: identity_substituted / leaf_failed are @property (models.py
            # :2758) -- read them, never call them.
            rep = {"dropped_items": len(getattr(report, "dropped_items", ()) or ()),
                   "skips": len(getattr(report, "skips", ()) or ())}
            for name in ("identity_substituted", "total_added", "total_skipped",
                         "leaf_failed", "enriched", "not_reproducible"):
                try:
                    v = getattr(report, name, None)
                except Exception as exc:  # noqa: BLE001
                    v = "<%s: %s>" % (type(exc).__name__, exc)
                if v is not None and not callable(v):
                    rep[name] = v
            per_cat = getattr(report, "per_category", {}) or {}
            rep["per_category"] = {
                str(k): {f: getattr(v, f, None)
                         for f in ("added", "skipped", "enriched",
                                   "identity_substitution", "not_reproducible")}
                for k, v in per_cat.items()
            }
            entry["report"] = rep
            # T024h: the two bare tallies, broken down so they can be read.
            entry["breakdown"] = breakdown(report, plan)
            entry["persist_error"] = globals().pop("_LAST_PERSIST_ERROR", None)
        except Exception as exc:  # noqa: BLE001
            entry["error"] = "%s: %s" % (type(exc).__name__, exc)
            entry["traceback"] = traceback.format_exc()
            print("[ERROR] transfer failed: %s" % exc)
            traceback.print_exc()
            results["modes"][mode] = entry
            continue

        after = inventory(args.destination)
        print("[INFO]   after : classes=%d objects=%d"
              % (len(after), sum(len(v) for v in after.values())))
        entry["after_objects"] = sum(len(v) for v in after.values())
        entry["delta"] = delta(source_inv, before, after)
        entry["_after_raw"] = {k: sorted(v) for k, v in after.items()}
        results["modes"][mode] = entry

    # Mode contrast (T024e): after_forceall - after_filtered.
    if all(m in results["modes"] and "_after_raw" in results["modes"][m]
           for m in ("forceall", "filtered")):
        fa = {k: set(v)
              for k, v in results["modes"]["forceall"]["_after_raw"].items()}
        fi = {k: set(v)
              for k, v in results["modes"]["filtered"]["_after_raw"].items()}
        contrast = {}
        for cls in sorted(set(fa) | set(fi)):
            only_fa = fa.get(cls, set()) - fi.get(cls, set())
            only_fi = fi.get(cls, set()) - fa.get(cls, set())
            if only_fa or only_fi:
                contrast[cls] = {"only_in_forceall": sorted(only_fa),
                                 "only_in_filtered": sorted(only_fi)}
        results["mode_contrast"] = contrast

    for m in results["modes"].values():
        m.pop("_after_raw", None)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("")
    print("[OK] wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
