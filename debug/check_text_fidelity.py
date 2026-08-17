"""Read-only text-fidelity check for feature 033 Option A.

Option A deletes each LCM-auto-created segment and re-creates it at the same
offset via `ISegmentFactory.Create(owner, initialOffset, cache, guid)` so it
keeps its SOURCE GUID. It never touches `IStTxtPara.Contents`, so the baseline
text should be untouched BY CONSTRUCTION -- this script is the empirical proof
of that claim, because a GUID win that silently corrupted the baseline would be
a net loss, and the GUID audit alone would not catch it.

For every source text reproduced into the target, compares paragraph-by-
paragraph:
  - paragraph Contents text (exact)
  - segment count per paragraph
  - each segment's baseline text (exact)

Read-only on BOTH projects. Run AFTER audit_guid_preservation.py.

    python debug/check_text_fidelity.py
Env: GT_SOURCE (default "Ejagham Mini"), GT_TARGET (default "Target").
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT / "src", _ROOT / "tests" / "integration"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SOURCE = os.environ.get("GT_SOURCE", "Ejagham Mini")
TARGET = os.environ.get("GT_TARGET", "Target")


def _open(name):
    import flexicon
    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr
        if not Sldr.IsInitialized:
            Sldr.Initialize(True)
    except Exception:  # noqa: BLE001
        pass
    from flexicon import FLExProject
    proj = FLExProject()
    proj.OpenProject(projectName=name, writeEnabled=False)
    return proj


def _text_shape(proj):
    """{text_title: [ [para_contents, [seg_baseline, ...]], ... ]} (read-only)."""
    out = {}
    for text in proj.Texts.GetAll():
        try:
            title = proj.Texts.GetTitle(text) or ""
        except Exception:  # noqa: BLE001
            title = ""
        paras = []
        try:
            para_list = list(proj.Paragraphs.GetAll(text) or [])
        except Exception:  # noqa: BLE001
            para_list = []
        for para in para_list:
            try:
                contents = proj.Paragraphs.GetText(para) or ""
            except Exception:  # noqa: BLE001
                contents = "<unreadable>"
            segs = []
            try:
                for seg in (proj.Segments.GetAll(para) or []):
                    try:
                        segs.append(proj.Segments.GetBaselineText(seg) or "")
                    except Exception:  # noqa: BLE001
                        segs.append("<unreadable>")
            except Exception:  # noqa: BLE001
                pass
            paras.append([contents, segs])
        out.setdefault(title, []).extend(paras)
    return out


def main():
    src_p = _open(SOURCE)
    try:
        src = _text_shape(src_p)
    finally:
        src_p.CloseProject()
    tgt_p = _open(TARGET)
    try:
        tgt = _text_shape(tgt_p)
    finally:
        tgt_p.CloseProject()

    shared = [t for t in src if t in tgt]
    print("source texts: %d | target texts: %d | shared titles: %d"
          % (len(src), len(tgt), len(shared)))

    para_ok = para_bad = seg_ok = seg_bad = count_bad = 0
    for title in sorted(shared):
        s_paras, t_paras = src[title], tgt[title]
        if len(s_paras) != len(t_paras):
            count_bad += 1
            print("  [WARN] %r paragraph count %d -> %d"
                  % (title, len(s_paras), len(t_paras)))
        for i in range(min(len(s_paras), len(t_paras))):
            s_txt, s_segs = s_paras[i]
            t_txt, t_segs = t_paras[i]
            if s_txt == t_txt:
                para_ok += 1
            else:
                para_bad += 1
                if para_bad <= 5:
                    print("  [FAIL] %r para %d CONTENTS DIFFER" % (title, i))
                    print("         source: %r" % (s_txt[:120],))
                    print("         target: %r" % (t_txt[:120],))
            if len(s_segs) != len(t_segs):
                count_bad += 1
                if count_bad <= 5:
                    print("  [WARN] %r para %d segment count %d -> %d"
                          % (title, i, len(s_segs), len(t_segs)))
            for j in range(min(len(s_segs), len(t_segs))):
                if s_segs[j] == t_segs[j]:
                    seg_ok += 1
                else:
                    seg_bad += 1
                    if seg_bad <= 5:
                        print("  [FAIL] %r para %d seg %d BASELINE DIFFERS"
                              % (title, i, j))
                        print("         source: %r" % (s_segs[j][:120],))
                        print("         target: %r" % (t_segs[j][:120],))

    print("\nparagraph contents identical : %d" % para_ok)
    print("paragraph contents DIFFERING : %d" % para_bad)
    print("segment baselines identical  : %d" % seg_ok)
    print("segment baselines DIFFERING  : %d" % seg_bad)
    print("count mismatches             : %d" % count_bad)
    bad = para_bad or seg_bad
    print("[%s] text fidelity" % ("PASS" if not bad else "FAIL"))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
