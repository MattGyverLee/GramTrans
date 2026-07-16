"""Cross-cutting tests for feature 025 (full reversals), Phase 6 Polish
T035/T036: proving that reversal drops (Part A) and config-view missing_refs
(Part B) land in the SAME unified 024 `dropped` collection from the ONE
run-plan builder (`Lib/preview.py.build_run_plan`), not two separate
channels -- and that an empty-content project makes both additions strict
no-ops (regression gate, empty === 024-only).

T035 drives the SAME wiring `build_run_plan` uses (`Lib/preview.py`:307-349):
`Lib/categories.py.plan_reversal_decisions` immediately followed by
`Lib/config_views.py.plan_config_views`, both folding into ONE shared
`dropped` list -- these are the actual production functions/call order/
shared-list identity `build_run_plan` uses, just without ALSO re-driving the
(orthogonal to this assertion) leaf-dispatch/lexical-relations machinery that
populates a real run's `context._copy_set` from live LCM entries -- this
module seeds `_copy_set` directly instead, mirroring the exact state
`build_run_plan` is in at its T035-relevant call site (`Lib/preview.py`
line ~309 onward).

T036 drives the REAL `Lib/preview.py.build_run_plan` end-to-end (full
Selection/RunContext/WSMapping), since an empty-content project needs no
extra fake LCM surface to exercise honestly.

Fakes mirror `tests/unit/test_reversal_walk.py` (reversal side) and
`tests/unit/test_config_view_copy.py` (config-view side), combined onto one
project double that exposes both surfaces (a real FLExProject handle would
too).
"""
from __future__ import annotations

import os

from gramtrans.Lib.categories import plan_reversal_decisions
from gramtrans.Lib.config_views import plan_config_views
from gramtrans.Lib.models import DroppedItemRecord, RunContext, Selection, WSMapping
from gramtrans.Lib.preview import build_run_plan


# ============================================================================
# Fakes -- reversal side (mirrors test_reversal_walk.py)
# ============================================================================

class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakeWS:
    def __init__(self, ws_id: str, handle: int) -> None:
        self.Id = ws_id
        self.Handle = handle


class _FakeWSRepo:
    def __init__(self, ws_list) -> None:
        self._ws_list = list(ws_list)

    def GetAll(self):
        return list(self._ws_list)


class _FakeReversalIndexesOps:
    def __init__(self, indexes=()) -> None:
        self._indexes = list(indexes)

    def GetAll(self):
        return list(self._indexes)


class _FakeSense:
    def __init__(self, guid: str) -> None:
        self.Guid = guid
        self.guid = guid


class _FakeReversalEntry:
    def __init__(self, guid, senses=(), form_alts=None, pos=None, subentries=()) -> None:
        self.Guid = guid
        self.guid = guid
        self.SensesRS = list(senses)
        self.ReversalForm = _FakeMultiString(form_alts or {})
        self.PartOfSpeechRA = pos
        self.SubentriesOS = list(subentries)


class _FakeReversalIndex:
    def __init__(self, guid, writing_system, entries=(), pos_list=None) -> None:
        self.Guid = guid
        self.guid = guid
        self.WritingSystem = writing_system
        self.EntriesOC = list(entries)
        self.PartsOfSpeechOA = pos_list


# ============================================================================
# Fakes -- config-view side (mirrors test_config_view_copy.py)
# ============================================================================

class _FakeCustomFields:
    """Mirrors the live `CustomFieldOperations.GetAllFields(owner_class)`: the
    argument is REQUIRED (a no-arg call raises `TypeError`, as it does against
    real flexicon). Fixture fields are modeled as entry-level; the R9 scan
    unions labels across owner classes, so class assignment is irrelevant."""

    _OWNER_CLASSES = ("LexEntry", "LexSense", "LexExampleSentence", "MoForm")

    def __init__(self, names) -> None:
        self._names = list(names)

    def GetAllFields(self, owner_class):
        if owner_class not in self._OWNER_CLASSES:
            raise ValueError("unknown owner class: %r" % (owner_class,))
        return list(self._names) if owner_class == "LexEntry" else []


# ============================================================================
# Combined project double -- exposes BOTH surfaces (a real FLExProject does
# too: WritingSystems/ReversalIndexes for the LCM side, ProjectFolder/
# CustomFields/Styles for the on-disk config-view side).
# ============================================================================

class _FakeProject:
    def __init__(self, ws_list, indexes=(), project_dir=None, custom_fields=(), styles=()) -> None:
        self.WritingSystems = _FakeWSRepo(ws_list)
        self.ReversalIndexes = _FakeReversalIndexesOps(indexes)
        if project_dir is not None:
            self.ProjectFolder = str(project_dir)
        self.CustomFields = _FakeCustomFields(custom_fields)
        self.Styles = list(styles)


class _Ctx:
    """Minimal plan-time context stand-in -- `plan_reversal_decisions` only
    reads `.source_handle`/`.target_handle`/`._copy_set` (and, inside
    `plan_reversals` itself, `._ws_map`); a bare mutable object (not the
    frozen `RunContext`) is enough and lets this test seed `_copy_set`
    directly, mirroring build_run_plan's own state at its reversal-walk call
    site without re-running the leaf-dispatch loop that would normally
    populate it."""


def _rev_dir(project_dir):
    return os.path.join(str(project_dir), "ConfigurationSettings", "ReversalIndex")


def _write(directory, filename, body):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


_CONFIG_WITH_MISSING_REFS = """<?xml version="1.0" encoding="utf-8"?>
<DictionaryConfiguration name="French" writingSystem="fr" version="26">
  <ConfigurationItem name="Reversal Entry" style="Missing-Style" field="ReversalIndexEntry">
    <ConfigurationItem name="Custom Note" isCustomField="true" field="MyCustomField">
      <WritingSystemOptions writingSystemType="analysis">
        <Option id="analysis" isEnabled="true" />
      </WritingSystemOptions>
    </ConfigurationItem>
    <ConfigurationItem name="Reversal Form" field="ReversalForm">
      <WritingSystemOptions writingSystemType="reversal">
        <Option id="de" isEnabled="true" />
      </WritingSystemOptions>
    </ConfigurationItem>
  </ConfigurationItem>
</DictionaryConfiguration>
"""


# ============================================================================
# T035 -- unified never-silent cross-cutting assertion
# ============================================================================

def test_reversal_and_config_view_drops_share_one_dropped_collection(tmp_path):
    """One shared `dropped` list, fed by the SAME two production functions
    `Lib/preview.py.build_run_plan` calls in the SAME order
    (`categories.plan_reversal_decisions` then `config_views.
    plan_config_views`'s `missing_refs` folded in) -- not two separate
    report channels. Forces at least one drop on EACH side:

    Part A (reversal): `idx_scoped` (WS 'en', mapped) has one entry linking
    both a copied and a non-copied sense -> a 'ReversalIndexEntry' partial-
    member drop; `idx_unmapped` (WS 'koh', unmapped) has an in-scope entry
    too -> a whole-index 'ReversalIndex' WS-gate drop. Together these prove
    BOTH Part-A drop shapes land in the same collector.

    Part B (config-view): a `.fwdictconfig` referencing a WS/custom-field/
    style the target lacks -> 'ConfigView' drops.
    """
    sense_copied_a = _FakeSense("s-copied-a")
    sense_other = _FakeSense("s-other")
    entry_scoped = _FakeReversalEntry(
        "e-scoped", senses=[sense_copied_a, sense_other])
    idx_scoped = _FakeReversalIndex("idx-scoped", "en", entries=[entry_scoped])

    sense_copied_b = _FakeSense("s-copied-b")
    entry_unmapped = _FakeReversalEntry("e-unmapped", senses=[sense_copied_b])
    idx_unmapped = _FakeReversalIndex(
        "idx-unmapped", "koh", entries=[entry_unmapped])

    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_rev_dir(src_dir), "fr.fwdictconfig", _CONFIG_WITH_MISSING_REFS)

    src = _FakeProject(
        ws_list=[_FakeWS("en", 1), _FakeWS("koh", 2), _FakeWS("fr", 3), _FakeWS("de", 4)],
        indexes=[idx_scoped, idx_unmapped],
        project_dir=src_dir,
    )
    tgt = _FakeProject(
        ws_list=[_FakeWS("en", 10)],  # lacks "koh", "fr", "de"
        indexes=[],
        project_dir=tgt_dir,
        custom_fields=[],
        styles=[],
    )

    ctx = _Ctx()
    ctx.source_handle = src
    ctx.target_handle = tgt
    ctx._copy_set = {"s-copied-a": True, "s-copied-b": True}
    ctx._ws_map = {}

    dropped: list = []
    resolver_cache: dict = {}

    # SAME order + SAME shared `dropped` list as Lib/preview.py.build_run_plan
    # (T018/T019 reversal call, then T033 config-view call).
    decisions = plan_reversal_decisions(ctx, resolver_cache, dropped)
    config_records = plan_config_views(src, tgt)
    for record in config_records:
        if record.missing_refs:
            dropped.extend(record.missing_refs)

    # --- Part A sanity: exactly one entry actually reproduced (idx_unmapped
    # is dropped whole, per R4 -- never guessed at). ---
    assert len(decisions) == 1
    assert decisions[0].source_entry_guid == "e-scoped"

    # --- The single unified collection carries all THREE owner_kinds. ---
    owner_kinds = {d.owner_kind for d in dropped}
    assert owner_kinds == {"ReversalIndexEntry", "ReversalIndex", "ConfigView"}

    # Every record identifies itself: owner + field + item (or, for
    # ConfigView, the config file label) + a non-empty reason.
    for record in dropped:
        assert isinstance(record, DroppedItemRecord)
        assert record.field_name
        assert record.reason
        assert record.owner_guid or record.owner_label
        assert record.item_name or record.item_guid or record.owner_label

    rev_index_entry_drops = [d for d in dropped if d.owner_kind == "ReversalIndexEntry"]
    assert len(rev_index_entry_drops) == 1
    assert rev_index_entry_drops[0].item_guid == "s-other"
    assert rev_index_entry_drops[0].reason == "member not in copy set"

    rev_index_drops = [d for d in dropped if d.owner_kind == "ReversalIndex"]
    assert len(rev_index_drops) == 1
    assert rev_index_drops[0].reason == "writing system not mapped"

    config_drops = [d for d in dropped if d.owner_kind == "ConfigView"]
    # fr.fwdictconfig: WS 'fr' (root) + WS 'de' (option) + custom field +
    # style, all absent from a target with only WS 'en' and no fields/styles.
    assert len(config_drops) == 4
    assert all(d.owner_label == "fr.fwdictconfig" for d in config_drops)


# ============================================================================
# T036 -- regression gate (empty === 024-only)
# ============================================================================

def _ctx(source, target) -> RunContext:
    return RunContext(
        source_handle=source,
        source_project_name="FakeSource",
        source_project_path="/fake/src",
        target_handle=target,
        target_project_name="FakeTarget",
        target_project_path="/fake/tgt",
        run_id="GT-20260712-000000",
        started_at="2026-07-12T00:00:00",
    )


def test_empty_project_reversal_and_config_additions_are_strict_noops(tmp_path):
    """A project with NO reversal content (empty `ReversalIndexes`) and NO
    `.fwdictconfig` files anywhere makes the 025 additions to `build_run_plan`
    strict no-ops: `reversal_decisions == ()`, `config_view_records == ()`,
    `dropped_items == ()`, and every field a 024-only plan would also have
    produced (`actions`/`skips`/`overwrites`/`excluded_lossy`) stays empty
    too -- the run-plan output is indistinguishable from a 024-only run over
    the same (empty) project."""
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    src_dir.mkdir()
    tgt_dir.mkdir()

    src = _FakeProject(
        ws_list=[_FakeWS("en", 1)], indexes=[], project_dir=src_dir,
    )
    tgt = _FakeProject(
        ws_list=[_FakeWS("en", 10)], indexes=[], project_dir=tgt_dir,
    )

    plan = build_run_plan(
        _ctx(src, tgt), Selection(), WSMapping(entries=()), src, tgt,
    )

    # 025 additions: strict no-ops.
    assert plan.reversal_decisions == ()
    assert plan.config_view_records == ()
    assert plan.dropped_items == ()
    # No stray ConfigurationSettings/* directory materialized either
    # (Preview never creates one -- P0-1, feature-025 cycle-6 remediation).
    assert not (tgt_dir / "ConfigurationSettings").exists()

    # 024-only surface: identical to what a project with nothing to transfer
    # and no reversal/config-view feature at all would have produced.
    assert plan.actions == ()
    assert plan.skips == ()
    assert plan.overwrites == ()
    assert plan.excluded_lossy == ()
