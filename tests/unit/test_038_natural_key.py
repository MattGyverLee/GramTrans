"""Feature 038 (transfer fidelity gaps) -- Phase 4 / US1 natural-key matching.

Covers **T026** (the matching ORDER) and **T027** (comparison STRICTNESS and
writing-system SCOPE), plus the per-class eligibility rules T030 implements.

THESE TESTS ARE WRITTEN TO FAIL. T029/T030 have not landed, and cannot land
until T028's external gate closes (035 must append 038's six `proposed_entries`
to `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json` on
`main`; as of this commit that file still carries only its original three
entries). They exist now so the surface below is a contract T029/T030 are
written against, rather than a shape invented after the fact.

The surface they pin, all in `gramtrans.Lib.matcher`
----------------------------------------------------

`NaturalKeyBinding` (frozen)
    `object_class`, `key_fn_id`, `scope_fn_id`, `ws_scope`, `creates_on_miss`.
    The EXECUTABLE half of a roster row. `data-model.md` marks `key_fn_id` /
    `scope_fn_id` as "038 adds", and 038 adds them HERE, in engine code -- not
    to 035's file, which T028 appends to verbatim and which therefore never
    carries them.

`NATURAL_KEY_BINDINGS: Dict[str, NaturalKeyBinding]`
    The six classes FR-005 admits. A binding is necessary but NOT sufficient:
    a class has a natural-key basis only when 035's roster file admits it AND
    a binding exists to execute it. Either half alone yields no basis, so a
    binding can never fabricate an admission the roster did not grant, and an
    admitted-but-unexecutable row never matches on a guessed key.

`NATURAL_KEY_FNS: Dict[str, Callable]`
    `key_fn_id -> (obj, ws_handle) -> Optional[str]`
`NATURAL_KEY_SCOPE_FNS: Dict[str, Callable]`
    `scope_fn_id -> (target) -> Iterable[obj]`

`natural_key_eligibility(object_class, obj) -> str`
    `""` when the object may be keyed at all; otherwise one of
    `KEY_INELIGIBLE_REASONS`. Never raises. Decided BEFORE candidate counting,
    so an ineligible object is not even an ambiguity.

`natural_key_for(object_class, obj, ws_handle) -> Optional[str]`
    The exact key string, or None for "this object HAS no key".

`resolve_match(object_class, source_obj, candidates, *, ws_handles,
               identity_remap=None, key_fn=None) -> MatchDecision`
    THE ordering function. `candidates` is the destination scope for the class
    (production resolves it through `NATURAL_KEY_SCOPE_FNS`; tests pass it
    directly). `key_fn` is an injection hook mirroring `lookup_target`'s
    existing `fingerprint_fn=`.

`MatchDecision` (frozen)
    `record: MatchBasisRecord`, `target_obj`, `enrich: bool`,
    `ineligible_reason: str`, `may_create: bool`, `parent_divergence: str`.

`NaturalKeyAmbiguityError`
    Raised -- never returned -- when an eligible key resolves to more than one
    destination candidate. The message names the class, the scope and the key.

Why `enrich` is on the decision at all: a matched GUID is a LINK, not a SKIP
(defect G3, data-model.md:209-213). Every matched object must go on to
field-identity comparison, so the decision says so explicitly rather than
leaving "matched" to be read as "done".
"""
import json
import pathlib
import unicodedata

import pytest

from gramtrans.Lib import census as census_mod
from gramtrans.Lib import matcher as matcher_mod
from gramtrans.Lib.matcher import (
    natural_key_roster_entry_for,
    reset_natural_key_roster_cache,
)
from gramtrans.Lib.models import MatchBasis

#: Every T029/T030 symbol is fetched through `_m()` at CALL time rather than
#: imported at module level, so this module still COLLECTS while the surface
#: is missing. A collection error would abort the whole pytest session and
#: hide every other test on the branch; these tests must be red on their own
#: and only on their own, for as long as T028's external gate stays shut.
_MISSING = object()


def _m(name):
    """One symbol from the T029/T030 matcher surface, or a precise failure."""
    value = getattr(matcher_mod, name, _MISSING)
    if value is _MISSING:
        pytest.fail(
            "gramtrans.Lib.matcher has no " + repr(name) + " -- the US1 "
            "natural-key matching surface (T029/T030) has not landed. It is "
            "gated on T028: 035 must first append 038's six proposed entries "
            "to specs/035-fullsweep-fidelity/contracts/"
            "natural-key-identity-roster.json on main."
        )
    return value

# ---------------------------------------------------------------------------
# The six classes FR-005 admits, and where their contract text lives
# ---------------------------------------------------------------------------

ADMITTED = (
    "PhPhoneme",
    "PhNCSegments",
    "PhNCFeatures",
    "PartOfSpeech",
    "MoMorphType",
    "LexEntryInflType",
)

#: Only `MoMorphType` is forbidden to create on an unmatched key: FLEx treats
#: the morph-types list as project-independent fixed content, so minting one
#: would add an object the canonical list does not contain (roster extension,
#: `MoMorphType.key_scoping_note`). `LexEntryInflType` is the explicit
#: opposite -- a project-local inflection type is ordinary linguistic content
#: and creating it IS correct (FR-007, GUID-preserving).
CREATES_ON_MISS = {
    "PhPhoneme": True,
    "PhNCSegments": True,
    "PhNCFeatures": True,
    "PartOfSpeech": True,
    "MoMorphType": False,
    "LexEntryInflType": True,
}

#: Opposite directions on the same roster, measured: phonemes key on the
#: default VERNACULAR (97/97 there, only 44/97 in the analysis WS); every
#: other admitted class keys on the default ANALYSIS WS (0/121 natural
#: classes and 0/51 categories carry a vernacular name).
WS_SCOPES = {
    "PhPhoneme": census_mod.WS_SCOPE_VERNACULAR,
    "PhNCSegments": census_mod.WS_SCOPE_ANALYSIS,
    "PhNCFeatures": census_mod.WS_SCOPE_ANALYSIS,
    "PartOfSpeech": census_mod.WS_SCOPE_ANALYSIS,
    "MoMorphType": census_mod.WS_SCOPE_ANALYSIS,
    "LexEntryInflType": census_mod.WS_SCOPE_ANALYSIS,
}

SUBCLASS_RESTRICTED = ("PhNCSegments", "PhNCFeatures", "LexEntryInflType")

#: U+00A0. Spelled as an escape because an invisible character in a test
#: fixture is a maintenance trap, and this one carries the assertion.
NBSP = "\u00a0"

VERN = "ws-handle-vernacular"
ANAL = "ws-handle-analysis"
WS_HANDLES = {
    census_mod.WS_SCOPE_VERNACULAR: VERN,
    census_mod.WS_SCOPE_ANALYSIS: ANAL,
}

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ROSTER_035 = (
    REPO_ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"
    / "natural-key-identity-roster.json"
)
EXTENSION_038 = (
    REPO_ROOT / "specs" / "038-transfer-fidelity-gaps" / "contracts"
    / "natural-key-roster-extension.json"
)


# ---------------------------------------------------------------------------
# Pure-Python LCM fakes (matcher imports no LCM; see its module docstring)
# ---------------------------------------------------------------------------

class _Ts:
    """Fake ITsString. `.Text` is None for an unset alt, as LCM returns."""

    def __init__(self, text):
        self.Text = text


class _MultiString:
    """Fake IMultiUnicode: `get_String(ws_handle)` -> `_Ts`."""

    def __init__(self, by_handle):
        self._by_handle = dict(by_handle)

    def get_String(self, ws_handle):
        return _Ts(self._by_handle.get(ws_handle))


class _Obj:
    """One destination or source object: GUID, class name, scoped Name, owner."""

    def __init__(self, guid, class_name, vern=None, anal=None, owner=None):
        self.Guid = guid
        self.ClassName = class_name
        self.Name = _MultiString({VERN: vern, ANAL: anal})
        self.Owner = owner


def _named(object_class, guid, name, owner=None):
    """An object of `object_class` whose name sits in ITS OWN scoped WS."""
    if WS_SCOPES[object_class] == census_mod.WS_SCOPE_VERNACULAR:
        return _Obj(guid, object_class, vern=name, owner=owner)
    return _Obj(guid, object_class, anal=name, owner=owner)


class _Exploding:
    """A key function that fails the test if it is ever called."""

    def __init__(self):
        self.calls = []

    def __call__(self, obj, ws_handle):
        self.calls.append((obj, ws_handle))
        raise AssertionError(
            "the natural key was computed on a path that had already matched "
            "by identity -- FR-001 makes identity authoritative and the key a "
            "fallback consulted ONLY when identity finds nothing"
        )


class _Recording:
    """A key function that records its calls and returns a fixed key."""

    def __init__(self, key):
        self.key = key
        self.calls = []

    def __call__(self, obj, ws_handle):
        self.calls.append((obj, ws_handle))
        return self.key


# ---------------------------------------------------------------------------
# Roster fixtures -- the file half of the two-halves admission rule
# ---------------------------------------------------------------------------

def _roster_with_038_entries(tmp_path):
    """035's real file with 038's six proposed entries appended, as T028 will
    leave it.

    Written to a temp path so these tests neither depend on nor anticipate
    035's commit: the shipped file's contents stay 035's business.
    """
    base = json.loads(ROSTER_035.read_text(encoding="utf-8"))
    ext = json.loads(EXTENSION_038.read_text(encoding="utf-8"))
    base["entries"] = list(base["entries"]) + list(ext["proposed_entries"])
    path = tmp_path / "natural-key-identity-roster.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return str(path)


@pytest.fixture
def appended_roster(tmp_path):
    """Point the module accessor at a roster that HAS the six entries."""
    reset_natural_key_roster_cache(_roster_with_038_entries(tmp_path))
    yield
    reset_natural_key_roster_cache(None)


@pytest.fixture
def original_roster():
    """Point the module accessor at the real, not-yet-appended file."""
    reset_natural_key_roster_cache(str(ROSTER_035))
    yield
    reset_natural_key_roster_cache(None)


# ===========================================================================
# T026 -- the matching order
# ===========================================================================

def test_identity_hit_never_computes_the_key(appended_roster):
    """GUID found -> IDENTITY, and the key is NEVER computed.

    Not an optimisation. Computing the key on an identity hit is how a name
    collision gets a chance to overwrite an object a GUID had already
    correctly identified (data-model.md, the MatchBasis ordering contract).
    """
    src = _named("PhPhoneme", "guid-p1", "a")
    dst = _named("PhPhoneme", "guid-p1", "completely-different-name")
    boom = _Exploding()

    decision = _m("resolve_match")(
        "PhPhoneme", src, [dst], ws_handles=WS_HANDLES, key_fn=boom,
    )

    assert boom.calls == []
    assert decision.record.basis is MatchBasis.IDENTITY
    assert decision.target_obj is dst
    assert decision.record.target_guid == "guid-p1"
    assert decision.record.candidate_count == 1
    # An IDENTITY record carries no key -- there was no key.
    assert decision.record.key_expression == ""
    assert decision.record.key_value == ""


def test_identity_hit_enriches_rather_than_skipping_the_whole_object(
    appended_roster,
):
    """A matched GUID is a LINK, not a SKIP (defect G3).

    `enrich` True is the decision's statement that field-identity comparison
    still has to happen. The pre-038 behaviour -- read "GUID already present"
    as "nothing to do" -- is what left matched categories missing whole owned
    collections.
    """
    src = _named("PartOfSpeech", "guid-pos-1", "Noun")
    dst = _named("PartOfSpeech", "guid-pos-1", "Noun")

    decision = _m("resolve_match")(
        "PartOfSpeech", src, [dst], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.IDENTITY
    assert decision.enrich is True
    assert decision.may_create is False


def test_identity_remap_hit_is_identity_not_natural_key(appended_roster):
    """A prior run's remap entry is IDENTITY (FR-001), not a substitution."""
    src = _named("PhPhoneme", "guid-src", "a")
    dst = _named("PhPhoneme", "guid-tgt", "a")

    decision = _m("resolve_match")(
        "PhPhoneme", src, [dst], ws_handles=WS_HANDLES,
        identity_remap={"guid-src": "guid-tgt"},
        key_fn=_Exploding(),
    )

    assert decision.record.basis is MatchBasis.IDENTITY
    assert decision.target_obj is dst
    assert decision.enrich is True


def test_identity_miss_computes_the_key_exactly_once(appended_roster):
    """Not found by GUID -> compute the key, on the SOURCE object, in the
    class's own writing system."""
    src = _named("PhPhoneme", "guid-src", "a")
    dst = _named("PhPhoneme", "guid-other", "a")
    keyfn = _Recording("a")

    decision = _m("resolve_match")(
        "PhPhoneme", src, [dst], ws_handles=WS_HANDLES, key_fn=keyfn,
    )

    assert [obj for obj, _ in keyfn.calls][:1] == [src]
    assert keyfn.calls[0][1] == VERN, "PhPhoneme keys on the default vernacular"
    assert decision.record.basis is MatchBasis.NATURAL_KEY


def test_exactly_one_candidate_reuses_and_records_the_substitution(
    appended_roster,
):
    """Exactly 1 candidate -> reuse it, and say so as an IDENTITY-SUBSTITUTION.

    `basis is NATURAL_KEY` IS the substitution record: data-model.md makes
    every NATURAL_KEY record increment `CategoryReport.identity_substitution`
    (FR-187 / FR-006), so a reader can always tell "found by GUID" from
    "found by name because the GUID was absent".
    """
    src = _named("PartOfSpeech", "guid-src", "Adverb")
    dst = _named("PartOfSpeech", "guid-dst", "Adverb")

    decision = _m("resolve_match")(
        "PartOfSpeech", src, [dst], ws_handles=WS_HANDLES,
    )

    rec = decision.record
    assert rec.basis is MatchBasis.NATURAL_KEY
    assert rec.source_guid == "guid-src"
    assert rec.target_guid == "guid-dst"
    assert rec.key_value == "Adverb"
    assert rec.candidate_count == 1
    # The key EXPRESSION is the roster's own text, not a paraphrase.
    assert rec.key_expression == (
        natural_key_roster_entry_for("PartOfSpeech").natural_key
    )
    assert decision.target_obj is dst
    assert decision.enrich is True
    assert decision.may_create is False


@pytest.mark.parametrize("object_class", ADMITTED)
def test_zero_candidates_never_matches_and_defers_to_the_class_create_rule(
    appended_roster, object_class,
):
    """0 candidates -> FR-007: create GUID-preserving, or report.

    `MoMorphType` is the one class forbidden to create; every other admitted
    class creates GUID-preserving. Both outcomes are reported -- neither is a
    silent drop.
    """
    src = _named(object_class, "guid-src", "SomethingNew")

    decision = _m("resolve_match")(
        object_class, src, [], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.NONE
    assert decision.record.target_guid == ""
    assert decision.record.candidate_count == 0
    assert decision.target_obj is None
    assert decision.enrich is False
    assert decision.ineligible_reason == ""
    assert decision.may_create is CREATES_ON_MISS[object_class]


def test_more_than_one_candidate_is_a_harness_error_naming_class_scope_and_key(
    appended_roster,
):
    """> 1 candidate -> `harness_error`. Measured: 66 collisions in 113
    natural classes, so this is the common case, not a corner."""
    src = _named("PhNCSegments", "guid-src", "Nasals")
    first = _named("PhNCSegments", "guid-a", "Nasals")
    second = _named("PhNCSegments", "guid-b", "Nasals")

    with pytest.raises(_m("NaturalKeyAmbiguityError")) as excinfo:
        _m("resolve_match")("PhNCSegments", src, [first, second], ws_handles=WS_HANDLES)

    message = str(excinfo.value)
    assert "PhNCSegments" in message
    assert "Nasals" in message
    assert _m("NATURAL_KEY_BINDINGS")["PhNCSegments"].scope_fn_id in message


def test_ambiguity_is_never_a_pick_and_never_a_substitution_record(
    appended_roster,
):
    """The ambiguous path returns NOTHING -- no decision, so no pick, and no
    IDENTITY-SUBSTITUTION record to inflate the count with a guess."""
    src = _named("MoMorphType", "guid-src", "prefix")
    dupes = [
        _named("MoMorphType", "guid-a", "prefix"),
        _named("MoMorphType", "guid-b", "prefix"),
        _named("MoMorphType", "guid-c", "prefix"),
    ]

    with pytest.raises(_m("NaturalKeyAmbiguityError")):
        _m("resolve_match")("MoMorphType", src, dupes, ws_handles=WS_HANDLES)


def test_ambiguity_does_not_fire_when_identity_already_matched(
    appended_roster,
):
    """Identity is authoritative: duplicate names in the destination cannot
    turn a clean GUID match into a harness error."""
    src = _named("MoMorphType", "guid-src", "prefix")
    hit = _named("MoMorphType", "guid-src", "prefix")
    other = _named("MoMorphType", "guid-b", "prefix")

    decision = _m("resolve_match")(
        "MoMorphType", src, [hit, other], ws_handles=WS_HANDLES,
        key_fn=_Exploding(),
    )

    assert decision.record.basis is MatchBasis.IDENTITY
    assert decision.target_obj is hit


def test_class_absent_from_the_roster_degrades_to_guid_only(original_roster):
    """A class 035's file does not admit has NO natural-key basis.

    It degrades to the pre-038 GUID-only behaviour: no key computed, no
    match, no raise. `natural_key_roster_entry_for` returning None is a
    normal answer, not an error (R1).
    """
    assert natural_key_roster_entry_for("PhPhoneme") is None

    src = _named("PhPhoneme", "guid-src", "a")
    dst = _named("PhPhoneme", "guid-dst", "a")

    decision = _m("resolve_match")(
        "PhPhoneme", src, [dst], ws_handles=WS_HANDLES, key_fn=_Exploding(),
    )

    assert decision.record.basis is MatchBasis.NONE
    assert decision.ineligible_reason == _m("KEY_INELIGIBLE_NOT_ADMITTED")
    assert decision.target_obj is None
    assert decision.enrich is False


def test_a_binding_alone_never_admits_a_class(original_roster):
    """Both halves are required. A binding exists for all six classes, but
    with the original three-entry roster none of them has a basis -- so
    engine code can never fabricate an admission the roster did not grant."""
    for object_class in ADMITTED:
        assert object_class in _m("NATURAL_KEY_BINDINGS")
        assert natural_key_roster_entry_for(object_class) is None


def test_a_roster_row_alone_never_admits_a_class(original_roster):
    """`WfiWordform` is admitted by 035's file and has a census key
    definition, but 038 binds no key function for it -- so it has no
    natural-key basis here. An unexecutable row must not match on a guess."""
    assert "WfiWordform" not in _m("NATURAL_KEY_BINDINGS")
    assert natural_key_roster_entry_for("WfiWordform") is None


# ===========================================================================
# T030 -- per-class eligibility, decided BEFORE candidate counting
# ===========================================================================

@pytest.mark.parametrize("object_class", SUBCLASS_RESTRICTED)
def test_subclass_restricted_classes_never_match_across_the_subclass(
    appended_roster, object_class,
):
    """`PhNCSegments` must never match `PhNCFeatures` (and vice versa), and
    `LexEntryInflType` must never match `LexEntryType`, even on an identical
    name."""
    other = {
        "PhNCSegments": "PhNCFeatures",
        "PhNCFeatures": "PhNCSegments",
        "LexEntryInflType": "LexEntryType",
    }[object_class]

    src = _named(object_class, "guid-src", "Shared Name")
    wrong = _Obj("guid-dst", other, vern="Shared Name", anal="Shared Name")

    decision = _m("resolve_match")(
        object_class, src, [wrong], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.NONE
    assert decision.record.candidate_count == 0
    assert decision.target_obj is None
    assert _m("natural_key_eligibility")(object_class, wrong) == (
        _m("KEY_INELIGIBLE_SUBCLASS_MISMATCH")
    )


def test_auto_generated_natural_class_names_are_ineligible(appended_roster):
    """`Created automatically for rule "<rule>"` names the RULE, not the
    class. Two objects sharing one are not the same linguistic object.

    Ineligibility is decided BEFORE candidate counting, so this is reported
    under its own outcome and is NOT an ambiguity -- 66 of 113 measured
    objects collide precisely on such labels.
    """
    label = 'Created automatically for rule "Nasal Assimilation"'
    src = _named("PhNCFeatures", "guid-src", label)
    first = _named("PhNCFeatures", "guid-a", label)
    second = _named("PhNCFeatures", "guid-b", label)

    # The handle is passed because the auto-label is checked on the SCOPED
    # name and only on it. Probing every alt instead would exclude a class
    # whose scoped name is a real linguist name while some other writing
    # system happens to hold a rule label -- a narrowing the roster does not
    # authorise. `_MultiString` exposes only `get_String(ws_handle)`, so a
    # handle-free read is not available to any implementation either.
    assert _m("natural_key_eligibility")("PhNCFeatures", src, ANAL) == (
        _m("KEY_INELIGIBLE_AUTO_GENERATED")
    )

    decision = _m("resolve_match")(
        "PhNCFeatures", src, [first, second], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.NONE
    assert decision.ineligible_reason == _m("KEY_INELIGIBLE_AUTO_GENERATED")
    assert decision.target_obj is None
    assert decision.enrich is False
    # Left to the owning rule's own transfer -- not created here by key.
    assert decision.may_create is False


def test_ineligible_never_creates_by_key(appended_roster):
    """Ineligible or not computable -> report, no match, NO create-by-key --
    even for a class that otherwise creates on a miss."""
    unkeyable = _Obj("guid-src", "PartOfSpeech")  # no Name in any WS

    decision = _m("resolve_match")(
        "PartOfSpeech", unkeyable, [], ws_handles=WS_HANDLES,
    )

    assert CREATES_ON_MISS["PartOfSpeech"] is True
    assert decision.record.basis is MatchBasis.NONE
    assert decision.ineligible_reason == _m("KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS")
    assert decision.may_create is False


def test_part_of_speech_keys_project_wide_ignoring_the_parent(appended_roster):
    """The owning parent is NOT part of the key: catalog category
    `093264d7-...` is depth-1 in one project and depth-2 in another.

    The parent is still recorded, and the divergence reported.
    """
    src_parent = _Obj("guid-parent-src", "PartOfSpeech", anal="Verb")
    dst_parent = _Obj("guid-parent-dst", "PartOfSpeech", anal="Adjective")
    src = _named("PartOfSpeech", "guid-src", "Demonstrative", owner=src_parent)
    dst = _named("PartOfSpeech", "guid-dst", "Demonstrative", owner=dst_parent)

    decision = _m("resolve_match")(
        "PartOfSpeech", src, [dst], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.NATURAL_KEY
    assert decision.target_obj is dst
    assert decision.parent_divergence != "", (
        "a matched category is NOT evidence that the two hierarchies agree"
    )
    assert "guid-parent-src" in decision.parent_divergence
    assert "guid-parent-dst" in decision.parent_divergence
    # matcher decides; it never writes. The destination keeps its own parent.
    assert dst.Owner is dst_parent


def test_part_of_speech_parent_agreement_reports_no_divergence(
    appended_roster,
):
    shared = _Obj("guid-parent", "PartOfSpeech", anal="Verb")
    src = _named("PartOfSpeech", "guid-src", "Demonstrative", owner=shared)
    dst = _named("PartOfSpeech", "guid-dst", "Demonstrative", owner=shared)

    decision = _m("resolve_match")(
        "PartOfSpeech", src, [dst], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.NATURAL_KEY
    assert decision.parent_divergence == ""


def test_lex_entry_infl_type_parent_divergence_is_reported(appended_roster):
    """14 of 15 measured inflection types sit under `Irregularly Inflected
    Form`, so a parent divergence here is anomalous rather than routine."""
    src_parent = _Obj(
        "guid-iif", "LexEntryType", anal="Irregularly Inflected Form",
    )
    dst_parent = _Obj("guid-list", "CmPossibilityList", anal="Variant Types")
    src = _named("LexEntryInflType", "guid-src", "Past", owner=src_parent)
    dst = _named("LexEntryInflType", "guid-dst", "Past", owner=dst_parent)

    decision = _m("resolve_match")(
        "LexEntryInflType", src, [dst], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.NATURAL_KEY
    assert decision.parent_divergence != ""


def test_every_ineligibility_token_is_in_the_declared_vocabulary():
    """The reasons are a closed set, so a report can enumerate them."""
    assert _m("KEY_INELIGIBLE_REASONS") == frozenset({
        _m("KEY_INELIGIBLE_NOT_ADMITTED"),
        _m("KEY_INELIGIBLE_SUBCLASS_MISMATCH"),
        _m("KEY_INELIGIBLE_AUTO_GENERATED"),
        _m("KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS"),
    })


# ===========================================================================
# T027 -- comparison strictness and writing-system scope
# ===========================================================================

@pytest.mark.parametrize("object_class", ADMITTED)
def test_binding_names_the_measured_writing_system_scope(object_class):
    """The scope differs BY CLASS and in OPPOSITE directions. It is stored
    per class rather than assumed once, and must not drift from the census
    definition measuring the same thing."""
    binding = _m("NATURAL_KEY_BINDINGS")[object_class]
    assert binding.object_class == object_class
    assert binding.ws_scope == WS_SCOPES[object_class]
    assert binding.ws_scope == (
        census_mod.NATURAL_KEY_DEFINITIONS[object_class].ws_scope
    ), "matcher and census must not hold two different keys for one class"
    assert binding.creates_on_miss is CREATES_ON_MISS[object_class]
    assert binding.key_fn_id in _m("NATURAL_KEY_FNS")
    assert binding.scope_fn_id in _m("NATURAL_KEY_SCOPE_FNS")


def test_the_six_admitted_classes_are_exactly_the_bound_ones():
    assert set(_m("NATURAL_KEY_BINDINGS")) == set(ADMITTED)


@pytest.mark.parametrize("object_class", ADMITTED)
def test_key_is_read_only_from_the_classes_own_writing_system(object_class):
    """A name in the OTHER default writing system is not a key.

    Never silently fall back: matching a secondary vernacular would have
    fabricated 16 matches on `Yi Sichuan` alone.
    """
    scope = WS_SCOPES[object_class]
    is_vern = scope == census_mod.WS_SCOPE_VERNACULAR
    scoped_handle = VERN if is_vern else ANAL

    if is_vern:
        obj_right = _Obj("guid-1", object_class, vern="Keyed")
        obj_wrong = _Obj("guid-2", object_class, anal="Keyed")
    else:
        obj_right = _Obj("guid-1", object_class, anal="Keyed")
        obj_wrong = _Obj("guid-2", object_class, vern="Keyed")

    assert _m("natural_key_for")(object_class, obj_right, scoped_handle) == "Keyed"
    assert _m("natural_key_for")(object_class, obj_wrong, scoped_handle) is None


@pytest.mark.parametrize("object_class", ADMITTED)
@pytest.mark.parametrize(
    ("source_name", "target_name", "why"),
    [
        ("Nasals", "nasals", "case-sensitive: no case folding"),
        ("Nasals", "NASALS", "case-sensitive: no upper-casing"),
        ("Nasals", "Nasal Consonants", "measured as three distinct classes"),
        ("Nasals", " Nasals", "no leading-whitespace trimming"),
        ("Nasals", "Nasals ", "no trailing-whitespace trimming"),
        ("Nasals", "Nasals" + NBSP, "a no-break space is not a space"),
    ],
)
def test_comparison_is_exact_for_every_admitted_class(
    appended_roster, object_class, source_name, target_name, why,
):
    src = _named(object_class, "guid-src", source_name)
    dst = _named(object_class, "guid-dst", target_name)

    decision = _m("resolve_match")(
        object_class, src, [dst], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.NONE, why
    assert decision.record.candidate_count == 0
    assert decision.target_obj is None


@pytest.mark.parametrize("object_class", ADMITTED)
def test_no_unicode_normalisation_is_applied(appended_roster, object_class):
    """NFC and NFD spellings of one grapheme are DIFFERENT keys.

    A vernacular phoneme inventory is exactly where composed and decomposed
    spellings coexist, so normalising here would silently merge two distinct
    objects.
    """
    composed = unicodedata.normalize("NFC", "\u00e1")     # 1 codepoint
    decomposed = unicodedata.normalize("NFD", "\u00e1")   # a + combining acute
    assert composed != decomposed

    src = _named(object_class, "guid-src", composed)
    dst = _named(object_class, "guid-dst", decomposed)

    decision = _m("resolve_match")(
        object_class, src, [dst], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.NONE
    assert _m("natural_key_for")(
        object_class, src, WS_HANDLES[WS_SCOPES[object_class]],
    ) == composed


@pytest.mark.parametrize("object_class", ADMITTED)
def test_an_object_with_no_name_in_the_scoped_ws_has_no_key(object_class):
    ws_handle = WS_HANDLES[WS_SCOPES[object_class]]
    assert _m("natural_key_for")(
        object_class, _Obj("g", object_class), ws_handle,
    ) is None
    assert _m("natural_key_for")(
        object_class, _named(object_class, "g", ""), ws_handle,
    ) is None


@pytest.mark.parametrize("object_class", ADMITTED)
def test_an_empty_key_never_matches_another_empty_key(
    appended_roster, object_class,
):
    """Two unnamed objects are not duplicates of each other. This is the
    measured case, not a hypothetical: `Ejagham Mini` holds a category
    (`400c5e75-...`) with no Name in either default writing system.
    """
    src = _Obj("guid-src", object_class)
    dst = _Obj("guid-dst", object_class)

    decision = _m("resolve_match")(
        object_class, src, [dst], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.NONE
    assert decision.target_obj is None
    assert decision.ineligible_reason == _m("KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS")
    assert decision.may_create is False


@pytest.mark.parametrize("object_class", ADMITTED)
def test_a_named_source_never_matches_an_unnamed_destination(
    appended_roster, object_class,
):
    src = _named(object_class, "guid-src", "Named")
    dst = _Obj("guid-dst", object_class)

    decision = _m("resolve_match")(
        object_class, src, [dst], ws_handles=WS_HANDLES,
    )

    assert decision.record.basis is MatchBasis.NONE
    assert decision.record.candidate_count == 0


def test_key_not_computable_when_the_scoped_ws_handle_is_absent(
    appended_roster,
):
    """A phoneme key is not computable unless the pre-run writing-system
    mapping produced a source -> target default vernacular. Report it; never
    fall back to another writing system."""
    src = _named("PhPhoneme", "guid-src", "a")
    dst = _named("PhPhoneme", "guid-dst", "a")

    decision = _m("resolve_match")(
        "PhPhoneme", src, [dst],
        ws_handles={census_mod.WS_SCOPE_ANALYSIS: ANAL},  # no vernacular
    )

    assert decision.record.basis is MatchBasis.NONE
    assert decision.ineligible_reason == _m("KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS")
    assert decision.target_obj is None
    assert decision.may_create is False
