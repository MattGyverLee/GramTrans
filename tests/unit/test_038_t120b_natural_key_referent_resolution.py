"""Feature 038 T120, second entry: the referent that was in the destination
all along, under a different GUID.

WHY THIS FILE EXISTS ALONGSIDE `test_038_t120_rhs_partial_loss.py`.
T120's first landing fixed a whole-loop `except` and added
`_report_dropped_rhs`, and its tests assert the SOURCE TEXT of that fix
(`inspect.getsource` + regex). T124 then measured the result and found the
reporter had **never fired on any pair**: 0 `RightHandSidesOS` drop records
against 14 missing right-hand sides. The source-text tests were all green
throughout, because a test that asserts a `try:` is placed correctly cannot
notice that no exception of the caught class is ever raised.

So this file is deliberately BEHAVIOURAL. Every test here drives the real
function with real values and asserts what comes back.

THE DEFECT, MEASURED (T124, three sanctioned pairs).
All 31 phonological-rule failures are `RuntimeError` raised by
`_copy_context_cell` when a context references a phoneme or natural class
"absent from target". They were not absent. The run's OWN report records
`identity_substitution` with `basis: NATURAL_KEY` on 21 / 20 / 19 `PhPhoneme`
plus 1 `PhNCSegments`: Preview matched those source phonemes to destination
objects by roster-admitted NAME and emitted a `PlannedOverwrite` carrying both
GUIDs. The executor then looked the referent up in a dict keyed by
DESTINATION GUID, using the SOURCE GUID, missed, and raised. That is a
Preview/Move divergence -- the plan had already answered the question the
executor re-asked and got wrong.

14 of the 31 fire in the `StrucDescOS` loop UPSTREAM of the right-hand-side
loop, so the rule shell exists and its right-hand sides are never attempted:
the census reads `PhRegularRule` MATCHED (6/6, 21/21, 39/39) while
`PhSegRuleRHS` is short by exactly 3 on ngoreme and 11 on mbugwe.

WHAT IS TESTED HERE, AND WHAT IS NOT.
`_resolve_scoped_referent` is a pure function over a dict and a context, so its
ordering and its fallbacks are testable host-free and are tested exactly. The
natural-key leg is stubbed, because `_process_referent_by_natural_key` reaches
the matcher seam and a live project; what matters at THIS seam is that the leg
is consulted in the right ORDER, on the right condition, and not at all when
identity already answered. The end-to-end claim -- that this recovers 14
right-hand sides on two live pairs -- is a live measurement and belongs to the
re-census, not to a unit test. Stated so nobody reads a green file here as
that claim.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories


class _Obj:
    """A destination or source object: a GUID and a ClassName, nothing more."""

    def __init__(self, guid, class_name="PhPhoneme"):
        self.Guid = guid
        self.ClassName = class_name


class _Plan:
    def __init__(self, identity_remap=None):
        self.identity_remap = identity_remap or {}


class _Ctx:
    """Just enough of an exec context: the plan, and the two handles
    `_process_referent_by_natural_key` guards on."""

    def __init__(self, identity_remap=None):
        self._run_plan = _Plan(identity_remap)
        self.source_handle = object()
        self.target_handle = object()


SRC_GUID = "11111111-1111-1111-1111-111111111111"
DEST_GUID = "22222222-2222-2222-2222-222222222222"
OTHER_GUID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def no_natural_key(monkeypatch):
    """The natural-key leg answers nothing, and RECORDS whether it was asked.

    Being able to assert it was NOT asked is half the point: identity must be
    authoritative, so a GUID hit has to return before this leg is reached.
    """
    calls = []

    def _stub(context, src_obj, object_class):
        calls.append((src_obj, object_class))
        return None

    monkeypatch.setattr(
        categories, "_process_referent_by_natural_key", _stub)
    return calls


@pytest.fixture
def natural_key_finds(monkeypatch):
    """The natural-key leg resolves to a named destination object."""

    def _install(dest_obj):
        def _stub(context, src_obj, object_class):
            return dest_obj

        monkeypatch.setattr(
            categories, "_process_referent_by_natural_key", _stub)

    return _install


# ---------------------------------------------------------------------------
# Ordering: identity is authoritative (FR-001 / FR-002)
# ---------------------------------------------------------------------------

def test_a_guid_hit_wins_and_the_natural_key_leg_is_never_consulted(
        no_natural_key):
    """A GUID that already identified an object must not be second-guessed by
    a name collision. If this regresses, a rule can silently come to reference
    a same-named but DIFFERENT destination phoneme -- a wrong answer that
    looks like a considered one."""
    src = _Obj(SRC_GUID)
    dest = _Obj(SRC_GUID)
    by_guid = {SRC_GUID: dest}

    found, basis = categories._resolve_scoped_referent(
        _Ctx(), src, by_guid, "PhPhoneme")

    assert found is dest
    assert basis == "guid"
    assert no_natural_key == [], (
        "the natural-key leg was consulted despite an identity hit")


def test_identity_remap_is_tried_before_the_natural_key_leg(no_natural_key):
    """The plan's own remap is still IDENTITY -- a GUID this run reassigned --
    so it outranks a name match."""
    src = _Obj(SRC_GUID)
    dest = _Obj(DEST_GUID)
    by_guid = {DEST_GUID: dest}
    ctx = _Ctx(identity_remap={SRC_GUID: DEST_GUID})

    found, basis = categories._resolve_scoped_referent(
        ctx, src, by_guid, "PhPhoneme")

    assert found is dest
    assert basis == "identity_remap"
    assert no_natural_key == []


# ---------------------------------------------------------------------------
# The defect itself
# ---------------------------------------------------------------------------

def test_a_natural_key_matched_referent_resolves_instead_of_raising(
        natural_key_finds):
    """THE REGRESSION TEST FOR THE MEASURED DEFECT.

    Source phoneme carries the source's GUID; the destination object it was
    matched to carries the DESTINATION's GUID; the class-scoped dict is keyed
    by destination GUID. Before the fix this returned None and the caller
    raised `RuntimeError(... absent from target)`, taking the whole rule down.
    """
    src = _Obj(SRC_GUID)
    dest = _Obj(DEST_GUID)
    natural_key_finds(dest)
    by_guid = {DEST_GUID: dest}

    found, basis = categories._resolve_scoped_referent(
        _Ctx(), src, by_guid, "PhPhoneme")

    assert found is dest, (
        "a phoneme matched to the destination by roster-admitted name still "
        "reads as absent -- this is the defect that cost 14 right-hand sides")
    assert basis == "natural_key"


def test_the_basis_is_reported_so_a_name_match_is_distinguishable(
        natural_key_finds):
    """A referent recovered by NAME is a materially different fact from one
    recovered by identity. Returning the basis rather than discarding it is
    what lets a report distinguish them; flattening them makes the run
    unauditable."""
    dest = _Obj(DEST_GUID)
    natural_key_finds(dest)

    _, by_identity = categories._resolve_scoped_referent(
        _Ctx(), _Obj(DEST_GUID), {DEST_GUID: dest}, "PhPhoneme")
    _, by_name = categories._resolve_scoped_referent(
        _Ctx(), _Obj(SRC_GUID), {DEST_GUID: dest}, "PhPhoneme")

    assert by_identity == "guid"
    assert by_name == "natural_key"
    assert by_identity != by_name


# ---------------------------------------------------------------------------
# Refusals: what must STILL fail
# ---------------------------------------------------------------------------

def test_a_genuinely_absent_referent_still_resolves_to_nothing(
        no_natural_key):
    """The fix must not convert a real loss into a false success. When neither
    identity nor the name finds anything, the caller still refuses -- and now
    reports rather than losing the rest of the rule."""
    found, basis = categories._resolve_scoped_referent(
        _Ctx(), _Obj(SRC_GUID), {OTHER_GUID: _Obj(OTHER_GUID)}, "PhPhoneme")

    assert found is None
    assert basis == ""


def test_an_ambiguous_key_is_not_a_pick(monkeypatch):
    """`_process_referent_by_natural_key` absorbs `NaturalKeyAmbiguityError`
    and returns None. Ambiguity in these classes is the NORMAL condition on
    real pairs (T098 measured 12 duplicate-name groups on one pair), so this
    leg must leave the referent unresolved rather than guess between two
    same-named destination phonemes."""
    monkeypatch.setattr(
        categories, "_process_referent_by_natural_key",
        lambda context, src_obj, object_class: None)

    found, basis = categories._resolve_scoped_referent(
        _Ctx(), _Obj(SRC_GUID), {DEST_GUID: _Obj(DEST_GUID)}, "PhPhoneme")

    assert found is None
    assert basis == ""


def test_a_wrong_class_natural_key_answer_is_refused(natural_key_finds):
    """A name match that lands on the wrong CLASS is not a match. Accepting it
    would wire a rule to an object of another type -- worse than the loss."""
    natural_key_finds(_Obj(DEST_GUID, class_name="PhNCSegments"))

    found, _ = categories._resolve_scoped_referent(
        _Ctx(), _Obj(SRC_GUID), {}, "PhPhoneme")

    assert found is None


# ---------------------------------------------------------------------------
# Degradation: the UPDATE path has no context and no plan
# ---------------------------------------------------------------------------

def test_without_a_context_it_degrades_to_a_plain_guid_lookup(no_natural_key):
    """`_execute_phon_rule_structural_update` passes `context=None`. Both
    fallbacks must be skipped there and behaviour must be exactly what it was,
    so this fix cannot change the UPDATE path's verdict in either direction."""
    dest = _Obj(SRC_GUID)

    hit, basis = categories._resolve_scoped_referent(
        None, _Obj(SRC_GUID), {SRC_GUID: dest}, "PhPhoneme")
    miss, miss_basis = categories._resolve_scoped_referent(
        None, _Obj(SRC_GUID), {DEST_GUID: _Obj(DEST_GUID)}, "PhPhoneme")

    assert (hit, basis) == (dest, "guid")
    assert (miss, miss_basis) == (None, "")
    assert no_natural_key == [], (
        "the natural-key leg was consulted with no context to resolve against")


def test_a_null_referent_is_not_an_error(no_natural_key):
    found, basis = categories._resolve_scoped_referent(
        _Ctx(), None, {}, "PhPhoneme")
    assert (found, basis) == (None, "")


# ---------------------------------------------------------------------------
# The reporter the shortfall actually needed
# ---------------------------------------------------------------------------

def test_a_struc_desc_cell_loss_is_reported_against_its_rule():
    """`_report_dropped_rhs` names `field_name="RightHandSidesOS"`, which is
    the wrong field for a `StrucDescOS` cell -- and 14 of the 31 measured
    failures are `StrucDescOS` cells. They need a record that names the rule
    and the cell, or the loss is invisible behind a MATCHED rule count."""
    dropped = []
    categories._report_dropped_struc_desc_cell(
        dropped, SRC_GUID, DEST_GUID, RuntimeError("phoneme absent"))

    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.owner_kind == "PhRegularRule"
    assert rec.owner_guid == SRC_GUID
    assert rec.field_name == "StrucDescOS"
    assert rec.item_guid == DEST_GUID
    assert "RuntimeError" in rec.reason


def test_the_struc_desc_reporter_tolerates_no_sink():
    """The UPDATE path may have no collector. A reporter that raised would be
    swallowed by the very guards this fix exists to stop hiding behind."""
    categories._report_dropped_struc_desc_cell(
        None, SRC_GUID, DEST_GUID, RuntimeError("boom"))


def test_the_rhs_reporter_now_catches_runtime_error():
    """Every one of the 31 measured failures is a `RuntimeError`, so the old
    `except (AttributeError, TypeError)` could not catch a single real one.
    This asserts the reporter accepts a `RuntimeError` and says so in the
    record -- the behavioural half of what the source-text test asserts."""
    dropped = []
    categories._report_dropped_rhs(
        dropped, SRC_GUID, DEST_GUID, RuntimeError("phoneme absent"))

    assert len(dropped) == 1
    assert "RuntimeError" in dropped[0].reason
