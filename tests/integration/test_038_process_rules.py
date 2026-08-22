"""T063 / T064 -- layer (c): the corpus acceptance for affix process rules.

Asserted against a COMMITTED MEASUREMENT
(`_snapshots/process-rules-038-mbugwe.json`, produced by
`debug/run038_phase6_live.py` transferring `Mbugwe LizzieHC practice` into a
target restored blank from `backups/Target 2026-07-06 0218.fwbackup`).
Asserting against a recorded run rather than re-running is the discipline
`test_038_two_mode_and_tallies.py` and
`test_object_census.py::TestMeasuredCensusSnapshots` already set: a live run
restores and rewrites a FLEx project and takes minutes, which is not something
a suite invocation may do by surprise.

`Mbugwe LizzieHC practice` is the ONLY sanctioned project with affix process
rules -- 18 `MoAffixProcess`, 124 `MoAffixAllomorph`, 137 `MoStemAllomorph`.
Ejagham Mini has 0 and Esperanto has 0 of 15,318 entries, so there is no second
corpus and no way to prove the create path generalises. That residual risk is
recorded in research.md R5 and is not something this file can close.

WHY THE COUNTS COME IN PAIRS. A downgrade produces `MoAffixProcess 0` with
`MoAffixAllomorph` inflated by exactly the rule count -- the +13/+1 excess
signature that exposed the original defect -- so either total alone can be
satisfied by the defect itself. And both totals together can still be satisfied
by a correctly-classed rule with an empty `InputOS`/`OutputOS`, which has lost
everything that makes it a rule, so the per-rule member shapes are asserted
too. That is what SC-006's "with their input and output content" means.

WHAT PHASE 6 CAN AND CANNOT DELIVER. T063's task text asks for
`count(MoAffixProcess) == 18`. Phase 6's OWN checkpoint says the opposite for
this phase -- "the 6 rules with shared contexts are reported and skipped with a
named reason" -- because those rules' `PhSequenceContext.MembersRS` reference
`PhSimpleContext*` objects owned by the shared, project-level
`PhPhonData.ContextsOS`, which is a Phase 7 closure dependency (create-path
contract condition 4). 18 is the Phase 8 figure and T077 is the task that
re-runs this file to claim it.

So the assertions are split deliberately:

  * the PHASE-INDEPENDENT invariants, which must hold now and after T076 --
    every rule is accounted for, every transferred rule has real content, every
    skipped rule has a reason, and no rule was downgraded;
  * the PHASE-SCOPED split, pinned to the measurement, which T077 updates by
    changing one expectation rather than by rewriting the test.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_SNAPSHOT = (Path(__file__).parent / "_snapshots"
             / "process-rules-038-mbugwe.json")

#: The source corpus, from the create-path contract section 4 (live
#: enumeration `op-042605267-012` / `op-042704061-014`).
SOURCE_RULES = 18
SOURCE_AFFIX_ALLOMORPHS = 124

#: Aggregate member census over those 18 rules, same source.
SOURCE_MEMBER_TOTALS = {
    "MoInsertPhones": 63,
    "MoCopyFromInput": 38,
    "PhVariable": 21,
    "PhSimpleContextSeg": 12,
    "PhSequenceContext": 6,
    "PhSimpleContextNC": 5,
}

#: Classes with zero instances INSIDE any affix process rule. They are NOT
#: zero project-wide and the first draft of this file wrongly asserted that
#: they were: the live run gained 9 `PhIterationContext`, 9
#: `PhSimpleContextBdry`, 20 `PhSequenceContext` and 56 `PhSimpleContextSeg`
#: in the destination, all of them owned by transferred PHONOLOGICAL RULES and
#: by `PhPhonData.ContextsOS`, which have nothing to do with US5. The claim
#: that survives measurement is per-RULE, so that is where it is asserted.
UNEXERCISED_IN_RULES = (
    "MoModifyFromInput", "MoInsertNC", "PhSimpleContextBdry",
    "PhIterationContext",
)


@pytest.fixture(scope="module")
def snapshot():
    if not _SNAPSHOT.is_file():
        pytest.skip(
            "no committed measurement at " + str(_SNAPSHOT) + " -- produce it "
            "with `python debug/run038_phase6_live.py` (it restores the "
            "throwaway target first)"
        )
    return json.loads(_SNAPSHOT.read_text(encoding="utf-8"))


# ===========================================================================
# The source is the corpus the contract measured
# ===========================================================================

def test_the_source_is_the_corpus_the_contract_measured(snapshot):
    """Guards every other assertion's premise. If the source project has
    changed since the contract enumerated it, the expected figures below are
    measuring something else and a green run would mean nothing."""
    src = snapshot["source_counts"]
    assert src["MoAffixProcess"] == SOURCE_RULES
    assert src["MoAffixAllomorph"] == SOURCE_AFFIX_ALLOMORPHS
    assert len(snapshot["source_rule_shapes"]) == SOURCE_RULES

    totals = {}
    for shape in snapshot["source_rule_shapes"]:
        for key, count in list(shape["inputs"].items()) + list(
                shape["outputs"].items()):
            totals[key] = totals.get(key, 0) + count
    assert totals == SOURCE_MEMBER_TOTALS


# ===========================================================================
# T063 -- phase-independent: what must hold now AND after T076
# ===========================================================================

def test_no_rule_was_downgraded(snapshot):
    """THE assertion this whole feature exists for. `MoAffixAllomorph` gains
    exactly the source's 124 -- not 124 + the number of rules.

    A downgrade is invisible in the `MoAffixProcess` count alone when the
    engine also skips (both read 0), and invisible in the allomorph count
    alone when it also transfers (both read +124). Together they are not
    satisfiable by the defect in any combination.
    """
    delta = snapshot["delta"]
    assert delta["MoAffixAllomorph"] == SOURCE_AFFIX_ALLOMORPHS, (
        "MoAffixAllomorph gained %s, expected exactly %s -- an excess of "
        "about the rule count is the +13/+1 downgrade signature"
        % (delta["MoAffixAllomorph"], SOURCE_AFFIX_ALLOMORPHS)
    )


def test_every_rule_is_accounted_for(snapshot):
    """Reproduced plus reported equals the source's 18. A rule that was
    neither is the silent loss FR-013 forbids -- and it is exactly what the
    original defect looked like from the report's side."""
    report = snapshot["report"]
    assert report["process_rules_total"] == SOURCE_RULES
    assert (report["process_rules_reproduced"]
            + len(report["process_rules_not_reproduced"])) == SOURCE_RULES


def test_the_destination_holds_exactly_the_rules_that_were_reproduced(
    snapshot
):
    """The report and the database agree. A report claiming reproductions the
    project does not hold is worse than an honest failure."""
    assert (snapshot["delta"]["MoAffixProcess"]
            == snapshot["report"]["process_rules_reproduced"])


def test_every_skipped_rule_names_its_blocker(snapshot):
    """FR-025/SC-010. An unexplained non-reproduction is a silent loss wearing
    a record."""
    for row in snapshot["report"]["process_rules_not_reproduced"]:
        assert row["reason"].strip(), row["source_guid"]
        assert "MoAffixProcess" in row["reason"]


def test_no_reproduced_rule_is_an_empty_shell(snapshot):
    """SC-006's "with their input and output content". A rule that arrived
    correctly classed and empty has lost everything that made it a rule, and
    the class totals cannot see that."""
    for shape in snapshot["after_rule_shapes"]:
        assert shape["input_total"] > 0, shape["guid"]
        assert shape["output_total"] > 0, shape["guid"]


def test_each_reproduced_rule_matches_its_source_shape(snapshot):
    """Per-rule, not merely in aggregate: the rule that arrived has the SAME
    member census as the rule it came from. Aggregate totals can balance while
    individual rules are wrong in compensating directions."""
    source_by_guid = {s["guid"]: s for s in snapshot["source_rule_shapes"]}
    for shape in snapshot["after_rule_shapes"]:
        src = source_by_guid.get(shape["guid"])
        assert src is not None, (
            "destination holds rule %s which is not in the source -- a "
            "reproduced rule must keep its source GUID" % shape["guid"]
        )
        assert shape["inputs"] == src["inputs"], shape["guid"]
        assert shape["outputs"] == src["outputs"], shape["guid"]


@pytest.mark.parametrize("class_name", UNEXERCISED_IN_RULES)
def test_an_unexercised_class_was_never_invented_inside_a_rule(
    snapshot, class_name
):
    """These ship behind the FR-025 skip, so no reproduced rule may contain
    one -- the engine would have had to build it from the index rather than
    from data.

    Scoped to rule membership, not to the project: these classes legitimately
    arrive in quantity via phonological rules and `PhPhonData.ContextsOS`, and
    a project-wide zero assertion would fail on a correct run.
    """
    for shape in snapshot["after_rule_shapes"]:
        assert class_name not in shape["inputs"], shape["guid"]
        assert class_name not in shape["outputs"], shape["guid"]

    # And the source really does have none, which is the premise.
    for shape in snapshot["source_rule_shapes"]:
        assert class_name not in shape["inputs"], shape["guid"]
        assert class_name not in shape["outputs"], shape["guid"]


# ===========================================================================
# T063 -- phase-scoped: the Phase 6a split, which T077 updates
# ===========================================================================

def test_the_only_rules_skipped_are_the_shared_context_ones(snapshot):
    """Phase 6a's checkpoint, stated as an assertion.

    Condition 4 is the ONLY blocker permitted at this phase. A rule skipped
    for an unimplemented member class, an unresolvable phoneme, or a factory
    failure would be a different defect wearing the same skip, and this is
    what tells them apart.

    T077 LANDED 2026-08-22 and did NOT make this vacuous, because it did not
    overwrite this artifact -- see the Phase 8 block below for why (T102's
    chain). This now reads as the recorded BEFORE: at the moment it was
    measured, 6 rules were skipped and condition 4 was the only cause. The
    AFTER is `test_t077_all_eighteen_rules_transfer`, and keeping both is what
    makes T076's claim a measurable delta rather than an assertion.
    """
    for row in snapshot["report"]["process_rules_not_reproduced"]:
        assert "PhPhonData.ContextsOS" in row["reason"], (
            "rule %s skipped for something other than condition 4: %s"
            % (row["source_guid"], row["reason"])
        )


def test_the_phase_6a_split_is_what_was_measured(snapshot):
    """The measured split, pinned so a regression is visible.

    Written expecting T077 to CHANGE this line to 18/0. T077 instead added a
    second artifact and left this one standing, so the line still says 12/6 --
    and that is the better outcome: an expectation edited in place erases the
    before, while a second artifact lets the delta itself be asserted
    (`test_t077_moved_exactly_nineteen_objects_and_no_others`).
    """
    report = snapshot["report"]
    expected_skipped = sum(
        1 for s in snapshot["source_rule_shapes"]
        if s["inputs"].get("PhSequenceContext")
    )
    assert len(report["process_rules_not_reproduced"]) == expected_skipped
    assert report["process_rules_reproduced"] == (
        SOURCE_RULES - expected_skipped)


# ===========================================================================
# T064 -- the census gate, predicate P4
# ===========================================================================
#
# P4 is "MoAffixProcess MATCHED and MoAffixAllomorph difference == 0 -- both,
# because either alone can be satisfied by the defect itself". The measured
# artifact is `_snapshots/census-038-mbugwe-phase6.json`, written by the same
# driver run.
#
# The gate exited 3 (DUPLICATE_IDENTITY) and P4 is NOT satisfied at this
# phase. Both facts are asserted rather than glossed: a gate that has not
# returned its own green is not a gate that passed, and this file records
# what it actually returned.

_CENSUS = (Path(__file__).parent / "_snapshots"
           / "census-038-mbugwe-phase6.json")

# T087's re-census. A SECOND artifact rather than a replacement of the one
# above, and the reason is a chain: `test_038_closure_edge_audit.py` asserts
# `census-038-mbugwe-phase6.json`'s class table EQUAL to
# `census-038-t067-registered.json`, `-t068-`, and `-t069-` -- four artifacts
# from four separately restored targets, compared against each other to prove
# that registering a closure edge moved no object count. That comparison
# includes `unexplained_shortfall`, so overwriting one link with a
# newer-instrument reading would turn three passing tests red for a reason
# that has nothing to do with what they assert. Its own docstring names the
# hazard: "a chain of pairwise comparisons can drift if one link is ever
# re-measured and the others are not."
#
# So the pre-fix artifact stays exactly as measured, and T087's reading lands
# beside it. Both projects were byte-identical for the two runs (asserted
# below), which is what makes the pair a measurement of the INSTRUMENT and of
# nothing else.
_CENSUS_T087 = (Path(__file__).parent / "_snapshots"
                / "census-038-t087-mbugwe.json")


@pytest.fixture(scope="module")
def census():
    if not _CENSUS.is_file():
        pytest.skip("no committed census artifact at " + str(_CENSUS))
    return json.loads(_CENSUS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def census_t087():
    if not _CENSUS_T087.is_file():
        pytest.skip("no committed census artifact at " + str(_CENSUS_T087))
    return json.loads(_CENSUS_T087.read_text(encoding="utf-8"))


def _row(census_artifact, class_name):
    for row in census_artifact["classes"]:
        if row["class"] == class_name:
            return row
    raise AssertionError("no census row for " + class_name)


def test_p4_second_half_holds_the_allomorph_count_exactly(census):
    """The half that would expose the downgrade, and it PASSES.

    A downgrade inflates `MoAffixAllomorph` by the rule count. 124 source,
    124 destination, difference 0 -- measured against a live database rather
    than a fake, which is what T064 exists to obtain.
    """
    row = _row(census, "MoAffixAllomorph")
    assert row["source_count"] == SOURCE_AFFIX_ALLOMORPHS
    assert row["destination_count_total"] == SOURCE_AFFIX_ALLOMORPHS
    assert row["difference"] == 0
    assert row["verdict_class"] == "MATCHED"


def test_p4_first_half_is_short_by_exactly_the_shared_context_rules(census):
    """NOT satisfied, and the shortfall is exactly the 6 rules on the
    condition-4 skip path -- not 18, and not some other number.

    T077 (Phase 8) is what turns this row MATCHED, after T076's closure pulls
    the shared `PhPhonData.ContextsOS` contexts. Asserting the exact figure
    rather than merely "shortfall" is what makes an unrelated regression here
    visible instead of being absorbed into an expected failure.
    """
    row = _row(census, "MoAffixProcess")
    assert row["source_count"] == SOURCE_RULES
    assert row["destination_count_total"] == SOURCE_RULES - 6
    assert row["difference"] == -6
    assert row["verdict_class"] == "SHORTFALL"


def test_the_census_and_the_run_report_agree_on_the_shortfall(census, snapshot):
    """The instrument and the engine tell the same story. A census shortfall
    the run report cannot explain, or vice versa, is a measurement that cannot
    be acted on."""
    row = _row(census, "MoAffixProcess")
    assert -row["difference"] == len(
        snapshot["report"]["process_rules_not_reproduced"])


def test_the_duplicate_identity_verdict_is_a_source_property(census):
    """The gate exited 3, and NOT because of anything US5 did.

    `PhNCFeatures` carries 23 duplicate natural-key groups (66 extra objects),
    every one of them named `Created automatically for rule "***"` -- FLEx
    generates a natural class per phonological rule and gives them all the
    same auto-name. The row itself is MATCHED at 113 -> 113 with GUIDs
    preserved and a destination that held none before, so the destination set
    IS the source set: the duplication was faithfully reproduced, not
    manufactured. Pinning it here stops a later reader from reading exit 3 as
    a US5 regression.
    """
    row = _row(census, "PhNCFeatures")
    assert row["verdict_class"] == "MATCHED"
    assert row["difference"] == 0
    assert row["duplicates"]["groups"] == 23
    assert row["duplicates"]["extra_objects"] == 66
    assert census["verdict"] == "DUPLICATE_IDENTITY"


# ===========================================================================
# T076 / T077 (2026-08-22) -- Phase 8: the AFTER, beside the BEFORE
# ===========================================================================
#
# The three artifacts above are NOT overwritten, and that is deliberate rather
# than cautious. `census-038-mbugwe-phase6.json` is one link in the pairwise
# equality chain `test_038_closure_edge_audit.py` maintains, and T076 MOVES
# object counts -- which is what it is for -- so replacing that link would
# turn three unrelated tests red. T102 records exactly this hazard. So T077's
# run wrote its own pair (`GT038_PHASE6_SNAPSHOT_SUFFIX=-t077`) and the
# earlier pair stands as the recorded BEFORE.
#
# Keeping both is worth more than tidiness: the claim T076 makes is a DELTA
# ("the 6 condition-4 rules now transfer, and nothing else moved"), and a
# delta cannot be asserted from one artifact.

_SNAPSHOT_T077 = (Path(__file__).parent / "_snapshots"
                  / "process-rules-038-t077-mbugwe.json")
_CENSUS_T077 = (Path(__file__).parent / "_snapshots"
                / "census-038-t077-mbugwe-phase6.json")
_MEMBERS_T077 = (Path(__file__).parent / "_snapshots"
                 / "t077-membersrs-completeness.json")


@pytest.fixture(scope="module")
def snapshot_t077():
    if not _SNAPSHOT_T077.is_file():
        pytest.skip("no committed T077 measurement at " + str(_SNAPSHOT_T077))
    return json.loads(_SNAPSHOT_T077.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def census_t077():
    if not _CENSUS_T077.is_file():
        pytest.skip("no committed T077 census at " + str(_CENSUS_T077))
    return json.loads(_CENSUS_T077.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def members_t077():
    if not _MEMBERS_T077.is_file():
        pytest.skip("no committed T077 MembersRS reading at "
                    + str(_MEMBERS_T077))
    return json.loads(_MEMBERS_T077.read_text(encoding="utf-8"))


def test_t077_all_eighteen_rules_transfer(snapshot_t077):
    """T077's headline. 18 of 18, and NO rule left on any skip path.

    The empty `process_rules_not_reproduced` is asserted as well as the count
    because "18 reproduced" and "0 skipped" are different claims: a run that
    reproduced 18 and ALSO reported skips would mean the report double-counts,
    which is the defect T063 found in `report.build` and fixed.
    """
    report = snapshot_t077["report"]
    assert report["process_rules_total"] == SOURCE_RULES
    assert report["process_rules_reproduced"] == SOURCE_RULES
    assert report["process_rules_not_reproduced"] == []
    assert snapshot_t077["delta"]["MoAffixProcess"] == SOURCE_RULES


def test_t077_no_rule_was_downgraded_either(snapshot_t077):
    """The invariant that had to survive the fix, re-asserted on the AFTER.

    `MoAffixAllomorph` gaining exactly its source count is the signal that
    distinguishes 18 rebuilt rules from 18 rules quietly turned into plain
    allomorphs. Six more rules now transfer, and this number did NOT move --
    which is what says the six arrived as rules.
    """
    assert snapshot_t077["delta"]["MoAffixAllomorph"] == SOURCE_AFFIX_ALLOMORPHS
    assert snapshot_t077["delta"]["MoStemAllomorph"] == 137


def test_t077_every_rule_matches_its_source_shape(snapshot_t077):
    """Per rule, not merely in aggregate. Aggregate totals can balance while
    individual rules are wrong in compensating directions."""
    src = {r["guid"]: r for r in snapshot_t077["source_rule_shapes"]}
    dest = {r["guid"]: r for r in snapshot_t077["after_rule_shapes"]}
    assert set(src) == set(dest)
    for guid, shape in sorted(src.items()):
        assert dest[guid] == shape, guid


def test_t077_every_sequence_arrived_with_its_members_intact(members_t077):
    """The clause T077 is actually about, and the one no count can answer.

    A `PhSequenceContext` counts as ONE input member whether its `MembersRS`
    holds three references or none, so every assertion above would be
    satisfied by a rule that arrived with an EMPTY sequence -- the
    partly-filled `MembersRS` FR-023 calls silent content loss and the exact
    outcome the condition-4 skip existed to prevent. So the ORDERED member
    GUID list is compared per sequence
    (`debug/verify038_t077_membersrs.py`, both projects read-only).
    """
    assert members_t077["source_rules"] == SOURCE_RULES
    assert members_t077["destination_rules"] == SOURCE_RULES
    assert members_t077["source_sequences"] == 6
    assert members_t077["sequences_identical"] == 6
    assert members_t077["sequences_empty_in_destination"] == 0
    assert members_t077["findings"] == []


def test_t077_the_six_shared_contexts_were_co_created(members_t077):
    """The mechanism, measured in the destination rather than inferred from
    the rule count.

    6 shared `PhPhonData.ContextsOS` contexts are referenced by a rule
    sequence and 6 are present in the destination, none missing. Before T076
    that number was 0 -- nothing in this engine created a `ContextsOS` member
    that a phonological rule did not also reference, and the audit measured
    0 of these 6 as reachable from `PhonRulesOS`.
    """
    assert members_t077["shared_contexts_referenced_by_a_sequence"] == 6
    assert members_t077["shared_contexts_present_in_destination"] == 6
    assert members_t077["shared_contexts_missing_from_destination"] == []


def test_t077_p4_is_now_satisfied_in_both_halves(census_t077):
    """T064's predicate P4, which four passes deliberately left open.

    Both halves, because either alone can be satisfied by the defect itself.
    """
    proc = _row(census_t077, "MoAffixProcess")
    assert proc["source_count"] == SOURCE_RULES
    assert proc["destination_count_total"] == SOURCE_RULES
    assert proc["difference"] == 0
    assert proc["verdict_class"] == "MATCHED"

    allo = _row(census_t077, "MoAffixAllomorph")
    assert allo["source_count"] == SOURCE_AFFIX_ALLOMORPHS
    assert allo["destination_count_total"] == SOURCE_AFFIX_ALLOMORPHS
    assert allo["difference"] == 0
    assert allo["verdict_class"] == "MATCHED"


def test_t077_moved_exactly_nineteen_objects_and_no_others(census, census_t077):
    """The delta, and the reason both artifacts are kept.

    Four rows move and their arithmetic closes exactly against
    `total_shortfall`:

        MoAffixProcess      -6  ->   0   (+6, the six rules)
        PhSequenceContext  -17  -> -11   (+6, their own sequences)
        PhSimpleContextNC  -28  -> -23   (+5, co-created shared contexts)
        PhSimpleContextSeg -23  -> -21   (+2, one co-created, one rule-owned)
                                    ----
                                     19  == 10262 - 10243

    Asserting the TOTAL as well as the rows is what makes this a claim about
    the whole project rather than about four rows somebody remembered to look
    at: a fifth row that moved would break the sum even if nobody named it.
    """
    expected = {
        "MoAffixProcess": (-6, 0),
        "PhSequenceContext": (-17, -11),
        "PhSimpleContextNC": (-28, -23),
        "PhSimpleContextSeg": (-23, -21),
    }
    for cls, (was, now) in expected.items():
        assert _row(census, cls)["difference"] == was, cls
        assert _row(census_t077, cls)["difference"] == now, cls

    moved = sum(now - was for was, now in expected.values())
    assert moved == 19
    assert (census["totals"]["total_shortfall"]
            - census_t077["totals"]["total_shortfall"]) == moved
    assert (census["totals"]["unexplained_shortfall"]
            - census_t077["totals"]["unexplained_shortfall"]) == moved
    assert census_t077["totals"]["classes_matched"] == (
        census["totals"]["classes_matched"] + 1)


def test_t077_did_not_change_the_duplicate_identity_verdict(census,
                                                            census_t077):
    """Exit 3 stands, for the SAME cause it always had.

    `PhNCFeatures`'s 66 duplicate extras are a faithfully reproduced source
    property (FLEx auto-names one natural class per phonological rule), and
    they are unchanged by T076. Asserting that the verdict did NOT improve is
    as important as asserting the rows that did: a fix that quietly silenced
    an unrelated failure would be indistinguishable here from one that
    addressed it.
    """
    assert census["verdict"] == census_t077["verdict"] == "DUPLICATE_IDENTITY"
    assert census["exit_code"] == census_t077["exit_code"] == 3
    assert (census["totals"]["duplicate_extra_objects"]
            == census_t077["totals"]["duplicate_extra_objects"] == 66)
    assert _row(census_t077, "PhNCFeatures")["verdict_class"] == "MATCHED"


def test_the_reported_rules_are_readable_as_accounted(census_t087):
    """T087, CLOSED. Was `test_the_reported_rules_are_not_yet_readable_as_
    accounted`, which pinned `unexplained_shortfall == 6` and
    `accounted_for == []` so that closing the gap would have to be a
    deliberate edit here. This is that edit.

    All 6 skipped rules were always reported -- a `DroppedItemRecord` each and
    a `ProcessRuleTransferRecord` with a non-empty reason -- so the loss was
    never silent under Principle I. What the census could not do was READ the
    second surface: `read_report_evidence` consumed `dropped_items` only, and
    no needle in `DROP_REASON_TOKENS` matches what `_reproduce_affix_process`
    writes. A named, deliberate deferral therefore scored as an unaccounted
    loss, which is the direction 5.2's cap rationale says an instrument must
    not be wrong in.

    The line is required to carry its evidence, not merely a token: all 6 rule
    GUIDs, the run id, the report path, and a detail naming the corroboration
    the credit rests on.
    """
    row = _row(census_t087, "MoAffixProcess")
    assert row["unexplained_shortfall"] == 0
    line, = row["accounted_for"]

    assert line["reason"] == "DEPENDENCY_UNRESOLVED"
    assert line["count"] == 6
    assert line["direction"] == "shortfall"
    assert line["report_ref"]["kind"] == "dropped_item"
    assert line["report_ref"]["count_in_report"] == 6
    assert line["report_ref"]["run_id"] == "GT-20260821-020541"
    assert len(line["report_ref"]["record_ids"]) == 6
    assert "ProcessRuleTransferRecord" in line["detail"]
    assert "corroborated" in line["detail"]

    assert row["verdict_class"] == "SHORTFALL", (
        "accounting does not change WHAT HAPPENED. The 6 rules really are "
        "missing and T077 is the task that transfers them; what changed is "
        "that the census can now see the run had already said so"
    )


def test_the_accounted_guids_are_the_rules_the_run_named(census_t087, snapshot):
    """R-1 at the corpus level: the 6 GUIDs the accounting line claims are the
    6 the run report actually reported as not reproduced -- not merely six of
    something. A line whose record_ids drifted from the report would be
    accounting against evidence that does not exist."""
    line, = _row(census_t087, "MoAffixProcess")["accounted_for"]
    reported = snapshot["report"]["process_rules_not_reproduced"]
    assert (sorted(line["report_ref"]["record_ids"])
            == sorted(record["source_guid"] for record in reported))
    assert all("is absent from the destination" in record["reason"]
               for record in reported), (
        "the needle the classification rests on, checked against the corpus "
        "measurement rather than only against a hand-built report"
    )


def test_the_pre_fix_artifact_is_kept_and_differs_only_by_the_instrument(
        census, census_t087):
    """The before/after pair, and why both files are committed.

    `census-038-mbugwe-phase6.json` still reads `unexplained_shortfall: 6` /
    `accounted_for: []` because it is a load-bearing link in
    `test_038_closure_edge_audit.py`'s four-artifact equality chain (see the
    comment on `_CENSUS_T087`). Keeping it is only defensible if the pair is
    demonstrably a measurement of the instrument and of nothing else -- so the
    project digests and every counted quantity are asserted equal, and the
    delta is required to be confined to the accounting fields.

    The two `MoForm` / `MoMorphSynAnalysis` rows are excluded from the
    row-by-row comparison: T099 landed between the two runs and turned their
    placeholder zeros into the nulls the schema always specified. That is a
    different fix's expected delta, recorded here rather than absorbed.
    """
    for side in ("source", "destination"):
        for when in ("before", "after"):
            key = "fwdata_sha256_" + when
            assert (census_t087["projects"][side][key]
                    == census["projects"][side][key]), side
        assert census_t087["projects"][side]["opened_read_only"] is True

    assert _row(census, "MoAffixProcess")["unexplained_shortfall"] == 6
    assert _row(census, "MoAffixProcess")["accounted_for"] == []

    t099_rows = {"MoForm", "MoMorphSynAnalysis"}
    counted = ("source_count", "destination_count_total",
               "destination_count_net", "difference", "difference_raw",
               "verdict_class", "duplicates")
    before = {r["class"]: r for r in census["classes"]}
    after = {r["class"]: r for r in census_t087["classes"]}
    assert set(before) == set(after)
    for name in sorted(set(before) - t099_rows):
        for key in counted:
            assert before[name].get(key) == after[name].get(key), (name, key)

    moved = {name for name in set(before) - t099_rows
             if before[name].get("accounted_for")
             != after[name].get("accounted_for")}
    assert moved == {"MoAffixProcess"}, (
        "T087 reads ONE report surface for ONE class; a second row gaining an "
        "accounting line would mean the change is wider than its filing"
    )

    assert (census["totals"]["accounted_shortfall"],
            census_t087["totals"]["accounted_shortfall"]) == (0, 6)
    assert (census["totals"]["unexplained_shortfall"]
            - census_t087["totals"]["unexplained_shortfall"]) == 6
    assert ((census_t087["verdict"], census_t087["exit_code"])
            == (census["verdict"], census["exit_code"])
            == ("DUPLICATE_IDENTITY", 3)), (
        "exit 3 is the PhNCFeatures duplicate finding this file already pins "
        "as a source property; accounting 6 rules does not and must not move it"
    )


def test_t064_the_gate_clause_is_met_the_way_t086_amended_it(census_t077):
    """T064's third clause, satisfied MECHANICALLY rather than in prose.

    T064's own text set the bar: "a gate that has not returned its own green
    is not a gate that passed". `gate --phase 4` still exits 3, so that bar is
    not cleared by the exit code alone -- and T086 already met this exact
    situation on T075/P2 and amended the clause rather than bending the gate.
    The amended form is: **the predicate is satisfied, and every row that
    decides the exit code lies provably OUTSIDE the classes this phase names,
    proved in a test rather than asserted in prose.**

    All three legs are checked here, off the shipped predicate rather than a
    hand-copied class list, so the scope cannot drift from the one
    `evaluate_phase` enforces:

      * the predicate is satisfied with no failures;
      * `phase_scoped_suppressions(artifact, 4)` is EMPTY -- no capped row
        falls inside phase 4;
      * the ONLY row carrying duplicates is `PhNCFeatures`, which is not one
        of phase 4's two classes, and which T063 measured as a faithfully
        reproduced source property (113 -> 113 MATCHED, FLEx auto-names one
        natural class per phonological rule).

    Bounding the EXIT CODE to the phase was rejected by T086 and is still
    rejected: it would exit 0 on a run that lost 1643 objects. The gate is
    unchanged and still exits 3.
    """
    from gramtrans.Lib import census as census_mod

    scope = census_mod.phase_classes(4)
    assert scope == {"MoAffixProcess", "MoAffixAllomorph"}

    result = census_mod.evaluate_phase(census_t077, 4)
    assert result.satisfied is True
    assert result.failures == ()

    assert census_mod.phase_scoped_suppressions(census_t077, 4) == ()

    duplicated = {row["class"] for row in census_t077["classes"]
                  if (row.get("duplicates") or {}).get("extra_objects")}
    assert duplicated == {"PhNCFeatures"}
    assert not (duplicated & scope), (
        "a phase-4 class now carries duplicates -- the exit code is no longer "
        "decided outside this phase and T064's clause is no longer met"
    )
    assert census_t077["exit_code"] == 3
