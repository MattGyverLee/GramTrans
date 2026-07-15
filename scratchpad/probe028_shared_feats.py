"""Ad-hoc probe: closed-feature values shared (by GUID) between source + Target.

Used to pick an MsEnvFeaturesOA value that resolves cross-project so the 028
feature-structure leg positively reproduces (rather than REPORT_DROPPED) in the
T019 live run. Read-only. ASCII output.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT / "src", _ROOT / "tests" / "integration"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

SRC = os.environ.get("GT_SOURCE", "Ejagham028Src")
TGT = os.environ.get("GT_TARGET", "Target")


def _vals(name):
    from harness import full_run
    full_run._ensure_flex_initialized()
    from flexicon import FLExProject
    from SIL.LCModel import ILangProject, IFsClosedFeature, IFsSymFeatVal
    p = FLExProject()
    p.OpenProject(projectName=name, writeEnabled=False)
    try:
        lp = ILangProject(p.lp)
        out = {}
        for f in lp.MsFeatureSystemOA.FeaturesOC:
            if f.ClassName == "FsClosedFeature":
                out[str(f.Guid)] = [str(IFsSymFeatVal(v).Guid)
                                    for v in IFsClosedFeature(f).ValuesOC]
        return out
    finally:
        p.CloseProject()


def main():
    src = _vals(SRC)
    tgt = _vals(TGT)
    print("SRC closed feats=%d  TGT closed feats=%d" % (len(src), len(tgt)))
    shared = set(src) & set(tgt)
    print("shared feature GUIDs: %s" % sorted(shared))
    found = False
    for f in sorted(shared):
        both = set(src[f]) & set(tgt[f])
        if both:
            found = True
            print("USE feat=%s value=%s" % (f, sorted(both)[0]))
    if not found:
        print("NO shared closed-feature value -- MsEnvFeaturesOA will "
              "REPORT_DROPPED (never-silent), which is still valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
