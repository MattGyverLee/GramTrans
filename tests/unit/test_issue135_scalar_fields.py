"""Issue #135 -- text fields flexicon's GetSyncableProperties omits are copied
GramTrans-side (`Lib/scalar_fields.py`), WS-mapped, never silent.  Host-free."""
from __future__ import annotations

from gramtrans.Lib.scalar_fields import (
    MULTISTRING_FIELDS, TSSTRING_FIELDS, copy_supplemental_fields)


class _Ts:
    def __init__(self, text):
        self.Text = text


class _MS:
    def __init__(self, data=None, drop=False):
        self.d = dict(data or {})
        self.drop = drop

    def get_String(self, h):
        return _Ts(self.d.get(h, ""))

    def set_String(self, h, v):
        if not self.drop:
            self.d[h] = v


class _WS:
    def __init__(self, i, h):
        self.Id, self.Handle = i, h


class _Proj:
    def __init__(self, wss):
        self.WritingSystems = type("W", (), {"GetAll": lambda s: wss})()
        self.Cache = type("C", (), {"DefaultVernWs": 1})()


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


SRC = _Proj([_WS("en", 1), _WS("ko", 2)])
TGT = _Proj([_WS("en", 10), _WS("ko-x", 20)])


def test_table_covers_issue_fields():
    assert MULTISTRING_FIELDS["LexSense"][1] == ("AnthroNote", "UsageNote")
    assert MULTISTRING_FIELDS["LexEntry"][1] == ("SummaryDefinition", "Restrictions")
    assert MULTISTRING_FIELDS["LexEtymology"][1] == ("Note", "PrecComment")
    assert MULTISTRING_FIELDS["Text"][1] == ("Source",)
    assert TSSTRING_FIELDS["LexPronunciation"][1] == ("CVPattern", "Tone")


def test_multistring_ws_mapped_and_empty_skipped():
    src = _Obj(AnthroNote=_MS({1: "a-en", 2: "a-ko"}), UsageNote=_MS())
    new = _Obj(AnthroNote=_MS(), UsageNote=_MS())
    drops = []
    w = copy_supplemental_fields(
        "LexSense", src, new, source=SRC, target=TGT, ws_map={"ko": "ko-x"},
        dropped=drops)
    assert new.AnthroNote.d == {10: "a-en", 20: "a-ko"}
    assert new.UsageNote.d == {}
    assert sorted(w) == ["AnthroNote@en", "AnthroNote@ko-x"] and drops == []


def test_unmapped_ws_is_dropped_not_silent():
    src = _Obj(SummaryDefinition=_MS({2: "x"}), Restrictions=_MS())
    new = _Obj(SummaryDefinition=_MS(), Restrictions=_MS())
    drops = []
    copy_supplemental_fields("LexEntry", src, new, source=SRC, target=TGT,
                             ws_map={}, dropped=drops, owner_guid="g")
    assert new.SummaryDefinition.d == {}
    assert [(d.owner_kind, d.field_name) for d in drops] == [
        ("LexEntry", "SummaryDefinition")]


def test_readback_failure_is_dropped():
    src = _Obj(Note=_MS({1: "n"}), PrecComment=_MS())
    new = _Obj(Note=_MS(drop=True), PrecComment=_MS())
    drops = []
    copy_supplemental_fields("LexEtymology", src, new, source=SRC, target=TGT,
                             ws_map={}, dropped=drops)
    assert len(drops) == 1 and "read-back" in drops[0].reason


def test_tsstring_pronunciation_fields():
    src = _Obj(CVPattern=_Ts("CVC"), Tone=_Ts(""))
    new = _Obj(CVPattern=_Ts(""), Tone=_Ts(""))
    drops = []
    w = copy_supplemental_fields("LexPronunciation", src, new, source=SRC,
                                 target=TGT, ws_map={}, dropped=drops)
    assert w == ["CVPattern"] and drops == []
    assert new.CVPattern == "CVC" or getattr(new.CVPattern, "Text", None) == "CVC"


def test_slice2_tables():
    from gramtrans.Lib.scalar_fields import VALUE_FIELDS
    assert MULTISTRING_FIELDS["LexReference"][1] == ("Name", "Comment")
    assert MULTISTRING_FIELDS["LexEntryInflType"][1] == ("GlossPrepend", "GlossAppend")
    assert VALUE_FIELDS["MoAlloAdhocProhib"][1] == ("Adjacency", "Disabled")
    assert VALUE_FIELDS["MoMorphAdhocProhib"][1] == ("Adjacency", "Disabled")


def test_lex_reference_name_comment_ws_mapped():
    src = _Obj(Name=_MS({1: "Calendar", 2: "Cal-ko"}), Comment=_MS({1: "c"}))
    new = _Obj(Name=_MS(), Comment=_MS())
    drops = []
    w = copy_supplemental_fields("LexReference", src, new, source=SRC, target=TGT,
                                 ws_map={"ko": "ko-x"}, dropped=drops)
    assert new.Name.d == {10: "Calendar", 20: "Cal-ko"}
    assert new.Comment.d == {10: "c"} and drops == []
    assert len(w) == 3


def test_infl_type_glosses_unmapped_ws_dropped():
    src = _Obj(GlossPrepend=_MS({2: "pre"}), GlossAppend=_MS({1: "app"}))
    new = _Obj(GlossPrepend=_MS(), GlossAppend=_MS())
    drops = []
    copy_supplemental_fields("LexEntryInflType", src, new, source=SRC, target=TGT,
                             ws_map={}, dropped=drops)
    assert new.GlossAppend.d == {10: "app"}
    assert [(d.owner_kind, d.field_name) for d in drops] == [
        ("LexEntryInflType", "GlossPrepend")]


def test_adhoc_adjacency_disabled_copied_and_defaults_untouched():
    src = _Obj(Adjacency=2, Disabled=True)
    new = _Obj(Adjacency=0, Disabled=False)
    drops = []
    w = copy_supplemental_fields("MoAlloAdhocProhib", src, new, source=SRC,
                                 target=TGT, ws_map={}, dropped=drops)
    assert (new.Adjacency, new.Disabled) == (2, True)
    assert w == ["Adjacency", "Disabled"] and drops == []
    same = _Obj(Adjacency=0, Disabled=False)
    assert copy_supplemental_fields(
        "MoMorphAdhocProhib", _Obj(Adjacency=0, Disabled=False), same,
        source=SRC, target=TGT, ws_map={}, dropped=drops) == []


def test_adhoc_readback_mismatch_dropped():
    class Stuck:
        Adjacency = 0
        Disabled = False

        def __setattr__(self, k, v):
            pass
    drops = []
    copy_supplemental_fields("MoAlloAdhocProhib", _Obj(Adjacency=3, Disabled=False),
                             Stuck(), source=SRC, target=TGT, ws_map={}, dropped=drops)
    assert len(drops) == 1 and drops[0].field_name == "Adjacency"
    assert "read-back" in drops[0].reason


def test_unknown_class_noop():
    assert copy_supplemental_fields("Nope", _Obj(), _Obj(), source=SRC,
                                    target=TGT, ws_map={}, dropped=[]) == []


def test_slice3_tables():
    from gramtrans.Lib.scalar_fields import VALUE_FIELDS
    for k in ("FsFeatDefn", "FsSymFeatVal"):
        assert MULTISTRING_FIELDS[k][1] == ("GlossAbbreviation", "RightGlossSep")
    assert VALUE_FIELDS["FsFeatDefn"][1] == ("ShowInGloss", "DisplayToRightOfValues")
    assert VALUE_FIELDS["FsSymFeatVal"][1] == ("ShowInGloss",)


def test_fs_feat_defn_gloss_fields_copied_ws_mapped():
    src = _Obj(GlossAbbreviation=_MS({1: "nom", 2: "nom-ko"}),
               RightGlossSep=_MS({1: "."}), ShowInGloss=True,
               DisplayToRightOfValues=True)
    new = _Obj(GlossAbbreviation=_MS(), RightGlossSep=_MS(),
               ShowInGloss=False, DisplayToRightOfValues=False)
    drops = []
    w = copy_supplemental_fields("FsFeatDefn", src, new, source=SRC, target=TGT,
                                 ws_map={"ko": "ko-x"}, dropped=drops)
    assert new.GlossAbbreviation.d == {10: "nom", 20: "nom-ko"}
    assert new.RightGlossSep.d == {10: "."}
    assert new.ShowInGloss is True and new.DisplayToRightOfValues is True
    assert drops == [] and "ShowInGloss" in w


def test_fs_sym_feat_val_unmapped_ws_dropped_and_defaults_untouched():
    src = _Obj(GlossAbbreviation=_MS({2: "x"}), RightGlossSep=_MS(),
               ShowInGloss=False)
    new = _Obj(GlossAbbreviation=_MS(), RightGlossSep=_MS(), ShowInGloss=False)
    drops = []
    w = copy_supplemental_fields("FsSymFeatVal", src, new, source=SRC, target=TGT,
                                 ws_map={}, dropped=drops)
    assert [(d.owner_kind, d.field_name) for d in drops] == [
        ("FsSymFeatVal", "GlossAbbreviation")]
    assert w == []
