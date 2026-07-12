"""Write-first regression tests for the OVERWRITE path's reference-fidelity
gap (feature 024, FR-006/007/010).

US2 (see `test_blanking_fix.py`) fixed the ADD/closure path
(`categories._apply_reference_fields`, the Move-mode dispatcher) so a
populated source reference lands on the target and an empty source never
blanks a populated target. That fix does NOT cover the OVERWRITE path:
`transfer._execute_overwrite`'s SENSE and ENTRY branches call the raw
flexicon `ApplySyncableProperties` with `fill_gaps=False` (SENSE: always;
ENTRY: whenever `write_mode != "merge"`, i.e. by default), and flexicon's
`fill_gaps=False` semantics for `SenseTypeRA` / `DoNotPublishInRC` /
`DoNotShowMainEntryInRC` are BLANK-ON-EMPTY / CLEAR-AND-REBUILD
(flexicon source: `LexSenseOperations.ApplySyncableProperties` lines
692-752, `LexEntryOperations.ApplySyncableProperties` lines 585-660):

- `SenseTypeRA`: an empty/unset source value sets `item.SenseTypeRA = None`
  unconditionally (line 706) -- blanks a populated target.
- `DoNotPublishInRC` / `DoNotShowMainEntryInRC`: `rc_collection.Clear()`
  runs unconditionally under `fill_gaps=False` (line 742 / entry-level
  equivalent) before re-adding whatever the (possibly empty) source had --
  an empty source clears a populated target collection.
- An unresolved custom `SenseTypeRA` GUID (present in source, absent from
  target's `SenseTypesOA`) only `_log.warning`s (lines 700-704) -- it is
  never surfaced as a `DroppedItemRecord` (FR-010), unlike the ADD/closure
  path's `decide_reference` -> `REPORT_DROPPED` handling.

This file drives `transfer._execute_overwrite` directly (its SENSE and
ENTRY branches), not the resolver in isolation, using fakes whose
`ApplySyncableProperties` models the real flexicon fill_gaps=False
blank/clear behavior described above -- so a red run here reflects the
actual production gap, not an artifact of an under-specified fake.

No live project is required anywhere in this file.
"""
from __future__ import annotations

import logging
import sys
import types

import pytest

from gramtrans.Lib import transfer
from gramtrans.Lib.models import DroppedItemRecord, GrammarCategory, PlannedOverwrite
from gramtrans.Lib.residue import ImportResidueTag


TAG = ImportResidueTag.make(
    run_id="GT-20260701-120000",
    source_project_name="Ejagham Mini",
    timestamp="2026-07-01T12:00:00",
)


# ============================================================================
# Fakes
# ============================================================================


class _FakeReportSink:
    def __init__(self):
        self.infos: list = []
        self.warnings: list = []

    def Info(self, msg):  # noqa: N802
        self.infos.append(msg)

    def Warning(self, msg):  # noqa: N802
        self.warnings.append(msg)

    def Error(self, msg):  # noqa: N802
        pass

    def Blank(self):
        pass


class _FakeRCCollection:
    """Fake FDO reference collection: `.Clear()` + `.Add()` + iteration --
    exactly the surface flexicon's `ApplySyncableProperties` writes through
    for `DoNotPublishInRC` / `DoNotShowMainEntryInRC`."""

    def __init__(self, items=()) -> None:
        self.items = list(items)

    def Clear(self) -> None:
        self.items = []

    def Add(self, item) -> None:
        self.items.append(item)

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


class _FakePossibility:
    def __init__(self, guid, name=""):
        self.Guid = guid
        self.Name = name


class _FakeSense:
    """Duck-typed ILexSense: only what `_execute_overwrite`'s SENSE branch
    and `apply_residue`'s Carrier-A path touch."""

    def __init__(self, guid, syncable_props, sense_type=None,
                 do_not_publish=(), do_not_show=()):
        self.Guid = guid
        self.ClassName = "LexSense"
        self.LiftResidue = None
        self.syncable_props = syncable_props
        self.SenseTypeRA = sense_type
        self.DoNotPublishInRC = _FakeRCCollection(do_not_publish)
        self.DoNotShowMainEntryInRC = _FakeRCCollection(do_not_show)


class _FakeEntry:
    """Duck-typed ILexEntry: only what `_execute_overwrite`'s ENTRY/SENSE
    branches and `apply_residue`'s Carrier-A path touch."""

    def __init__(self, guid, syncable_props, do_not_publish=(), do_not_show=(),
                 senses=()):
        self.Guid = guid
        self.ClassName = "LexEntry"
        self.LiftResidue = None
        self.syncable_props = syncable_props
        self.DoNotPublishInRC = _FakeRCCollection(do_not_publish)
        self.DoNotShowMainEntryInRC = _FakeRCCollection(do_not_show)
        self._senses = list(senses)


class _FakeSensesOps:
    """Fake flexicon `LexSenseOperations`: `GetSyncableProperties` is a
    passthrough; `ApplySyncableProperties` MODELS the real
    `fill_gaps=False` blank/clear behavior (flexicon
    `code/Lexicon/LexSenseOperations.py` lines 692-752) -- this is the
    fake that lets these tests genuinely exercise the current bug rather
    than assume it."""

    def __init__(self, sense_type_by_guid=None, pub_by_guid=None):
        self._sense_type_by_guid = dict(sense_type_by_guid or {})
        self._pub_by_guid = dict(pub_by_guid or {})

    def GetSyncableProperties(self, sense):
        return dict(sense.syncable_props)

    def ApplySyncableProperties(self, item, props, ws_map=None, fill_gaps=False):
        # --- SenseTypeRA (mirrors lines 692-706) ---
        if "SenseTypeRA" in props:
            guid_str = props["SenseTypeRA"]
            if guid_str:
                obj = self._sense_type_by_guid.get(guid_str)
                if obj is not None:
                    item.SenseTypeRA = obj
                else:
                    # Mirrors the real code's fate for an unresolved custom
                    # SenseType GUID: a log line, nothing structural.
                    logging.getLogger(__name__).warning(
                        "[WARN] ApplySyncableProperties: SenseTypeRA GUID %s "
                        "not found in target project -- skipped", guid_str,
                    )
            else:
                item.SenseTypeRA = None  # <-- models the real blank-on-empty (line 706)

        # --- DoNotPublishInRC / DoNotShowMainEntryInRC (mirrors 708-752) ---
        for field_name in ("DoNotPublishInRC", "DoNotShowMainEntryInRC"):
            if field_name not in props:
                continue
            if fill_gaps:
                continue
            guid_set = props[field_name]
            rc_collection = getattr(item, field_name)
            rc_collection.Clear()  # <-- models the real unconditional Clear() (line 742)
            for gs in guid_set:
                obj = self._pub_by_guid.get(gs)
                if obj is not None:
                    rc_collection.Add(obj)


class _FakeLexEntryOps:
    """Fake flexicon `LexEntryOperations`: `GetAll`/`GetSenses` are the
    lookup surface `_execute_overwrite` scans by GUID;
    `ApplySyncableProperties` models the real entry-level
    `fill_gaps=False` clear-and-rebuild for the two RC fields (flexicon
    `code/Lexicon/LexEntryOperations.py` lines 585-660)."""

    def __init__(self, entries, pub_by_guid=None):
        self._entries = list(entries)
        self._pub_by_guid = dict(pub_by_guid or {})

    def GetAll(self):
        return list(self._entries)

    def GetSenses(self, entry):
        return list(entry._senses)

    def GetSyncableProperties(self, entry):
        return dict(entry.syncable_props)

    def ApplySyncableProperties(self, item, props, ws_map=None, fill_gaps=False):
        for field_name in ("DoNotPublishInRC", "DoNotShowMainEntryInRC"):
            if field_name not in props:
                continue
            if fill_gaps:
                continue
            guid_set = props[field_name]
            rc_collection = getattr(item, field_name)
            rc_collection.Clear()  # <-- models the real unconditional Clear()
            for gs in guid_set:
                obj = self._pub_by_guid.get(gs)
                if obj is not None:
                    rc_collection.Add(obj)


class _FakeCache:
    def __init__(self, lang_project=None):
        self.DefaultAnalWs = 1
        self.LangProject = lang_project


class _FakeTargetList:
    """Fake ICmPossibilityList: flat GUID-searchable container -- mirrors
    `references._find_in_possibility_list`'s `PossibilitiesOS` walk."""

    def __init__(self, items=()) -> None:
        self.PossibilitiesOS = list(items)


class _FakeLexDb:
    def __init__(self, sense_types_list, publication_types_list) -> None:
        self.SenseTypesOA = sense_types_list
        self.PublicationTypesOA = publication_types_list


class _FakeLangProject:
    def __init__(self, lex_db) -> None:
        self.LexDbOA = lex_db


class _FakeProject:
    """Minimal fake FLExProject: `.LexEntry`, `.Senses`, `.Cache` -- the
    exact accessors `_execute_overwrite`'s ENTRY/SENSE branches use.

    `lang_project` (feature 024 US2 double-application regression test,
    below): optional `_FakeLangProject`, threaded onto `.Cache.LangProject`
    so the resolver's `references._lp(target).LexDbOA.{SenseTypesOA,
    PublicationTypesOA}` target-list lookups succeed for the non-empty-
    source overwrite scenarios. `None` (the default) matches every
    pre-existing test in this file, none of which exercise the resolver's
    target-list lookup (their sources are all empty, so `decide_reference`
    is never reached)."""

    def __init__(self, lex_entry_ops, senses_ops, lang_project=None):
        self.LexEntry = lex_entry_ops
        self.Senses = senses_ops
        self.Cache = _FakeCache(lang_project)


@pytest.fixture()
def patch_lcmodel(monkeypatch):
    """Inject a fake `SIL.LCModel` module so `_execute_overwrite`'s lazy
    `from SIL.LCModel import ICmObject` succeeds without pythonnet/LCM.
    `ICmObject` is identity here: our fakes already expose `.Guid` and
    `.ClassName` directly, matching the real cast's observable surface."""
    fake_pkg = types.ModuleType("SIL")
    fake_lcmodel = types.ModuleType("SIL.LCModel")
    fake_lcmodel.ICmObject = lambda obj: obj
    fake_pkg.LCModel = fake_lcmodel
    monkeypatch.setitem(sys.modules, "SIL", fake_pkg)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", fake_lcmodel)


# ============================================================================
# 1. SENSE overwrite: empty source SenseTypeRA must not blank a populated
#    target SenseTypeRA (FR-006/007). Fails today -- fake models line 706.
# ============================================================================


def test_overwrite_sense_empty_source_sense_type_does_not_blank_target(patch_lcmodel):
    entry_guid = "11111111-0000-0000-0000-000000000001"
    sense_guid = "22222222-0000-0000-0000-000000000002"
    existing_sense_type = _FakePossibility("existing-st-guid", name="Already Set")

    tgt_sense = _FakeSense(
        sense_guid,
        syncable_props={"Gloss": {}},
        sense_type=existing_sense_type,
    )
    tgt_entry = _FakeEntry(entry_guid, syncable_props={}, senses=[tgt_sense])

    src_sense = _FakeSense(
        sense_guid,
        # Empty/unset on source -- matches GetSyncableProperties's
        # always-present-key, None-when-unset shape (flexicon line 626).
        syncable_props={"Gloss": {}, "SenseTypeRA": None,
                         "DoNotPublishInRC": frozenset(),
                         "DoNotShowMainEntryInRC": frozenset()},
    )
    src_entry = _FakeEntry(entry_guid, syncable_props={}, senses=[src_sense])

    senses_ops = _FakeSensesOps()
    target = _FakeProject(_FakeLexEntryOps([tgt_entry]), senses_ops)
    source = _FakeProject(_FakeLexEntryOps([src_entry]), senses_ops)

    overwrite = PlannedOverwrite(
        category=GrammarCategory.SENSE,
        source_guid=sense_guid,
        target_guid=sense_guid,
        summary="overwrite sense",
        owner_guid=entry_guid,
    )

    transfer._execute_overwrite(overwrite, source, target, _FakeReportSink(), TAG)

    assert tgt_sense.SenseTypeRA is existing_sense_type, (
        "FR-006/007: an empty/unset source SenseTypeRA must never blank the "
        "target's existing populated SenseTypeRA during OVERWRITE"
    )


# ============================================================================
# 2. SENSE overwrite: empty source DoNotPublishInRC / DoNotShowMainEntryInRC
#    must not clear a populated target collection. Fails today -- fake
#    models line 742's unconditional Clear().
# ============================================================================


def test_overwrite_sense_empty_source_rc_fields_do_not_clear_target(patch_lcmodel):
    entry_guid = "33333333-0000-0000-0000-000000000003"
    sense_guid = "44444444-0000-0000-0000-000000000004"
    existing_pub = _FakePossibility("existing-pub-guid", name="Already Set")
    existing_hide = _FakePossibility("existing-hide-guid", name="Already Set")

    tgt_sense = _FakeSense(
        sense_guid,
        syncable_props={"Gloss": {}},
        do_not_publish=[existing_pub],
        do_not_show=[existing_hide],
    )
    tgt_entry = _FakeEntry(entry_guid, syncable_props={}, senses=[tgt_sense])

    src_sense = _FakeSense(
        sense_guid,
        syncable_props={"Gloss": {}, "SenseTypeRA": None,
                         "DoNotPublishInRC": frozenset(),
                         "DoNotShowMainEntryInRC": frozenset()},
    )
    src_entry = _FakeEntry(entry_guid, syncable_props={}, senses=[src_sense])

    senses_ops = _FakeSensesOps()
    target = _FakeProject(_FakeLexEntryOps([tgt_entry]), senses_ops)
    source = _FakeProject(_FakeLexEntryOps([src_entry]), senses_ops)

    overwrite = PlannedOverwrite(
        category=GrammarCategory.SENSE,
        source_guid=sense_guid,
        target_guid=sense_guid,
        summary="overwrite sense",
        owner_guid=entry_guid,
    )

    transfer._execute_overwrite(overwrite, source, target, _FakeReportSink(), TAG)

    assert list(tgt_sense.DoNotPublishInRC) == [existing_pub], (
        "FR-006/007: an empty source DoNotPublishInRC must never clear the "
        "target's existing populated collection during OVERWRITE"
    )
    assert list(tgt_sense.DoNotShowMainEntryInRC) == [existing_hide], (
        "FR-006/007: an empty source DoNotShowMainEntryInRC must never "
        "clear the target's existing populated collection during OVERWRITE"
    )


# ============================================================================
# 3. ENTRY overwrite: empty entry-level source DoNotPublishInRC /
#    DoNotShowMainEntryInRC must not clear a populated target. Fails today
#    -- fake models the entry-level equivalent of line 742's Clear().
# ============================================================================


def test_overwrite_entry_empty_source_rc_fields_do_not_clear_target(patch_lcmodel):
    entry_guid = "55555555-0000-0000-0000-000000000005"
    existing_pub = _FakePossibility("existing-pub-guid", name="Already Set")
    existing_hide = _FakePossibility("existing-hide-guid", name="Already Set")

    tgt_entry = _FakeEntry(
        entry_guid,
        syncable_props={"CitationForm": {}},
        do_not_publish=[existing_pub],
        do_not_show=[existing_hide],
    )
    src_entry = _FakeEntry(
        entry_guid,
        syncable_props={"CitationForm": {},
                         "DoNotPublishInRC": frozenset(),
                         "DoNotShowMainEntryInRC": frozenset()},
    )

    target = _FakeProject(_FakeLexEntryOps([tgt_entry]), _FakeSensesOps())
    source = _FakeProject(_FakeLexEntryOps([src_entry]), _FakeSensesOps())

    overwrite = PlannedOverwrite(
        category=GrammarCategory.ENTRY,
        source_guid=entry_guid,
        target_guid=entry_guid,
        summary="overwrite entry",
    )

    transfer._execute_overwrite(overwrite, source, target, _FakeReportSink(), TAG)

    assert list(tgt_entry.DoNotPublishInRC) == [existing_pub], (
        "FR-006/007: an empty entry-level source DoNotPublishInRC must "
        "never clear the target's existing populated collection during "
        "OVERWRITE"
    )
    assert list(tgt_entry.DoNotShowMainEntryInRC) == [existing_hide], (
        "FR-006/007: an empty entry-level source DoNotShowMainEntryInRC "
        "must never clear the target's existing populated collection "
        "during OVERWRITE"
    )


# ============================================================================
# 4. SENSE overwrite: an unresolved CUSTOM SenseType GUID must yield exactly
#    one DroppedItemRecord (FR-010), not a silent log.
#
#    Post feature-024-US2-FIX-1 update: `_strip_ref_fields` now strips
#    `SenseTypeRA` from `src_props` UNCONDITIONALLY (see `transfer.py`), so
#    the raw `ApplySyncableProperties` call never sees the key at all any
#    more -- `_FakeSensesOps`'s `if "SenseTypeRA" in props:` guard (mirroring
#    the real code's `_log.warning`, lines 700-704) is therefore never
#    entered, and the old "a log line fires" assertion that used to hold
#    here no longer applies (that log line was always only an incidental
#    confirmation of the OLD path, not this test's actual FR-010 contract).
#    The load-bearing assertion is unchanged and still exercised: the
#    SENSE branch's dedicated `_raw_sense_type_guid` fallback (the resolver
#    structurally cannot see a raw GUID with no matching live `src_sense`
#    attribute) must still surface exactly one DroppedItemRecord.
# ============================================================================


def test_overwrite_sense_unresolved_custom_sense_type_yields_dropped_record(
    patch_lcmodel, caplog,
):
    entry_guid = "66666666-0000-0000-0000-000000000006"
    sense_guid = "77777777-0000-0000-0000-000000000007"
    custom_sense_type_guid = "custom-sense-type-guid-absent-from-target"

    tgt_sense = _FakeSense(sense_guid, syncable_props={"Gloss": {}})
    tgt_entry = _FakeEntry(entry_guid, syncable_props={}, senses=[tgt_sense])

    src_sense = _FakeSense(
        sense_guid,
        syncable_props={"Gloss": {}, "SenseTypeRA": custom_sense_type_guid,
                         "DoNotPublishInRC": frozenset(),
                         "DoNotShowMainEntryInRC": frozenset()},
    )
    src_entry = _FakeEntry(entry_guid, syncable_props={}, senses=[src_sense])

    # sense_type_by_guid deliberately does NOT contain custom_sense_type_guid
    # -- it exists in source but not target, exactly the FR-010 scenario.
    senses_ops = _FakeSensesOps(sense_type_by_guid={})
    target = _FakeProject(_FakeLexEntryOps([tgt_entry]), senses_ops)
    source = _FakeProject(_FakeLexEntryOps([src_entry]), senses_ops)

    overwrite = PlannedOverwrite(
        category=GrammarCategory.SENSE,
        source_guid=sense_guid,
        target_guid=sense_guid,
        summary="overwrite sense",
        owner_guid=entry_guid,
    )

    with caplog.at_level(logging.WARNING):
        result = transfer._execute_overwrite(
            overwrite, source, target, _FakeReportSink(), TAG,
        )

    # Post-FIX-1: `SenseTypeRA` is stripped from `src_props` unconditionally
    # BEFORE the raw ApplySyncableProperties call, so `_FakeSensesOps` never
    # even sees the key -- its internal `_log.warning`-mirroring branch is
    # not entered, and no log line fires here any more (this is the
    # expected, intentional consequence of FIX 1 making the resolver the
    # sole handler for this field; the raw call no longer runs its own
    # partial "baseline" resolution/logging for it at all).
    assert not any(
        custom_sense_type_guid in rec.message for rec in caplog.records
    ), (
        "post-FIX-1: the raw ApplySyncableProperties call must never see "
        "SenseTypeRA any more (stripped unconditionally), so its own "
        "unresolved-GUID log line must not fire"
    )

    # The load-bearing FR-010 contract: `_execute_overwrite`'s SENSE branch
    # has a dedicated targeted fallback (`_raw_sense_type_guid`) for exactly
    # this case -- a raw GUID present in the flat props dict with no
    # matching live object on `src_sense` for the resolver to see -- and it
    # must still surface exactly one structured DroppedItemRecord.
    dropped_records = [r for r in (result or []) if isinstance(r, DroppedItemRecord)]
    assert len(dropped_records) == 1, (
        "FR-010: an unresolved custom SenseTypeRA GUID during OVERWRITE "
        "must surface exactly one DroppedItemRecord, not only a log line "
        f"-- got {len(dropped_records)} DroppedItemRecord(s) in the "
        f"_execute_overwrite return value {result!r}"
    )


# ============================================================================
# 5. SENSE overwrite: a NON-EMPTY source DoNotPublishInRC /
#    DoNotShowMainEntryInRC must land on the target EXACTLY ONCE.
#
#    Defect (double-application): `_strip_empty_ref_fields` only strips a
#    ref key when its value is FALSY. A TRUTHY collection therefore reaches
#    BOTH the raw `ApplySyncableProperties` (Clear()+re-Add() -- models
#    flexicon's real fill_gaps=False behavior, see `_FakeSensesOps` above)
#    AND the resolver's collection branch (`categories._apply_reference_fields`,
#    `owner_coll.Add(resolved)` with NO membership check) -- both resolve the
#    SAME source GUID to the SAME target-side object, so the target
#    collection ends up holding it TWICE. RED before FIX 1 (unconditional
#    strip, so the raw call never sees these fields at all) + FIX 2
#    (resolver membership-check idempotence).
# ============================================================================


def test_overwrite_sense_nonempty_source_rc_fields_no_duplicates(patch_lcmodel):
    entry_guid = "88888888-0000-0000-0000-000000000008"
    sense_guid = "99999999-0000-0000-0000-000000000009"
    new_pub_guid = "aaaaaaa1-0000-0000-0000-0000000000a1"
    new_hide_guid = "aaaaaaa2-0000-0000-0000-0000000000a2"

    # The SAME target-side objects must be reachable BOTH via the raw
    # ApplySyncableProperties fake's `pub_by_guid` map (what the Clear()+
    # Add() path adds) AND via `Cache.LangProject.LexDbOA.PublicationTypesOA`
    # (what the resolver's `decide_reference` finds by GUID) -- exactly the
    # real-world shape: both paths resolve the same GUID to the same live
    # target possibility, so a naive double-Add is genuinely observable.
    tgt_new_pub = _FakePossibility(new_pub_guid, name="New Pub")
    tgt_new_hide = _FakePossibility(new_hide_guid, name="New Hide")

    tgt_sense = _FakeSense(sense_guid, syncable_props={"Gloss": {}})
    tgt_entry = _FakeEntry(entry_guid, syncable_props={}, senses=[tgt_sense])

    # Source-side objects: distinct instances, same GUIDs -- what the
    # resolver's `_iter_reference_items` walk reads directly off `src_sense`.
    src_new_pub = _FakePossibility(new_pub_guid, name="New Pub")
    src_new_hide = _FakePossibility(new_hide_guid, name="New Hide")
    src_sense = _FakeSense(
        sense_guid,
        syncable_props={"Gloss": {}, "SenseTypeRA": None,
                         "DoNotPublishInRC": frozenset({new_pub_guid}),
                         "DoNotShowMainEntryInRC": frozenset({new_hide_guid})},
        do_not_publish=[src_new_pub],
        do_not_show=[src_new_hide],
    )
    src_entry = _FakeEntry(entry_guid, syncable_props={}, senses=[src_sense])

    senses_ops = _FakeSensesOps(
        pub_by_guid={new_pub_guid: tgt_new_pub, new_hide_guid: tgt_new_hide},
    )
    lang_project = _FakeLangProject(_FakeLexDb(
        sense_types_list=_FakeTargetList([]),
        publication_types_list=_FakeTargetList([tgt_new_pub, tgt_new_hide]),
    ))
    target = _FakeProject(_FakeLexEntryOps([tgt_entry]), senses_ops, lang_project)
    source = _FakeProject(_FakeLexEntryOps([src_entry]), senses_ops)

    overwrite = PlannedOverwrite(
        category=GrammarCategory.SENSE,
        source_guid=sense_guid,
        target_guid=sense_guid,
        summary="overwrite sense",
        owner_guid=entry_guid,
    )

    transfer._execute_overwrite(overwrite, source, target, _FakeReportSink(), TAG)

    assert list(tgt_sense.DoNotPublishInRC) == [tgt_new_pub], (
        "feature 024 US2: a non-empty source DoNotPublishInRC must land on "
        "the target EXACTLY ONCE, not be double-applied via both the raw "
        "ApplySyncableProperties Clear()+Add() and the resolver's Add() -- "
        f"got {list(tgt_sense.DoNotPublishInRC)!r}"
    )
    assert list(tgt_sense.DoNotShowMainEntryInRC) == [tgt_new_hide], (
        "feature 024 US2: a non-empty source DoNotShowMainEntryInRC must "
        "land on the target EXACTLY ONCE, not be double-applied -- got "
        f"{list(tgt_sense.DoNotShowMainEntryInRC)!r}"
    )


# ============================================================================
# 6. SENSE overwrite: a NON-EMPTY source SenseTypeRA must still set the
#    target's SenseTypeRA correctly once the raw ApplySyncableProperties
#    call stops seeing it at all (FIX 1 strips it unconditionally) -- the
#    resolver pass must be the one carrying it end to end. (ATOMIC, so a
#    second resolver setattr is naturally idempotent; this pins the
#    non-empty-source coverage the empty-source tests above don't reach.)
# ============================================================================


def test_overwrite_sense_nonempty_source_sense_type_sets_target(patch_lcmodel):
    entry_guid = "aaaaaaaa-1111-0000-0000-000000000001"
    sense_guid = "bbbbbbbb-1111-0000-0000-000000000002"
    sense_type_guid = "cccccccc-1111-0000-0000-000000000003"

    tgt_sense_type = _FakePossibility(sense_type_guid, name="Idiom")
    tgt_sense = _FakeSense(sense_guid, syncable_props={"Gloss": {}})
    tgt_entry = _FakeEntry(entry_guid, syncable_props={}, senses=[tgt_sense])

    src_sense_type = _FakePossibility(sense_type_guid, name="Idiom")
    src_sense = _FakeSense(
        sense_guid,
        syncable_props={"Gloss": {}, "SenseTypeRA": sense_type_guid,
                         "DoNotPublishInRC": frozenset(),
                         "DoNotShowMainEntryInRC": frozenset()},
        sense_type=src_sense_type,
    )
    src_entry = _FakeEntry(entry_guid, syncable_props={}, senses=[src_sense])

    senses_ops = _FakeSensesOps(sense_type_by_guid={sense_type_guid: tgt_sense_type})
    lang_project = _FakeLangProject(_FakeLexDb(
        sense_types_list=_FakeTargetList([tgt_sense_type]),
        publication_types_list=_FakeTargetList([]),
    ))
    target = _FakeProject(_FakeLexEntryOps([tgt_entry]), senses_ops, lang_project)
    source = _FakeProject(_FakeLexEntryOps([src_entry]), senses_ops)

    overwrite = PlannedOverwrite(
        category=GrammarCategory.SENSE,
        source_guid=sense_guid,
        target_guid=sense_guid,
        summary="overwrite sense",
        owner_guid=entry_guid,
    )

    transfer._execute_overwrite(overwrite, source, target, _FakeReportSink(), TAG)

    assert tgt_sense.SenseTypeRA is tgt_sense_type, (
        "a non-empty source SenseTypeRA must set the target's SenseTypeRA "
        f"during OVERWRITE -- got {tgt_sense.SenseTypeRA!r}"
    )
