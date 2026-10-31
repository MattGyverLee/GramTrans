"""Issue #146 -- Preview over-reported vs Move (constitution Principle III).

1. A SECOND reference to an item already planned for CREATE showed as CREATE
   again in Preview: Move's `apply_reference` CREATE arm caches what it creates
   (so the second reference becomes LINK), but Preview never applies, so its
   resolver cache stayed unprimed. Fix: `preview.build_run_plan` marks its
   cache as a planning cache and `references.decide_reference` primes it with a
   `PlannedCreate` placeholder for exactly what Move's CREATE arm would cache.
2. `pictures.plan_sense_picture_decisions` deduped image copies per SENSE while
   Move's asset cache spans the whole run. Fix: the planned-hash set lives in
   the run's resolver cache.
Sweep sibling: the 028 MsEnv POS / inflection-class Preview twins had the same
per-reference CREATE shape against Move's per-run dedup caches.

Move behaviour is the reference throughout; an UNMARKED cache (every Move
cache) must behave exactly as before.
"""
from __future__ import annotations

import os

import pytest

import test_issue116_preview_sense_list_decisions as t116
import test_029_picture_asset_copy as t029
import test_028_affix_msenv_reproduction as t028

from gramtrans.Lib import categories, owned, pictures, references
from gramtrans.Lib.models import ReferenceAction


def _planning():
    return references.mark_planning_cache({})


def _thes_fixture():
    """Source list `Thes`: new top-level P with new children C and C3, plus a
    second unrelated new top-level item N. Target's mirrored list is empty."""
    src_list = t116._List("src-thes", "Thes", owner=object())
    p = t116._Item("p", "parent", owner=src_list)
    c = t116._Item("c", "child", parent=p)
    c3 = t116._Item("c3", "second child", parent=p)
    n = t116._Item("n", "other", owner=src_list)
    src_list.PossibilitiesOS = [p, n]
    tgt_list = t116._List("tgt-thes", "Thes", items=[])
    target = t116._Target(possibility_lists=[tgt_list])
    return dict(P=p, C=c, C3=c3, N=n, target=target, tgt_list=tgt_list)


def _actions(records):
    return [(r.owner_guid, r.action, r.item_guid, r.new_ancestors) for r in records]


# ============================================================================
# decide_reference: planning cache vs Move (unmarked) cache
# ============================================================================

def _spec(fx):
    return references.build_thesaurus_spec(fx["tgt_list"])


def test_planning_cache_second_reference_is_link_with_no_target_item():
    fx = _thes_fixture()
    cache = _planning()
    d1 = references.decide_reference(fx["C"], fx["target"], _spec(fx), cache)
    d2 = references.decide_reference(fx["C"], fx["target"], _spec(fx), cache)
    assert d1.action == ReferenceAction.CREATE
    assert d2.action == ReferenceAction.LINK
    # The placeholder never leaks as a target item.
    assert d2.target_item is None
    # Primed with exactly what Move's CREATE arm caches: the new ancestor + leaf.
    assert references.is_planned_create(cache["p"])
    assert references.is_planned_create(cache["c"])
    assert cache["p"].planned_by == "c" and cache["c"].planned_by == "c"


def test_unmarked_cache_is_unchanged_move_semantics():
    """Move's cache is never marked: a decide-only pass (Move's reversal walk
    decides everything before applying) must still yield CREATE, CREATE and
    must not put anything in the cache."""
    fx = _thes_fixture()
    cache: dict = {}
    d1 = references.decide_reference(fx["C"], fx["target"], _spec(fx), cache)
    d2 = references.decide_reference(fx["C"], fx["target"], _spec(fx), cache)
    assert (d1.action, d2.action) == (ReferenceAction.CREATE, ReferenceAction.CREATE)
    assert cache == {}


def test_negative_control_distinct_items_both_create():
    fx = _thes_fixture()
    cache = _planning()
    d1 = references.decide_reference(fx["C"], fx["target"], _spec(fx), cache)
    d2 = references.decide_reference(fx["N"], fx["target"], _spec(fx), cache)
    assert (d1.action, d2.action) == (ReferenceAction.CREATE, ReferenceAction.CREATE)


def test_existing_ancestor_is_not_planned():
    """Move reuses an ancestor already in the target WITHOUT caching it, so the
    planning cache must not record it either (a later direct reference to it
    must re-decide against the target, as in Move)."""
    fx = _thes_fixture()
    tgt_p = t116._Item("p", "parent")
    fx["tgt_list"].PossibilitiesOS = [tgt_p]
    cache = _planning()
    d = references.decide_reference(fx["C"], fx["target"], _spec(fx), cache)
    assert d.action == ReferenceAction.CREATE
    assert "p" not in cache
    assert references.is_planned_create(cache["c"])


def test_real_cached_object_still_links_to_it():
    fx = _thes_fixture()
    real = object()
    cache = _planning()
    cache["c"] = real
    d = references.decide_reference(fx["C"], fx["target"], _spec(fx), cache)
    assert d.action == ReferenceAction.LINK and d.target_item is real


# ============================================================================
# Thesaurus: two senses sharing an item -- Preview rows == Move rows
# ============================================================================

def _fake_move_apply(refs, decision, target, owner_obj, spec, cache, *a, **k):
    """Stand-in for `apply_reference` (needs a live LCM factory for CREATE):
    reproduces exactly its cache semantics -- each chain member is reused from
    the cache or the target list, else created, added to the list and
    cached."""
    if decision.action == ReferenceAction.LINK:
        return decision.target_item, True
    if decision.action != ReferenceAction.CREATE:
        return decision.target_item, True
    target_list = spec.target_list_path(target)
    created = None
    for anc in decision.ancestors_to_create:
        g = references._guid_str(anc)
        existing = cache.get(g) or references._find_in_possibility_list(target_list, g)
        if existing is None:
            existing = t116._Item(g, references._item_label(anc))
            if created is None:
                target_list.PossibilitiesOS.append(existing)
            else:
                created.SubPossibilitiesOS.append(existing)
            cache[g] = existing
        created = existing
    return created, True


def _two_senses(fx, extra=()):
    return [t116._Sense("s1", thesaurus_items=[fx["C"]]),
            t116._Sense("s2", thesaurus_items=[fx["C"], *extra])]


def test_thesaurus_preview_matches_move_for_shared_item(monkeypatch):
    # Preview (planning cache, no writes).
    fx = _thes_fixture()
    cache = _planning()
    preview_rows = []
    for sense in _two_senses(fx, extra=[fx["C3"], fx["P"]]):
        preview_rows += _actions(categories._resolve_sense_thesaurus_items(
            sense, None, fx["target"], cache, [], tag=None))
    assert fx["tgt_list"].PossibilitiesOS == []  # Preview wrote nothing

    # Move (fresh fixture, unmarked cache, emulated apply_reference).
    monkeypatch.setattr(categories, "_call_apply_reference", _fake_move_apply)
    fx_m = _thes_fixture()
    move_cache: dict = {}
    move_rows = []
    for sense in _two_senses(fx_m, extra=[fx_m["C3"], fx_m["P"]]):
        move_rows += _actions(categories._resolve_sense_thesaurus_items(
            sense, t116._NewSense(), fx_m["target"], move_cache, [], tag=None))

    assert preview_rows == move_rows == [
        ("s1", ReferenceAction.CREATE, "c", (("parent", "p"),)),
        ("s2", ReferenceAction.LINK, "c", ()),
        # Sibling under the parent the first CREATE already pulled in:
        # neither mode lists P again.
        ("s2", ReferenceAction.CREATE, "c3", ()),
        # Direct reference to the planned/created ancestor.
        ("s2", ReferenceAction.LINK, "p", ()),
    ]
    # Move created exactly one P and one C (and one C3).
    assert [i.guid for i in fx_m["tgt_list"].PossibilitiesOS] == ["p"]
    assert [i.guid for i in fx_m["tgt_list"].PossibilitiesOS[0].SubPossibilitiesOS] == [
        "c", "c3"]


# ============================================================================
# Pictures: two senses sharing an image file -- run-wide dedup
# ============================================================================

def _picture_senses(src_linked, same_content=True):
    a = t029._write(os.path.join(src_linked, "Pictures", "shared.jpg"))
    b = a if same_content else t029._write(
        os.path.join(src_linked, "Pictures", "other.jpg"), data=b"OTHER")
    s1 = t029._Sense("s1", pictures=[t029._Picture(
        "p1", caption={1: "one"},
        file=t029._CmFile(internal="Pictures/x.jpg", abspath=a))])
    s2 = t029._Sense("s2", pictures=[t029._Picture(
        "p2", caption={1: "two"},
        file=t029._CmFile(internal="Pictures/y.jpg", abspath=b))])
    return s1, s2


def test_pictures_preview_dedups_across_senses_like_move(tmp_path):
    ctx, tgt_senses, src_linked, tgt_linked = t029._build(tmp_path)
    s1, s2 = _picture_senses(src_linked)
    cache = _planning()
    preview = (pictures.plan_sense_picture_decisions(s1, ctx, cache, [])
               + pictures.plan_sense_picture_decisions(s2, ctx, cache, []))
    assert [d.action for d in preview] == [ReferenceAction.CREATE, ReferenceAction.LINK]
    assert tgt_senses.copy_count == 0  # Preview copied nothing

    move_cache: dict = {}
    for src in (s1, s2):
        pictures.reproduce_sense_pictures(
            src, t029._Sense("t-" + src.guid), ctx, None, move_cache, [])
    assert tgt_senses.copy_count == 1  # Move copied the shared image once


def test_pictures_negative_control_distinct_files_two_creates(tmp_path):
    ctx, tgt_senses, src_linked, _ = t029._build(tmp_path)
    s1, s2 = _picture_senses(src_linked, same_content=False)
    cache = _planning()
    preview = (pictures.plan_sense_picture_decisions(s1, ctx, cache, [])
               + pictures.plan_sense_picture_decisions(s2, ctx, cache, []))
    assert [d.action for d in preview] == [ReferenceAction.CREATE, ReferenceAction.CREATE]
    for src in (s1, s2):
        pictures.reproduce_sense_pictures(
            src, t029._Sense("t-" + src.guid), ctx, None, {}, [])
    assert tgt_senses.copy_count == 2


def test_pictures_without_cache_dict_still_plans(tmp_path):
    ctx, _, src_linked, _ = t029._build(tmp_path)
    s1, _ = _picture_senses(src_linked)
    assert [d.action for d in pictures.plan_sense_picture_decisions(
        s1, ctx, None, [])] == [ReferenceAction.CREATE]


# ============================================================================
# The Preview entry walk: one entry, two senses sharing thesaurus item + image
# ============================================================================

class _CombinedTarget(t116._Target):
    def __init__(self, linked, possibility_lists):
        super().__init__(possibility_lists=possibility_lists)
        self._linked = linked

    def GetLinkedFilesDir(self):
        return self._linked


class _Src:
    def __init__(self, linked):
        self._linked = linked

    def GetLinkedFilesDir(self):
        return self._linked


def test_preview_entry_walk_create_then_link_for_both(tmp_path):
    fx = _thes_fixture()
    src_linked = str(tmp_path / "src" / "LinkedFiles")
    tgt_linked = str(tmp_path / "tgt" / "LinkedFiles")
    os.makedirs(tgt_linked, exist_ok=True)
    pic_s1, pic_s2 = _picture_senses(src_linked)
    senses = []
    for guid, pic_sense in (("s1", pic_s1), ("s2", pic_s2)):
        s = t116._Sense(guid, thesaurus_items=[fx["C"]])
        s.PicturesOS = list(pic_sense.PicturesOS)
        senses.append(s)
    entry = t116._Entry("e1", senses)
    ctx = t116._Ctx()
    ctx.source_handle = _Src(src_linked)
    ctx.target_handle = _CombinedTarget(tgt_linked, fx["target"].possibility_lists)
    ctx._resolver_cache = _planning()

    records = categories._plan_entry_reference_decisions(
        entry, ctx, ctx.target_handle)
    rows = [(r.owner_guid, r.field_name, r.action) for r in records
            if r.field_name in ("ThesaurusItemsRC", "PicturesOS")]
    assert rows == [
        ("s1", "ThesaurusItemsRC", ReferenceAction.CREATE),
        ("s1", "PicturesOS", ReferenceAction.CREATE),
        ("s2", "ThesaurusItemsRC", ReferenceAction.LINK),
        ("s2", "PicturesOS", ReferenceAction.LINK),
    ]
    assert not os.listdir(tgt_linked)  # nothing copied


def test_build_run_plan_marks_its_cache():
    """The one preview.py hook: `build_run_plan`'s cache is a planning cache.
    Asserted on source text so this stays host-free."""
    import inspect
    from gramtrans.Lib import preview
    src = inspect.getsource(preview.build_run_plan)
    assert "_mark_planning_cache(_resolver_cache)" in src


# ============================================================================
# Sweep sibling: 028 MsEnv POS / inflection-class Preview twins
# ============================================================================

def test_msenv_pos_second_allomorph_is_link_like_move():
    target, factory = t028._make_target(pos=[])
    cache = _planning()
    rows = []
    for allo in ("a", "b"):
        recs = owned._plan_moaffix_msenv_decisions(
            t028._FakeAffixAllomorph(allo, msenv_pos=t028._FakePOS("pos-abs")),
            t028._FakeCtx(target), cache, [])
        rows += [r.action for r in recs if r.field_name == "MsEnvPartOfSpeechRA"]
    assert rows == [ReferenceAction.CREATE, ReferenceAction.LINK]
    assert factory.create_calls == []  # Preview created nothing

    # Negative control: a different absent POS is still CREATE.
    recs = owned._plan_moaffix_msenv_decisions(
        t028._FakeAffixAllomorph("c", msenv_pos=t028._FakePOS("pos-other")),
        t028._FakeCtx(target), cache, [])
    assert [r.action for r in recs if r.field_name == "MsEnvPartOfSpeechRA"] == [
        ReferenceAction.CREATE]


def test_infl_class_second_allomorph_is_link_like_move():
    tgt_pos = t028._FakePOS("pos-p")
    target, _ = t028._make_target(pos=[tgt_pos], with_factory=False,
                                  infl_class_factory=True)
    cache = _planning()
    rows = []
    for allo in ("a", "b"):
        recs = owned._plan_moaffix_msenv_decisions(
            t028._FakeAffixAllomorph(allo, inflection_classes=[
                t028._FakeInflClass("ic-new", owner=t028._FakePOS("pos-p"))]),
            t028._FakeCtx(target), cache, [])
        rows += [r.action for r in recs if r.field_name == "InflectionClassesRC"]
    assert rows == [ReferenceAction.CREATE, ReferenceAction.LINK]


@pytest.mark.parametrize("fn", ["_plan_msenv_pos_ra", "_plan_inflection_classes_rc"])
def test_msenv_twins_keep_three_arg_signature(fn):
    """`resolver_cache` is an optional trailing kwarg: legacy 3-arg calls
    still plan (with call-local dedup)."""
    target, _ = t028._make_target(pos=[])
    getattr(owned, fn)(
        t028._FakeAffixAllomorph("a", msenv_pos=t028._FakePOS("pos-abs")),
        t028._FakeCtx(target), [])
