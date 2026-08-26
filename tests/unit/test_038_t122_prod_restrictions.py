"""Feature 038 T122: `CmPossibility` is nineteen lists, and one of them is ours.

WHAT T115 MEASURED, AND WHY THE ROW WAS NEVER THE UNIT OF WORK. The census row
reads -308 / -398 / -335. That is a GROSS starter basis: 302 objects per pair
are canonical FLEx starter lists present identically on both sides. The real
loss is `difference_raw` -- **-6 / -96 / -33** -- and the per-list deltas sum to
it exactly on all three pairs, which is what makes the attribution a
measurement rather than a story:

    ejagham  GenreList -6
    ngoreme  Scripture.NoteCategories -115, CheckLists -5, GenreList -3,
             DialectLabels -2, Status -1, MoMorphData.ProdRestrict -1;
             surplus ChartMarkers +30, ExtendedNoteTypes +1
    mbugwe   LexDb.Languages -15, ChartMarkers -10, GenreList -5,
             ProdRestrict -3, ConstChartTempl -1; surplus ExtendedNoteTypes +1

Exactly ONE of those lists is unambiguously grammatical and inside this
feature's Assumptions: `MoMorphData.ProdRestrict`, productivity restrictions,
1 and 3 objects. The rest are Scripture notes, dialect labels, genres and
discourse-chart furniture. Closing them here by class name would be the T023b
defect in a new place, so this task takes the one list and rules on the others
rather than sweeping them.

NOT `IPartOfSpeech.ExceptionFeaturesOC`. That is the EXCEPTION_FEATURES
category and it is a REFERENCE collection of `IFsSymFeatVal`. This is a
`CmPossibilityList` of `CmPossibility`. `categories.py` already documents that
flexicon's `InflectionClassGetAll()` / `InflectionClassCreate()` read and write
THIS list by mistake when they mean inflection classes -- which is precisely
why GramTrans reaches it directly instead of through that wrapper.

Host-free: duck fakes only.
"""
from __future__ import annotations

import inspect
import types

from gramtrans.Lib import categories


class _AddList(list):
    def Add(self, item):  # noqa: N802
        self.append(item)


class _MultiString:
    def __init__(self, text=""):
        self._v = {1: text} if text else {}

    def get_String(self, h):  # noqa: N802
        return self._v.get(h, "")

    def set_String(self, h, v):  # noqa: N802
        self._v[h] = v


class _Poss:
    def __init__(self, guid, name=""):
        self.guid = guid
        self.Name = _MultiString(name)
        self.Abbreviation = _MultiString()
        self.Description = _MultiString()


class _PossList:
    def __init__(self, guid="list", items=()):
        self.guid = guid
        self.PossibilitiesOS = _AddList(items)


class _WS:
    def __init__(self, handle, ws_id):
        self.Handle = handle
        self.Id = ws_id


class _Handle:
    def __init__(self, prod_list=None, has_morph_data=True):
        morph = types.SimpleNamespace(ProdRestrictOA=prod_list) \
            if has_morph_data else None
        self.Cache = types.SimpleNamespace(
            LangProject=types.SimpleNamespace(MorphologicalDataOA=morph))
        self.WritingSystems = types.SimpleNamespace(
            GetAll=lambda: [_WS(1, "en")])


def _ctx(source):
    return types.SimpleNamespace(source_handle=source, _run_plan=None)


def _fake_create(monkeypatch):
    seen = []

    def _fake(factory_iface, owner, guid_str, target):
        p = _Poss(guid_str)
        owner.Add(p)
        seen.append(guid_str)
        return p, True

    monkeypatch.setattr(categories, "_create_with_guid", _fake)
    monkeypatch.setattr(categories, "ICmPossibilityFactory_ref", lambda: object())
    return seen


def test_productivity_restrictions_transfer(monkeypatch):
    """The one list this feature owns: 1 object on ngoreme, 3 on mbugwe."""
    seen = _fake_create(monkeypatch)
    src = _Handle(_PossList(items=[_Poss("pr1", "Ideophone"),
                                   _Poss("pr2", "Borrowed")]))
    tgt_list = _PossList()
    tgt = _Handle(tgt_list)

    skips = categories._wire_prod_restrictions(_ctx(src), tgt)

    assert skips == []
    assert [p.guid for p in tgt_list.PossibilitiesOS] == ["pr1", "pr2"]
    assert seen == ["pr1", "pr2"]          # GUID-preserved


def test_is_idempotent(monkeypatch):
    _fake_create(monkeypatch)
    src = _Handle(_PossList(items=[_Poss("pr1", "Ideophone")]))
    tgt_list = _PossList()
    tgt = _Handle(tgt_list)
    ctx = _ctx(src)

    categories._wire_prod_restrictions(ctx, tgt)
    categories._wire_prod_restrictions(ctx, tgt)

    assert [p.guid for p in tgt_list.PossibilitiesOS] == ["pr1"]


def test_an_already_present_item_is_left_alone(monkeypatch):
    seen = _fake_create(monkeypatch)
    src = _Handle(_PossList(items=[_Poss("pr1"), _Poss("pr2")]))
    tgt_list = _PossList(items=[_Poss("pr1")])
    tgt = _Handle(tgt_list)

    categories._wire_prod_restrictions(_ctx(src), tgt)

    assert seen == ["pr2"]
    assert [p.guid for p in tgt_list.PossibilitiesOS] == ["pr1", "pr2"]


def test_an_empty_source_list_is_a_no_op(monkeypatch):
    _fake_create(monkeypatch)
    src = _Handle(_PossList())
    tgt = _Handle(_PossList())
    assert categories._wire_prod_restrictions(_ctx(src), tgt) == []


def test_a_missing_target_list_is_reported_not_swallowed(monkeypatch):
    """The source HAS restrictions, so a destination with nowhere to put them
    is a real loss. Never-silent (SC-010)."""
    _fake_create(monkeypatch)
    src = _Handle(_PossList(items=[_Poss("pr1"), _Poss("pr2")]))
    tgt = _Handle(None)

    skips = categories._wire_prod_restrictions(_ctx(src), tgt)

    assert len(skips) == 1
    assert "ProdRestrictOA" in skips[0].detail
    assert "2" in skips[0].detail          # says HOW MANY were lost


def test_a_missing_source_list_is_silent(monkeypatch):
    """No source data is not a loss."""
    _fake_create(monkeypatch)
    src = _Handle(None)
    tgt = _Handle(_PossList())
    assert categories._wire_prod_restrictions(_ctx(src), tgt) == []


def test_a_failed_create_is_reported(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("no Create(Guid)")
    monkeypatch.setattr(categories, "_create_with_guid", _boom)
    monkeypatch.setattr(categories, "ICmPossibilityFactory_ref",
                        lambda: object())
    src = _Handle(_PossList(items=[_Poss("pr1")]))
    tgt = _Handle(_PossList())

    skips = categories._wire_prod_restrictions(_ctx(src), tgt)
    assert len(skips) == 1
    assert skips[0].source_guid == "pr1"


# --------------------------------------------------------------------------
# Scope: the eighteen lists this must NOT sweep
# --------------------------------------------------------------------------

def test_only_the_prod_restrict_list_is_touched():
    """The scope guard. A helper that walked `CmPossibility` generically -- or
    reached any other possibility list by name -- would be closing a
    polymorphic bucket, which is the T023b defect this task was warned about
    by name."""
    body = inspect.getsource(categories._wire_prod_restrictions)
    assert "ProdRestrictOA" in body
    for other in ("NoteCategories", "GenreList", "ChartMarkers", "CheckLists",
                  "DialectLabels", "ConstChartTempl", "LanguagesOA"):
        assert other not in body.split('"""')[2], other


def test_it_does_not_go_through_the_flexicon_inflection_class_wrapper():
    """flexicon's InflectionClassGetAll()/InflectionClassCreate() read and
    write ProdRestrictOA.PossibilitiesOS when they mean inflection classes --
    documented in this module as a flexicon-side defect. Using them here would
    inherit it."""
    # Split past the docstring: both names appear THERE on purpose, saying why
    # they are not used. The claim is about the code.
    code = inspect.getsource(categories._wire_prod_restrictions).split('"""')[2]
    assert "InflectionClassGetAll" not in code
    assert "InflectionClassCreate" not in code


def test_the_subpass_runs_it():
    body = inspect.getsource(categories._run_171_subpass)
    assert "_wire_prod_restrictions" in body


def test_names_are_copied_ws_mapped():
    body = inspect.getsource(categories._wire_prod_restrictions)
    assert "_copy_multistrings_ws_mapped" in body
    assert "Abbreviation" in body
