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


# ---------------------------------------------------------------------------
# T092 -- the seam had zero production callers, and four production BYPASSES
# ---------------------------------------------------------------------------
#
# T092 asked whether this seam earns its callers or should be deleted, on the
# grounds that "a seam with no callers and no plan to acquire them is dead code
# that reads as coverage". The measurement below is the answer, and it is not
# the one the filing's framing invites.
#
# `plan_match_decision`'s only importer is this file -- that half of T092 is
# confirmed. But the question it answers is being answered four more times, in
# production, by open-coded calls straight to `matcher.resolve_match`:
#
#   * `_match_collection_child`            (T044) -- collection-scoped
#     candidates by design, plus a GUID-only fallback for a child that cannot
#     be keyed. Takes `ws_handles` / `source_ws_handles` ALREADY RESOLVED.
#   * `_resolve_target_pos_by_natural_key` (T032) -- candidates from a
#     recursive `_iter_pos` walk rather than the class's registered scope
#     function, and the only site that reports `parent_divergence`.
#   * `_process_referent_by_natural_key`   -- resolves candidates through
#     `NATURAL_KEY_SCOPE_FNS[binding.scope_fn_id]`, i.e. it reproduces the
#     seam's own candidate branch line for line, MINUS the `_log.warning` the
#     seam emits when the scope cannot be enumerated. It also converts
#     `NaturalKeyAmbiguityError` into "unresolved" where the seam propagates it
#     deliberately, so an ambiguous key reaches the operator at one site and is
#     swallowed at the other.
#   * `_plan_natural_key_match`            -- caller-supplied `target_iter`,
#     and the only site that builds a `PlannedOverwrite` from the decision.
#
# So the seam is BYPASSED, not unwanted. Its own docblock exists because
# "three implementations of one question" is how the two opposite failure modes
# 038 removes get reintroduced; the measured count is four, and one of the four
# has already lost the seam's enumeration-failure report. Deleting the seam
# would ratify the divergence rather than end it -- so the answer to "does the
# seam earn its callers" is yes, on evidence, and T092 does not close by
# deleting either the seam or this file's tests.
#
# WHY THE ROUTING IS NOT DONE HERE. T092 says it plainly: pointing the plan
# paths through the seam is a live-behaviour change across every category that
# plans a roster-admitted class, and needs its own census. Two of the four
# sites cannot even reach the seam today -- it takes a `RunContext` and they
# have no `context` parameter at all. That split is asserted below, because it
# is the scope the routing task inherits, and it must go red if it moves.
#
# What T092 closes with instead: the count stops growing. A NEW open-coded
# `resolve_match` call in production fails `test_no_new_production_site_
# bypasses_the_seam`, in the idiom T094 used for `_resolve_target_pos`.

_SRC_DIR_T092 = REPO_ROOT / "src" / "gramtrans"

#: Every production function that calls `matcher.resolve_match` directly.
#: `plan_match_decision` is the seam itself; the four `categories.py` entries
#: are the bypasses T092 measured. Adding a name here is a deliberate act that
#: says "this site answers the match question on its own" -- which after T092
#: needs a reason in the commit, not a green suite.
_APPROVED_RESOLVE_MATCH_SITES = {
    ("preview.py", "plan_match_decision"),
    ("categories.py", "_match_collection_child"),
    ("categories.py", "_resolve_target_pos_by_natural_key"),
    ("categories.py", "_process_referent_by_natural_key"),
    ("categories.py", "_plan_natural_key_match"),
}

#: The two bypasses that DO hold a `RunContext`, and could therefore be routed
#: through the seam without a signature change. This is the routing task's
#: reachable scope; the other two need a handle-pair entry point first.
_CONTEXT_BEARING_BYPASSES = {
    ("categories.py", "_process_referent_by_natural_key"),
    ("categories.py", "_plan_natural_key_match"),
}


def _resolve_match_call_sites():
    """`{(file, enclosing function): [param names]}` for every production
    call to `resolve_match`.

    Read from the source with `ast`, not from the call graph: a site reachable
    only with a live LCM host is still visible here, which is the whole reason
    T094 pinned its sweep this way rather than per site. Keyed by enclosing
    function name rather than line number, so the pin survives an edit above it.
    """
    import ast

    out = {}
    for path in sorted(_SRC_DIR_T092.rglob("*.py")):
        if path.name == "matcher.py":
            continue  # where `resolve_match` is DEFINED, not called
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                fn = call.func
                name = (
                    fn.attr if isinstance(fn, ast.Attribute)
                    else fn.id if isinstance(fn, ast.Name)
                    else None
                )
                if name != "resolve_match":
                    continue
                args = node.args
                params = [
                    a.arg for a in
                    (args.posonlyargs + args.args + args.kwonlyargs)
                ]
                out[(path.name, node.name)] = params
    return out


def _seam_call_sites():
    """Production files containing a CALL to `plan_match_decision`.

    The seam's own `def` is skipped; a call inside the seam would be
    recursion, not a caller.
    """
    import ast

    callers = set()
    for path in sorted(_SRC_DIR_T092.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "plan_match_decision" not in text:
            continue
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = (
                fn.attr if isinstance(fn, ast.Attribute)
                else fn.id if isinstance(fn, ast.Name)
                else None
            )
            if name == "plan_match_decision":
                callers.add(path.name)
    return callers


def test_no_new_production_site_bypasses_the_seam():
    """T092's claim, as a fact about the tree rather than a commit message.

    The seam exists so that Preview and Move answer "which destination object
    is this?" once. Every additional open-coded `resolve_match` call is another
    place that answer can drift -- and `_process_referent_by_natural_key`
    already drifted, losing the seam's warning on an unenumerable scope and
    swallowing the ambiguity error the seam propagates. A new one arrives
    silently, so it is pinned structurally.
    """
    found = set(_resolve_match_call_sites())
    unapproved = sorted(found - _APPROVED_RESOLVE_MATCH_SITES)
    assert unapproved == [], (
        "these production sites answer the plan-time match question without "
        "going through `preview.plan_match_decision`, and were not among the "
        "four T092 measured: %r" % (unapproved,)
    )
    vanished = sorted(_APPROVED_RESOLVE_MATCH_SITES - found)
    assert vanished == [], (
        "these sites no longer call `resolve_match`; if one was ROUTED through "
        "the seam, drop it from `_APPROVED_RESOLVE_MATCH_SITES` in the same "
        "commit so the list keeps meaning what it says: %r" % (vanished,)
    )


def test_the_pin_can_see_every_site_t092_measured():
    """Guard against the pin above passing because it found nothing.

    An `ast` walk that stopped matching would make the exclusion test
    vacuously green -- the failure mode a source-reading test actually has,
    and the reason T094 paired its pin with a floor.
    """
    sites = _resolve_match_call_sites()
    assert len(sites) == 5, sites
    assert {f for f, _ in sites} == {"preview.py", "categories.py"}, sites


def test_the_seam_still_has_no_production_caller():
    """The other half of T092's measurement, and the reason its successor
    stays open.

    Kept as an assertion rather than a note so that the day a production path
    DOES call the seam, this test fails and forces the routing census to be
    recorded instead of arriving as a silent green.
    """
    callers = _seam_call_sites()
    assert callers == set(), (
        "a production path now calls the seam. That is a live-behaviour change "
        "across every category that plans a roster-admitted class -- record "
        "the census it required and close T092's successor: %r" % (callers,)
    )


def test_only_two_bypasses_can_reach_the_seam_today():
    """The routing task's reachable scope, pinned so it cannot move quietly.

    `plan_match_decision` takes a `RunContext` and reads both project handles
    off it. `_match_collection_child` receives `ws_handles`/`source_ws_handles`
    already resolved and `_resolve_target_pos_by_natural_key` takes `target`
    and `source_handle` -- neither holds a context, so routing them needs a
    handle-pair entry point on the seam, which is a design decision and not a
    re-point. The other two hold a context and could be routed today.

    If a context arrives at one of the first two, the routing task just got
    bigger, and this test is where that is noticed.
    """
    sites = _resolve_match_call_sites()
    context_bearing = {
        where for where, params in sites.items()
        if where != ("preview.py", "plan_match_decision")
        and "context" in params
    }
    assert context_bearing == _CONTEXT_BEARING_BYPASSES, (
        "the set of bypasses holding a `RunContext` has changed, so the "
        "routing task's reachable scope has changed with it: %r"
        % (sorted(context_bearing),)
    )
