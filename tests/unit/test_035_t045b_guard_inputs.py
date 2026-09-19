"""T045b -- the remaining eight guard inputs.

Three things are pinned here, in this order:

1. the ACCUMULATORS (``fullsweep.instrument``) record what they are supposed
   to and stay silent-proof: an accumulator that was never threaded must be
   distinguishable from one that was threaded and saw nothing;
2. the DERIVATIONS (``fullsweep.distortion``) turn measurements the run
   already holds into the shapes FR-098/FR-099/FR-102's guards read;
3. the whole set, fed to the real registry, takes the answering set from
   7/15 to 15/15 -- which is the claim this task exists to make, and the one
   that must be re-checkable in one place.

The negative direction is pinned at least as hard as the positive one
throughout. "This guard now answers" is only interesting if "this guard still
declines when the measurement is genuinely absent" also holds; a guard that
answers unconditionally has not been wired, it has been broken.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT, _ROOT / "src", _ROOT / "tests" / "integration", _ROOT / "debug"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from debug.fullsweep import artifact as artifact_mod  # noqa: E402
from debug.fullsweep import distortion, guards, instrument  # noqa: E402

CONTRACTS = _ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"


# ===========================================================================
# 1. THE ACCUMULATORS
# ===========================================================================

# -- FR-103, the accessor counters -----------------------------------------


def test_the_four_counter_names_match_the_guard_registry_exactly():
    """``instrument`` restates the four names rather than importing them, so
    that a rename in either file is caught HERE instead of silently producing
    a counter no guard reads."""
    assert instrument.ACCESSOR_COUNTER_NAMES == guards.ACCESSOR_COUNTERS


def test_a_fifth_counter_is_refused_at_the_call_site():
    """FR-103 names four. Inventing a fifth at a call site would produce a
    number the guard never looks at -- a measurement taken and discarded,
    which is the exact defect this whole wave exists to remove."""
    c = instrument.AccessorCounters()
    with pytest.raises(ValueError, match="FR-103"):
        c.record("unreadable_widgets", scope="P:census")


def test_an_untouched_accumulator_is_distinguishable_from_an_unused_one():
    """All four at zero is FR-103's PASS condition, so "nothing went wrong"
    and "nothing was instrumented" must not look alike. ``scopes_instrumented``
    is what tells them apart."""
    never_used = instrument.AccessorCounters()
    assert never_used.total() == 0
    assert never_used.scopes_instrumented == 0

    threaded = instrument.AccessorCounters()
    threaded.open_scope("Ejagham Mini:source_inventory")
    assert threaded.total() == 0                      # same totals ...
    assert threaded.scopes_instrumented == 1          # ... different claim


def test_counters_aggregate_over_the_run_and_break_down_by_scope():
    """The recorded ruling on aggregation scope: the guard's verdict is over
    the RUN (a source enumeration that dropped objects invalidates the census
    triple exactly as a target one does, since the reconciliation subtracts
    one from the other), and ``by_scope`` carries the diagnostic."""
    c = instrument.AccessorCounters()
    c.record("unreadable_identifiers", scope="Target:census_baseline",
             accessor="ICmObject.Guid", error=RuntimeError("boom"))
    c.record("unreadable_identifiers", scope="Ejagham Mini:source_inventory",
             accessor="ICmObject.Guid", error=RuntimeError("boom"))
    c.record("skipped_source_objects", scope="Ejagham Mini:source_inventory",
             accessor="ICmObject.Guid", error=RuntimeError("boom"))

    d = c.as_dict()
    assert d["unreadable_identifiers"] == 2
    assert d["skipped_source_objects"] == 1
    assert d["by_scope"]["Target:census_baseline"]["unreadable_identifiers"] == 1
    assert d["by_scope"]["Ejagham Mini:source_inventory"]["skipped_source_objects"] == 1
    assert d["scopes_instrumented"] == 2


def test_one_broken_accessor_firing_repeatedly_does_not_produce_a_row_each_time():
    """40,000 identical failures must raise the COUNT to 40,000 and the
    evidence list by one. A row per occurrence would make the artifact
    unreadable and would itself be the truncation pressure FR-105 forbids
    responding to by shortening lists."""
    c = instrument.AccessorCounters()
    for _ in range(500):
        c.record("unreadable_names", scope="P:census",
                 accessor="ICmObject.ClassName", error=RuntimeError("same"))
    assert c.unreadable_names == 500
    assert len(c.failed_accessors) == 1
    assert c.failed_accessors[0]["occurrences"] == 500


def test_the_counter_dict_is_the_shape_the_guard_reads_and_it_answers():
    """End to end against the REAL guard, both ways."""
    c = instrument.AccessorCounters()
    c.open_scope("P:census")
    clean = guards.guard_accessor_integrity(
        guards.RunContext(project="P", accessor_counters=c.as_dict()))
    assert clean.result == "pass"

    c.record("enumeration_failures", scope="P:census",
             accessor="AllInstances", error=RuntimeError("nope"))
    dirty = guards.guard_accessor_integrity(
        guards.RunContext(project="P", accessor_counters=c.as_dict()))
    assert dirty.result == "fail"
    assert "FR-103" in dirty.message

    absent = guards.guard_accessor_integrity(guards.RunContext(project="P"))
    assert absent.result == "not-evaluated"


# -- FR-104 / FR-108, the operation log ------------------------------------


def test_a_close_appears_in_both_projections_in_each_guards_own_shape():
    """The task text's open point (b), ruled: ONE record list, TWO
    projections. FR-104 covers "open, reopen, close, or initialize" and reads
    ``error_type``; FR-108 covers close and reads ``timed_out`` /
    ``followed_by``. Two independently appended lists is how a close ends up
    in one and not the other."""
    log = instrument.OperationLog(timeout_s=90.0)
    log.record("OpenProject", "P", ok=True, kind="open", duration_s=1.0)
    log.record("CloseProject", "P", ok=True, kind="close", duration_s=2.0)

    handles = log.handle_operations()
    closes = log.close_operations()
    assert len(handles) == 2, "the close must be a handle operation too"
    assert len(closes) == 1, "only the close is a close"

    close_as_handle = [h for h in handles if h["kind"] == "close"][0]
    assert "error_type" in close_as_handle
    assert "timed_out" not in close_as_handle, (
        "FR-104 does not distinguish a hang from a throw; handing the guard a "
        "key it does not read hides a fact it should have failed on")
    assert "timed_out" in closes[0] and "followed_by" in closes[0]


def test_timed_out_is_derived_from_the_clock_not_from_an_exception():
    """``api._close_project_watchdog`` only LOGS after its deadline -- a
    wedged .NET call cannot be interrupted from Python, so it returns normally
    and raises nothing. A timeout that waited for an exception would never
    fire."""
    log = instrument.OperationLog(timeout_s=5.0)
    log.record("CloseProject", "P", ok=True, kind="close", duration_s=4.9)
    log.record("CloseProject", "Q", ok=True, kind="close", duration_s=5.1)
    by_project = {c["project"]: c for c in log.close_operations()}
    assert by_project["P"]["timed_out"] is False
    assert by_project["Q"]["timed_out"] is True
    assert by_project["Q"]["ok"] is True, (
        "a hung close raised nothing -- ok and timed_out are independent facts")

    result = guards.guard_clean_close(
        guards.RunContext(project="P", close_operations=log.close_operations()))
    assert result.result == "fail", "a timed-out close must fail CLEAN-CLOSE"


def test_followed_by_names_only_the_measurements_after_that_close():
    """FR-108: a close invalidates what came AFTER it, so the record has to
    know the order. Derived from a shared sequence counter rather than from a
    caller's memory, so a reordered step cannot make it silently wrong."""
    log = instrument.OperationLog()
    log.note_measurement("census_baseline")
    log.record("CloseProject", "T", ok=False, kind="close",
               error=RuntimeError("fail"))
    log.note_measurement("census_after_first")
    log.note_measurement("census_after_second")

    (close,) = log.close_operations()
    assert close["followed_by"] == ["census_after_first", "census_after_second"]
    assert "census_baseline" not in close["followed_by"]


def test_watch_records_a_failure_and_then_re_raises_it():
    """The context manager is instrumentation, not error handling. The bare
    excepts at the call sites stay; what changes is that the evidence no
    longer goes down with the exception."""
    log = instrument.OperationLog()
    with pytest.raises(RuntimeError, match="close blew up"):
        with log.watch("CloseProject", "P", kind="close"):
            raise RuntimeError("close blew up")
    (close,) = log.close_operations()
    assert close["ok"] is False
    assert "close blew up" in close["error_message"]


def test_an_unknown_operation_kind_is_refused():
    log = instrument.OperationLog()
    with pytest.raises(ValueError, match="FR-104"):
        log.record("Frobnicate", "P", ok=True, kind="frobnicate")


def test_handle_integrity_answers_from_the_log_and_declines_without_it():
    log = instrument.OperationLog()
    log.record("OpenProject", "P", ok=True, kind="open")
    assert guards.guard_handle_integrity(guards.RunContext(
        project="P", handle_operations=log.handle_operations())).result == "pass"

    log.record("bind_target", "T", ok=False, kind="initialize",
               error=ValueError("locked"))
    failed = guards.guard_handle_integrity(guards.RunContext(
        project="P", handle_operations=log.handle_operations()))
    assert failed.result == "fail"
    assert failed.evidence["failures"][0]["error_type"] == "ValueError"

    assert guards.guard_handle_integrity(
        guards.RunContext(project="P")).result == "not-evaluated"


# -- FR-105, the truncation counters ---------------------------------------


def test_the_omission_count_is_measured_against_the_serialized_view():
    """Comparing a document with ITSELF measures nothing. ``default=str`` is
    not an identity map, and what FR-105 asks about is what the WRITER does to
    the document."""
    doc = {"drops": {"first": {"by_reason": {"a": 2}, "records": [{"reason": "a"},
                                                                  {"reason": "a"}]}},
           "findings": [{"x": 1}], "errors": []}
    counts = instrument.count_document_omissions(
        doc, instrument.serialized_view(doc))
    assert counts["dropped_breakdown_omitted"] == 0
    assert counts["detail_omitted"] == 0


def test_a_records_list_shorter_than_its_own_reason_totals_is_an_omission():
    """The real failure mode: a caller passed a ``console_truncate``d list
    into a ``ProjectArtifact`` field, which that helper's docstring forbids.
    The reason totals are the authority on how many rows there should be."""
    doc = {"drops": {"first": {"by_reason": {"alignment": 27844},
                               "records": [{"reason": "alignment"}]}}}
    counts = instrument.count_document_omissions(
        doc, instrument.serialized_view(doc))
    assert counts["detail_omitted"] == 27843
    assert counts["where"][0]["field"] == "drops.first.records"


def test_a_detail_list_dropped_by_the_writer_is_counted():
    src = {"findings": [{"a": 1}, {"b": 2}, {"c": 3}], "errors": []}
    written = {"findings": [{"a": 1}], "errors": []}
    counts = instrument.count_document_omissions(src, written)
    assert counts["detail_omitted"] == 2


def test_no_truncation_answers_from_the_counters_and_declines_without_them():
    t = instrument.TruncationCounters()
    doc = {"drops": {}, "findings": [], "errors": []}
    t.observe("flush-1", doc, instrument.serialized_view(doc))
    assert guards.guard_no_truncation(guards.RunContext(
        project="P", truncation=t.as_dict())).result == "pass"

    bad = {"findings": [{"a": 1}], "errors": []}
    t.observe("flush-2", bad, {"findings": [], "errors": []})
    assert guards.guard_no_truncation(guards.RunContext(
        project="P", truncation=t.as_dict())).result == "fail"

    assert guards.guard_no_truncation(
        guards.RunContext(project="P")).result == "not-evaluated"


def test_the_final_flush_gap_is_bounded_and_named_rather_than_shrugged_at():
    """The 2026-08-19 open point (a). The guards read inside ``finally`` and
    the artifact is flushed immediately after, so the last write cannot feed
    the guard that judges it. Closed by measuring a dry run BEFORE the guards
    and naming exactly what the final flush adds on top -- all scalars and the
    guard block, none of them a detail-bearing list."""
    t = instrument.TruncationCounters()
    scope = t.as_dict()["final_flush_scope"]
    assert scope["none_is_a_detail_bearing_list"] is True
    for added in scope["adds_after_measurement"]:
        assert added not in instrument.DETAIL_BEARING_FIELDS, (
            "%r is added after the truncation measurement AND is a "
            "detail-bearing list -- the bound no longer holds" % added)
    assert scope["verified"] is False, "not verified until verify_final runs"


def test_verify_final_reports_a_mismatch_rather_than_assuming_none():
    t = instrument.TruncationCounters()
    t.verify_final({"findings": [{"a": 1}], "errors": []},
                   {"findings": [], "errors": []})
    d = t.as_dict()
    assert d["final_flush_scope"]["verified"] is True
    assert d["final_flush_scope"]["mismatch"], "a real mismatch must be recorded"


# ===========================================================================
# 2. THE DERIVATIONS
# ===========================================================================

# -- FR-098 ----------------------------------------------------------------


def test_an_empty_class_is_found_by_walking_the_roster_not_the_census():
    """``inventory_all`` builds from a ``defaultdict(set)``, so a class with
    zero instances is ABSENT from the census dict rather than present with an
    empty set. Iterating the census would therefore find no empties at all --
    the measurement would be vacuous by construction."""
    records = distortion.empty_measurements(
        source_census={"LexEntry": {"a"}},
        in_scope_classes=["LexEntry", "PhEnvironment", "MoStemMsa"],
        corroborating_counts={"PhEnvironment": 0, "MoStemMsa": 0},
    )
    assert {r["class"] for r in records} == {"PhEnvironment", "MoStemMsa"}


def test_the_two_fr098_outcomes_stay_distinct_once_corroborated():
    """The known weakness the 2026-08-19 ruling recorded, now closed: with an
    independent count the class-granular reading CAN tell "the project has
    rows the census did not enumerate" from "there is nothing there"."""
    records = {r["class"]: r for r in distortion.empty_measurements(
        source_census={},
        in_scope_classes=["PhEnvironment", "MoStemMsa"],
        corroborating_counts={"PhEnvironment": 12, "MoStemMsa": 0},
    )}
    assert records["PhEnvironment"]["outcome"] == guards.EMPTY_OUTCOME_PRESENT_BUT_EMPTY
    assert records["MoStemMsa"]["outcome"] == guards.EMPTY_OUTCOME_ABSENT_OR_NULL
    assert guards.guard_empty_corroboration(guards.RunContext(
        project="P", empty_measurements=list(records.values()))).result == "pass"


def test_an_uncorroborated_empty_measurement_fails_rather_than_defaulting_to_zero():
    """Substituting 0 for a scan that did not run would INVENT the
    corroboration. The guard exists to refuse exactly that."""
    records = distortion.empty_measurements(
        source_census={}, in_scope_classes=["PhEnvironment"],
        corroborating_counts=None,
    )
    assert records[0]["corroborating_count"] is None
    result = guards.guard_empty_corroboration(
        guards.RunContext(project="P", empty_measurements=records))
    assert result.result == "fail"
    assert "never corroborated" in result.message


def test_every_empty_record_says_which_granularity_produced_it():
    """The class-granular and property-granular readings answer different
    questions, and FR-098's distinction is only fully meaningful at the
    second. A record that did not say which it was could be read as the one it
    is not."""
    for rec in distortion.empty_measurements(
        source_census={}, in_scope_classes=["PhEnvironment"],
        corroborating_counts={"PhEnvironment": 0},
    ):
        assert rec["granularity"] == "class"
        assert rec["reason"]


# -- FR-099 ----------------------------------------------------------------


def test_the_three_unmeasured_dispositions_stay_apart():
    """"No accessor exists", "the accessor raised" and "never on the roster"
    are three different statements about why nothing was compared. FR-099's
    whole point is that they must not collapse."""
    records = {r["subtype"]: r for r in distortion.unhandled_subtypes(
        source_census={"TextTag": {"a"}, "ReversalIndex": {"b", "c"},
                       "CmWeirdThing": {"d"}, "LexEntry": {"e"}},
        undispatchable={"TextTag": "no ITextTag reference in flexicon"},
        unreadable={"ReversalIndex": "GetSyncableProperties hit the stub"},
        in_scope_classes=["LexEntry", "TextTag", "ReversalIndex"],
    )}
    assert records["TextTag"]["outcome_name"] == distortion.OUTCOME_UNDISPATCHABLE
    assert records["ReversalIndex"]["outcome_name"] == distortion.OUTCOME_UNREADABLE
    assert records["CmWeirdThing"]["outcome_name"] == distortion.OUTCOME_OUT_OF_SCOPE
    assert "LexEntry" not in records, "a measured class is not an unhandled subtype"


def test_each_unhandled_subtype_is_named_and_counted():
    """FR-099's actual requirement. A named outcome with no count, or a count
    with no name, fails the guard."""
    records = distortion.unhandled_subtypes(
        source_census={"ReversalIndex": {"a", "b", "c"}},
        unreadable={"ReversalIndex": "accessor raised"},
    )
    assert records[0]["count"] == 3
    assert records[0]["outcome_name"]
    assert guards.guard_unhandled_subtype(
        guards.RunContext(project="P", unhandled_subtypes=records)).result == "pass"


def test_a_subtype_reduced_to_an_equal_comparison_fails_the_guard():
    """The flag is a MEASURED fact, not a constant. Today every record sets it
    False because these classes never reach the comparator at all; should a
    path ever exist that reduces one to an absent value that compares equal,
    the guard must fail."""
    forged = [{"subtype": "X", "outcome_name": "reduced", "count": 1,
               "reduced_to_equal_comparison": True}]
    result = guards.guard_unhandled_subtype(
        guards.RunContext(project="P", unhandled_subtypes=forged))
    assert result.result == "fail"
    assert "FR-099" in result.message


def test_a_class_is_never_counted_twice_across_the_two_unmeasured_maps():
    """Double-counting would make the guard's total meaningless."""
    records = distortion.unhandled_subtypes(
        source_census={"X": {"a"}},
        undispatchable={"X": "no dispatch"},
        unreadable={"X": "also raised"},
    )
    assert len(records) == 1
    assert records[0]["outcome_name"] == distortion.OUTCOME_UNDISPATCHABLE


# -- FR-102 / FR-183 -------------------------------------------------------


def test_the_reverse_walk_sees_what_the_source_driven_walk_cannot():
    """``reconcile_objects`` walks source -> target only, so a target-side
    addition under an identity no source object carries is invisible to it."""
    records = distortion.extras(
        source_census={"LexEntry": {"a"}},
        target_before={"LexEntry": set()},
        target_after={"LexEntry": {"a", "ghost"}},
    )
    by_id = {r["id"]: r for r in records}
    assert by_id["a"]["traceable_to_source"] is True
    assert by_id["ghost"]["traceable_to_source"] is False


def test_an_object_the_target_already_had_is_not_an_extra():
    """Counting pre-existing target data would make every run's extras list
    the whole target."""
    records = distortion.extras(
        source_census={},
        target_before={"LexEntry": {"native"}},
        target_after={"LexEntry": {"native"}},
    )
    assert records == []


def test_an_untraceable_extra_fails_no_extra_and_is_not_allowlisted():
    """The recorded ruling, and its stated consequence: with no
    expected-target-native-addition roster in ``contracts/``, ``allowlisted``
    is False for every record, so real extras flip a project from VACUOUS to
    UNEXPLAINED_LOSS. A worse-looking result and a truer one."""
    records = distortion.extras(
        source_census={"LexEntry": set()},
        target_before={"LexEntry": set()},
        target_after={"LexEntry": {"ghost"}},
    )
    assert records[0]["allowlisted"] is False
    assert records[0]["allowlist_note"]
    result = guards.guard_no_extra(
        guards.RunContext(project="P", extras=records))
    assert result.result == "fail"
    assert "FR-102" in result.message


def test_native_instances_of_a_tool_owned_class_are_not_duplicates():
    """CAUGHT LIVE, and it would have failed every project in the corpus.

    ``TOOL_OWNED_IDENTITY_CLASSES``'s only member is ``CmAgent``, and every
    real FieldWorks project natively contains several (the default user, the
    parser agents) -- measured: FOUR in ``Ejagham Mini``, on a walk that
    preserved every identity and lost nothing. Judging FR-183's "exactly one"
    over the whole post-run set therefore reported a duplicate on a clean
    transfer. The population is instances purporting to record THE TOOL'S OWN
    act, not every instance of the class.
    """
    cls = "CmAgent"
    assert distortion.is_tool_owned_class(cls)
    native = {"native-default-user", "native-parser", "native-parser-2", "native-4"}
    records = distortion.extras(
        source_census={cls: native},
        target_before={cls: set()},
        target_after={cls: native},
    )
    assert len(records) == 4
    assert not any(r["tool_owned_duplicate"] for r in records)
    assert guards.guard_no_extra(
        guards.RunContext(project="P", extras=records)).result == "pass"


def test_the_pinned_tool_owned_agent_is_allowlisted_by_its_own_contract():
    """The one enumerated exception to "allowlisted is always False".

    FR-183 does not merely EXPECT this object, it REQUIRES the engine to
    create it under exactly this identity and derived from no source value.
    Reporting the contract being honoured as an unexplained extra would be a
    false failure on every successful transfer.
    """
    from debug.fullsweep.identity import TOOL_OWNED_AGENT_GUID
    records = distortion.extras(
        source_census={"CmAgent": {"native"}},
        target_before={"CmAgent": {"native"}},
        target_after={"CmAgent": {"native", TOOL_OWNED_AGENT_GUID}},
    )
    (rec,) = records
    assert rec["traceable_to_source"] is False, (
        "FR-183 forbids deriving it from a source value, so it must NOT be "
        "traceable -- the exemption is the allowlist, not a fake trace")
    assert rec["allowlisted"] is True
    assert "TOOL_OWNED_IDENTITY_CLASSES" in rec["allowlist_note"]
    assert guards.guard_no_extra(
        guards.RunContext(project="P", extras=records)).result == "pass"


def test_an_agent_under_an_unpinned_identity_is_still_a_failure():
    """The exemption is for the PINNED constant, not for the class. An agent
    recording the tool's act under some other identity is FR-183's
    "unpinned" outcome and must not ride in on the exemption."""
    records = distortion.extras(
        source_census={"CmAgent": {"native"}},
        target_before={"CmAgent": {"native"}},
        target_after={"CmAgent": {"native", "some-other-guid"}},
    )
    assert records[0]["allowlisted"] is False
    assert guards.guard_no_extra(
        guards.RunContext(project="P", extras=records)).result == "fail"


def test_a_second_tool_owned_agent_is_never_allowlistable():
    """FR-183: a SECOND instance is unexplained loss however an allowlist
    entry is written. ``guard_no_extra`` checks the duplicate branch BEFORE
    the allowlist branch, so the pinned-agent exemption above cannot launder
    a duplicate."""
    from debug.fullsweep.identity import TOOL_OWNED_AGENT_GUID
    records = distortion.extras(
        source_census={"CmAgent": {"native"}},
        target_before={"CmAgent": {"native"}},
        target_after={"CmAgent": {"native", TOOL_OWNED_AGENT_GUID, "second"}},
    )
    assert len(records) == 2
    assert all(r["tool_owned_duplicate"] for r in records)
    assert any(r["allowlisted"] for r in records), (
        "the pinned one IS allowlisted -- and must still fail")
    result = guards.guard_no_extra(guards.RunContext(project="P", extras=records))
    assert result.result == "fail"
    assert "FR-183" in result.message
    assert "never allowlistable" in result.message


def test_zero_extras_and_a_walk_that_never_ran_are_different_statements():
    """FR-137's shape, applied to the reverse walk: "0 extras" and "nobody
    looked" are the same number of records."""
    ran = guards.guard_no_extra(guards.RunContext(project="P", extras=[]))
    never = guards.guard_no_extra(guards.RunContext(project="P"))
    assert ran.result == "pass"
    assert never.result == "not-evaluated"
    assert distortion.extras_summary([])["extras_examined"] == 0


# ===========================================================================
# 3. FR-106 AT TWO SCOPES
# ===========================================================================


def _artifact(project="P", **kw):
    a = artifact_mod.ProjectArtifact(
        project=project, run_intent="BASELINE",
        revision_pair={"gramtrans": {"sha": "abc123", "dirty": False}},
        dirty_gramtrans=False, coverage_categories=["affixes"],
    )
    a.preflight = {"ok": True}
    a.baseline = {"archive": "x.fwbackup", "sha256": "deadbeef"}
    a.diagnostic_level = "normal"
    a.guards = {n: {"result": "pass"} for n in guards.GUARD_NAMES}
    a.status = "passed"
    a.verdict = "CLEAN_PASS"
    a.exit_code = 0
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def test_an_empty_exclusion_list_is_a_recorded_decision_not_a_missing_field():
    """FR-134 demands a full-coverage sweep and FR-135 demands the exclusion
    decision be recorded. ``bool([])`` is False, so reading this field's
    truthiness would fail exactly the run the feature is for."""
    driver = _driver()
    a = _artifact(excluded_category_records=[])
    record = driver.artifact_self_record(
        a, exclusion_decision_recorded=True, guards_complete=True)
    assert record["excluded_categories"] is True
    assert record["_excluded_category_count"] == 0


def test_the_capability_fingerprint_is_a_required_field_nothing_used_to_write():
    """The defect this task found: ``_preflight_gate`` discarded its result on
    the success path, so no artifact ever carried a capability fingerprint --
    and ARTIFACT-INTEGRITY, having no corpus index, never noticed."""
    driver = _driver()
    a = _artifact()
    a.preflight = {}
    record = driver.artifact_self_record(
        a, exclusion_decision_recorded=True, guards_complete=True)
    assert record["capability_fingerprint"] is False
    result = guards.guard_artifact_integrity(guards.RunContext(
        project="P", corpus_projects=["P"], artifacts_present={"P": record}))
    assert result.result == "fail"


def test_the_per_project_evidence_says_it_is_not_a_corpus_claim():
    """Two scopes, and neither may be mistaken for the other."""
    driver = _driver()
    record = driver.artifact_self_record(
        _artifact(), exclusion_decision_recorded=True, guards_complete=True)
    assert "NOT the corpus" in record["_scope"]


def test_the_corpus_index_reads_the_project_key_back_rather_than_de_mangling(tmp_path):
    """``flush_artifact``'s ``re.sub(r"[^A-Za-z0-9._ -]", "_", ...)`` is LOSSY
    and has no inverse: two project names differing only in characters that
    both map to ``_`` land on one filename."""
    for name in ("Ngoreme/FLEx", "Ngoreme:FLEx"):
        a = _artifact(project=name)
        artifact_mod.flush_artifact(a, tmp_path)
    index = artifact_mod.build_artifact_index(tmp_path)
    # Both mangle to the same file, so the second overwrote the first -- and
    # the index says which project the surviving document actually names,
    # rather than guessing from the filename.
    assert set(index) - {"_index_problems"} <= {"Ngoreme/FLEx", "Ngoreme:FLEx"}
    assert len(list(tmp_path.glob("*.json"))) == 1, "the mangle collided"
    assert "Ngoreme_FLEx" not in index, "a de-mangled name would be a guess"


def test_an_unparseable_artifact_is_a_problem_not_an_absent_project(tmp_path):
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    index = artifact_mod.build_artifact_index(tmp_path)
    assert index["_index_problems"]["unreadable"], "silence would lose it"


def test_the_corpus_document_ranges_over_the_frozen_manifest_not_the_batch(tmp_path):
    """FR-106 says "every project in the run's corpus". Reporting 3-of-3 for a
    batch drawn from eighty-four answers an easier question."""
    artifact_mod.flush_artifact(_artifact(project="A"), tmp_path)
    _path, doc = artifact_mod.write_corpus_artifact(
        corpus_projects=["A", "B", "C"], batch=["A"],
        run_intent="baseline", artifacts_dir=tmp_path)
    assert doc["corpus_size"] == 3
    assert doc["batch_size"] == 1
    assert doc["verdict"] == "INCOMPLETE", "B and C have no artifact"
    assert doc["exit_code"] != 0


def test_the_corpus_block_is_never_called_guards(tmp_path):
    """FR-109's fifteen-key completeness is a PER-PROJECT invariant. A
    one-guard block named ``guards`` would make a fourteen-key per-project
    block expressible by precedent."""
    artifact_mod.flush_artifact(_artifact(project="A"), tmp_path)
    _path, doc = artifact_mod.write_corpus_artifact(
        corpus_projects=["A"], batch=["A"],
        run_intent="baseline", artifacts_dir=tmp_path)
    assert "guards" not in doc
    assert set(doc["corpus_guards"]) == {"ARTIFACT-INTEGRITY"}
    assert doc["verdict"] == artifact_mod.CORPUS_VERDICT_COMPLETE
    with pytest.raises(ValueError, match="FR-109"):
        guards.assert_guard_block_complete(doc["corpus_guards"])


def test_the_corpus_document_does_not_borrow_a_project_verdict(tmp_path):
    """A corpus whose every child FAILED must not report a passing word at the
    top level. ``CORPUS_COMPLETE`` says only that the artifacts are all
    there."""
    a = _artifact(project="A")
    a.status, a.verdict, a.exit_code = "failed", "UNEXPLAINED_LOSS", 1
    artifact_mod.flush_artifact(a, tmp_path)
    _path, doc = artifact_mod.write_corpus_artifact(
        corpus_projects=["A"], batch=["A"],
        run_intent="baseline", artifacts_dir=tmp_path)
    assert doc["verdict"] == "CORPUS_COMPLETE"
    assert doc["verdict"] not in ("CLEAN_PASS", "PASS_WITH_ALLOWLIST")
    assert doc["artifacts_present"]["A"]["_verdict"] == "UNEXPLAINED_LOSS"


# ===========================================================================
# 4. THE CLAIM: 15/15
# ===========================================================================


def _driver():
    import importlib
    return importlib.import_module("debug.run_fullcopy_sweep")


def _full_measurement_set(driver):
    """Every guard input a complete run deposits, at its minimum honest shape."""
    from debug.fullsweep.compare import BUCKET_TRANSFERRED, ObjectAccounting
    from debug.fullsweep.moves import IdempotencyResult

    acc = ObjectAccounting(project="P")
    acc.assign("LexEntry", "a", BUCKET_TRANSFERRED, detail="payload equal")
    _members, excluded = driver.resolve_excluded_categories([])

    counters = instrument.AccessorCounters()
    counters.open_scope("P:source_inventory")
    log = instrument.OperationLog()
    log.record("OpenProject", "P", ok=True, kind="open")
    log.record("CloseProject", "P", ok=True, kind="close")
    trunc = instrument.TruncationCounters()
    doc = {"drops": {}, "findings": [], "errors": []}
    trunc.observe("flush", doc, instrument.serialized_view(doc))

    self_record = driver.artifact_self_record(
        _artifact(), exclusion_decision_recorded=True, guards_complete=True)

    return {
        "census_baseline": {"LexEntry": {"a"}},
        "census_after_first": {"LexEntry": {"a", "b"}},
        "census_after_second": {"LexEntry": {"a", "b"}},
        "written": {"LexEntry": {"new": ["b"], "removed": []}},
        "idempotency": IdempotencyResult(("LexEntry",), ("LexEntry",), {}, True),
        "planned_action_count": 2,
        "plan_conservation": {
            "per_category": {"affixes": {"planned": 2, "added": 2, "skipped": 0}},
            "total": {"planned": 2, "added": 2, "skipped": 0}},
        "accounting": acc,
        "enabled_categories": ["affixes"],
        "measured_categories": ["affixes"],
        "excluded_categories": excluded,
        "comparisons": {"affixes": {"source_objects": 1, "comparisons_performed": 4,
                                    "objects_compared": 1}},
        "drop_reasons": [],
        "engine_bug_signatures": guards.load_engine_bug_signatures(
            contracts_dir=CONTRACTS),
        # -- T045b --
        "empty_measurements": distortion.empty_measurements(
            source_census={"LexEntry": {"a"}},
            in_scope_classes=["LexEntry", "PhEnvironment"],
            corroborating_counts={"PhEnvironment": 0}),
        "unhandled_subtypes": distortion.unhandled_subtypes(
            source_census={"ReversalIndex": {"x"}},
            unreadable={"ReversalIndex": "accessor raised"}),
        "extras": distortion.extras(
            source_census={"LexEntry": {"a"}},
            target_before={"LexEntry": set()},
            target_after={"LexEntry": {"a"}}),
        "accessor_counters": counters.as_dict(),
        "handle_operations": log.handle_operations(),
        "close_operations": log.close_operations(),
        "truncation": trunc.as_dict(),
        "corpus_projects": ["P"],
        "artifacts_present": {"P": self_record},
    }


def test_the_full_measurement_set_answers_all_fifteen():
    """THE CLAIM OF T045b, in one place.

    T045a(a)+(b) reached 5/15, T045a(c) reached 7/15, and FR-109 sank both to
    VACUOUS. With the eight inputs this task adds, every guard answers -- so
    the verdict is decided by what the guards FOUND rather than by what the
    run failed to look at.
    """
    driver = _driver()
    results = guards.run_all_guards(
        driver.build_run_context("P", _full_measurement_set(driver)))
    declining = sorted(n for n, r in results.items() if r.result == "not-evaluated")
    assert declining == [], (
        "these guards still have no input: %r -- the answering set is %d/15"
        % (declining, 15 - len(declining)))
    assert driver.verdict_for_guard_results(results) != "VACUOUS"


#: The eight inputs T045b deposits. Each is load-bearing for FR-109 on its
#: own: drop one and the run is VACUOUS again.
T045B_FIELDS = (
    "empty_measurements", "unhandled_subtypes", "extras", "accessor_counters",
    "handle_operations", "close_operations", "truncation", "corpus_projects",
    "artifacts_present",
)


def test_removing_any_t045b_input_puts_the_run_straight_back_to_vacuous():
    """FR-109 is not a majority vote. Fourteen answers and one abstention is
    VACUOUS, which is what makes "15/15" the only interesting number -- and
    what makes each of these eight load-bearing rather than incremental."""
    driver = _driver()
    full = _full_measurement_set(driver)
    for name in T045B_FIELDS:
        assert name in full, "%r is not in the full measurement set" % name
        partial = {k: v for k, v in full.items() if k != name}
        results = guards.run_all_guards(driver.build_run_context("P", partial))
        assert driver.verdict_for_guard_results(results) == "VACUOUS", (
            "dropping %r still produced a non-VACUOUS verdict" % name)


def test_written_is_deposited_but_no_guard_reads_it():
    """Measured while pinning the above, and recorded rather than tidied away.

    ``written`` is on ``MEASURABLE_RUN_CONTEXT_FIELDS`` and is deposited on
    every run, but no guard reads ``ctx.written`` -- idempotency reads the
    class set off ``IdempotencyResult.written_class_set`` instead. It is not
    dead: the artifact carries it and FR-045's derivation needs it. It is
    simply not a guard INPUT, which is why dropping it leaves the verdict
    unchanged, and why the test above ranges over the eight rather than over
    every key in the measurement dict.
    """
    import dataclasses
    driver = _driver()
    assert "written" in driver.MEASURABLE_RUN_CONTEXT_FIELDS
    assert "written" in {f.name for f in dataclasses.fields(guards.RunContext)}

    full = _full_measurement_set(driver)
    without = {k: v for k, v in full.items() if k != "written"}
    with_it = guards.run_all_guards(driver.build_run_context("P", full))
    less = guards.run_all_guards(driver.build_run_context("P", without))
    assert {n: r.result for n, r in with_it.items()} ==            {n: r.result for n, r in less.items()}, (
        "a guard started reading ctx.written -- move it into T045B_FIELDS' "
        "sibling list of load-bearing inputs and update this test")


def test_every_measurable_field_name_is_a_real_run_context_field():
    """A typo in the measurable tuple would silently discard the measurement
    it names -- ``build_run_context`` would pass it to a ``RunContext`` that
    has no such keyword."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(guards.RunContext)}
    for name in _driver().MEASURABLE_RUN_CONTEXT_FIELDS:
        assert name in fields, "%r is not a RunContext field" % name


def test_the_new_measurements_survive_the_artifact_writer():
    """FR-145: a block ``flush_artifact`` could only write as a repr is not
    evidence. Both T045b blocks go through the same check T045f installed."""
    driver = _driver()
    full = _full_measurement_set(driver)
    for name in ("empty_measurements", "unhandled_subtypes", "extras",
                 "accessor_counters", "handle_operations", "close_operations",
                 "truncation", "artifacts_present"):
        json.dumps(full[name])   # raises if a record leaked a live object
