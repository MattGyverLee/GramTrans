"""Full-sweep transfer + structural intactness verification (attended, destructive).

Runs a FULL-selection Move (every GrammarCategory except STEMS, per
harness.full_run.build_full_selection) from SOURCE into a disposable TARGET that
this driver restores from a clean backup first -- then proves, by GUID-keyed
source-vs-target diff, that four domains arrived INTACT:

  D1 features        IFsClosedFeature in MsFeatureSystemOA.FeaturesOC + their
                     IFsSymFeatVal values + each POS's InflectableFeatsRC links.
  D2 affixes         LexEntry whose LexemeFormOA.MorphTypeRA.IsAffixType, plus
                     each entry's MSAs (POS + slot memberships).
  D3 affix templates IMoInflAffixTemplate in IPartOfSpeech.AffixTemplatesOS with
                     its ORDERED slot sequences (Prefix/Suffix/Proclitic/Enclitic/
                     Slots RS), and the IMoInflAffixSlot inventory itself.
  D4 feats-on-affix  IMoInflAffMsa.InflFeatsOA -> FeatureSpecsOC -> IFsClosedValue
                     (FeatureRA, ValueRA) pairs: the features actually ASSIGNED to
                     each affix. Also MoDerivAffMsa From/To infl feats when present.

"Intact" is a set/sequence equality on GUIDs, not a count match: a count-equal but
identity-shifted transfer FAILS. Ordered slot sequences compare as sequences, so a
reordered template FAILS.

Move #2 re-runs the identical transfer to prove idempotency across all four domains.

Casts follow the FLExToolsMCP-validated shapes (IPartOfSpeech.AffixTemplatesOS /
AffixSlotsOC / InflectableFeatsRC; IMoInflAffixTemplate.*SlotsRS; IMoInflAffMsa.
InflFeatsOA + SlotsRC; IFsClosedValue.FeatureRA/ValueRA) -- every one requires an
explicit interface cast; a bare ICmObject fails the accessor.

ASCII-only output (Windows-terminal safe). Run from the repo root:
    python scratchpad/run_fullsweep_verify.py
Env: GT_SOURCE (default "Ejagham Mini"), GT_TARGET (default "Target"),
     GT_BACKUP (default backups/Target 2026-07-06 0218.fwbackup).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT / "src", _ROOT / "tests" / "integration", _ROOT / "debug"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SOURCE = os.environ.get("GT_SOURCE", "Ejagham Mini")
TARGET = os.environ.get("GT_TARGET", "Target")
TARGET_PATH = os.environ.get(
    "GT_TARGET_PATH", r"C:\ProgramData\SIL\FieldWorks\Projects\Target")
BACKUP = Path(os.environ.get(
    "GT_BACKUP", str(_ROOT / "backups" / "Target 2026-07-06 0218.fwbackup")))
OUT_JSON = Path(os.environ.get(
    "GT_OUT", str(_ROOT / "scratchpad" / "fullsweep_verify.json")))


def _banner(msg):
    print("\n" + "=" * 72)
    print("== " + msg)
    print("=" * 72)


def _g(obj):
    """Lowercase GUID string, or None."""
    try:
        return str(obj.Guid).lower()
    except Exception:  # noqa: BLE001
        return None


def _name(obj, ws):
    """Best-effort Name in `ws` across the interfaces that declare Name."""
    from SIL.LCModel import (  # noqa: PLC0415
        IFsFeatDefn, IFsSymFeatVal, IMoInflAffixSlot, IMoInflAffixTemplate,
        ICmPossibility,
    )
    for iface in (IFsFeatDefn, IFsSymFeatVal, IMoInflAffixSlot,
                  IMoInflAffixTemplate, ICmPossibility):
        try:
            ts = iface(obj).Name.get_String(ws)
            return ts.Text or ""
        except Exception:  # noqa: BLE001 -- wrong cast; try the next
            continue
    return ""


def _iter_entries(lp):
    """Yield every ILexEntry. Mirrors categories._iter_lex_entries' live shape:
    LangProject.LexDbOA exposes `.Entries` live (`.EntriesOC` on the contract
    shape). NOTE: flexicon's FLExProject has no `.lexicon` attribute -- see the
    finding note in the run summary."""
    lexdb = lp.LexDbOA
    if lexdb is None:
        return []
    for attr in ("Entries", "EntriesOC"):
        coll = getattr(lexdb, attr, None)
        if coll is not None:
            return list(coll)
    return []


# ---------------------------------------------------------------------------
# Inventory (read-only)
# ---------------------------------------------------------------------------

def inventory(project_name):
    """Open `project_name` READ-ONLY and return the 4-domain GUID inventory."""
    import flexicon  # noqa: PLC0415
    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr  # noqa: PLC0415
        if not Sldr.IsInitialized:
            Sldr.Initialize(True)
    except Exception:  # noqa: BLE001
        pass

    from flexicon import FLExProject  # noqa: PLC0415
    from SIL.LCModel import (  # noqa: PLC0415
        ILangProject, IPartOfSpeech, IFsClosedFeature, IFsClosedValue,
        IFsFeatStruc, IMoInflAffixTemplate, IMoInflAffMsa, IMoDerivAffMsa,
        IMoForm, IMoMorphType, ILexEntry,
    )

    proj = FLExProject()
    proj.OpenProject(projectName=project_name, writeEnabled=False)
    inv = {
        "features": {}, "feature_values": {}, "pos_inflectable_feats": {},
        "affixes": {}, "affix_msas": {}, "affix_slots": {},
        "affix_templates": {}, "affix_msa_feats": {},
    }
    try:
        cache = proj.project
        ws = cache.DefaultAnalWs
        lp = ILangProject(cache.LangProject)

        # -- D1 features + values ------------------------------------------
        fs = lp.MsFeatureSystemOA
        for feat in (list(fs.FeaturesOC) if fs is not None else []):
            fg = _g(feat)
            inv["features"][fg] = _name(feat, ws)
            try:
                vals = list(IFsClosedFeature(feat).ValuesOC)
            except Exception:  # noqa: BLE001 -- complex feature: no ValuesOC
                vals = []
            for val in vals:
                inv["feature_values"][_g(val)] = {
                    "feature": fg, "name": _name(val, ws)}

        # -- D1 links + D3 slots/templates (both hang off IPartOfSpeech) ----
        for pos_obj in lp.AllPartsOfSpeech:
            pos = IPartOfSpeech(pos_obj)   # CAST: bare ICmObject fails these
            pg = _g(pos_obj)
            inv["pos_inflectable_feats"][pg] = sorted(
                _g(f) for f in pos.InflectableFeatsRC)
            for slot in pos.AffixSlotsOC:
                inv["affix_slots"][_g(slot)] = {
                    "pos": pg, "name": _name(slot, ws)}
            for tmpl_obj in pos.AffixTemplatesOS:
                t = IMoInflAffixTemplate(tmpl_obj)
                inv["affix_templates"][_g(tmpl_obj)] = {
                    "pos": pg,
                    "name": _name(tmpl_obj, ws),
                    # ORDERED -> compared as sequences, not sets.
                    "prefix_slots": [_g(s) for s in t.PrefixSlotsRS],
                    "suffix_slots": [_g(s) for s in t.SuffixSlotsRS],
                    "slots": [_g(s) for s in t.SlotsRS],
                    "proclitic_slots": [_g(s) for s in t.ProcliticSlotsRS],
                    "enclitic_slots": [_g(s) for s in t.EncliticSlotsRS],
                    "final": bool(t.Final),
                }

        # -- D2 affixes + D4 features assigned to them ---------------------
        def _feat_pairs(struc):
            """(feature_guid, value_guid) pairs owned by an IFsFeatStruc."""
            if struc is None:
                return []
            out = []
            for spec in IFsFeatStruc(struc).FeatureSpecsOC:
                try:
                    cv = IFsClosedValue(spec)   # CAST before FeatureRA/ValueRA
                    out.append([_g(cv.FeatureRA), _g(cv.ValueRA)])
                except Exception:  # noqa: BLE001 -- complex/negated value
                    out.append([_g(getattr(spec, "FeatureRA", None)), None])
            return sorted(out, key=lambda p: (p[0] or "", p[1] or ""))

        for entry_obj in _iter_entries(lp):
            entry = ILexEntry(entry_obj)
            form = entry.LexemeFormOA
            if form is None:
                continue
            try:
                mt = IMoForm(form).MorphTypeRA
                if mt is None or not IMoMorphType(mt).IsAffixType:
                    continue
            except Exception:  # noqa: BLE001
                continue
            eg = _g(entry_obj)
            inv["affixes"][eg] = {
                "morph_type": _g(mt),
                "form": (IMoForm(form).Form.get_String(
                    cache.DefaultVernWs).Text or ""),
            }
            for msa in entry.MorphoSyntaxAnalysesOC:
                mg = _g(msa)
                rec = {"entry": eg, "class": msa.ClassName, "pos": None,
                       "slots": []}
                try:
                    im = IMoInflAffMsa(msa)
                    rec["pos"] = _g(im.PartOfSpeechRA)
                    rec["slots"] = sorted(_g(s) for s in im.SlotsRC)
                    inv["affix_msa_feats"][mg] = _feat_pairs(im.InflFeatsOA)
                except Exception:  # noqa: BLE001 -- not an inflectional affix MSA
                    try:
                        dm = IMoDerivAffMsa(msa)
                        rec["pos"] = _g(dm.ToPartOfSpeechRA)
                        inv["affix_msa_feats"][mg] = (
                            _feat_pairs(dm.FromInflFeatsOA)
                            + _feat_pairs(dm.ToInflFeatsOA))
                    except Exception:  # noqa: BLE001 -- stem/unclassified MSA
                        pass
                inv["affix_msas"][mg] = rec
    finally:
        try:
            proj.CloseProject()
        except Exception:  # noqa: BLE001
            pass
    return inv


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def diff_domain(label, src, tgt):
    """Compare two {guid: detail} maps. Returns a result dict."""
    s_keys, t_keys = set(src), set(tgt)
    missing = sorted(s_keys - t_keys)
    extra = sorted(t_keys - s_keys)
    mismatched = []
    for k in sorted(s_keys & t_keys):
        if src[k] != tgt[k]:
            mismatched.append({"guid": k, "source": src[k], "target": tgt[k]})
    return {
        "domain": label,
        "source_count": len(s_keys), "target_count": len(t_keys),
        "missing": missing, "extra": extra, "mismatched": mismatched,
        "intact": not missing and not mismatched,
    }


def compare(src_inv, tgt_inv):
    domains = ("features", "feature_values", "pos_inflectable_feats",
               "affixes", "affix_msas", "affix_slots", "affix_templates",
               "affix_msa_feats")
    return [diff_domain(d, src_inv[d], tgt_inv[d]) for d in domains]


def _print_diffs(diffs):
    print("  %-24s %8s %8s %8s %8s %8s  %s"
          % ("domain", "source", "target", "missing", "extra", "mismatch",
             "verdict"))
    for d in diffs:
        print("  %-24s %8d %8d %8d %8d %8d  %s"
              % (d["domain"], d["source_count"], d["target_count"],
                 len(d["missing"]), len(d["extra"]), len(d["mismatched"]),
                 "INTACT" if d["intact"] else "**BROKEN**"))
    for d in diffs:
        if d["intact"]:
            continue
        print("\n  [DETAIL] %s" % d["domain"])
        for g in d["missing"][:10]:
            print("    MISSING  %s  src=%r" % (g, d.get("_", "")))
        for m in d["mismatched"][:10]:
            print("    MISMATCH %s\n      source=%r\n      target=%r"
                  % (m["guid"], m["source"], m["target"]))


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------

def run_full_move():
    """Full-selection Move SOURCE -> TARGET. Returns a summary dict."""
    from collections import Counter
    from gramtrans.Lib import api
    from gramtrans.Lib.debuglog import DEBUG_ENV
    from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
    from harness import full_run

    os.environ[DEBUG_ENV] = "0"   # keep the console readable
    source_handle = full_run._open_source_readonly(SOURCE)
    context = None
    try:
        stub = api.initialize_run(
            source_handle, source_project_name=SOURCE, source_project_path="")
        choice = api.TargetCandidate(project_name=TARGET, project_path=TARGET_PATH)
        context = api.bind_target(stub, choice)
        selection = full_run.build_full_selection()   # all cats except STEMS
        src_vern = source_handle.GetDefaultVernacularWS()[0]
        tgt_vern = context.target_handle.GetDefaultVernacularWS()[0]
        ws_mapping = WSMapping(entries=(WSMappingEntry(
            source_ws_id=src_vern, source_ws_kind=WSKind.VERNACULAR,
            target_ws_id=tgt_vern, create_in_target=False),))

        state, plan = api.compute_preview(context, selection, ws_mapping=ws_mapping)
        if state is not api.PreviewState.PREVIEW_READY:
            raise RuntimeError("compute_preview returned %r" % (state,))
        report = api.execute_move(context, plan)
        added = sum(r.added for r in report.per_category.values())
        skipped = sum(r.skipped for r in report.per_category.values())
        drops = Counter("%s/%s" % (d.owner_kind, d.reason)
                        for d in report.dropped_items)
        return {
            "actions": len(plan.actions), "added": added, "skipped": skipped,
            "dropped_items": len(report.dropped_items),
            "dropped_breakdown": dict(drops.most_common(12)),
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

    result = {"source": SOURCE, "target": TARGET}

    _banner("SOURCE inventory: %s" % SOURCE)
    src_inv = inventory(SOURCE)
    for k, v in src_inv.items():
        print("  %-24s %d" % (k, len(v)))

    _banner("RESTORE %s from clean backup" % TARGET)
    print("[INFO] backup: %s" % BACKUP)
    restore.restore_target(TARGET, backup_path=str(BACKUP))

    _banner("FULL-SELECTION MOVE #1 (%s -> %s)" % (SOURCE, TARGET))
    result["move1"] = run_full_move()
    print("[MOVE1] %s" % json.dumps(result["move1"]))

    _banner("TARGET inventory after Move #1")
    tgt1 = inventory(TARGET)
    diffs1 = compare(src_inv, tgt1)
    result["diffs_move1"] = diffs1
    _print_diffs(diffs1)

    _banner("FULL-SELECTION MOVE #2 (idempotency re-run)")
    result["move2"] = run_full_move()
    print("[MOVE2] %s" % json.dumps(result["move2"]))

    _banner("TARGET inventory after Move #2")
    tgt2 = inventory(TARGET)
    diffs2 = compare(src_inv, tgt2)
    result["diffs_move2"] = diffs2
    _print_diffs(diffs2)

    # Idempotency: the post-Move#2 inventory must equal post-Move#1 exactly.
    idem = {k: {"post1": len(tgt1[k]), "post2": len(tgt2[k]),
                "equal": tgt1[k] == tgt2[k]} for k in tgt1}
    result["idempotent"] = idem

    _banner("SUMMARY")
    focus = ("features", "feature_values", "pos_inflectable_feats", "affixes",
             "affix_msas", "affix_slots", "affix_templates", "affix_msa_feats")
    ok = True
    for d in diffs1:
        passed = d["intact"]
        ok = ok and passed
        print("  [%s] D1 intact after Move #1: %s"
              % ("PASS" if passed else "FAIL", d["domain"]))
    for k in focus:
        passed = idem[k]["equal"]
        ok = ok and passed
        print("  [%s] idempotent (Move #2 changed nothing): %s"
              % ("PASS" if passed else "FAIL", k))
    m2_added = result["move2"]["added"]
    print("  [%s] Move #2 added==0 (actual %d)"
          % ("PASS" if m2_added == 0 else "FAIL", m2_added))
    ok = ok and (m2_added == 0)

    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\n[RESULT_FILE] %s" % OUT_JSON)
    print("[%s] full-sweep intactness verification" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
