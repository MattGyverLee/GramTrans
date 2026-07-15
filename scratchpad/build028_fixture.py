"""T019 fixture builder for feature 028 (attended, destructive on the SOURCE).

Populates all four `MoAffixAllomorph`/`MoAffixForm` morphosyntactic-environment
fields on ONE affix allomorph in a DISPOSABLE source project, so the live Move
has something non-vacuous to reproduce (Ejagham corpora populate 0/106).

    MsEnvPartOfSpeechRA  -> a NEW POS (absent from Target => CREATE on Move)
    InflectionClassesRC  -> a NEW inflection class under that POS (=> CREATE)
    MsEnvFeaturesOA      -> a deep IFsFeatStruc w/ one closed value (=> deep-copy)
    PositionRS           -> >=2 existing IPhEnvironments (=> LINK, order kept)

!!! UNTESTED IN THE AUTHORING ENVIRONMENT (flexicon is not installed there).
    Run ATTENDED in the FLEx host and ITERATE -- the cross-project resolvability
    of the feature value and the PositionRS environments depends on whether the
    Target backup shares those GUIDs with the source. Confirm the live GUIDs
    (run the read-only inventory block first) and adjust as needed. ASCII-only.

Run:  python scratchpad/build028_fixture.py           # dry-run (inventory only)
      python scratchpad/build028_fixture.py --write    # actually mutate SOURCE
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT / "src", _ROOT / "tests" / "integration"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

SOURCE = os.environ.get("GT_SOURCE", "Ejagham028Src")
WRITE = "--write" in sys.argv

# A GUID-preserving name unlikely to already exist in Target (forces CREATE).
NEW_POS_NAME = "Affix028Env POS"
NEW_INFLCLASS_NAME = "Affix028 InflClass"


def _banner(msg):
    print("\n" + "=" * 72 + "\n== " + msg + "\n" + "=" * 72)


def main():
    from harness import full_run  # reuses FLExInitialize + open helpers
    full_run._ensure_flex_initialized()
    from flexicon import FLExProject
    from SIL.LCModel import (
        ILangProject, ILexEntry, IMoAffixAllomorph, IMoAffixForm, IPhEnvironment,
        IPartOfSpeech, IMoInflClass, IFsClosedFeature, IFsSymFeatVal,
        IPartOfSpeechFactory, IMoInflClassFactory, IFsFeatStrucFactory,
        IFsClosedValueFactory, IFsFeatStruc,
    )
    from SIL.LCModel.Core.KernelInterfaces import ITsString  # noqa: F401
    import System
    Guid = System.Guid

    proj = FLExProject()
    proj.OpenProject(projectName=SOURCE, writeEnabled=WRITE)
    try:
        lp = ILangProject(proj.lp)
        cache = proj.project.cache
        wsf = cache.WritingSystemFactory
        anal_ws = cache.DefaultAnalWs
        vern_ws = cache.DefaultVernWs

        # --- read-only inventory (ALWAYS printed; confirm live GUIDs here) ---
        _banner("SOURCE inventory (%s)" % SOURCE)
        envs = [IPhEnvironment(e) for e in lp.PhonologicalDataOA.EnvironmentsOS]
        print("[INV] environments: %d" % len(envs))
        for e in envs[:6]:
            sr = e.StringRepresentation.Text if e.StringRepresentation else "?"
            print("[INV]   env %s  %s" % (e.Guid, sr))
        closed = [(IFsClosedFeature(f), list(IFsClosedFeature(f).ValuesOC))
                  for f in lp.MsFeatureSystemOA.FeaturesOC
                  if f.ClassName == "FsClosedFeature"]
        print("[INV] closed features: %d" % len(closed))
        for cf, vals in closed[:4]:
            print("[INV]   feat %s vals=%s" % (
                cf.Guid, [str(IFsSymFeatVal(v).Guid) for v in vals]))

        # first affix allomorph in the lexicon
        target_allo = None
        target_form = None
        host_entry = None
        for _e in proj.LexEntry.GetAll():
            e = ILexEntry(_e)
            forms = list(e.AlternateFormsOS)
            if e.LexemeFormOA is not None:
                forms.append(e.LexemeFormOA)
            for allo in forms:
                if allo is not None and allo.ClassName == "MoAffixAllomorph":
                    target_allo = IMoAffixAllomorph(allo)
                    target_form = IMoAffixForm(allo)
                    host_entry = e
                    break
            if target_allo is not None:
                break
        if target_allo is None:
            print("[ERROR] no MoAffixAllomorph found in %s -- add an affix entry "
                  "in FLEx first, or point GT_SOURCE at a project that has one."
                  % SOURCE)
            return 2
        print("[INV] fixture allomorph: entry='%s' allo=%s" % (
            host_entry.HeadWord.Text if host_entry.HeadWord else "?",
            target_allo.Guid))

        if not WRITE:
            print("\n[DRY-RUN] re-run with --write to populate the four fields. "
                  "Confirm the env/feature GUIDs above resolve in Target first.")
            return 0

        # --- WRITE: populate the four fields (guarded) ------------------------
        _banner("WRITE fixture fields onto allomorph %s" % target_allo.Guid)

        def _run_write(action_desc, fn):
            # LCM writes must be inside a UOW; flexicon exposes the cache's
            # action handler. Mirror how the engine wraps mutations.
            from SIL.LCModel.Infrastructure import NonUndoableUnitOfWorkHelper
            NonUndoableUnitOfWorkHelper.Do(
                action_desc, "undo", cache.ActionHandlerAccessor, System.Action(fn))

        # 1) MsEnvPartOfSpeechRA -> a new POS (GUID-preserved, absent in Target)
        pos_holder = {}

        def _mk_pos():
            fac = cache.ServiceLocator.GetInstance[IPartOfSpeechFactory]()
            new_pos = fac.Create(Guid.NewGuid(), lp.PartsOfSpeechOA)
            new_pos.Name.set_String(anal_ws, NEW_POS_NAME)
            pos_holder["pos"] = new_pos
            target_allo.MsEnvPartOfSpeechRA = new_pos
        _run_write("028 fixture: MsEnvPartOfSpeechRA", _mk_pos)
        print("[WRITE] MsEnvPartOfSpeechRA -> new POS '%s' %s"
              % (NEW_POS_NAME, pos_holder["pos"].Guid))

        # 2) InflectionClassesRC -> a new class under that POS
        def _mk_infl():
            fac = cache.ServiceLocator.GetInstance[IMoInflClassFactory]()
            ic = fac.Create()
            pos_holder["pos"].InflectionClassesOC.Add(ic)
            IMoInflClass(ic).Name.set_String(anal_ws, NEW_INFLCLASS_NAME)
            target_form.InflectionClassesRC.Add(ic)
        _run_write("028 fixture: InflectionClassesRC", _mk_infl)
        print("[WRITE] InflectionClassesRC -> new class '%s'" % NEW_INFLCLASS_NAME)

        # 3) MsEnvFeaturesOA -> deep IFsFeatStruc with one existing closed value
        if closed and closed[0][1]:
            cf, vals = closed[0]
            symval = IFsSymFeatVal(vals[0])

            def _mk_feat():
                fsfac = cache.ServiceLocator.GetInstance[IFsFeatStrucFactory]()
                fs = fsfac.Create()
                target_allo.MsEnvFeaturesOA = fs
                cvfac = cache.ServiceLocator.GetInstance[IFsClosedValueFactory]()
                cv = cvfac.Create()
                IFsFeatStruc(fs).FeatureSpecsOC.Add(cv)
                cv.FeatureRA = cf
                cv.ValueRA = symval
            _run_write("028 fixture: MsEnvFeaturesOA", _mk_feat)
            print("[WRITE] MsEnvFeaturesOA -> struct w/ closed value feat=%s val=%s"
                  % (cf.Guid, symval.Guid))
        else:
            print("[SKIP] MsEnvFeaturesOA -- no closed feature+value in source; "
                  "add one in FLEx (Grammar > Inflection Features) and re-run.")

        # 4) PositionRS -> the first >=2 environments (must exist in Target too)
        if len(envs) >= 2:
            pick = envs[:2]

            def _mk_pos_rs():
                for e in pick:
                    target_allo.PositionRS.Add(e)
            _run_write("028 fixture: PositionRS", _mk_pos_rs)
            print("[WRITE] PositionRS -> %s" % [str(e.Guid) for e in pick])
            print("[NOTE] confirm these env GUIDs also exist in Target (=> LINK); "
                  "if not, they REPORT_DROPPED (still valid, but not the LINK arm).")
        else:
            print("[SKIP] PositionRS -- source has <2 environments.")

        print("\n[DONE] fixture written. Now run: python scratchpad/run028_live.py")
        return 0
    finally:
        try:
            proj.CloseProject()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
