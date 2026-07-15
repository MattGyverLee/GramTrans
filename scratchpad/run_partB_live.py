"""Live validation driver for coverage-content-fidelity Part B (4 new content
categories). ATTENDED / DESTRUCTIVE.

Designed to run INSIDE the FLExTools MCP `run_module` host process:
    from run_partB_live import Main            # (path-injected below)
    Main(project, report, modifyAllowed)
where `project` is the MCP-opened SOURCE handle (French-FLExTrans-Demo2025,
read-only) -- reused as the source handle so the source is never double-opened.
The TARGET is restored + opened by this driver itself, so `run_module` must NOT
be pointed at TARGET (a locked .fwdata cannot be restored).

Proves each of the 4 Part B categories transfers 0->N under its CORRECT owner
collection on a live target, and is idempotent on a re-Move. GUID-based metric
(resolution-independent):

  B.1 inflection_features complex : source FsComplexFeature GUIDs land in target
                                    MsFeatureSystemOA.FeaturesOC (open features
                                    stay ABSENT -- clean skip).
  B.2 feature_struct_types        : source MsFeatureSystemOA.TypesOC GUIDs land
                                    in target MsFeatureSystemOA.TypesOC.
  B.3 pos_inflectable_feats       : source (pos_guid::feat_guid) pairs land in
                                    target per-POS IPartOfSpeech.InflectableFeatsRC.
  B.4 phon_feat_types             : source PhFeatureSystemOA.TypesOC GUIDs land
                                    in target PhFeatureSystemOA.TypesOC.

ATTENDED-ONLY: live restore + destructive Move. NEVER under an unattended loop.
ASCII-only output (Windows-terminal safe).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

WORKTREE = Path(r"D:\Github\_Projects\_LEX\GramTrans-coverage-content-fidelity-v2")
for _p in (WORKTREE / "src", WORKTREE / "tests" / "integration"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SOURCE = os.environ.get("GT_SOURCE", "French-FLExTrans-Demo2025")
TARGET = os.environ.get("GT_TARGET", "Target")
TARGET_PATH = r"C:\ProgramData\SIL\FieldWorks\Projects\Target"
BACKUP = WORKTREE / "backups" / "Target 2026-07-06 0218.fwbackup"


_REPORTER = None


def _say(msg):
    """Emit a line via the MCP report.Info if set, else stdout print."""
    if _REPORTER is not None:
        try:
            _REPORTER.Info(msg)
            return
        except Exception:
            pass
    print(msg)


def _banner(msg):
    _say("\n" + "=" * 72)
    _say("== " + msg)
    _say("=" * 72)


# --------------------------------------------------------------------------
# GUID-based inventory of an OPEN flexicon handle -- one dict per category.
# Mirrors the exact owner-collection reads in categories.py.
# --------------------------------------------------------------------------
def inventory(handle):
    from gramtrans.Lib import categories
    gid = categories._guid_str_from

    def _clean(s):
        s.discard(None)
        s.discard("")
        return s

    cache = getattr(handle, "Cache", None)
    lp = cache.LangProject if cache is not None else None

    # B.1 inflection features by ClassName + the whole MS FeaturesOC membership.
    complex_feats, open_feats, closed_feats = set(), set(), set()
    try:
        for f in handle.InflectionFeatures.FeatureGetAll():
            cn = getattr(f, "ClassName", None)
            g = gid(f)
            if cn == "FsComplexFeature":
                complex_feats.add(g)
            elif cn == "FsOpenFeature":
                open_feats.add(g)
            else:
                closed_feats.add(g)
    except Exception as exc:  # noqa: BLE001
        _say("  [WARN] InflectionFeatures enum failed: %s" % exc)
    ms_features_oc = set()
    try:
        for f in lp.MsFeatureSystemOA.FeaturesOC:
            ms_features_oc.add(gid(f))
    except Exception as exc:  # noqa: BLE001
        _say("  [WARN] MsFeatureSystemOA.FeaturesOC enum failed: %s" % exc)

    # B.2 feature_struct_types : MsFeatureSystemOA.TypesOC
    ms_types = set()
    try:
        for t in lp.MsFeatureSystemOA.TypesOC:
            ms_types.add(gid(t))
    except Exception as exc:  # noqa: BLE001
        _say("  [WARN] MsFeatureSystemOA.TypesOC enum failed: %s" % exc)

    # B.4 phon_feat_types : PhFeatureSystemOA.TypesOC
    ph_types = set()
    try:
        for t in lp.PhFeatureSystemOA.TypesOC:
            ph_types.add(gid(t))
    except Exception as exc:  # noqa: BLE001
        _say("  [WARN] PhFeatureSystemOA.TypesOC enum failed: %s" % exc)

    # B.3 pos_inflectable_feats : per-POS IPartOfSpeech.InflectableFeatsRC pairs
    pos_feat_pairs = set()
    try:
        from SIL.LCModel import IPartOfSpeech
        for pos in categories._iter_pos(handle):
            concrete = pos.concrete if hasattr(pos, "concrete") else pos
            pos_guid = gid(concrete)
            try:
                pos_obj = IPartOfSpeech(concrete)
                for feat in pos_obj.InflectableFeatsRC:
                    fg = gid(feat)
                    if pos_guid and fg:
                        pos_feat_pairs.add("%s::%s" % (pos_guid, fg))
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        _say("  [WARN] InflectableFeatsRC enum failed: %s" % exc)

    return {
        "complex_feats": _clean(complex_feats),
        "open_feats": _clean(open_feats),
        "closed_feats": _clean(closed_feats),
        "ms_features_oc": _clean(ms_features_oc),
        "ms_types": _clean(ms_types),
        "ph_types": _clean(ph_types),
        "pos_feat_pairs": _clean(pos_feat_pairs),
    }


def inventory_project(project_name):
    """Open a project read-only, take inventory, close."""
    from harness import full_run
    h = full_run._open_source_readonly(project_name)
    try:
        return inventory(h)
    finally:
        try:
            h.CloseProject()
        except Exception:  # noqa: BLE001
            pass


_PART_B_CATS = (
    "INFLECTION_FEATURES", "FEATURE_STRUCT_TYPES",
    "POS_INFLECTABLE_FEATS", "PHON_FEAT_TYPES",
)

# When set (list of GrammarCategory.name strings) run_move builds a targeted
# selection with exactly those True; otherwise the full selection is used.
SELECTED_CAT_NAMES = None


def _build_selection():
    from gramtrans.Lib.models import GrammarCategory, Selection
    from harness import full_run
    if SELECTED_CAT_NAMES is None:
        return full_run.build_full_selection(exclude=frozenset())
    wanted = set(SELECTED_CAT_NAMES)
    return Selection(categories={c: (c.name in wanted) for c in GrammarCategory})


def run_move(label, source_handle):
    """Full Move SOURCE(handle) -> TARGET. Does NOT close source_handle
    (owned by the caller / MCP). Returns per-category plan-action counts."""
    from gramtrans.Lib import api
    from gramtrans.Lib.debuglog import DEBUG_ENV
    from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
    from harness import full_run

    os.environ.setdefault(DEBUG_ENV, "1")
    _banner(label)
    context = None
    try:
        stub = api.initialize_run(
            source_handle, source_project_name=SOURCE, source_project_path="")
        choice = api.TargetCandidate(project_name=TARGET, project_path=TARGET_PATH)
        context = api.bind_target(stub, choice)
        selection = _build_selection()
        src_vern = source_handle.GetDefaultVernacularWS()[0]
        tgt_vern = context.target_handle.GetDefaultVernacularWS()[0]
        ws_mapping = WSMapping(entries=(WSMappingEntry(
            source_ws_id=src_vern, source_ws_kind=WSKind.VERNACULAR,
            target_ws_id=tgt_vern, create_in_target=False),))

        state, plan = api.compute_preview(context, selection, ws_mapping=ws_mapping)
        if state is not api.PreviewState.PREVIEW_READY:
            raise RuntimeError("compute_preview returned %r" % (state,))

        def _cat(x):
            return getattr(getattr(x, "category", None), "name", "")
        act_counts = {c: sum(1 for a in plan.actions if _cat(a) == c) for c in _PART_B_CATS}
        skp_counts = {c: sum(1 for s in plan.skips if _cat(s) == c) for c in _PART_B_CATS}
        _say("[PLAN] total actions=%d skips=%d" % (len(plan.actions), len(plan.skips)))
        for c in _PART_B_CATS:
            _say("[PLAN]   %-24s actions=%-4d skips=%d"
                  % (c, act_counts[c], skp_counts[c]))

        _banner("EXECUTE MOVE (destructive)")
        report = api.execute_move(context, plan)
        added = sum(v.added for v in report.per_category.values())
        skipped = sum(v.skipped for v in report.per_category.values())
        move_skips = {c: sum(1 for s in report.skips if _cat(s) == c) for c in _PART_B_CATS}
        _say("[MOVE] total added=%d skipped=%d" % (added, skipped))
        for c in _PART_B_CATS:
            _say("[MOVE]   %-24s move-skips=%d" % (c, move_skips[c]))
        return act_counts
    finally:
        if context is not None:
            try:
                api._close_project_watchdog(
                    context.target_handle, api._SCHEMA_CLOSE_TIMEOUT_S, "target")
            except Exception as exc:  # noqa: BLE001
                _say("[WARN] target close: %s" % exc)


def _fmt(name, src_n, base_n, p1_n, p2_n):
    _say("  %-22s source=%-4d base=%-4d post#1=%-4d post#2=%-4d"
          % (name, src_n, base_n, p1_n, p2_n))


def Main(project, report=None, modifyAllowed=False):
    from harness import restore

    if not modifyAllowed:
        _say("[ABORT] modifyAllowed is False -- refusing destructive live proof. "
              "Re-run with write_enabled=True.")
        return 1

    # ---- SOURCE inventory (reuse the MCP-injected read-only handle) ----
    _banner("SOURCE inventory (%s)" % SOURCE)
    src = inventory(project)
    _say("  complex inflection feats : %d" % len(src["complex_feats"]))
    _say("  open inflection feats     : %d" % len(src["open_feats"]))
    _say("  MS feature-struct types   : %d" % len(src["ms_types"]))
    _say("  POS inflectable-feat pairs: %d" % len(src["pos_feat_pairs"]))
    _say("  PH feature-struct types   : %d" % len(src["ph_types"]))

    # ---- restore clean target ----
    _banner("RESTORE Target from clean backup")
    _say("[INFO] backup: %s" % BACKUP)
    restore.restore_target(TARGET, backup_path=str(BACKUP))
    base = inventory_project(TARGET)

    # ---- Move #1 ----
    a1 = run_move("live Move #1 (%s -> %s)" % (SOURCE, TARGET), project)
    p1 = inventory_project(TARGET)

    # ---- Move #2 (idempotency) ----
    a2 = run_move("idempotent re-Move #2", project)
    p2 = inventory_project(TARGET)

    # ---- metrics (GUID-based intersections with the source set) ----
    def isect(inv, key):
        return len(src[key] & inv[key])

    _banner("SUMMARY (coverage Part B live proof) -- source&target GUID counts")
    # B.1 complex features land in MS FeaturesOC
    b1_src = len(src["complex_feats"])
    b1_base = len(src["complex_feats"] & base["ms_features_oc"])
    b1_p1 = len(src["complex_feats"] & p1["ms_features_oc"])
    b1_p2 = len(src["complex_feats"] & p2["ms_features_oc"])
    _fmt("B.1 complex->FeaturesOC", b1_src, b1_base, b1_p1, b1_p2)
    # open features must NOT be created
    open_base = len(src["open_feats"] & base["ms_features_oc"])
    open_p1 = len(src["open_feats"] & p1["ms_features_oc"])
    _say("  B.1 open feats present on target: base=%d post#1=%d (expect clean skip -> no NEW)"
          % (open_base, open_p1))
    # B.2 / B.4 struct types
    b2_src, b2_base, b2_p1, b2_p2 = (len(src["ms_types"]), isect(base, "ms_types"),
                                     isect(p1, "ms_types"), isect(p2, "ms_types"))
    _fmt("B.2 MS TypesOC", b2_src, b2_base, b2_p1, b2_p2)
    b4_src, b4_base, b4_p1, b4_p2 = (len(src["ph_types"]), isect(base, "ph_types"),
                                     isect(p1, "ph_types"), isect(p2, "ph_types"))
    _fmt("B.4 PH TypesOC", b4_src, b4_base, b4_p1, b4_p2)
    # B.3 pos-inflectable-feat pairs
    b3_src, b3_base, b3_p1, b3_p2 = (len(src["pos_feat_pairs"]), isect(base, "pos_feat_pairs"),
                                     isect(p1, "pos_feat_pairs"), isect(p2, "pos_feat_pairs"))
    _fmt("B.3 POS InflectableFeatsRC", b3_src, b3_base, b3_p1, b3_p2)

    _say("\n  plan actions Move#1: %s" % a1)
    _say("  plan actions Move#2: %s" % a2)

    # ---- acceptance checks ----
    checks = []
    # Only assert 0->N for categories the SOURCE actually has content for.
    def add_check(name, src_n, base_n, p1_n, p2_n):
        if src_n == 0:
            _say("  [SKIP] %s -- source has none (nothing to prove)" % name)
            return
        checks.append(("%s baseline 0 of source" % name, base_n == 0))
        checks.append(("%s all source landed (0 -> %d)" % (name, src_n), p1_n == src_n))
        checks.append(("%s idempotent re-Move stable" % name, p2_n == p1_n))

    add_check("B.1 complex", b1_src, b1_base, b1_p1, b1_p2)
    add_check("B.2 MS types", b2_src, b2_base, b2_p1, b2_p2)
    add_check("B.3 POS feats", b3_src, b3_base, b3_p1, b3_p2)
    add_check("B.4 PH types", b4_src, b4_base, b4_p1, b4_p2)
    # open-feature clean skip: no NEW open feature created beyond baseline
    if len(src["open_feats"]) > 0:
        checks.append(("B.1 open feats not created (clean skip)", open_p1 == open_base))

    _banner("ACCEPTANCE")
    ok = True
    for name, passed in checks:
        _say("  [%s] %s" % ("PASS" if passed else "FAIL", name))
        ok = ok and passed

    # ---- leave target clean ----
    _banner("RESTORE Target to clean backup (leave no residue)")
    try:
        restore.restore_target(TARGET, backup_path=str(BACKUP))
        _say("[INFO] Target restored clean.")
    except Exception as exc:  # noqa: BLE001
        _say("[WARN] final restore failed: %s" % exc)

    _say("\n[%s] coverage Part B live validation" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1
