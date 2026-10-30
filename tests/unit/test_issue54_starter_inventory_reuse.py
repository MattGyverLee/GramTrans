"""Issue #54 -- a fresh FLEx project's starter phonology must be REUSED, not
doubled, and reusing it must not lose anything.

A newly created project ships 23 phonemes (`a b d e f g i j k l m n o p r s t
u v w x z` + U+014B) and two `PhNCSegments` (`Consonants`, `Vowels`). Before
feature 038 a phonology transfer matched by GUID only, so every source phoneme
sharing a starter's name was created beside it: 23 + 41 = 64 with 20-21
duplicate names, measured on `Ngoreme Target` and `Ejagham W Target`.

What is pinned here, host-free:

1. **The inventory is not doubled.** Planning a starter-shaped target against
   an overlapping source matches every shared name to its starter (a
   natural-key `PlannedOverwrite`, never an ADD), creates only the rest, and
   never maps two source phonemes onto one starter. U+014B (eng) is included
   because the issue names it.

2. **A key-matched starter `Vowels` gains the source's extra members.** The
   overwrite that reuses it runs BEFORE this run creates phonemes, and its only
   membership carrier (`PhonemeGuids`) is not written by flexicon's base
   `ApplySyncableProperties`. Measured live: `Ejagham W Mini`'s 7-member
   `Vowels` arrived with the starter's 5, losing U+0259 and U+0289.
   `_wire_matched_nc_segments` runs after every create and unions them in --
   add-only, idempotent.

3. **The phantom write is gone.** `PhonemeGuids` no longer reaches the
   per-field UPDATE write, which counted it as "1 field written" on every run.

4. **A matched starter's code list is not doubled either.** The starter `a`
   already owns code `a`; the source `a`'s identically spelled code is not
   added again under its own GUID (measured: 21 of 21 matched phonemes carried
   two `a`-style codes).
"""
from __future__ import annotations

import json
import pathlib
import types

import pytest

from gramtrans.Lib import categories as categories_mod
from gramtrans.Lib import matcher as matcher_mod
from gramtrans.Lib import transfer as transfer_mod
from gramtrans.Lib.models import (
    GrammarCategory,
    MatchBasis,
    MatchBasisRecord,
    PlannedAction,
    PlannedOverwrite,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ROSTER_035 = (
    REPO_ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"
    / "natural-key-identity-roster.json"
)
EXTENSION_038 = (
    REPO_ROOT / "specs" / "038-transfer-fidelity-gaps" / "contracts"
    / "natural-key-roster-extension.json"
)

#: Per-project handles, deliberately different so a crossed read returns None.
SRC_VERN, SRC_ANAL = 101, 102
TGT_VERN, TGT_ANAL = 201, 202

ENG = "ŋ"
STARTER_NAMES = list("abdefgijklmnoprstuvwxz") + [ENG]
#: Ejagham-W-Mini-shaped: 21 names shared with the starter set (incl. eng),
#: 20 of its own.
SOURCE_NAMES = (
    list("abdefgijklmnoprstuwz") + [ENG]
    + ["ə", "bh", "ch", "ny", "gy", "gh", "H", "ṃ", "y", "L",
       "ʉ", "HL", "kp", "HD", "D", "gb", "LH", "~", "ṇ", "ky"]
)


# ---------------------------------------------------------------------------
# Fakes -- no LCM
# ---------------------------------------------------------------------------

class _Ts:
    def __init__(self, text):
        self.Text = text


class _MultiString:
    def __init__(self, by_handle=None):
        self._by_handle = dict(by_handle or {})

    def get_String(self, ws_handle):  # noqa: N802 -- mirrors LCM
        return _Ts(self._by_handle.get(ws_handle))


class _AddList(list):
    def Add(self, item):  # noqa: N802 -- mirrors LCM
        self.append(item)


class _Phoneme:
    def __init__(self, guid, name, ws_handle, codes=()):
        self.Guid = guid
        self.ClassName = "PhPhoneme"
        self.Name = _MultiString({ws_handle: name})
        self.CodesOS = _AddList(codes)


class _Code:
    def __init__(self, guid, rep, ws_handle):
        self.guid = guid
        self.Representation = _MultiString({ws_handle: rep})


class _NC:
    def __init__(self, guid, name, segments, ws_handle):
        self.Guid = guid
        self.ClassName = "PhNCSegments"
        self.Name = _MultiString({ws_handle: name})
        self.SegmentsRC = _AddList(segments)


class _Handle:
    def __init__(self, vern, anal, phonemes=(), ncs=(), registry=()):
        self._vern, self._anal = vern, anal
        self.Phonemes = types.SimpleNamespace(GetAll=lambda: list(phonemes))
        self.NaturalClasses = types.SimpleNamespace(GetAll=lambda: list(ncs))
        self._registry = {str(o.Guid if hasattr(o, "Guid") else o.guid).lower():
                          o for o in registry}

    def GetDefaultVernacularWSHandle(self):  # noqa: N802
        return self._vern

    def GetDefaultAnalysisWSHandle(self):  # noqa: N802
        return self._anal

    def get_object_by_guid(self, guid):
        return self._registry.get(str(guid).lower())


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
def phoneme_scope():
    """The real scope enumerates a live LCM repository; install the fake
    target's phonemes instead, restoring the registered function after."""
    scope_id = matcher_mod.NATURAL_KEY_BINDINGS["PhPhoneme"].scope_fn_id
    original = matcher_mod.NATURAL_KEY_SCOPE_FNS[scope_id]

    def _install(candidates):
        frozen = list(candidates)
        matcher_mod.NATURAL_KEY_SCOPE_FNS[scope_id] = lambda _t: list(frozen)

    yield _install
    matcher_mod.NATURAL_KEY_SCOPE_FNS[scope_id] = original


def _starters():
    return [_Phoneme("starter-%d" % i, n, TGT_VERN)
            for i, n in enumerate(STARTER_NAMES)]


def _sources():
    return [_Phoneme("src-%d" % i, n, SRC_VERN)
            for i, n in enumerate(SOURCE_NAMES)]


def _ctx(source, target, plan=None):
    ctx = types.SimpleNamespace(
        source_handle=source, target_handle=target, _run_plan=plan,
        _selection=None, _dropped=[])
    return ctx


def _nk_overwrite(category, object_class, src_guid, tgt_guid, key):
    return PlannedOverwrite(
        category=category, source_guid=src_guid, target_guid=tgt_guid,
        summary="nk", match_via="natural_key", write_mode="merge",
        match_basis=MatchBasisRecord(
            basis=MatchBasis.NATURAL_KEY, object_class=object_class,
            source_guid=src_guid, target_guid=tgt_guid,
            key_expression="name", key_value=key, candidate_count=1),
    )


# ---------------------------------------------------------------------------
# 1. The inventory is not doubled
# ---------------------------------------------------------------------------

def test_shared_names_reuse_starters_and_only_the_rest_are_created(admitted):
    starters = _starters()
    source = _Handle(SRC_VERN, SRC_ANAL)
    target = _Handle(TGT_VERN, TGT_ANAL, phonemes=starters)
    ctx = _ctx(source, target)

    plans = [
        categories_mod._phonology_simple_plan(
            p, ctx, GrammarCategory.PHONEMES, "Phonemes", "Phoneme")
        for p in _sources()
    ]

    reused = [p for p in plans if isinstance(p, PlannedOverwrite)]
    created = [p for p in plans if isinstance(p, PlannedAction)]
    assert len(reused) == 21
    assert len(created) == 20
    assert all(p.match_basis.basis is MatchBasis.NATURAL_KEY for p in reused)
    # Injective: no starter is claimed by two source phonemes.
    targets = [p.target_guid for p in reused]
    assert len(set(targets)) == len(targets)
    # The resulting inventory has no duplicate name: 23 starters + 20 created.
    final_names = STARTER_NAMES + [
        SOURCE_NAMES[int(p.source_guid.split("-")[1])] for p in created]
    assert len(final_names) == 43
    assert len(set(final_names)) == 43


def test_eng_is_matched_to_the_starter_eng(admitted):
    starters = _starters()
    target = _Handle(TGT_VERN, TGT_ANAL, phonemes=starters)
    ctx = _ctx(_Handle(SRC_VERN, SRC_ANAL), target)
    src_eng = _Phoneme("src-eng", ENG, SRC_VERN)

    planned = categories_mod._phonology_simple_plan(
        src_eng, ctx, GrammarCategory.PHONEMES, "Phonemes", "Phoneme")

    assert isinstance(planned, PlannedOverwrite)
    assert planned.target_guid == "starter-%d" % STARTER_NAMES.index(ENG)
    assert planned.match_basis.key_value == ENG


# ---------------------------------------------------------------------------
# 2. A key-matched starter Vowels gains the source's members
# ---------------------------------------------------------------------------

def _vowels_fixture():
    starters = _starters()
    by_name = {n: p for n, p in zip(STARTER_NAMES, starters)}
    starter_vowels = _NC("starter-vowels", "Vowels",
                         [by_name[v] for v in "aeiou"], TGT_ANAL)
    # Source vowels: the five shared names plus two the source alone has.
    src_shared = {v: _Phoneme("src-" + v, v, SRC_VERN) for v in "aeiou"}
    schwa = _Phoneme("src-schwa", "ə", SRC_VERN)
    barred_u = _Phoneme("src-barred-u", "ʉ", SRC_VERN)
    src_vowels = _NC("src-vowels", "Vowels",
                     [schwa, src_shared["i"], src_shared["a"], src_shared["e"],
                      src_shared["o"], barred_u, src_shared["u"]], SRC_ANAL)
    # This run CREATED the two source-only vowels, GUID-preserved.
    created_schwa = _Phoneme("src-schwa", "ə", TGT_VERN)
    created_barred = _Phoneme("src-barred-u", "ʉ", TGT_VERN)
    tgt_phonemes = starters + [created_schwa, created_barred]
    source = _Handle(SRC_VERN, SRC_ANAL,
                     phonemes=list(src_shared.values()) + [schwa, barred_u],
                     ncs=[src_vowels])
    target = _Handle(TGT_VERN, TGT_ANAL, phonemes=tgt_phonemes,
                     registry=tgt_phonemes + [starter_vowels])
    plan = types.SimpleNamespace(
        overwrites=(
            _nk_overwrite(GrammarCategory.NATURAL_CLASSES, "PhNCSegments",
                          "src-vowels", "starter-vowels", "Vowels"),
        ),
        identity_remap={}, actions=())
    return source, target, plan, starter_vowels, tgt_phonemes


def _names(nc):
    return sorted(p.Name.get_String(TGT_VERN).Text for p in nc.SegmentsRC)


def test_matched_starter_class_gains_the_source_members(admitted,
                                                        phoneme_scope):
    source, target, plan, vowels, tgt_phonemes = _vowels_fixture()
    phoneme_scope(tgt_phonemes)
    ctx = _ctx(source, target, plan)
    before = [p.Guid for p in vowels.SegmentsRC]

    skips = categories_mod._wire_matched_nc_segments(ctx, target, plan)

    assert skips == []
    assert _names(vowels) == sorted(list("aeiou") + ["ə", "ʉ"])
    # Add-only: every starter member is still there, in its place.
    assert [p.Guid for p in vowels.SegmentsRC][:5] == before
    # The shared vowels resolved to the STARTERS, not to a second copy.
    assert len({p.Guid for p in vowels.SegmentsRC}) == 7
    assert ctx._dropped == []


def test_rerun_adds_nothing(admitted, phoneme_scope):
    source, target, plan, vowels, tgt_phonemes = _vowels_fixture()
    phoneme_scope(tgt_phonemes)
    ctx = _ctx(source, target, plan)

    categories_mod._wire_matched_nc_segments(ctx, target, plan)
    first = [p.Guid for p in vowels.SegmentsRC]
    categories_mod._wire_matched_nc_segments(ctx, target, plan)

    assert [p.Guid for p in vowels.SegmentsRC] == first


def test_an_unresolvable_member_is_reported_not_raised(admitted,
                                                       phoneme_scope):
    source, target, plan, vowels, tgt_phonemes = _vowels_fixture()
    # The run did NOT create the barred u -- nothing on the target names it.
    missing = [p for p in tgt_phonemes if p.Guid != "src-barred-u"]
    target.Phonemes = types.SimpleNamespace(GetAll=lambda: list(missing))
    phoneme_scope(missing)
    ctx = _ctx(source, target, plan)

    categories_mod._wire_matched_nc_segments(ctx, target, plan)

    assert "ʉ" not in _names(vowels)
    assert "ə" in _names(vowels)
    assert len(ctx._dropped) == 1
    assert ctx._dropped[0].item_guid == "src-barred-u"


def test_a_guid_matched_class_is_left_alone(admitted, phoneme_scope):
    """Only NATURAL_KEY reuse is #54's case; an identity-matched class keeps
    its pre-#54 behaviour."""
    source, target, plan, vowels, tgt_phonemes = _vowels_fixture()
    phoneme_scope(tgt_phonemes)
    ov = plan.overwrites[0]
    identity = PlannedOverwrite(
        category=ov.category, source_guid=ov.source_guid,
        target_guid=ov.target_guid, summary="guid", match_via="guid",
        write_mode="merge",
        match_basis=MatchBasisRecord(
            basis=MatchBasis.IDENTITY, object_class="PhNCSegments",
            source_guid=ov.source_guid, target_guid=ov.target_guid,
            candidate_count=1))
    plan.overwrites = (identity,)
    ctx = _ctx(source, target, plan)

    categories_mod._wire_matched_nc_segments(ctx, target, plan)

    assert _names(vowels) == sorted("aeiou")


def test_the_pass_is_called_after_the_leaf_loop():
    """Ordering is the fix: the overwrite loop runs before this run's creates,
    so the member pass must be called after the leaf-dispatch loop."""
    import inspect
    src = inspect.getsource(transfer_mod.execute)
    leaf_loop = src.index("for action in plan.actions:")
    member_pass = src.index("_ensure_matched_nc_segments(")
    assert member_pass > leaf_loop


# ---------------------------------------------------------------------------
# 3. The phantom PhonemeGuids write
# ---------------------------------------------------------------------------

def test_phoneme_guids_never_reach_the_per_field_update_write():
    assert "PhonemeGuids" in transfer_mod._UPDATE_UNWRITABLE_KEYS[
        GrammarCategory.NATURAL_CLASSES]


def test_an_nc_differing_only_in_phoneme_guids_is_an_update_skip():
    """End to end through `_execute_update_semantic`: only the membership list
    differs, so nothing may be written and the line must say UPDATE-SKIP."""
    applied = []

    class _Ops:
        def __init__(self, objs, props):
            self._objs, self._props = objs, props

        def GetAll(self):  # noqa: N802
            return list(self._objs)

        def GetSyncableProperties(self, obj):  # noqa: N802
            return dict(self._props)

        def ApplySyncableProperties(self, obj, props, ws_map=None):  # noqa: N802
            applied.append(props)

    common = {"Name": {"en": "Vowels"}, "Abbreviation": {"en": "V"}}
    src_obj = types.SimpleNamespace(Guid="src-vowels")
    tgt_obj = types.SimpleNamespace(Guid="starter-vowels", Description=None)
    source = types.SimpleNamespace(NaturalClasses=_Ops(
        [src_obj], dict(common, PhonemeGuids=["s1", "s2", "s3"])))
    target = types.SimpleNamespace(NaturalClasses=_Ops(
        [tgt_obj], dict(common, PhonemeGuids=["t1", "t2"])))
    lines = []
    sink = types.SimpleNamespace(Info=lines.append, Warning=lines.append)
    ov = types.SimpleNamespace(
        category=GrammarCategory.NATURAL_CLASSES, source_guid="src-vowels",
        target_guid="starter-vowels", write_mode="merge", match_basis=None,
        enrichment=None)

    transfer_mod._execute_update_semantic(ov, source, target, sink, None)

    assert applied == []
    assert any("UPDATE-SKIP" in line for line in lines), lines


# ---------------------------------------------------------------------------
# 4. A matched starter's codes are not doubled
# ---------------------------------------------------------------------------

def _fake_create_with_guid(monkeypatch):
    seen = []

    def _fake(factory_iface, owner_collection, guid_str, target):
        code = _Code(guid_str, "", TGT_VERN)
        owner_collection.Add(code)
        seen.append(guid_str)
        return code, True

    monkeypatch.setattr(categories_mod, "_create_with_guid", _fake)
    monkeypatch.setattr(categories_mod, "IPhCodeFactory_ref", lambda: object())
    monkeypatch.setattr(categories_mod, "_copy_multistrings_ws_mapped",
                        lambda *a, **k: None)
    return seen


def test_a_starter_matched_phoneme_keeps_one_code_per_spelling(monkeypatch):
    seen = _fake_create_with_guid(monkeypatch)
    src_a = _Phoneme("src-a", "a", SRC_VERN, codes=[
        _Code("src-code-a", "a", SRC_VERN),
        _Code("src-code-aa", "aa", SRC_VERN),
    ])
    starter_a = _Phoneme("starter-a", "a", TGT_VERN,
                         codes=[_Code("starter-code-a", "a", TGT_VERN)])
    source = _Handle(SRC_VERN, SRC_ANAL, phonemes=[src_a])
    target = _Handle(TGT_VERN, TGT_ANAL, registry=[starter_a])
    plan = types.SimpleNamespace(
        overwrites=(_nk_overwrite(GrammarCategory.PHONEMES, "PhPhoneme",
                                  "src-a", "starter-a", "a"),),
        identity_remap={}, actions=(), ws_mapping=None)
    ctx = _ctx(source, target, plan)

    categories_mod._wire_phoneme_codes(ctx, target, None)

    # The identically spelled `a` is NOT added again; the new spelling is.
    assert seen == ["src-code-aa"]
    assert [c.guid for c in starter_a.CodesOS] == [
        "starter-code-a", "src-code-aa"]


def test_a_created_phoneme_still_gets_every_source_code(monkeypatch):
    """The de-duplication is scoped to STARTER-matched phonemes; a phoneme
    this run created carries exactly the source's codes."""
    seen = _fake_create_with_guid(monkeypatch)
    src_p = _Phoneme("src-p", "p", SRC_VERN, codes=[
        _Code("c1", "p", SRC_VERN), _Code("c2", "ph", SRC_VERN)])
    created_p = _Phoneme("src-p", "p", TGT_VERN)
    source = _Handle(SRC_VERN, SRC_ANAL, phonemes=[src_p])
    target = _Handle(TGT_VERN, TGT_ANAL, registry=[created_p])
    plan = types.SimpleNamespace(overwrites=(), identity_remap={},
                                 actions=(), ws_mapping=None)

    categories_mod._wire_phoneme_codes(_ctx(source, target, plan), target,
                                       None)

    assert seen == ["c1", "c2"]
