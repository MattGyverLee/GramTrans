"""T036 (FR-001/FR-006/FR-007/FR-013): the EXECUTOR consumes the plan's
`match_basis` through ONE resolve-or-create path, and adds no matching logic
of its own.

Why this file exists, separately from `test_038_natural_key.py` (the MATCHER)
and `test_038_report_natural_key.py` (the REPORT). Those prove that a
`MatchBasisRecord` can be produced and that a produced record is reported.
Neither says anything about what the thing that WRITES TO THE PROJECT does
with it, and before T036 the answer was "nothing at all": `Lib/transfer.py`
consumed exactly three plan fields -- `match_via`, `write_mode`, and the
action's category -- and `match_basis` was read nowhere in the module.

The two failure modes that absence produced are opposites, which is why one
path has to replace both rather than either being patched:

  * CREATE-ANYWAY. `_idempotency_guard` asks `target.Object(SOURCE guid)`. A
    destination object the plan matched by a roster-admitted NATURAL KEY lives
    under a DIFFERENT GUID, so the guard cannot see it, the caller Creates, and
    the project gains a duplicate of FLEx's own starter content -- a second
    `Verb`, a second `n` -- permanently written to .fwdata on CloseProject.
    `test_natural_key_record_resolves_the_other_guid_and_never_creates` and
    `test_create_pos_with_a_natural_key_basis_never_calls_the_factory` pin
    this shut.

  * RESOLVE-ONLY. Six category-scoped linear scans (`_find_target_pos_by_guid`,
    `_find_target_template_by_guid`, `_find_target_slot_by_guid`,
    `_find_target_morph_type_by_guid`, `_find_target_env_by_guid`,
    `_find_obj_by_guid`) each answer a NARROWER question than the plan did --
    two of them are scoped to an owner POS -- and each ends a miss with
    `report_sink.Warning(...)` + `return`, discarding the plan's work. In
    export mode the `_NullReportSink` discards the Warning too, so the abandon
    leaves no trace (the same shape as feature 037's defect C).
    `test_update_semantic_falls_back_to_the_plans_object_when_the_scan_misses`
    and `test_overwrite_pos_uses_the_planned_object_when_the_scan_misses` pin
    this shut.

THE CONSTRAINT THIS FILE EXISTS TO ENFORCE MOST OF ALL is the third one:
`match_basis is None` must be bit-for-bit pre-038 behaviour. That is not a
theoretical concern -- it is the state of EVERY plan item in production today.
`preview._emit_present_outcome` attaches a record only when its caller passes
`object_class=`, and no caller passes it, so as of T036 not one plan item
carries a record at all. Every "unchanged" test below therefore covers real,
live behaviour, and every "new" test below covers behaviour no production plan
reaches yet. The `..._is_unchanged` / `..._pre_038_...` names mark which is
which on purpose.

Register note: these tests construct REAL `MatchBasisRecord`s, never duck-typed
stand-ins, because `MatchBasisRecord.__post_init__` is what guarantees a
non-NONE basis carries a `target_guid` and a NONE basis does not. The executor
leans on that invariant (it never re-validates it), so a stand-in would let a
test pass against a record production could not build.
"""

from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import transfer
from gramtrans.Lib.matcher import natural_key_binding_for
from gramtrans.Lib.models import (
    GrammarCategory,
    MatchBasis,
    MatchBasisRecord,
    PlannedAction,
    PlannedOverwrite,
)


# ============================================================================
# Fakes. Deliberately tiny: the executor's resolve-or-create path touches a
# project through exactly one primitive (`target.Object(guid)`), which is the
# whole point of the design and is what makes these fakes honest rather than
# convenient.
# ============================================================================

SRC_GUID = "11111111-1111-1111-1111-111111111111"
TGT_GUID = "22222222-2222-2222-2222-222222222222"


class _FakeObj:
    """A destination object that knows only its class name -- all the executor
    reads off a resolved object before handing it to a category writer."""

    def __init__(self, class_name: str, guid: str = TGT_GUID):
        self.ClassName = class_name
        self.Guid = guid


class _FakeTarget:
    """A project whose `Object(guid)` is a dict lookup, recording every GUID it
    was asked for so a test can assert WHICH question the executor asked --
    the source GUID (the create-anyway bug) or the planned target GUID."""

    def __init__(self, objects=None, raises=False):
        self._objects = dict(objects or {})
        self._raises = raises
        self.asked = []
        self.Cache = types.SimpleNamespace(DefaultAnalWs=1)

    def Object(self, guid):
        self.asked.append(guid)
        if self._raises:
            raise RuntimeError("cache lookup exploded")
        return self._objects.get(guid)


class _RecordingSink:
    """FlexTools-shaped report sink that keeps every line, so a test can assert
    an item was REPORTED rather than silently dropped (FR-013)."""

    def __init__(self):
        self.info = []
        self.warnings = []
        self.errors = []

    def Info(self, msg):
        self.info.append(msg)

    def Warning(self, msg):
        self.warnings.append(msg)

    def Error(self, msg):
        self.errors.append(msg)

    def Blank(self):
        pass


def _identity_record(object_class="PartOfSpeech", source=SRC_GUID, target=TGT_GUID):
    return MatchBasisRecord(
        basis=MatchBasis.IDENTITY,
        object_class=object_class,
        source_guid=source,
        target_guid=target,
        candidate_count=1,
    )


def _natural_key_record(object_class="PhPhoneme", source=SRC_GUID, target=TGT_GUID):
    return MatchBasisRecord(
        basis=MatchBasis.NATURAL_KEY,
        object_class=object_class,
        source_guid=source,
        key_expression="PhPhoneme.Name (default vernacular)",
        key_value="n",
        target_guid=target,
        candidate_count=1,
    )


def _none_record(object_class="PhPhoneme", source=SRC_GUID):
    return MatchBasisRecord(
        basis=MatchBasis.NONE,
        object_class=object_class,
        source_guid=source,
        candidate_count=0,
    )


# ============================================================================
# The path itself: `resolve_planned_destination`
# ============================================================================

def test_no_record_is_undetermined_and_never_touches_the_project():
    """The prime constraint. `match_basis=None` must not even ASK the project a
    question, because asking is how a behaviour change sneaks in: a fake that
    raises would surface it, and so would a real project whose cache lookup has
    a side effect. `target.asked` staying empty is the strongest available
    statement of "pre-038 behaviour, bit for bit"."""
    target = _FakeTarget(raises=True)
    dest = transfer.resolve_planned_destination(
        None, target, creation_licensed=True,
    )
    assert dest.outcome == transfer.DESTINATION_UNDETERMINED
    assert dest.undetermined is True
    assert dest.resolved is False
    assert dest.obj is None
    assert target.asked == []


def test_identity_record_resolves_the_planned_guid():
    obj = _FakeObj("PartOfSpeech")
    target = _FakeTarget({TGT_GUID: obj})
    dest = transfer.resolve_planned_destination(
        _identity_record(), target, creation_licensed=True,
    )
    assert dest.resolved is True
    assert dest.obj is obj
    assert dest.target_guid == TGT_GUID
    assert dest.basis is MatchBasis.IDENTITY
    # Exactly one lookup, of the PLANNED guid. Not a scan, not a retry.
    assert target.asked == [TGT_GUID]


def test_natural_key_record_resolves_the_other_guid_and_never_creates():
    """THE create-anyway fix, stated as a test.

    A natural-key match is by construction a destination object under a GUID
    that is NOT the source's -- that is what makes it a key match rather than
    an identity match. The pre-038 guard asked for `SRC_GUID` and got nothing,
    so it created a duplicate. Asserting that `SRC_GUID` was never even asked
    for is what makes this a regression fence rather than a restatement.
    """
    obj = _FakeObj("PhPhoneme")
    target = _FakeTarget({TGT_GUID: obj})
    dest = transfer.resolve_planned_destination(
        _natural_key_record(), target, creation_licensed=True,
    )
    assert dest.resolved is True
    assert dest.obj is obj
    assert dest.basis is MatchBasis.NATURAL_KEY
    assert target.asked == [TGT_GUID]
    assert SRC_GUID not in target.asked


def test_identity_and_natural_key_take_the_same_branch():
    """The plan already applied the ordering contract (identity first and
    authoritative, the key only when identity found nothing). The executor must
    not re-apply it, or the two halves can disagree again -- which is the
    original defect. Same input GUID, same object, same outcome, whichever
    basis produced the record."""
    obj = _FakeObj("PhPhoneme")
    by_identity = transfer.resolve_planned_destination(
        _identity_record(object_class="PhPhoneme"),
        _FakeTarget({TGT_GUID: obj}), creation_licensed=True,
    )
    by_key = transfer.resolve_planned_destination(
        _natural_key_record(),
        _FakeTarget({TGT_GUID: obj}), creation_licensed=True,
    )
    assert by_identity.obj is by_key.obj
    assert by_identity.outcome == by_key.outcome == transfer.DESTINATION_RESOLVED


@pytest.mark.parametrize("record", [_identity_record(), _natural_key_record()])
def test_a_promised_destination_that_is_gone_is_a_harness_error(record):
    """Neither fallback is safe, so there is no fallback.

    Falling back to Create writes the destination object a second time under a
    second GUID; falling back to a Warning + return throws away everything the
    plan computed for the item. The message has to name the class, both GUIDs
    and the refusal, because the operator's actual fix (re-run Preview) is not
    guessable from a bare KeyError.
    """
    target = _FakeTarget({})  # the promised object is not there
    with pytest.raises(transfer.PlannedDestinationError) as exc:
        transfer.resolve_planned_destination(
            record, target, creation_licensed=True,
        )
    message = str(exc.value)
    assert TGT_GUID in message
    assert record.source_guid in message
    assert record.object_class in message
    assert "Re-run Preview" in message


def test_a_resolve_that_raises_is_reported_as_missing_not_swallowed():
    """`_resolve_guid_in_target` swallows the exception -- "not present" and
    "malformed GUID" are the same answer to its question -- but the swallow
    must not become a silent drop one level up. It becomes the same loud
    harness error."""
    target = _FakeTarget({TGT_GUID: _FakeObj("PartOfSpeech")}, raises=True)
    with pytest.raises(transfer.PlannedDestinationError):
        transfer.resolve_planned_destination(
            _identity_record(), target, creation_licensed=True,
        )


def test_a_class_mismatch_is_a_harness_error_not_a_warning():
    """`PhNCSegments` must never match `PhNCFeatures` and `LexEntryInflType`
    must never match `LexEntryType`, however identical their names: they are
    different linguistic objects that happen to share a list. Applying source
    properties onto the wrong class is a corruption, so this stops rather than
    warns."""
    target = _FakeTarget({TGT_GUID: _FakeObj("PhNCFeatures")})
    with pytest.raises(transfer.PlannedDestinationError) as exc:
        transfer.resolve_planned_destination(
            _identity_record(object_class="PhNCSegments"),
            target, creation_licensed=True,
        )
    assert "PhNCSegments" in str(exc.value)
    assert "PhNCFeatures" in str(exc.value)


def test_a_resolved_object_with_no_class_name_is_accepted():
    """Not every proxy the LCM cache hands back declares `ClassName`, and
    absence of evidence is not a mismatch. The check fires only when BOTH names
    are known and differ -- otherwise a wrapper without the attribute would
    turn every correct plan into a harness error."""
    obj = types.SimpleNamespace(Guid=TGT_GUID)  # no ClassName at all
    target = _FakeTarget({TGT_GUID: obj})
    dest = transfer.resolve_planned_destination(
        _identity_record(), target, creation_licensed=True,
    )
    assert dest.resolved is True
    assert dest.obj is obj


def test_none_basis_never_asks_the_project_for_anything():
    """A NONE record names no destination, so there is nothing to resolve. If
    this ever started probing the project it would be the executor doing its
    own matching, which is the one thing T036 forbids."""
    target = _FakeTarget(raises=True)
    dest = transfer.resolve_planned_destination(
        _none_record(), target, creation_licensed=True,
    )
    assert dest.outcome == transfer.DESTINATION_CREATE
    assert target.asked == []


def test_none_basis_creates_only_when_the_roster_allows_it():
    """`PhPhoneme` sets `creates_on_miss` true; a missed key may mint one."""
    assert natural_key_binding_for("PhPhoneme").creates_on_miss is True
    dest = transfer.resolve_planned_destination(
        _none_record("PhPhoneme"), _FakeTarget(), creation_licensed=True,
    )
    assert dest.outcome == transfer.DESTINATION_CREATE
    assert dest.detail == ""


def test_none_basis_on_morph_type_is_reported_never_created():
    """`MoMorphType` is the one admitted class the roster forbids creating on a
    missed key: FLEx treats the morph-types list as project-independent fixed
    content (all 19 GUIDs byte-identical across the three projects measured),
    so minting one would add an object the canonical list does not contain.

    The reason travels in `detail` rather than being reconstructed by the
    reader, because "creation refused" without the rule that refused it is the
    kind of report line that gets ignored."""
    assert natural_key_binding_for("MoMorphType").creates_on_miss is False
    dest = transfer.resolve_planned_destination(
        _none_record("MoMorphType"), _FakeTarget(), creation_licensed=True,
    )
    assert dest.outcome == transfer.DESTINATION_REPORT
    assert "creates_on_miss=false" in dest.detail


def test_none_basis_for_an_unbound_class_is_reported_never_created():
    """"Never create when the record shows the key could not be computed."

    `WfiWordform` is the exact case: 035's roster admits it and the census can
    key it, but 038 binds no key function for it, so no key was -- or could
    have been -- computed. Its NONE therefore means "not keyed", not "keyed and
    missed", and a create off the back of it would be a create-anyway with a
    record attached to make it look considered."""
    assert natural_key_binding_for("WfiWordform") is None
    dest = transfer.resolve_planned_destination(
        _none_record("WfiWordform"), _FakeTarget(), creation_licensed=True,
    )
    assert dest.outcome == transfer.DESTINATION_REPORT
    assert "WfiWordform" in dest.detail


def test_none_basis_without_a_creation_licence_is_reported():
    """An OVERWRITE/UPDATE plan item is an instruction to write onto an object
    that already exists. A NONE record on one means the plan found nothing to
    write onto, and creating from there is the create-anyway defect with extra
    steps."""
    dest = transfer.resolve_planned_destination(
        _none_record("PhPhoneme"), _FakeTarget(), creation_licensed=False,
    )
    assert dest.outcome == transfer.DESTINATION_REPORT
    assert "not an ADD" in dest.detail


def test_an_unknown_basis_is_refused_rather_than_guessed():
    """Guessing between resolve and create is exactly the choice that produced
    the two opposite defects. A basis the executor does not recognise gets
    neither."""
    bogus = types.SimpleNamespace(
        basis="something_new", object_class="PhPhoneme",
        source_guid=SRC_GUID, target_guid="",
    )
    with pytest.raises(transfer.PlannedDestinationError) as exc:
        transfer.resolve_planned_destination(
            bogus, _FakeTarget(), creation_licensed=True,
        )
    assert "refuses to guess" in str(exc.value)


def test_a_matched_basis_with_no_target_guid_is_refused():
    """`MatchBasisRecord.__post_init__` already forbids this, so it can only
    reach the executor from a record built some other way. Checked anyway: an
    empty GUID would resolve to None and be reported as "the destination is
    gone", sending the operator hunting for a data problem that is really a
    producer bug."""
    bogus = types.SimpleNamespace(
        basis=MatchBasis.IDENTITY, object_class="PhPhoneme",
        source_guid=SRC_GUID, target_guid="",
    )
    with pytest.raises(transfer.PlannedDestinationError) as exc:
        transfer.resolve_planned_destination(
            bogus, _FakeTarget(), creation_licensed=True,
        )
    assert "names no target_guid" in str(exc.value)


# ============================================================================
# The plan-item front door: `planned_destination_for`
# ============================================================================

def _action(match_basis=None):
    return PlannedAction(
        category=GrammarCategory.PHONEMES,
        source_guid=SRC_GUID,
        intended_target_guid=SRC_GUID,
        summary="phoneme",
        match_basis=match_basis,
    )


def _overwrite(match_basis=None):
    return PlannedOverwrite(
        category=GrammarCategory.PHONEMES,
        source_guid=SRC_GUID,
        target_guid=TGT_GUID,
        summary="phoneme",
        match_basis=match_basis,
    )


def test_the_add_verb_is_what_licenses_a_create():
    """The plan says whether creation is allowed, and it says it by which verb
    it used. Nothing else in the executor gets a vote."""
    assert transfer.planned_destination_for(
        _action(_none_record()), _FakeTarget(),
    ).outcome == transfer.DESTINATION_CREATE
    assert transfer.planned_destination_for(
        _overwrite(_none_record()), _FakeTarget(),
    ).outcome == transfer.DESTINATION_REPORT


def test_a_plan_item_without_the_field_degrades_cleanly():
    """`plan.actions` is heterogeneous: `CreateDefinitionAction` is a
    schema-level MDC write with no `match_basis` at all (the same reason
    `execute()` reads `pulled_in_by` defensively). A schema action must reach
    pre-038 behaviour, not an AttributeError."""
    schema_shaped = types.SimpleNamespace(source_guid=SRC_GUID)
    dest = transfer.planned_destination_for(schema_shaped, _FakeTarget(raises=True))
    assert dest.undetermined is True


@pytest.mark.parametrize("item", [_action(), _overwrite()])
def test_a_plan_item_with_no_record_is_undetermined(item):
    """Production's actual state: no planner attaches a record yet, so this is
    the branch every live plan item takes."""
    assert transfer.planned_destination_for(
        item, _FakeTarget(raises=True),
    ).undetermined is True


# ============================================================================
# `_idempotency_guard` -- the create-anyway site
# ============================================================================

def test_guard_without_a_record_is_unchanged_when_the_guid_is_absent():
    """Pre-038, verbatim: probe the SOURCE guid, find nothing, tell the caller
    to proceed with Create."""
    target = _FakeTarget({})
    sink = _RecordingSink()
    assert transfer._idempotency_guard(target, SRC_GUID, "PartOfSpeech", sink) == (False, None)
    assert target.asked == [SRC_GUID]
    assert sink.warnings == []


def test_guard_without_a_record_is_unchanged_when_the_guid_is_present():
    obj = _FakeObj("PartOfSpeech", guid=SRC_GUID)
    target = _FakeTarget({SRC_GUID: obj})
    found, existing = transfer._idempotency_guard(
        target, SRC_GUID, "PartOfSpeech", _RecordingSink(),
    )
    assert (found, existing) == (True, obj)
    assert target.asked == [SRC_GUID]


def test_guard_without_a_record_is_unchanged_on_a_wrong_class_collision():
    """LCM's `factory.Create(existingGuid, owner)` does not throw -- it silently
    creates a duplicate. The wrong-class arm is what stops that, and it must
    keep warning-and-skipping exactly as before."""
    target = _FakeTarget({SRC_GUID: _FakeObj("LexEntry", guid=SRC_GUID)})
    sink = _RecordingSink()
    assert transfer._idempotency_guard(target, SRC_GUID, "PartOfSpeech", sink) == (True, None)
    assert any("IDEMPOTENCY" in w for w in sink.warnings)


def test_guard_with_a_natural_key_record_resolves_instead_of_creating():
    """The defect, closed at its site. The guard's own question (`is SRC_GUID
    present?`) answers "no" here -- `_FakeTarget` holds nothing at SRC_GUID --
    and pre-038 that answer sent the caller straight into Create. With the
    plan's record the guard returns the destination object the plan matched by
    name, so no Create happens and no duplicate `n` is written."""
    obj = _FakeObj("PhPhoneme")
    target = _FakeTarget({TGT_GUID: obj})
    sink = _RecordingSink()
    found, existing = transfer._idempotency_guard(
        target, SRC_GUID, "PhPhoneme", sink, match_basis=_natural_key_record(),
    )
    assert (found, existing) == (True, obj)
    assert target.asked == [TGT_GUID]
    assert SRC_GUID not in target.asked


def test_guard_with_a_promised_but_absent_destination_raises():
    """No silent fallback to Create at the one site where Create is one line
    away."""
    with pytest.raises(transfer.PlannedDestinationError):
        transfer._idempotency_guard(
            _FakeTarget({}), SRC_GUID, "PhPhoneme", _RecordingSink(),
            match_basis=_identity_record(object_class="PhPhoneme"),
        )


def test_guard_reports_and_skips_when_creation_is_refused():
    """FR-013: reported, never silently dropped -- and never created."""
    target = _FakeTarget({})
    sink = _RecordingSink()
    found, existing = transfer._idempotency_guard(
        target, SRC_GUID, "MoMorphType", sink,
        match_basis=_none_record("MoMorphType"),
    )
    assert (found, existing) == (True, None)
    assert any("creates_on_miss=false" in w for w in sink.warnings)
    assert target.asked == []


def test_guard_still_probes_for_a_duplicate_guid_when_creation_is_allowed():
    """A CREATE outcome does not retire the anti-corruption probe. "Did the
    plan find a counterpart?" and "would this Create silently duplicate a
    GUID?" are different questions, and only the first one is answered by
    `match_basis`."""
    target = _FakeTarget({})
    assert transfer._idempotency_guard(
        target, SRC_GUID, "PhPhoneme", _RecordingSink(),
        match_basis=_none_record("PhPhoneme"),
    ) == (False, None)
    assert target.asked == [SRC_GUID]


def test_guard_refuses_when_the_create_site_builds_a_different_class():
    """The record's class is right and the destination's class agrees with it,
    but this create helper builds something else -- a wiring bug in the caller.
    Skipped and reported rather than created, because creating would duplicate
    the object the plan just resolved."""
    target = _FakeTarget({TGT_GUID: _FakeObj("PartOfSpeech")})
    sink = _RecordingSink()
    found, existing = transfer._idempotency_guard(
        target, SRC_GUID, "MoInflAffixSlot", sink,
        match_basis=_identity_record(object_class="PartOfSpeech"),
    )
    assert (found, existing) == (True, None)
    assert any("038 T036" in w for w in sink.warnings)


# ============================================================================
# A real create helper, end to end
# ============================================================================

@pytest.fixture
def _stub_lcm():
    """Minimum SIL.LCModel / System surface `_create_pos_with_guid` imports.

    Installed per test and restored after, following the established pattern in
    `test_027_entry_type_resolve.py`: pythonnet's CLR loader is not available
    offline, and the executor's `from SIL.LCModel import ...` calls are
    function-local precisely so they can be stubbed like this."""
    fake_lcm = types.ModuleType("SIL.LCModel")
    for iface in ("IPartOfSpeech", "IPartOfSpeechFactory", "ICmPossibilityList"):
        setattr(fake_lcm, iface, (lambda raw: raw))
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original_lcm = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake_lcm

    fake_system = types.ModuleType("System")
    fake_system.Guid = type("FakeGuid", (), {"Parse": staticmethod(lambda s: s)})
    original_system = sys.modules.get("System")
    sys.modules["System"] = fake_system

    yield

    for name, original in (("SIL.LCModel", original_lcm), ("System", original_system)):
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


class _ExplodingFactory:
    """Any call is a test failure: the whole point of the resolve arm is that
    the factory is never reached."""

    def Create(self, *args, **kwargs):  # noqa: N802 -- mirrors the LCM name
        raise AssertionError(
            "factory.Create was called even though the plan had already "
            "resolved a destination object -- this is the create-anyway defect"
        )


def test_create_pos_with_a_natural_key_basis_never_calls_the_factory(_stub_lcm):
    """The whole defect in one call: a POS the plan matched by name, and a
    creator that must return it rather than mint a second `Verb`."""
    obj = _FakeObj("PartOfSpeech")
    target = _FakeTarget({TGT_GUID: obj})
    target.GetFactory = lambda iface: _ExplodingFactory()
    sink = _RecordingSink()

    result = transfer._create_pos_with_guid(
        target, SRC_GUID, {"Name": {"en": "Verb"}}, _tag(), sink,
        match_basis=_natural_key_record(object_class="PartOfSpeech"),
    )
    assert result is obj
    assert any("idempotency reuse" in m for m in sink.info)


def test_create_pos_without_a_record_still_creates(monkeypatch, _stub_lcm):
    """The other half of the same call: with no record the creator behaves
    exactly as it did before 038, GUID-preserving Create included."""
    created = {}
    # Carrier-B residue writes a real Description multistring; out of scope
    # here, and stubbing it keeps the assertion about the GUID the factory saw.
    monkeypatch.setattr(transfer, "apply_carrier_b", lambda *a, **k: True)

    class _Factory:
        def Create(self, guid, owner):  # noqa: N802
            created["guid"] = guid
            return _FakeObj("PartOfSpeech", guid=guid)

    target = _FakeTarget({})
    target.GetFactory = lambda iface: _Factory()
    target.Cache = types.SimpleNamespace(
        DefaultAnalWs=1,
        LangProject=types.SimpleNamespace(PartsOfSpeechOA=object()),
    )
    target.POS = types.SimpleNamespace(ApplySyncableProperties=lambda *a, **k: None)

    result = transfer._create_pos_with_guid(
        target, SRC_GUID, {"Name": {"en": "Verb"}}, _tag(), _RecordingSink(),
    )
    assert created["guid"] == SRC_GUID
    assert result.Guid == SRC_GUID


def _tag():
    """A residue tag stand-in exposing only what the create path touches."""
    return types.SimpleNamespace(
        run_id="run-1",
        serialize=lambda: "tag",
        with_snapshot=lambda props: _tag(),
    )


# ============================================================================
# The resolve-only sites: the plan's object wins over a narrower scan
# ============================================================================

def _ops(objects):
    return types.SimpleNamespace(
        GetAll=lambda: list(objects),
        GetSyncableProperties=lambda obj: {"Name": {"en": "x"}},
        ApplySyncableProperties=lambda *a, **k: None,
    )


def test_update_semantic_without_a_record_is_unchanged_when_the_scan_misses(monkeypatch):
    """Pre-038: the scoped scan misses, the item is warned about and abandoned,
    and `_execute_update_semantic` returns an empty skip list. Unchanged."""
    monkeypatch.setattr(transfer, "apply_residue", lambda *a, **k: None)
    source = types.SimpleNamespace(POS=_ops([_FakeObj("PartOfSpeech", guid=SRC_GUID)]))
    target = _FakeTarget({})
    target.POS = _ops([])
    sink = _RecordingSink()

    result = transfer._execute_update_semantic(
        _overwrite_for(GrammarCategory.GRAM_CATEGORIES, None),
        source, target, sink, _tag(),
    )
    assert result == []
    assert any("not found" in w for w in sink.warnings)


def test_update_semantic_falls_back_to_the_plans_object_when_the_scan_misses(monkeypatch):
    """THE resolve-only fix. `_find_obj_by_guid` walks ONE category's
    `GetAll()` and swallows every exception on the way, so a miss is
    indistinguishable from an accessor that raised -- and either way the UPDATE
    was abandoned with a Warning the export path discards. When the plan named
    the destination, the update proceeds against it."""
    written = {}
    monkeypatch.setattr(transfer, "apply_residue", lambda *a, **k: None)
    monkeypatch.setattr(
        transfer, "compute_disposition",
        lambda **kwargs: transfer.ItemDisposition.UPDATE,
    )

    def _apply(src_props, tgt_props, tgt_ops, tgt_obj, ws_map=None):
        written["obj"] = tgt_obj
        return 1

    monkeypatch.setattr(transfer, "apply_update_semantic", _apply)

    planned = _FakeObj("PartOfSpeech")
    source = types.SimpleNamespace(POS=_ops([_FakeObj("PartOfSpeech", guid=SRC_GUID)]))
    target = _FakeTarget({TGT_GUID: planned})
    target.POS = _ops([])  # the category-scoped scan finds nothing
    sink = _RecordingSink()

    result = transfer._execute_update_semantic(
        _overwrite_for(
            GrammarCategory.GRAM_CATEGORIES,
            _identity_record(object_class="PartOfSpeech"),
        ),
        source, target, sink, _tag(),
    )
    assert result == []
    assert written["obj"] is planned
    assert not any("not found" in w for w in sink.warnings)


def test_update_semantic_raises_outside_its_own_except(monkeypatch):
    """The destination is resolved BEFORE the broad `except Exception` that
    wraps the rest of the function, so a harness error cannot be downgraded
    into one more swallowed Warning."""
    source = types.SimpleNamespace(POS=_ops([]))
    target = _FakeTarget({})
    target.POS = _ops([])
    with pytest.raises(transfer.PlannedDestinationError):
        transfer._execute_update_semantic(
            _overwrite_for(
                GrammarCategory.GRAM_CATEGORIES,
                _identity_record(object_class="PartOfSpeech"),
            ),
            source, target, _RecordingSink(), _tag(),
        )


def _overwrite_for(category, match_basis):
    return PlannedOverwrite(
        category=category,
        source_guid=SRC_GUID,
        target_guid=TGT_GUID,
        summary="item",
        match_basis=match_basis,
    )


def test_overwrite_pos_without_a_record_is_unchanged_when_the_scan_misses():
    """Pre-038: both scans miss, one Warning, `None` returned, nothing written."""
    source = types.SimpleNamespace(
        POS=types.SimpleNamespace(GetAll=lambda recursive=False: []),
    )
    target = _FakeTarget({})
    target.POS = types.SimpleNamespace(GetAll=lambda recursive=False: [])
    sink = _RecordingSink()

    assert transfer._execute_overwrite(
        _overwrite_for(GrammarCategory.POS, None), source, target, sink, _tag(),
    ) is None
    assert any("not found in source or target" in w for w in sink.warnings)
    assert target.asked == []


def test_overwrite_pos_uses_the_planned_object_when_the_scan_misses(monkeypatch, _stub_lcm):
    """`_find_target_pos_by_guid` walks `target.POS.GetAll(recursive=True)` and
    can only answer for objects that walk yields. The plan's record answers for
    the object itself, so a scan miss no longer discards the overwrite."""
    written = {}
    planned = _FakeObj("PartOfSpeech")
    src_pos = _FakeObj("PartOfSpeech", guid=SRC_GUID)

    monkeypatch.setattr(transfer, "_find_source_pos_by_guid", lambda s, g: src_pos)
    monkeypatch.setattr(transfer, "apply_residue", lambda *a, **k: None)
    monkeypatch.setattr(
        transfer, "_resolve_and_tag",
        lambda src_props, tgt_pre, tag, log, cat, tgt_guid, run_id: (src_props, tag, []),
    )

    def _apply(obj, props, ws_map=None):
        written["obj"] = obj

    source = types.SimpleNamespace(POS=types.SimpleNamespace(
        GetSyncableProperties=lambda o: {"Name": {"en": "Verb"}},
    ))
    target = _FakeTarget({TGT_GUID: planned})
    target.POS = types.SimpleNamespace(
        GetAll=lambda recursive=False: [],  # scoped scan finds nothing
        GetSyncableProperties=lambda o: {},
        ApplySyncableProperties=_apply,
    )
    sink = _RecordingSink()

    result = transfer._execute_overwrite(
        _overwrite_for(GrammarCategory.POS, _identity_record()),
        source, target, sink, _tag(),
    )
    assert result == []
    assert written["obj"] is planned
    assert not any("not found in source or target" in w for w in sink.warnings)
