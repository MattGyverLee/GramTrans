"""Feature 038 T032 / T033 -- the category fallback, and the end of the
silent abandon.

`_resolve_target_pos` was the `None`-returns-and-caller-abandons path that lost
**all 2,088 MSAs** on the measured pair. Two things were wrong with it, and
they are separate defects fixed by separate tasks:

- **T032**: it matched by GUID only. Whether that works is not something a
  linguist can see or control. Catalog-sourced categories share GUIDs across
  projects (`Noun` is `a8e41fd3-...` in both `Ejagham Mini` and `Mbugwe LizzieHC
  practice`); categories created any other way do not (Esperanto's `Noun` is
  `e09a4354-...`). census-evidence.md records the consequence exactly --
  "Ejagham escaped total loss only by accident: its 5 target POSes happened to
  be GUID-identical to the source's", while Ngoreme matched none.

- **T033**: four of its eight call sites answered `None` by returning `None`
  with no record at all. `transfer.py` discards every `execute_action` return
  value and then increments `leaf_succeeded` unconditionally, so the item
  vanished AND the run counted it a success.

The most important test in this file is the FIRST one. The fallback had to be
landable ahead of its call-site sweep, so a two-positional call must behave
exactly as it did before 038. If that ever stops being true, every caller not
yet swept changes behaviour silently.
"""
import json
import pathlib

import pytest

from gramtrans.Lib import categories as cat_mod
from gramtrans.Lib import matcher as matcher_mod
from gramtrans.Lib.models import (
    GrammarCategory, PlannedAction, PlannedOverwrite, Skip, SkipReason,
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

SRC_ANAL, TGT_ANAL = 102, 202
SRC_VERN, TGT_VERN = 101, 201


class _Ts:
    def __init__(self, text):
        self.Text = text


class _MultiString:
    def __init__(self, by_handle):
        self._by_handle = dict(by_handle)

    def get_String(self, ws_handle):
        return _Ts(self._by_handle.get(ws_handle))


class _Pos:
    def __init__(self, guid, name=None, ws_handle=None, owner=None):
        self.Guid = guid
        self.ClassName = "PartOfSpeech"
        self.Name = _MultiString({ws_handle: name} if ws_handle else {})
        self.Owner = owner


class _PosAccessor:
    def __init__(self, poses):
        self._poses = list(poses)

    def GetAll(self, recursive=False):
        return list(self._poses)


class _Handle:
    def __init__(self, poses, vern, anal):
        self.POS = _PosAccessor(poses)
        self._vern = vern
        self._anal = anal

    def GetDefaultVernacularWSHandle(self):
        return self._vern

    def GetDefaultAnalysisWSHandle(self):
        return self._anal


class _Context:
    """Minimal RunContext stand-in. `_exec_skips` mirrors what
    `transfer.execute` attaches; omitting it models an older caller."""

    def __init__(self, source_handle, target_handle, with_skips=True):
        self.source_handle = source_handle
        self.target_handle = target_handle
        if with_skips:
            self._exec_skips = []


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
def not_admitted(tmp_path):
    """A roster carrying only 035's original three entries -- i.e. one that
    does NOT admit `PartOfSpeech`. The fallback must be inert.

    This used to point at the shipped file, on the reasoning that this
    worktree had not yet merged T028's append. That was true when written and
    false one merge later, which is exactly why a test must not use a live
    artifact as a stand-in for a state it happens to be in today.
    """
    base = json.loads(ROSTER_035.read_text(encoding="utf-8"))
    base["entries"] = list(base["entries"])[:3]
    path = tmp_path / "natural-key-identity-roster.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    matcher_mod.reset_natural_key_roster_cache(str(path))
    yield
    matcher_mod.reset_natural_key_roster_cache(None)


# ---------------------------------------------------------------------------
# The safety property: a two-positional call is unchanged
# ---------------------------------------------------------------------------

def test_two_positional_call_never_consults_the_key(admitted):
    """THE landing-safety test. `src_pos` and `source_handle` are keyword-only
    and default to None, so a caller that has not been swept gets exactly its
    pre-038 behaviour even when the roster admits the class and a name would
    have matched."""
    target = _Handle([_Pos("guid-dst", "Noun", TGT_ANAL)], TGT_VERN, TGT_ANAL)
    assert cat_mod._resolve_target_pos(target, "guid-src") is None


def test_fallback_is_inert_while_the_roster_does_not_admit_the_class(
    not_admitted,
):
    """Both halves of the basis are required. With the class off the roster
    the fallback finds nothing, however complete the call."""
    source = _Handle([_Pos("guid-src", "Noun", SRC_ANAL)], SRC_VERN, SRC_ANAL)
    target = _Handle([_Pos("guid-dst", "Noun", TGT_ANAL)], TGT_VERN, TGT_ANAL)
    assert cat_mod._resolve_target_pos(
        target, "guid-src",
        src_pos=source.POS.GetAll()[0], source_handle=source,
    ) is None


# ---------------------------------------------------------------------------
# T032 -- identity first, then the key
# ---------------------------------------------------------------------------

def test_identity_still_wins_and_short_circuits(admitted):
    """FR-001. A destination object whose GUID matches is returned even though
    its name is completely different -- and the differently-named object that
    WOULD have matched by key is not chosen."""
    src = _Pos("guid-1", "Noun", SRC_ANAL)
    by_guid = _Pos("guid-1", "something else entirely", TGT_ANAL)
    by_name = _Pos("guid-other", "Noun", TGT_ANAL)
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    target = _Handle([by_guid, by_name], TGT_VERN, TGT_ANAL)

    got = cat_mod._resolve_target_pos(
        target, "guid-1", src_pos=src, source_handle=source,
    )
    assert got is by_guid


def test_a_guid_miss_now_matches_by_name(admitted):
    """The 2,088-MSA fix. Same category, different GUIDs in the two projects --
    the shape census-evidence.md measured on the Ngoreme pair."""
    src = _Pos("guid-src", "Adverb", SRC_ANAL)
    dst = _Pos("guid-dst", "Adverb", TGT_ANAL)
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    target = _Handle([dst], TGT_VERN, TGT_ANAL)

    got = cat_mod._resolve_target_pos(
        target, "guid-src", src_pos=src, source_handle=source,
    )
    assert got is dst


def test_each_project_is_read_through_its_own_writing_system_handle(admitted):
    """A WS handle is per project. Put the destination's name under the SOURCE
    project's handle and it must NOT match -- that is what a crossed handle
    looks like from the outside, and it has to be a miss, not a match."""
    src = _Pos("guid-src", "Adverb", SRC_ANAL)
    dst = _Pos("guid-dst", "Adverb", SRC_ANAL)  # wrong project's handle
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    target = _Handle([dst], TGT_VERN, TGT_ANAL)

    assert cat_mod._resolve_target_pos(
        target, "guid-src", src_pos=src, source_handle=source,
    ) is None


def test_comparison_is_exact(admitted):
    """`Nasals` / `nasals` / `Nasal Consonants` were measured as three distinct
    classes; the same strictness applies to categories."""
    src = _Pos("guid-src", "Adverb", SRC_ANAL)
    dst = _Pos("guid-dst", "adverb", TGT_ANAL)
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    target = _Handle([dst], TGT_VERN, TGT_ANAL)

    assert cat_mod._resolve_target_pos(
        target, "guid-src", src_pos=src, source_handle=source,
    ) is None


def test_an_ambiguous_name_raises_rather_than_picking(admitted):
    """The roster sets on_ambiguous_key=harness_error for PartOfSpeech and does
    not claim the key is unique by construction. Picking one would fabricate a
    correspondence and then record it as an identity substitution."""
    src = _Pos("guid-src", "Noun", SRC_ANAL)
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    target = _Handle(
        [_Pos("guid-a", "Noun", TGT_ANAL), _Pos("guid-b", "Noun", TGT_ANAL)],
        TGT_VERN, TGT_ANAL,
    )
    with pytest.raises(matcher_mod.NaturalKeyAmbiguityError):
        cat_mod._resolve_target_pos(
            target, "guid-src", src_pos=src, source_handle=source,
        )


def test_an_unnamed_source_category_never_matches(admitted):
    """`Ejagham Mini` holds a category (`400c5e75-...`) with no Name in either
    default writing system. It has no key, and an empty key never matches
    another empty key."""
    src = _Pos("guid-src")
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    target = _Handle([_Pos("guid-dst")], TGT_VERN, TGT_ANAL)

    assert cat_mod._resolve_target_pos(
        target, "guid-src", src_pos=src, source_handle=source,
    ) is None


def test_the_parent_is_not_part_of_the_key_and_is_not_rewritten(admitted):
    """Catalog category `093264d7-...` ("Demonstrative") is depth-1 in one
    project and depth-2 in another, so a parent-scoped key would fail to match
    precisely the category a linguist has re-parented. The destination keeps
    its own parent regardless."""
    src_parent = _Pos("guid-parent-src", "Verb", SRC_ANAL)
    dst_parent = _Pos("guid-parent-dst", "Adjective", TGT_ANAL)
    src = _Pos("guid-src", "Demonstrative", SRC_ANAL, owner=src_parent)
    dst = _Pos("guid-dst", "Demonstrative", TGT_ANAL, owner=dst_parent)
    source = _Handle([src_parent, src], SRC_VERN, SRC_ANAL)
    target = _Handle([dst_parent, dst], TGT_VERN, TGT_ANAL)

    assert cat_mod._resolve_target_pos(
        target, "guid-src", src_pos=src, source_handle=source,
    ) is dst
    assert dst.Owner is dst_parent


def test_an_empty_guid_still_short_circuits(admitted):
    """No GUID means no identity and no key either -- a caller with no GUID has
    no source object to key from."""
    target = _Handle([_Pos("guid-dst", "Noun", TGT_ANAL)], TGT_VERN, TGT_ANAL)
    assert cat_mod._resolve_target_pos(target, "") is None
    assert cat_mod._resolve_target_pos(target, None) is None


# ---------------------------------------------------------------------------
# T033 -- report, never drop
# ---------------------------------------------------------------------------

def test_source_pos_by_guid_finds_the_object_a_compound_key_cannot_carry():
    src = _Pos("guid-src", "Noun", SRC_ANAL)
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    assert cat_mod._source_pos_by_guid(source, "guid-src") is src
    assert cat_mod._source_pos_by_guid(source, "guid-absent") is None
    assert cat_mod._source_pos_by_guid(source, "") is None


def test_an_unresolved_owner_is_reported_rather_than_dropped():
    """FR-013. The record is what distinguishes "not transferred" from
    "transferred", which `transfer.py` could not tell before: it discards the
    return value and counts the call a success either way."""
    context = _Context(None, None)
    cat_mod._report_owner_pos_unresolved(
        context, GrammarCategory.SLOTS, "slot-guid-123", "pos-guid-456",
        "affix slot",
    )

    assert len(context._exec_skips) == 1
    skip = context._exec_skips[0]
    assert isinstance(skip, Skip)
    assert skip.category is GrammarCategory.SLOTS
    assert skip.source_guid == "slot-guid-123"
    assert skip.reason is SkipReason.DEPENDENCY_UNRESOLVED
    assert "affix slot" in skip.detail
    assert "pos-guid" in skip.detail


def test_reporting_never_raises_when_the_context_carries_no_skip_list():
    """The condition being reported is already a degraded run; the report must
    not be the thing that turns it into a crash."""
    context = _Context(None, None, with_skips=False)
    cat_mod._report_owner_pos_unresolved(
        context, GrammarCategory.SLOTS, "g", "p", "affix slot",
    )  # must not raise


@pytest.mark.parametrize("category", [
    GrammarCategory.INFLECTION_CLASSES,
    GrammarCategory.POS_INFLECTABLE_FEATS,
    GrammarCategory.SLOTS,
    GrammarCategory.AFFIX_TEMPLATES,
])
def test_every_converted_site_has_a_category_to_report_under(category):
    """The four sites T033 converted, pinned by name so a future edit that
    drops one is visible here rather than only in a live run."""
    context = _Context(None, None)
    cat_mod._report_owner_pos_unresolved(
        context, category, "item-guid", "pos-guid", "item",
    )
    assert context._exec_skips[0].category is category


# ---------------------------------------------------------------------------
# T091 -- the PLAN path, which is where the fallback was NOT wired
# ---------------------------------------------------------------------------
#
# Everything above this line exercises `_resolve_target_pos`: the OWNER
# resolution path, which answers "which target POS does this slot belong to?".
# T032/T033 landed the fallback there, and it works. What no test asked until
# now is the other question -- "should I create this POS at all?" -- which is
# `_plan_pos_piece`'s, and which reached its create without ever consulting the
# matcher. A full copy of `Ngoreme FLEx` therefore created a second `Verb`,
# `Noun`, `Pronoun`, `Adverb` and `Pro-form` beside the five starter ones. That
# is RC-1, the defect feature 038's highest-value phase exists to close, and it
# survived every green run because `Ejagham W Mini`'s starters carry the GOLD
# catalog GUIDs and match on IDENTITY -- so the only pair in the corpus that
# reaches the fallback at all is the one nothing had been re-run against.
#
# The two categories below are one code path: `gram_categories_plan_action` and
# `pos_plan_action` both delegate to `_plan_pos_piece` and differ only in the
# category stamped on the decision. Both are parameterized everywhere rather
# than trusting that they cannot drift apart.

_POS_PLANNERS = [
    (GrammarCategory.GRAM_CATEGORIES, "gram_categories_plan_action"),
    (GrammarCategory.POS, "pos_plan_action"),
]


def _plan_pos(fn_name, source, target):
    return getattr(cat_mod, fn_name)(
        source.POS.GetAll()[0], _Context(source, target), None,
    )


@pytest.mark.parametrize("category,fn_name", _POS_PLANNERS)
def test_plan_reuses_a_same_named_destination_pos_instead_of_creating(
    admitted, category, fn_name,
):
    """RC-1 ITSELF. Different GUIDs, same name -- the exact shape of Ngoreme's
    five starter categories against the source's own. The plan must NAME the
    destination object, not mint a second one beside it."""
    src = _Pos("guid-src", "Noun", SRC_ANAL)
    dst = _Pos("guid-dst", "Noun", TGT_ANAL)
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    target = _Handle([dst], TGT_VERN, TGT_ANAL)

    decision = _plan_pos(fn_name, source, target)

    assert isinstance(decision, PlannedOverwrite), (
        "a same-named destination POS was already there and the plan still "
        "emitted %s -- that is the duplicate-identity defect"
        % type(decision).__name__
    )
    assert decision.category is category
    assert decision.source_guid == "guid-src"
    assert decision.target_guid == "guid-dst"


@pytest.mark.parametrize("category,fn_name", _POS_PLANNERS)
def test_plan_records_the_basis_as_name_and_the_write_as_non_destructive(
    admitted, category, fn_name,
):
    """FR-006: the report may not claim a GUID-strength match the matcher never
    made, and the write may not blank a populated destination. `match_basis` is
    what `report._count_substitution` tallies as an identity substitution --
    `test_038_report_natural_key.py` has asserted a nonzero
    `per_category[POS].identity_substitution` since Phase 4 with no producer to
    supply it. This is the producer."""
    src = _Pos("guid-src", "Adverb", SRC_ANAL)
    dst = _Pos("guid-dst", "Adverb", TGT_ANAL)
    decision = _plan_pos(
        fn_name,
        _Handle([src], SRC_VERN, SRC_ANAL),
        _Handle([dst], TGT_VERN, TGT_ANAL),
    )

    assert decision.match_via == "natural_key"
    assert decision.write_mode == "merge"
    assert decision.match_basis is not None
    assert decision.match_basis.basis is matcher_mod.MatchBasis.NATURAL_KEY
    assert decision.match_basis.object_class == "PartOfSpeech"
    assert decision.match_basis.key_value == "Adverb"
    assert decision.match_basis.target_guid == "guid-dst"


@pytest.mark.parametrize("category,fn_name", _POS_PLANNERS)
def test_plan_still_creates_when_no_destination_name_matches(
    admitted, category, fn_name,
):
    """The fallback NARROWS the create; it must not abolish it. A genuinely new
    category is still an ADD, with its source GUID preserved."""
    src = _Pos("guid-src", "Ideophone", SRC_ANAL)
    dst = _Pos("guid-dst", "Noun", TGT_ANAL)
    decision = _plan_pos(
        fn_name,
        _Handle([src], SRC_VERN, SRC_ANAL),
        _Handle([dst], TGT_VERN, TGT_ANAL),
    )

    assert isinstance(decision, PlannedAction)
    assert decision.intended_target_guid == "guid-src"


@pytest.mark.parametrize("category,fn_name", _POS_PLANNERS)
def test_plan_still_creates_into_an_empty_destination(
    admitted, category, fn_name,
):
    """The case `test_017_gold_reserved_edit_copy.py`'s
    `test_d_absent_emits_planned_action` builds -- an EMPTY candidate scope --
    which is why that pin holds unchanged across this fix rather than needing
    to be relaxed. Asserted here too, so the REASON it holds is recorded on
    this side of the change and not only in a diagnosis nobody re-reads."""
    src = _Pos("guid-src", "Noun", SRC_ANAL)
    decision = _plan_pos(
        fn_name,
        _Handle([src], SRC_VERN, SRC_ANAL),
        _Handle([], TGT_VERN, TGT_ANAL),
    )
    assert isinstance(decision, PlannedAction)


@pytest.mark.parametrize("category,fn_name", _POS_PLANNERS)
def test_plan_is_inert_while_the_roster_does_not_admit_the_class(
    not_admitted, category, fn_name,
):
    """Both halves of the basis are required on the plan side too. Off the
    roster, a same-named destination is NOT a match and the create stands --
    the fix may not smuggle in an admission 035's file did not grant."""
    src = _Pos("guid-src", "Noun", SRC_ANAL)
    dst = _Pos("guid-dst", "Noun", TGT_ANAL)
    decision = _plan_pos(
        fn_name,
        _Handle([src], SRC_VERN, SRC_ANAL),
        _Handle([dst], TGT_VERN, TGT_ANAL),
    )
    assert isinstance(decision, PlannedAction)


@pytest.mark.parametrize("category,fn_name", _POS_PLANNERS)
def test_identity_wins_on_the_plan_path_and_is_not_a_substitution(
    admitted, category, fn_name,
):
    """FR-001's ordering, on the planner. A destination holding the source GUID
    is found by `_plan_gold_reserved_edit` first, so the key is never reached
    and the decision carries no natural-key basis -- otherwise a name collision
    could restate a correct GUID match as a weaker one."""
    src = _Pos("guid-1", "Noun", SRC_ANAL)
    by_guid = _Pos("guid-1", "something else entirely", TGT_ANAL)
    by_name = _Pos("guid-other", "Noun", TGT_ANAL)
    decision = _plan_pos(
        fn_name,
        _Handle([src], SRC_VERN, SRC_ANAL),
        _Handle([by_guid, by_name], TGT_VERN, TGT_ANAL),
    )
    assert getattr(decision, "match_via", "guid") != "natural_key"
    assert getattr(decision, "match_basis", None) is None


class _OneShotPosAccessor:
    """`GetAll` yields a GENERATOR and counts how often it was asked.

    The hazard the `_phonology_simple_plan` comment already names, pinned on
    the POS path: the GUID scan consumes the scope, and a candidate list handed
    to the key step second-hand is EMPTY -- which reads as "no match" and
    creates the duplicate the step exists to prevent. The fix re-invokes the
    iterator factory rather than reusing its output, so this must match.
    """

    def __init__(self, poses):
        self._poses = list(poses)
        self.calls = 0

    def GetAll(self, recursive=False):
        self.calls += 1
        return (p for p in self._poses)


@pytest.mark.parametrize("category,fn_name", _POS_PLANNERS)
def test_a_one_shot_destination_iterator_still_matches(
    admitted, category, fn_name,
):
    src = _Pos("guid-src", "Verb", SRC_ANAL)
    target = _Handle([], TGT_VERN, TGT_ANAL)
    target.POS = _OneShotPosAccessor([_Pos("guid-dst", "Verb", TGT_ANAL)])

    decision = _plan_pos(
        fn_name, _Handle([src], SRC_VERN, SRC_ANAL), target,
    )

    assert isinstance(decision, PlannedOverwrite)
    assert decision.target_guid == "guid-dst"
    assert target.POS.calls == 2, (
        "the destination scope must be enumerated AFRESH for the key step; "
        "reusing the GUID scan's exhausted iterator is the duplicate bug"
    )


# ---------------------------------------------------------------------------
# T091, second site -- LexEntryInflType. Same shape, and LATENT.
# ---------------------------------------------------------------------------
#
# `variant_types_plan_action` carries the identical
# `_plan_gold_reserved_edit`-returns-None-then-create shape over a second
# roster-admitted, creates-on-miss class. It is closed with the same insertion,
# but honestly: its effect is UNMEASURED on the available corpus. On the pair
# that exposed the POS defect the `LexEntryInflType` row is 3 -> 4 with zero
# duplicate name groups, so the extra object's name differs and the key would
# not have fired there. These tests are the only evidence for this half.


class _InflType:
    def __init__(self, guid, name=None, ws_handle=None,
                 class_name="LexEntryInflType"):
        self.Guid = guid
        self.ClassName = class_name
        self.Name = _MultiString({ws_handle: name} if ws_handle else {})
        self.Owner = None
        self.SubPossibilitiesOS = []


class _PossibilityList:
    def __init__(self, items):
        self.PossibilitiesOS = list(items)


class _VariantHandle:
    def __init__(self, items, vern, anal):
        lex_db = type("_LexDb", (), {})()
        lex_db.VariantEntryTypesOA = _PossibilityList(items)
        lang = type("_Lang", (), {})()
        lang.LexDbOA = lex_db
        cache = type("_Cache", (), {})()
        cache.LangProject = lang
        self.Cache = cache
        self._vern = vern
        self._anal = anal

    def GetDefaultVernacularWSHandle(self):
        return self._vern

    def GetDefaultAnalysisWSHandle(self):
        return self._anal


def _plan_variant(piece, source, target):
    return cat_mod.variant_types_plan_action(
        piece, _Context(source, target), None,
    )


def test_variant_type_plan_reuses_a_same_named_inflection_type(admitted):
    """A project-local inflection type (`Class 10`, `Perfective`) is ordinary
    linguistic content whose GUIDs need not agree across projects -- which is
    exactly why the roster admits the class with `creates_on_miss=True`."""
    src = _InflType("guid-src", "Perfective", SRC_ANAL)
    dst = _InflType("guid-dst", "Perfective", TGT_ANAL)
    decision = _plan_variant(
        src,
        _VariantHandle([src], SRC_VERN, SRC_ANAL),
        _VariantHandle([dst], TGT_VERN, TGT_ANAL),
    )

    assert isinstance(decision, PlannedOverwrite)
    assert decision.category is GrammarCategory.VARIANT_TYPES
    assert decision.target_guid == "guid-dst"
    assert decision.match_basis.object_class == "LexEntryInflType"
    assert decision.match_basis.key_value == "Perfective"


def test_a_base_variant_type_is_never_keyed_under_the_inflectional_subclass(
    admitted,
):
    """WHY THE LITERAL CLASS NAME IS SAFE HERE. The variant-entry-types walk
    yields base `LexEntryType` possibilities alongside `LexEntryInflType` ones,
    and the roster admits only the subclass. `natural_key_eligibility` refuses
    the base class on BOTH sides, so a base type is neither keyed nor offered
    as a candidate -- it still creates, under its own GUID."""
    src = _InflType("guid-src", "Dialectal Variant", SRC_ANAL,
                    class_name="LexEntryType")
    dst = _InflType("guid-dst", "Dialectal Variant", TGT_ANAL,
                    class_name="LexEntryType")
    decision = _plan_variant(
        src,
        _VariantHandle([src], SRC_VERN, SRC_ANAL),
        _VariantHandle([dst], TGT_VERN, TGT_ANAL),
    )
    assert isinstance(decision, PlannedAction)


def test_an_inflection_type_never_matches_a_same_named_base_type(admitted):
    """The subclass restriction is not decoration. An inflection type must not
    be silently merged onto a base variant type that happens to share a
    name."""
    src = _InflType("guid-src", "Irregularly Inflected Form", SRC_ANAL)
    dst = _InflType("guid-dst", "Irregularly Inflected Form", TGT_ANAL,
                    class_name="LexEntryType")
    decision = _plan_variant(
        src,
        _VariantHandle([src], SRC_VERN, SRC_ANAL),
        _VariantHandle([dst], TGT_VERN, TGT_ANAL),
    )
    assert isinstance(decision, PlannedAction)
