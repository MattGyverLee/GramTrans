"""Feature 038 T031 -- the plan-time match decision.

`preview.plan_match_decision` is the seam that makes Preview and Move agree by
construction: both match steps run in the plan builder, and the answer travels
on the plan as a `MatchBasisRecord` rather than being recomputed by the
executor.

What these tests pin, beyond "it returns a decision":

1. **The two projects have different writing-system handles.** This is the
   defect most likely to be reintroduced. A handle is a per-project integer,
   so reading a destination object's name through the SOURCE project's handle
   does not raise -- it returns None. Every candidate key would then evaluate
   to "this object has no key", the natural-key step would silently match
   nothing at all, and the run would look like a clean set of misses rather
   than a broken comparison. `_ws_handles_for` is resolved per project and
   handed to `resolve_match` as two separate mappings for exactly this reason.

2. **A fingerprint match gets NO `MatchBasisRecord`.** `MatchBasis` has three
   members and none of them means "matched by fingerprint". Recording one as
   IDENTITY would claim a GUID hit that never happened; recording it as
   NATURAL_KEY would corrupt `CategoryReport.identity_substitution`, whose
   entire purpose is to count roster-admitted name matches. Absent is honest.

3. **A class with no binding yields None**, not a fabricated decision -- the
   caller keeps its pre-038 GUID-only behaviour.
"""
import json
import pathlib

import pytest

from gramtrans.Lib import census as census_mod
from gramtrans.Lib import matcher as matcher_mod
from gramtrans.Lib import preview as preview_mod
from gramtrans.Lib.models import (
    GrammarCategory,
    MatchBasis,
    Selection,
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

#: Deliberately different integers per project. If any production path crosses
#: them, the key read returns None and the assertions below fail loudly rather
#: than passing on a coincidence.
SRC_VERN, SRC_ANAL = 101, 102
TGT_VERN, TGT_ANAL = 201, 202


# ---------------------------------------------------------------------------
# Fakes -- no LCM. `preview` and `matcher` import none at module level.
# ---------------------------------------------------------------------------

class _Ts:
    def __init__(self, text):
        self.Text = text


class _MultiString:
    def __init__(self, by_handle):
        self._by_handle = dict(by_handle)

    def get_String(self, ws_handle):
        return _Ts(self._by_handle.get(ws_handle))


class _Obj:
    def __init__(self, guid, class_name, names=None, owner=None):
        self.Guid = guid
        self.ClassName = class_name
        self.Name = _MultiString(names or {})
        self.Owner = owner


class _Handle:
    """A project handle exposing the two WS getters `census._ws_handle_for`
    looks for. `vern`/`anal` None models a project where that default writing
    system cannot be resolved at all."""

    def __init__(self, vern, anal):
        self._vern = vern
        self._anal = anal

    def GetDefaultVernacularWSHandle(self):
        if self._vern is None:
            raise RuntimeError("no default vernacular in this project")
        return self._vern

    def GetDefaultAnalysisWSHandle(self):
        if self._anal is None:
            raise RuntimeError("no default analysis in this project")
        return self._anal


class _Context:
    def __init__(self, source_handle, target_handle):
        self.source_handle = source_handle
        self.target_handle = target_handle


def _appended_roster(tmp_path):
    """035's file with 038's six proposed entries appended, as T028 left it on
    `main`. Built in `tmp_path` so these tests neither depend on nor anticipate
    which branch currently carries the merged file."""
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
def context():
    return _Context(_Handle(SRC_VERN, SRC_ANAL), _Handle(TGT_VERN, TGT_ANAL))


def _pos(guid, name, ws_handle, owner=None):
    return _Obj(guid, "PartOfSpeech", {ws_handle: name}, owner=owner)


def _phoneme(guid, name, ws_handle):
    return _Obj(guid, "PhPhoneme", {ws_handle: name})


# ---------------------------------------------------------------------------
# _ws_handles_for
# ---------------------------------------------------------------------------

def test_ws_handles_are_resolved_per_project():
    src = preview_mod._ws_handles_for(_Handle(SRC_VERN, SRC_ANAL))
    tgt = preview_mod._ws_handles_for(_Handle(TGT_VERN, TGT_ANAL))
    assert src == {
        census_mod.WS_SCOPE_VERNACULAR: SRC_VERN,
        census_mod.WS_SCOPE_ANALYSIS: SRC_ANAL,
    }
    assert tgt == {
        census_mod.WS_SCOPE_VERNACULAR: TGT_VERN,
        census_mod.WS_SCOPE_ANALYSIS: TGT_ANAL,
    }
    assert src != tgt, (
        "the whole point: a handle is per project and the two must not be "
        "interchangeable"
    )


def test_an_unresolvable_scope_is_omitted_rather_than_defaulted():
    """A missing scope means NOT COMPUTABLE, which the matcher reports. It must
    never be filled in with the other default writing system -- matching a
    secondary vernacular would have fabricated 16 matches on `Yi Sichuan`."""
    handles = preview_mod._ws_handles_for(_Handle(None, TGT_ANAL))
    assert census_mod.WS_SCOPE_VERNACULAR not in handles
    assert handles[census_mod.WS_SCOPE_ANALYSIS] == TGT_ANAL


# ---------------------------------------------------------------------------
# plan_match_decision
# ---------------------------------------------------------------------------

def test_a_class_with_no_binding_yields_no_decision(context):
    """`WfiWordform` is admitted by 035 and keyable by the census, but 038
    binds no key function for it. The caller keeps its GUID-only behaviour."""
    assert "WfiWordform" not in matcher_mod.NATURAL_KEY_BINDINGS
    assert preview_mod.plan_match_decision(
        "WfiWordform", _Obj("g", "WfiWordform"), context, candidates=[],
    ) is None


def test_identity_hit_is_decided_in_the_plan(admitted, context):
    src = _pos("guid-1", "Noun", SRC_ANAL)
    dst = _pos("guid-1", "Noun", TGT_ANAL)

    decision = preview_mod.plan_match_decision(
        "PartOfSpeech", src, context, candidates=[dst],
    )

    assert decision.record.basis is MatchBasis.IDENTITY
    assert decision.target_obj is dst
    assert decision.enrich is True, "a matched GUID is a LINK, not a SKIP"


def test_natural_key_hit_reads_each_side_through_its_own_project_handle(
    admitted, context,
):
    """THE regression test for the cross-project handle bug.

    The source name lives only under the SOURCE project's analysis handle and
    the destination name only under the TARGET's. If one handle were used for
    both, one of the two reads returns None, no key matches, and this comes
    back as a miss that looks entirely legitimate.
    """
    src = _pos("guid-src", "Adverb", SRC_ANAL)
    dst = _pos("guid-dst", "Adverb", TGT_ANAL)

    decision = preview_mod.plan_match_decision(
        "PartOfSpeech", src, context, candidates=[dst],
    )

    assert decision.record.basis is MatchBasis.NATURAL_KEY
    assert decision.record.key_value == "Adverb"
    assert decision.target_obj is dst
    assert decision.record.source_guid == "guid-src"
    assert decision.record.target_guid == "guid-dst"


def test_phoneme_keys_on_the_vernacular_of_each_project(admitted, context):
    """`PhPhoneme` is the one class keyed on the default VERNACULAR, and it is
    keyed on each project's own. 97 of 97 phonemes carry a vernacular name;
    only 44 of 97 carry an analysis one."""
    src = _phoneme("guid-src", "a", SRC_VERN)
    dst = _phoneme("guid-dst", "a", TGT_VERN)

    decision = preview_mod.plan_match_decision(
        "PhPhoneme", src, context, candidates=[dst],
    )

    assert decision.record.basis is MatchBasis.NATURAL_KEY
    assert decision.record.key_value == "a"


def test_a_name_under_the_other_projects_handle_is_not_a_key(admitted, context):
    """Belt to the previous test's braces: put the destination's name under the
    SOURCE handle and it must NOT match. This is what a crossed handle looks
    like from the outside, and it must be a miss rather than a match."""
    src = _pos("guid-src", "Adverb", SRC_ANAL)
    dst = _pos("guid-dst", "Adverb", SRC_ANAL)  # wrong project's handle

    decision = preview_mod.plan_match_decision(
        "PartOfSpeech", src, context, candidates=[dst],
    )

    assert decision.record.basis is MatchBasis.NONE
    assert decision.record.candidate_count == 0
    assert decision.may_create is True


def test_key_not_computable_when_the_source_scope_is_unavailable(
    admitted,
):
    """A phoneme key is not computable unless the pre-run WS mapping produced a
    source -> target default vernacular. Reported, never substituted."""
    ctx = _Context(_Handle(None, SRC_ANAL), _Handle(TGT_VERN, TGT_ANAL))
    src = _phoneme("guid-src", "a", SRC_VERN)
    dst = _phoneme("guid-dst", "a", TGT_VERN)

    decision = preview_mod.plan_match_decision(
        "PhPhoneme", src, ctx, candidates=[dst],
    )

    assert decision.record.basis is MatchBasis.NONE
    assert decision.ineligible_reason == (
        matcher_mod.KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS
    )
    assert decision.may_create is False, (
        "an object that could not be keyed was never compared, so creating it "
        "here would be the create-anyway half of the defect 038 removes"
    )


def test_ambiguity_is_allowed_through_rather_than_absorbed(admitted, context):
    """An ambiguous key is a harness error the operator must see. The plan-time
    wrapper must not turn it into a silent miss."""
    src = _pos("guid-src", "Noun", SRC_ANAL)
    dupes = [
        _pos("guid-a", "Noun", TGT_ANAL),
        _pos("guid-b", "Noun", TGT_ANAL),
    ]
    with pytest.raises(matcher_mod.NaturalKeyAmbiguityError):
        preview_mod.plan_match_decision(
            "PartOfSpeech", src, context, candidates=dupes,
        )


def test_parent_divergence_is_reported_and_the_destination_keeps_its_parent(
    admitted, context,
):
    src_parent = _pos("guid-parent-src", "Verb", SRC_ANAL)
    dst_parent = _pos("guid-parent-dst", "Adjective", TGT_ANAL)
    src = _pos("guid-src", "Demonstrative", SRC_ANAL, owner=src_parent)
    dst = _pos("guid-dst", "Demonstrative", TGT_ANAL, owner=dst_parent)

    decision = preview_mod.plan_match_decision(
        "PartOfSpeech", src, context, candidates=[dst],
    )

    assert decision.record.basis is MatchBasis.NATURAL_KEY
    assert "guid-parent-src" in decision.parent_divergence
    assert "guid-parent-dst" in decision.parent_divergence
    assert dst.Owner is dst_parent, "the matcher decides; it never re-parents"


def test_an_unenumerable_scope_reports_a_miss_rather_than_matching(
    admitted, context,
):
    """A scope that raises must not be read as "no candidates, so create" via
    a partial scan. It becomes an accounted miss whose may_create follows the
    class rule."""
    src = _pos("guid-src", "Noun", SRC_ANAL)

    def _boom(_target):
        raise RuntimeError("cannot enumerate PartOfSpeech")

    original = matcher_mod.NATURAL_KEY_SCOPE_FNS[
        matcher_mod.NATURAL_KEY_BINDINGS["PartOfSpeech"].scope_fn_id
    ]
    matcher_mod.NATURAL_KEY_SCOPE_FNS[
        matcher_mod.NATURAL_KEY_BINDINGS["PartOfSpeech"].scope_fn_id
    ] = _boom
    try:
        decision = preview_mod.plan_match_decision(
            "PartOfSpeech", src, context,
        )
    finally:
        matcher_mod.NATURAL_KEY_SCOPE_FNS[
            matcher_mod.NATURAL_KEY_BINDINGS["PartOfSpeech"].scope_fn_id
        ] = original

    assert decision.record.basis is MatchBasis.NONE
    assert decision.target_obj is None


# ---------------------------------------------------------------------------
# match_basis_for_present_by_guid / _emit_present_outcome
# ---------------------------------------------------------------------------

def test_present_by_guid_record_is_an_identity_record():
    record = preview_mod.match_basis_for_present_by_guid(
        "PartOfSpeech", "guid-src", "guid-src",
    )
    assert record.basis is MatchBasis.IDENTITY
    assert record.object_class == "PartOfSpeech"
    assert record.key_expression == "", "an IDENTITY record carries no key"
    assert record.key_value == ""


def _emit(match_via, object_class, category=GrammarCategory.GRAM_CATEGORIES):
    overwrites = []
    preview_mod._emit_present_outcome(
        category,
        "guid-src",
        "guid-tgt",
        "summary",
        "skip detail",
        Selection(categories={category: True}, enable_overwrite=True),
        [],
        overwrites,
        match_via=match_via,
        object_class=object_class,
    )
    return overwrites[0]


@pytest.mark.parametrize("match_via", ["guid", "identity_remap"])
def test_guid_and_remap_matches_carry_an_identity_record(match_via):
    """FR-001 treats a previous run's remap entry as identity, not as a
    substitution."""
    overwrite = _emit(match_via, "PartOfSpeech")
    assert overwrite.match_basis is not None
    assert overwrite.match_basis.basis is MatchBasis.IDENTITY


def test_a_fingerprint_match_carries_no_record():
    """`MatchBasis` has no member for a fingerprint match. Claiming IDENTITY
    would assert a GUID hit that never happened; claiming NATURAL_KEY would
    corrupt `CategoryReport.identity_substitution`."""
    assert _emit("fingerprint", "PartOfSpeech").match_basis is None


def test_the_class_is_derived_from_the_category_not_demanded_of_the_caller():
    """The `object_class=` parameter came first and NOTHING passed it, so the
    record was never actually produced -- an opt-in every caller must remember
    is the wrong shape for an accounting record. The class is now derived."""
    overwrite = _emit("guid", "", GrammarCategory.GRAM_CATEGORIES)
    assert overwrite.match_basis is not None
    assert overwrite.match_basis.object_class == "PartOfSpeech"
    assert preview_mod.lcm_class_for_category(GrammarCategory.SLOTS) == (
        "MoInflAffixSlot"
    )


@pytest.mark.parametrize("category", [
    GrammarCategory.ALLOMORPH,      # MoStemAllomorph vs MoAffixAllomorph
    GrammarCategory.MSA,            # four Mo*Msa subclasses
    GrammarCategory.NATURAL_CLASSES,   # PhNCSegments vs PhNCFeatures
    GrammarCategory.VARIANT_TYPES,     # LexEntryType vs LexEntryInflType
])
def test_a_category_whose_lcm_class_is_not_one_to_one_yields_no_record(
    category,
):
    """`object_class` is the field the report GROUPS BY, so a guessed name is
    worse than no record: it files the match under another class's row.

    `NATURAL_CLASSES` and `VARIANT_TYPES` are the sharp cases -- 038's own
    roster keeps `PhNCSegments`/`PhNCFeatures` and
    `LexEntryType`/`LexEntryInflType` strictly apart and forbids them matching
    each other, so collapsing either pair to one name here would undo that at
    the report layer.
    """
    assert preview_mod.lcm_class_for_category(category) == ""
    assert _emit("guid", "", category).match_basis is None


def test_an_explicit_object_class_overrides_the_derivation():
    """A caller that knows which subclass it is holding says so."""
    overwrite = _emit("guid", "MoAffixAllomorph", GrammarCategory.ALLOMORPH)
    assert overwrite.match_basis.object_class == "MoAffixAllomorph"
