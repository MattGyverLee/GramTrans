"""Integration (#146 on merged tree) -- Move-side segment-tag rebind, LIVE.

Two NEW source texts each carry a segment tagged with the SAME new
TextMarkupTags possibility T (absent in target); a third text carries a
distinct new tag U (negative control).  Preview plans T create-then-link;
Move must create T once and wire BOTH ITextTags to it
(``references.rebind_planned_link`` in ``texts._apply_segment_tags``).

WRITES ONLY GT-Src-146 / GT-Sandbox-146 (restored from the Target backup).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_live_project]

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1", allow_module_level=True)

import test_issue146_preview_cache_picture_dedup_live as base  # noqa: E402

SOURCE_NAME = base.SOURCE_NAME
TARGET_NAME = base.TARGET_NAME
assert SOURCE_NAME == "GT-Src-146" and TARGET_NAME == "GT-Sandbox-146"
TARGET_PATH = base.TARGET_PATH


def _author() -> dict:
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from SIL.LCModel import (ILangProject, ICmPossibilityList, ICmPossibilityFactory,
                             ITextTagFactory, IStText,
                             )
    from System import Guid as DotNetGuid
    proj = base._open(SOURCE_NAME, write=True)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        sl = proj.Cache.ServiceLocator
        info = {"list_preexisting": lp.TextMarkupTagsOA is not None}
        if lp.TextMarkupTagsOA is None:
            raise RuntimeError("TextMarkupTagsOA is null in source")
        tags = ICmPossibilityList(lp.TextMarkupTagsOA)
        pf = ICmPossibilityFactory(sl.GetService(ICmPossibilityFactory))
        T = pf.Create(DotNetGuid.NewGuid(), tags)
        base._name(proj, T, "GT146 shared tag")
        U = pf.Create(DotNetGuid.NewGuid(), tags)
        base._name(proj, U, "GT146 control tag")
        tf = ITextTagFactory(proj.GetFactory(ITextTagFactory))
        texts, tagobjs = [], []
        for title, poss in (("GT146T text one", T), ("GT146T text two", T),
                            ("GT146T text three", U)):
            t = proj.Texts.Create(title)
            para = proj.Paragraphs.Create(t, "Hello there.")
            segs = list(proj.Paragraphs.GetSegments(para))
            if not segs:
                proj.Segments.AppendSentence(para, "Hello there.")
                segs = list(proj.Paragraphs.GetSegments(para))
            seg = segs[0]
            tg = tf.Create()
            IStText(proj.Texts.GetContents(t)).TagsOC.Add(tg)
            tg.TagRA = poss
            tg.BeginSegmentRA = seg
            tg.EndSegmentRA = seg
            texts.append(base._g(t))
            tagobjs.append(base._g(tg))
        info.update(T=base._g(T), U=base._g(U), t=texts, tagobjs=tagobjs)
        return info
    finally:
        proj.CloseProject()


def _state(fx) -> dict:
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from SIL.LCModel import ILangProject, IText, IStText
    from System import Guid
    proj = base._open(TARGET_NAME)
    try:
        repo = proj.Cache.ServiceLocator.ObjectRepository
        lp = ILangProject(proj.Cache.LangProject)
        lst = lp.TextMarkupTagsOA
        out = {"list": sorted(base._g(x) for x in lst.PossibilitiesOS) if lst else [],
               "texts": {}}
        for tg in fx["t"]:
            try:
                t = IText(repo.GetObject(Guid.Parse(tg)))
                st = IStText(t.ContentsOA)
                out["texts"][tg] = sorted(
                    base._g(x.TagRA) if x.TagRA is not None else None
                    for x in st.TagsOC)
            except Exception:  # noqa: BLE001
                out["texts"][tg] = None
        return out
    finally:
        proj.CloseProject()


def _tag_rows(plan, fx):
    idx = {g: i + 1 for i, g in enumerate(fx["t"])}
    rows = []
    for tp in getattr(plan, "text_plans", ()) or ():
        i = idx.get(getattr(tp, "source_guid", ""))
        if i is None:
            continue
        for pp in getattr(tp, "paragraphs", ()) or ():
            for sp in getattr(pp, "segments", ()) or ():
                for d in getattr(sp, "tag_decisions", ()) or ():
                    rows.append((i, d.action.value))
    return sorted(rows)


@pytest.fixture(scope="module")
def live():
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    def run(fx, preview_only=False):
        assert TARGET_NAME == "GT-Sandbox-146"

        def _sel(_full):
            return Selection(categories={GC.TEXTS: True},
                             text_picks=frozenset(fx["t"]), include_closure=True)
        return full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=_sel,
            preview_only=preview_only)
    try:
        base._fork_target()
        fx = _author()
        res = {"fx": fx, "pre": _state(fx)}
        before = Path(TARGET_PATH).read_bytes()
        res["preview"], _ = run(fx, preview_only=True)
        res["preview_wrote"] = Path(TARGET_PATH).read_bytes() != before
        res["plan"], res["report"] = run(fx)
        res["post"] = _state(fx)
        run(fx)
        res["post2"] = _state(fx)
        print("[LIVE-TAGS] fixture=%s" % fx)
        print("[LIVE-TAGS] preview rows=%s" % _tag_rows(res["preview"], fx))
        print("[LIVE-TAGS] pre=%s" % res["pre"])
        print("[LIVE-TAGS] post=%s" % res["post"])
        print("[LIVE-TAGS] post2=%s" % res["post2"])
        yield res
    finally:
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                base._restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


def test_preview_wrote_nothing(live):
    assert not live["preview_wrote"]
    assert all(v is None for v in live["pre"]["texts"].values())
    assert live["fx"]["T"] not in live["pre"]["list"]


def test_preview_plans_create_then_link(live):
    rows = _tag_rows(live["preview"], live["fx"])
    # Plan order between the two T texts is not fixed: exactly one is the
    # CREATE and the other the LINK; the U text is its own CREATE.
    assert sorted(a for i, a in rows if i in (1, 2)) == ["create", "link"], rows
    assert [a for i, a in rows if i == 3] == ["create"], rows


def test_move_both_texts_reference_same_created_tag(live):
    fx, pre, post = live["fx"], live["pre"], live["post"]
    added = sorted(set(post["list"]) - set(pre["list"]))
    assert added == sorted([fx["T"], fx["U"]]), added      # T once, U once
    t1, t2, t3 = (post["texts"][g] for g in fx["t"])
    assert t1 == [fx["T"]]
    assert t2 == [fx["T"]]                                  # rebound LINK
    assert t3 == [fx["U"]]


def test_move_rerun_idempotent(live):
    assert live["post2"] == live["post"]
