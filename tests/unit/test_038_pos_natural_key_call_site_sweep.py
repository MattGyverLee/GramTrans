"""T094 -- finishing the sweep T032 deferred, and why nothing could test it.

T032 landed `_resolve_target_pos`'s natural-key fallback with `src_pos` and
`source_handle` KEYWORD-ONLY and defaulting to `None`, so that every existing
two-positional caller kept its exact pre-038 GUID-only behaviour and the
fallback could land ahead of a sweep of its callers. T033 then swept four
sites and stopped.

**The remaining sites could not fail, and therefore could not be tested.**
Nothing in the tree could produce a category whose destination GUID differed
from its source GUID: the planner only ever created a POS under the source's
own GUID, so identity always succeeded for every category that was present
at all, and the fallback was dead code at those sites by construction.

T091 is the change that ends that invariant. It makes the planner REUSE a
same-named destination category instead of duplicating it -- and the instant
it does, the reused category's destination GUID is NOT its source GUID.
Measured on `Ngoreme FLEx`: 1,848 MSAs pointing at the reused `Noun` and
`Verb` lost their entire morphosyntactic analysis, `MoStemMsa` 1951 -> 164,
`MoInflAffMsa` 134 -> 36, `MoDerivAffMsa` 3 -> 0,
`MoUnclassifiedAffixMsa` 2 -> 0.

So every test in this file describes an input the tree **could not produce**
before T091: a source category that exists in the destination under a
DIFFERENT GUID and the SAME name. A deferred sweep with no producer is not
latent; it is invisible.

The four production sites swept here, and the one structural pin that covers
the whole set:

* `resolve_or_create_target_pos` -- would CREATE a duplicate of a category
  the planner had already decided to reuse.
* `can_create_inflection_class` -- the Preview twin (G6). Would answer
  REPORT_DROPPED for exactly the classes its executor twin goes on to create.
* `resolve_or_create_inflection_class` -- would abandon a class whose owning
  category was reused.
* `_create_msa_for_closure` -- **the 1,848.** Its `_pos_guid_of` helper read
  the source POS reference and THREW THE OBJECT AWAY, keeping only the GUID,
  which is precisely the value the natural key cannot use.
* `owned._resolve_target_pos_by_guid` and its three callers.

`test_no_production_call_site_is_two_positional` is the pin that makes the
whole sweep, including the sites no host-free fake can reach, a fact about
the tree rather than a claim in a commit message.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import types
from types import SimpleNamespace

import pytest

from gramtrans.Lib import categories as cat_mod
from gramtrans.Lib import matcher as matcher_mod
from gramtrans.Lib import owned as owned_mod
import gramtrans.Lib.residue as _residue_mod

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src" / "gramtrans" / "Lib"
ROSTER_035 = (
    REPO_ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"
    / "natural-key-identity-roster.json"
)
EXTENSION_038 = (
    REPO_ROOT / "specs" / "038-transfer-fidelity-gaps" / "contracts"
    / "natural-key-roster-extension.json"
)

SRC_ANAL, TGT_ANAL = 302, 402
SRC_VERN, TGT_VERN = 301, 401


# ---------------------------------------------------------------------------
# Fakes -- deliberately duck-typed, so the sweep is exercised host-free
# ---------------------------------------------------------------------------

class _Ts:
    def __init__(self, text):
        self.Text = text


class _MultiString:
    def __init__(self, by_handle):
        self._by_handle = dict(by_handle)

    def get_String(self, ws_handle):
        return _Ts(self._by_handle.get(ws_handle))


class _Pos:
    """A category. `guid` is lowercase because both `categories._guid_str_from`
    and `matcher._guid_text` read the lowercase attribute FIRST."""

    def __init__(self, guid, name=None, ws_handle=None, owner=None):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "PartOfSpeech"
        self.Name = _MultiString({ws_handle: name} if ws_handle else {})
        self.Owner = owner
        self.InflectionClassesOC = _Coll()
        self.StemNamesOC = []


class _Coll(list):
    def Add(self, item):
        self.append(item)


class _InflClass:
    def __init__(self, guid, owner=None, name=None, ws_handle=None):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "MoInflClass"
        self.Owner = owner
        self.Name = _MultiString({ws_handle: name} if ws_handle else {})
        self.SubclassesOC = _Coll()


class _PosAccessor:
    def __init__(self, poses):
        self._poses = list(poses)

    def GetAll(self, recursive=False):
        return list(self._poses)


class _Handle:
    def __init__(self, poses, vern, anal):
        self.POS = _PosAccessor(poses)
        self.Cache = SimpleNamespace(DefaultAnalWs=anal)
        self._vern = vern
        self._anal = anal

    def GetDefaultVernacularWSHandle(self):
        return self._vern

    def GetDefaultAnalysisWSHandle(self):
        return self._anal


class _Ctx:
    def __init__(self, source_handle, target_handle):
        self.source_handle = source_handle
        self.target_handle = target_handle
        self._exec_skips = []
        self._ws_map = None


def _appended_roster(tmp_path):
    base = json.loads(ROSTER_035.read_text(encoding="utf-8"))
    ext = json.loads(EXTENSION_038.read_text(encoding="utf-8"))
    base["entries"] = list(base["entries"]) + list(ext["proposed_entries"])
    path = tmp_path / "natural-key-identity-roster.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return str(path)


@pytest.fixture
def admitted(tmp_path):
    matcher_mod.reset_natural_key_roster_cache(_appended_roster(tmp_path))
    yield
    matcher_mod.reset_natural_key_roster_cache(None)


@pytest.fixture
def guids_are_lowercase_attrs(monkeypatch):
    """`_guid_str_from` host-free, so the duck fakes above are keyable."""
    monkeypatch.setattr(
        cat_mod, "_guid_str_from",
        lambda obj: str(getattr(obj, "guid", "") or "").lower())


def _reused_pair():
    """The input the tree could not produce before T091.

    A source `Noun` and a destination `Noun` that share a NAME and not a GUID
    -- i.e. a category the planner reused rather than duplicated.
    """
    src = _Pos("src-noun", "Noun", SRC_ANAL)
    dst = _Pos("dst-noun", "Noun", TGT_ANAL)
    return src, dst, _Handle([src], SRC_VERN, SRC_ANAL), _Handle(
        [dst], TGT_VERN, TGT_ANAL)


# ---------------------------------------------------------------------------
# The structural pin: the sweep is complete, and stays complete
# ---------------------------------------------------------------------------

_CALL_RE = re.compile(r"_resolve_target_pos(?:_by_guid)?\(")


def _production_call_sites():
    """Every production call to `_resolve_target_pos` (or `owned.py`'s
    `_resolve_target_pos_by_guid` wrapper), with its balanced argument text.

    Skips the two `def` lines. Reading the source rather than the call graph is
    the point: a site that cannot be reached by any host-free fake -- and
    `_create_msa_for_closure`'s is nearly one -- is still visible here.
    """
    out = []
    for path in sorted(SRC_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for m in _CALL_RE.finditer(text):
            if text[max(0, m.start() - 4):m.start()] == "def ":
                continue
            i, depth = m.end(), 1
            while depth and i < len(text):
                if text[i] == "(":
                    depth += 1
                elif text[i] == ")":
                    depth -= 1
                i += 1
            args = " ".join(text[m.end():i - 1].split())
            line = text[:m.start()].count("\n") + 1
            out.append((f"{path.name}:{line}", args))
    return out


def test_no_production_call_site_is_two_positional():
    """T094's whole claim, as a fact about the tree.

    T032's keyword defaults are a LANDING mechanism, not a design: a caller
    that omits them gets a GUID-only answer, which after T091 means "absent"
    for a category that is present under another identity. T033 swept four
    sites; the five the filing named -- `categories.py` x4 plus `owned.py`'s
    wrapper, which is really three call sites behind one signature -- are
    swept here.

    A NEW two-positional call is the way this defect comes back, and it comes
    back silently, so it is pinned structurally rather than per site.
    """
    unswept = [
        (where, args) for where, args in _production_call_sites()
        if not ("src_pos=" in args and "source_handle=" in args)
    ]
    assert unswept == [], (
        "these production call sites still pass a GUID alone, so they cannot "
        "follow a natural-key identity substitution: %r" % (unswept,))


def test_the_pin_can_see_every_site_the_filing_named():
    """Guard against the pin above passing because it found nothing.

    A regex that stopped matching would make `test_no_production_call_site_
    is_two_positional` vacuously green, which is the failure mode a
    source-reading test actually has.

    T106 WIDENED THE FILE SET, deliberately. `transfer.py` and `preview.py`
    each gained a `_target_pos_for_source_guid` wrapper over
    `categories._resolve_target_pos` -- the same shape `owned.py` already had,
    and for the same reason: five callers in `transfer.py` and three in
    `preview.py` held a SOURCE category GUID and could not follow a T091
    natural-key reuse. Both wrappers pass `src_pos=` AND `source_handle=`, so
    the load-bearing assertion above covers them unchanged; only this guard's
    file set had to move, and it is recorded rather than relaxed.
    """
    sites = dict(_production_call_sites())
    assert len(sites) >= 13, sites
    files = {where.split(":")[0] for where in sites}
    assert files == {"categories.py", "owned.py",
                     "preview.py", "transfer.py"}, files


# ---------------------------------------------------------------------------
# Site 1 -- `resolve_or_create_target_pos` (categories.py, feature 028 R1)
# ---------------------------------------------------------------------------

def test_resolve_or_create_reuses_a_reused_category_instead_of_duplicating(
    admitted, guids_are_lowercase_attrs,
):
    """The duplicate-maker. This path RESOLVES OR CREATES, so a GUID-only
    resolve does not merely lose the reference -- it manufactures a second
    copy of the very category T091 stopped duplicating, from the other end of
    the run."""
    src, dst, source, target = _reused_pair()
    got = cat_mod.resolve_or_create_target_pos(
        _Ctx(source, target), src, {}, "tag")
    assert got is dst


def test_resolve_or_create_does_not_reuse_a_differently_named_category(
    admitted, guids_are_lowercase_attrs, monkeypatch,
):
    """The key is a key, not a wildcard. With no name match and no factory
    obtainable the answer is None -- reported, never guessed."""
    src = _Pos("src-noun", "Noun", SRC_ANAL)
    dst = _Pos("dst-verb", "Verb", TGT_ANAL)
    monkeypatch.setattr(cat_mod, "_get_pos_factory", lambda _t: None)
    got = cat_mod.resolve_or_create_target_pos(
        _Ctx(_Handle([src], SRC_VERN, SRC_ANAL),
             _Handle([dst], TGT_VERN, TGT_ANAL)),
        src, {}, "tag")
    assert got is None


def test_resolve_or_create_still_prefers_identity(
    admitted, guids_are_lowercase_attrs,
):
    """FR-001 at this site: a GUID match wins even when another destination
    category would have matched by name."""
    src = _Pos("shared-guid", "Noun", SRC_ANAL)
    by_guid = _Pos("shared-guid", "something else", TGT_ANAL)
    by_name = _Pos("other-guid", "Noun", TGT_ANAL)
    got = cat_mod.resolve_or_create_target_pos(
        _Ctx(_Handle([src], SRC_VERN, SRC_ANAL),
             _Handle([by_guid, by_name], TGT_VERN, TGT_ANAL)),
        src, {}, "tag")
    assert got is by_guid


# ---------------------------------------------------------------------------
# Site 2 -- `can_create_inflection_class` (the G6 Preview twin)
# ---------------------------------------------------------------------------

@pytest.fixture
def infl_class_factory(monkeypatch):
    """A factory that mints a duck-typed class, so the two inflection-class
    sites are reachable host-free."""
    made: list = []

    class _Factory:
        def Create(self, guid):
            ic = _InflClass(str(guid))
            made.append(ic)
            return ic

    monkeypatch.setattr(
        cat_mod, "_get_inflection_class_factory", lambda _t: _Factory())
    monkeypatch.setattr(cat_mod, "_guid_arg_for_create", lambda g: g)
    monkeypatch.setattr(
        cat_mod, "_find_target_inflection_class", lambda _t, _g: None)
    monkeypatch.setattr(
        cat_mod, "_sync_inflection_class_properties",
        lambda *a, **k: None)
    return made


def test_preview_twin_says_creatable_when_the_owner_was_reused(
    admitted, guids_are_lowercase_attrs, infl_class_factory,
):
    """G6 parity, which is the reason this site is swept at all.

    Its executor twin resolves the owning category by identity THEN by key. A
    predicate that asked identity only would answer REPORT_DROPPED for exactly
    the classes the executor goes on to CREATE -- a preview that understates
    the run.
    """
    src, dst, source, target = _reused_pair()
    src_class = _InflClass("src-class", owner=src, name="Cl 9",
                           ws_handle=SRC_ANAL)
    assert cat_mod.can_create_inflection_class(
        target, src_class, source_handle=source) is True


def test_preview_twin_keeps_its_pre_038_answer_with_no_source_handle(
    admitted, guids_are_lowercase_attrs, infl_class_factory,
):
    """`source_handle` is keyword-only and optional on purpose. A caller with
    no source project must get the old GUID-only answer rather than a
    different one arrived at silently."""
    src, dst, source, target = _reused_pair()
    src_class = _InflClass("src-class", owner=src, name="Cl 9",
                           ws_handle=SRC_ANAL)
    assert cat_mod.can_create_inflection_class(target, src_class) is False


# ---------------------------------------------------------------------------
# Site 3 -- `resolve_or_create_inflection_class`
# ---------------------------------------------------------------------------

def test_inflection_class_lands_under_the_reused_owner(
    admitted, guids_are_lowercase_attrs, infl_class_factory,
):
    """Closure-scoped and never invented (G8/Principle V): the class is
    attached to the DESTINATION category the planner reused, and the source's
    own GUID is not resurrected as a second `Noun`."""
    src, dst, source, target = _reused_pair()
    src_class = _InflClass("src-class", owner=src, name="Cl 9",
                           ws_handle=SRC_ANAL)
    got = cat_mod.resolve_or_create_inflection_class(
        _Ctx(source, target), src_class, {}, "tag")
    assert got is not None
    assert list(dst.InflectionClassesOC) == [got]


def test_inflection_class_is_still_abandoned_when_no_key_matches(
    admitted, guids_are_lowercase_attrs, infl_class_factory,
):
    """The other half of G8: an owning category that is neither present by
    GUID nor matchable by key is not invented, and the class is not created."""
    src = _Pos("src-noun", "Noun", SRC_ANAL)
    dst = _Pos("dst-verb", "Verb", TGT_ANAL)
    src_class = _InflClass("src-class", owner=src, name="Cl 9",
                           ws_handle=SRC_ANAL)
    got = cat_mod.resolve_or_create_inflection_class(
        _Ctx(_Handle([src], SRC_VERN, SRC_ANAL),
             _Handle([dst], TGT_VERN, TGT_ANAL)),
        src_class, {}, "tag")
    assert got is None


# ---------------------------------------------------------------------------
# Site 4 -- `_create_msa_for_closure`. THE 1,848.
# ---------------------------------------------------------------------------

class _Entry:
    def __init__(self, guid):
        self.guid = guid
        self.MorphoSyntaxAnalysesOC = []


class _Sense:
    def __init__(self):
        self.MorphoSyntaxAnalysisRA = None


@pytest.fixture
def msa_host_free(monkeypatch):
    """Enough of `SIL.LCModel` for the MSA closure to run over duck fakes --
    the same shape `test_038_null_pos_msa.py` uses, which is what makes this
    site reachable at all without FieldWorks."""
    fake = types.ModuleType("SIL.LCModel")
    fake.ICmObject = lambda obj: SimpleNamespace(
        Guid=getattr(obj, "guid", ""),
        ClassName=getattr(obj, "ClassName", None),
    )
    fake.ILexEntry = lambda obj: obj
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake
    monkeypatch.setattr(
        cat_mod, "_guid_str_from",
        lambda obj: str(getattr(obj, "guid", "") or "").lower())
    monkeypatch.setattr(cat_mod, "_cast_msa_concrete", lambda obj: obj)
    monkeypatch.setattr(_residue_mod, "apply_residue", lambda *a, **k: None)
    yield
    if original is None:
        sys.modules.pop("SIL.LCModel", None)
    else:
        sys.modules["SIL.LCModel"] = original


@pytest.fixture
def msa_pos_fields(monkeypatch):
    """Records the POS fields the GUID-preserving create was handed -- the
    only place the fix is observable, since a dropped MSA never gets here."""
    calls: list = []

    def _spy(target, new_entry, new_sense, subclass, src_guid, pos_fields):
        calls.append(dict(pos_fields))
        made = SimpleNamespace(guid=src_guid, ClassName=subclass,
                               StratumRA=None, **pos_fields)
        new_entry.MorphoSyntaxAnalysesOC.append(made)
        new_sense.MorphoSyntaxAnalysisRA = made
        return made

    monkeypatch.setattr(cat_mod, "_create_msa_with_guid", _spy)
    return calls


def _msa_target(dst_poses, anal):
    def _boom(*_a, **_k):
        raise AssertionError("the flexicon MSA wrapper must not be reached")

    return SimpleNamespace(
        Cache=SimpleNamespace(DefaultAnalWs=anal, DefaultVernWs=TGT_VERN),
        POS=_PosAccessor(dst_poses),
        Strata=SimpleNamespace(GetAll=lambda: []),
        MSA=SimpleNamespace(CreateStem=_boom, CreateInflAff=_boom,
                            CreateDerivAff=_boom,
                            CreateUnclassifiedAffix=_boom),
        GetDefaultVernacularWSHandle=lambda: TGT_VERN,
        GetDefaultAnalysisWSHandle=lambda: anal,
    )


def _run_msa(src_msa, dst_poses, src_poses, dropped):
    target = _msa_target(dst_poses, TGT_ANAL)
    ctx = SimpleNamespace(
        target_handle=target,
        source_handle=_Handle(src_poses, SRC_VERN, SRC_ANAL),
        _ws_map=None,
    )
    entry = _Entry("entry-guid")
    return cat_mod._create_msa_for_closure(
        src_msa, _Sense(), entry, ctx, None, {},
        dropped=dropped, src_entry=entry)


@pytest.mark.parametrize("subclass", [
    "MoStemMsa", "MoInflAffMsa", "MoUnclassifiedAffixMsa",
])
def test_an_msa_follows_its_category_to_the_reused_destination(
    subclass, admitted, msa_host_free, msa_pos_fields,
):
    """THE 1,848, host-free.

    `MoStemMsa` 1167 + 600 and `MoInflAffMsa` 57 + 24 `dropped_items` records
    on `Ngoreme FLEx`, every one of them a sense losing its part-of-speech
    analysis so that five duplicate category objects could be removed. The
    reference resolves; the MSA is not dropped.
    """
    src, dst, _source, _target = _reused_pair()
    src_msa = SimpleNamespace(guid="msa-guid", ClassName=subclass,
                              PartOfSpeechRA=src, StratumRA=None)
    dropped: list = []

    out = _run_msa(src_msa, [dst], [src], dropped)

    assert out is not None, "the MSA was dropped -- this is the T094 defect"
    assert dropped == []
    assert msa_pos_fields == [{"PartOfSpeechRA": dst}]


def test_a_derivational_msa_follows_both_of_its_categories(
    admitted, msa_host_free, msa_pos_fields,
):
    """`MoDerivAffMsa` 3 -> 0. Both `FromPartOfSpeechRA` and
    `ToPartOfSpeechRA` go through the same resolver, so both were lost."""
    src_from = _Pos("src-verb", "Verb", SRC_ANAL)
    src_to = _Pos("src-noun", "Noun", SRC_ANAL)
    dst_from = _Pos("dst-verb", "Verb", TGT_ANAL)
    dst_to = _Pos("dst-noun", "Noun", TGT_ANAL)
    src_msa = SimpleNamespace(
        guid="msa-guid", ClassName="MoDerivAffMsa",
        FromPartOfSpeechRA=src_from, ToPartOfSpeechRA=src_to, StratumRA=None)
    dropped: list = []

    out = _run_msa(src_msa, [dst_from, dst_to], [src_from, src_to], dropped)

    assert out is not None
    assert dropped == []
    assert msa_pos_fields == [{"FromPartOfSpeechRA": dst_from,
                              "ToPartOfSpeechRA": dst_to}]


def test_an_msa_whose_category_is_genuinely_absent_is_still_reported(
    admitted, msa_host_free, msa_pos_fields,
):
    """The sweep must not turn a real dependency failure into a silent
    success. A destination with no same-named category is still a drop, and
    still a `DroppedItemRecord` naming the class, the field and the GUID
    (Principle I / FR-010)."""
    src = _Pos("src-noun", "Noun", SRC_ANAL)
    dst = _Pos("dst-verb", "Verb", TGT_ANAL)
    src_msa = SimpleNamespace(guid="msa-guid", ClassName="MoInflAffMsa",
                              PartOfSpeechRA=src, StratumRA=None)
    dropped: list = []

    out = _run_msa(src_msa, [dst], [src], dropped)

    assert out is None
    assert len(dropped) == 1
    assert "PartOfSpeechRA" in dropped[0].reason
    assert msa_pos_fields == []


def test_a_null_category_is_still_reproduced_not_keyed(
    admitted, msa_host_free, msa_pos_fields,
):
    """T043b must survive the sweep. A null `PartOfSpeechRA` is a legal FLEx
    state (Category = `<Not Sure>`); the resolver is never consulted for it,
    so the empty slot cannot be answered by keying on some other category."""
    dst = _Pos("dst-noun", "Noun", TGT_ANAL)
    src_msa = SimpleNamespace(guid="msa-guid", ClassName="MoStemMsa",
                              PartOfSpeechRA=None, StratumRA=None)
    dropped: list = []

    out = _run_msa(src_msa, [dst], [], dropped)

    assert out is not None
    assert dropped == []
    assert msa_pos_fields == [{"PartOfSpeechRA": None}]


# ---------------------------------------------------------------------------
# Site 5 -- `owned._resolve_target_pos_by_guid`, one signature, three callers
# ---------------------------------------------------------------------------

def test_owned_wrapper_follows_the_substitution_when_given_the_keywords(
    admitted, guids_are_lowercase_attrs,
):
    """`owned.py`'s wrapper is the fifth site the filing named, and it is
    three call sites behind one signature (`_reproduce_stem_name_ra`,
    `_plan_msenv_pos_ra`, `_plan_stem_name_ra_decision`). The name still says
    "by guid"; after T091 a GUID is no longer sufficient."""
    src, dst, source, target = _reused_pair()
    got = owned_mod._resolve_target_pos_by_guid(
        target, "src-noun", src_pos=src, source_handle=source)
    assert got is dst


def test_owned_wrapper_keeps_the_pre_038_answer_without_them(
    admitted, guids_are_lowercase_attrs,
):
    """The opt-in shape is mirrored deliberately: this module's own unit fakes
    call the wrapper two-positionally and must not change behaviour."""
    src, dst, source, target = _reused_pair()
    assert owned_mod._resolve_target_pos_by_guid(target, "src-noun") is None
