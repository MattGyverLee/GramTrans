"""Issue #131: the CmSemanticDomain create path copied no Name/Abbreviation/
Description, so a domain created by a transfer arrived nameless.

AUDIT (issue acceptance 1): nothing else writes that text for a NEWLY created
domain. `semantic_domains_plan_action` emits a bare create PlannedAction for an
absent GUID and a `write_mode="merge"` overwrite ONLY for a GUID already present
in the target; the create executor ran `factory.Create`, an owner-add and
`apply_carrier_b` (Description tag line only). `test_trace_*` below pins the
trace: with the copy neutralised, the new object carries no Name/Abbreviation.

Host-free: duck fakes plus an offline `SIL.LCModel`/`System` stub.
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import GrammarCategory, PlannedAction, RunContext
from gramtrans.Lib.residue import ImportResidueTag

_TAG = ImportResidueTag.make(
    run_id="GT-20261031-000000", source_project_name="Src",
    timestamp="2026-10-31T00:00:00")

# WS id -> handle; source and target handles deliberately differ.
SRC_WS = {"en": 11, "fr": 12, "es": 13}
TGT_WS = {"en": 101, "fr": 102, "es": 103, "de": 104}


class _TS:
    def __init__(self, text=""):
        self.Text = text


class _MS:
    def __init__(self, data=None):
        self._d = dict(data or {})

    def get_String(self, h):
        return _TS(self._d.get(h, ""))

    def set_String(self, h, text):
        self._d[h] = text


class _Seq:
    def __init__(self, items=()):
        self._items = list(items)

    def Add(self, o):
        self._items.append(o)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


class _SD:
    def __init__(self, guid, name=None, abbr=None, desc=None):
        self.Guid = guid
        self.guid = guid
        self.ClassName = "CmSemanticDomain"
        self.OwningFlid = 8008
        self.Owner = None
        self.SubPossibilitiesOS = _Seq()
        self.Name = _MS(name)
        self.Abbreviation = _MS(abbr)
        self.Description = _MS(desc)


class _SDList:
    def __init__(self, items=()):
        self.PossibilitiesOS = _Seq(items)


def _ws_list(m):
    return [types.SimpleNamespace(Id=i, Handle=h) for i, h in m.items()]


class _Project:
    def __init__(self, ws_map, items=()):
        self.WritingSystems = types.SimpleNamespace(GetAll=lambda: _ws_list(ws_map))
        self.Cache = types.SimpleNamespace(
            LangProject=types.SimpleNamespace(SemanticDomainListOA=_SDList(items)),
            DefaultAnalWs=TGT_WS["en"])
        self.factory_calls = []

    def GetFactory(self, iface):
        outer = self

        class _F:
            def Create(self, guid):
                outer.factory_calls.append(guid)
                return _SD(guid)
        return _F()


def _ctx(src, tgt):
    return RunContext(
        source_handle=src, source_project_name="Src", source_project_path="/s",
        target_handle=tgt, target_project_name="Tgt", target_project_path="/t",
        run_id="GT-20261031-000000", started_at="2026-10-31T00:00:00")


def _act(guid):
    return PlannedAction(category=GrammarCategory.SEMANTIC_DOMAINS,
                         source_guid=guid, intended_target_guid=guid, summary="t")


@pytest.fixture
def _stub_lcm():
    lcm = types.ModuleType("SIL.LCModel")
    for n in ("ICmObject", "ICmPossibility", "ICmPossibilityList",
              "ICmSemanticDomainFactory"):
        setattr(lcm, n, (lambda raw: raw))
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    orig_lcm = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = lcm
    sysmod = types.ModuleType("System")
    sysmod.Guid = type("G", (), {"Parse": staticmethod(lambda s: s)})
    orig_sys = sys.modules.get("System")
    sys.modules["System"] = sysmod
    yield
    for k, o in (("SIL.LCModel", orig_lcm), ("System", orig_sys)):
        if o is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = o


GUID = "aaaaaaaa-0000-0000-0000-000000000131"


def _text(ms, ws_id):
    return ms.get_String(TGT_WS[ws_id]).Text


def test_trace_create_alone_writes_no_text_so_the_copy_is_the_only_writer(_stub_lcm):
    """Audit trace: with the copy step neutralised, the new object carries no
    Name/Abbreviation and none of the source Description -- no other pass in
    the executor supplies them."""
    sd = _SD(GUID, name={11: "Fish"}, abbr={11: "f"}, desc={11: "swims"})
    src = _Project(SRC_WS, [sd])
    tgt = _Project(TGT_WS)
    orig = categories._copy_multistrings_ws_mapped
    categories._copy_multistrings_ws_mapped = lambda *a, **k: None
    try:
        new = categories.semantic_domains_execute_action(
            _act(GUID), _ctx(src, tgt), {}, _TAG)
    finally:
        categories._copy_multistrings_ws_mapped = orig
    assert new.Name._d == {} and new.Abbreviation._d == {}
    assert "swims" not in _text(new.Description, "en")


def test_create_copies_all_three_fields_across_multiple_ws(_stub_lcm):
    sd = _SD(GUID,
             name={11: "Fish", 12: "Poisson"},
             abbr={11: "fsh", 12: "poi", 13: "pez"},
             desc={11: "Creatures that swim", 13: "Criaturas"})
    src = _Project(SRC_WS, [sd])
    tgt = _Project(TGT_WS)
    new = categories.semantic_domains_execute_action(
        _act(GUID), _ctx(src, tgt), {}, _TAG)
    assert tgt.factory_calls == [GUID]
    assert _text(new.Name, "en") == "Fish"
    assert _text(new.Name, "fr") == "Poisson"
    assert _text(new.Name, "es") == ""
    assert [_text(new.Abbreviation, w) for w in ("en", "fr", "es")] == [
        "fsh", "poi", "pez"]
    en_desc = _text(new.Description, "en")
    # source text first, carrier-B audit line last
    assert en_desc.startswith("Creatures that swim")
    assert "[GT-Tag]" in en_desc
    assert _text(new.Description, "es") == "Criaturas"
    assert new in list(tgt.Cache.LangProject.SemanticDomainListOA.PossibilitiesOS)


def test_ws_mapping_redirects_to_the_mapped_target_ws(_stub_lcm):
    sd = _SD(GUID, name={11: "Fish", 12: "Poisson"})
    src = _Project(SRC_WS, [sd])
    tgt = _Project(TGT_WS)
    new = categories.semantic_domains_execute_action(
        _act(GUID), _ctx(src, tgt), {"fr": "de"}, _TAG)
    assert _text(new.Name, "en") == "Fish"
    assert _text(new.Name, "de") == "Poisson"
    assert _text(new.Name, "fr") == ""


def test_ws_without_a_target_counterpart_is_skipped_never_misfiled(_stub_lcm):
    sd = _SD(GUID, name={11: "Fish", 13: "Pez"})
    src = _Project(SRC_WS, [sd])
    tgt = _Project({"en": 101, "fr": 102})   # no es
    new = categories.semantic_domains_execute_action(
        _act(GUID), _ctx(src, tgt), {}, _TAG)
    assert new.Name._d == {101: "Fish"}


def test_empty_source_alternative_never_blanks(_stub_lcm):
    sd = _SD(GUID, name={11: "Fish", 12: ""}, abbr={})
    src = _Project(SRC_WS, [sd])
    tgt = _Project(TGT_WS)
    new = categories.semantic_domains_execute_action(
        _act(GUID), _ctx(src, tgt), {}, _TAG)
    assert new.Name._d == {101: "Fish"}      # fr empty: not written at all
    assert new.Abbreviation._d == {}          # fully empty: nothing written


def test_nested_domain_copies_text_and_nests(_stub_lcm):
    parent_guid = "bbbbbbbb-0000-0000-0000-000000000131"
    parent_src = _SD(parent_guid, name={11: "Parent"})
    child = _SD(GUID, name={11: "Child"})
    child.OwningFlid = categories._CMPOSSIBILITY_SUBPOSSIBILITIES_FLID
    child.Owner = types.SimpleNamespace(Guid=parent_guid)
    parent_src.SubPossibilitiesOS = _Seq([child])
    src = _Project(SRC_WS, [parent_src])
    tgt_parent = _SD(parent_guid, name={101: "Parent"})
    tgt = _Project(TGT_WS, [tgt_parent])
    new = categories.semantic_domains_execute_action(
        _act(GUID), _ctx(src, tgt), {}, _TAG)
    assert list(tgt_parent.SubPossibilitiesOS) == [new]
    assert _text(new.Name, "en") == "Child"


def test_demoted_top_level_branch_also_copies_text(_stub_lcm):
    """Missing target parent: demoted to top level (T123), text still copied --
    this is the second create branch."""
    parent_guid = "cccccccc-0000-0000-0000-000000000131"
    parent_src = _SD(parent_guid, name={11: "Parent"})
    child = _SD(GUID, name={11: "Orphan"}, abbr={11: "o"})
    child.OwningFlid = categories._CMPOSSIBILITY_SUBPOSSIBILITIES_FLID
    child.Owner = types.SimpleNamespace(Guid=parent_guid)
    parent_src.SubPossibilitiesOS = _Seq([child])
    src = _Project(SRC_WS, [parent_src])
    tgt = _Project(TGT_WS)  # parent absent
    new = categories.semantic_domains_execute_action(
        _act(GUID), _ctx(src, tgt), {}, _TAG)
    assert new in list(tgt.Cache.LangProject.SemanticDomainListOA.PossibilitiesOS)
    assert _text(new.Name, "en") == "Orphan"
    assert _text(new.Abbreviation, "en") == "o"


def test_guid_preserving_create_unchanged(_stub_lcm):
    sd = _SD(GUID, name={11: "Fish"})
    src = _Project(SRC_WS, [sd])
    tgt = _Project(TGT_WS)
    new = categories.semantic_domains_execute_action(
        _act(GUID), _ctx(src, tgt), {}, _TAG)
    assert tgt.factory_calls == [GUID]
    assert new.Guid == GUID
