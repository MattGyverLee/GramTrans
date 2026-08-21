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

    T077 (Phase 8) re-runs the driver after T076's closure lands; this
    assertion then holds vacuously over an empty set, and
    `test_the_phase_6a_split_is_what_was_measured` is the one that changes.
    """
    for row in snapshot["report"]["process_rules_not_reproduced"]:
        assert "PhPhonData.ContextsOS" in row["reason"], (
            "rule %s skipped for something other than condition 4: %s"
            % (row["source_guid"], row["reason"])
        )


def test_the_phase_6a_split_is_what_was_measured(snapshot):
    """The measured split, pinned so a regression is visible.

    This is the ONE assertion T077 updates -- to 18 reproduced and 0 skipped --
    and it is deliberately separate from the invariants above so that flipping
    the phase does not mean rewriting the file.
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
