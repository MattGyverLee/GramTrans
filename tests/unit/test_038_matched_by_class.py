"""T024d-a: per-LCM-object-class tallies of destination objects matched to source.

Why this exists. `census.unmatched_starter` subtracts
`starter_matched_to_source` from `starter_baseline_count`, and
`starter_subtraction_basis` can only ever be `baseline_matched` when that matched
count is known per OBJECT CLASS. Before this task nothing emitted it:
`census_cli._row_for_entry` hardcoded `baseline_gross` on every path and said so
in its own docstring, so `CENSUS_CLEAN` was unreachable on any real pair and the
5.2 cap's remediation advice ("supply the run report") could not be followed.

The hard part is attribution, not counting. `RunReport.per_category` is keyed by
`GrammarCategory`, every census row is keyed by LCM class, and the mapping is not
1:1 for the affix and MSA categories -- so a per-category tally cannot be
credited to a row without guessing, and a wrongly-credited match subtracts the
wrong number from the wrong class. Only two things on a plan item name a class
authoritatively: `MatchBasisRecord.object_class` and
`EnrichmentRecord.object_class`. Everything else goes to
`matches_unattributed`, which WITHHOLDS the stronger basis rather than asserting
a number nothing supports.
"""

from __future__ import annotations

import pytest

import gramtrans.Lib.report  # noqa: F401 -- attaches build_from_plan
from gramtrans.Lib.models import (
    CategoryReport,
    EnrichmentRecord,
    GrammarCategory,
    MatchBasis,
    MatchBasisRecord,
    PlannedAction,
    PlannedOverwrite,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
)


def _ctx():
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path=r"C:\p\Src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path=r"C:\p\Tgt",
        run_id="GT-20260819-000000",
        started_at="2026-08-19T00:00:00",
    )


def _basis(object_class, guid, *, basis=MatchBasis.NATURAL_KEY, target="tgt-1"):
    return MatchBasisRecord(
        basis=basis,
        object_class=object_class,
        source_guid=guid,
        key_expression="Name" if basis is MatchBasis.NATURAL_KEY else "",
        key_value="p" if basis is MatchBasis.NATURAL_KEY else "",
        target_guid=target,
        candidate_count=1 if basis is MatchBasis.NATURAL_KEY else 0,
    )


def _plan(*, actions=(), overwrites=(), enrichments=()):
    return RunPlan(
        context=_ctx(),
        selection=None,
        ws_mapping=None,
        actions=tuple(actions),
        skips=(),
        overwrites=tuple(overwrites),
        enrichments=tuple(enrichments),
    )


def _report(plan):
    return RunReport.build_from_plan(plan, RunMode.MOVE)


# ---------------------------------------------------------------------------
# What counts as a match
# ---------------------------------------------------------------------------


def test_overwrite_is_always_a_match():
    """An overwrite writes onto an object that ALREADY EXISTED, so it is a match
    however it was found -- by GUID, identity remap, fingerprint or natural
    key."""
    ow = PlannedOverwrite(
        category=GrammarCategory.PHONEMES,
        source_guid="src-1",
        target_guid="tgt-1",
        summary="phoneme p",
        match_basis=_basis("PhPhoneme", "src-1", basis=MatchBasis.IDENTITY),
    )
    report = _report(_plan(overwrites=[ow]))

    assert report.matched_by_class == {"PhPhoneme": 1}
    assert report.matches_unattributed == {}
    assert report.matched_to_source_total == 1


def test_plain_add_is_not_a_match():
    """A brand-new create carries no match_basis and must not be counted -- it
    did not consume a starter object, so subtracting for it would understate the
    destination."""
    action = PlannedAction(
        category=GrammarCategory.PHONEMES,
        source_guid="src-1",
        intended_target_guid="tgt-1",
        summary="phoneme q",
    )
    report = _report(_plan(actions=[action]))

    assert report.matched_by_class == {}
    assert report.matched_to_source_total == 0


def test_natural_key_matched_add_is_a_match():
    """The case the census exists for: a starter phoneme claimed by NAME rather
    than by GUID. It arrives as an ADD but it DID consume a starter object, so it
    must be counted -- this is the 23-starter-phoneme scenario in which gross
    subtraction reports a phantom -23 on a lossless run."""
    action = PlannedAction(
        category=GrammarCategory.PHONEMES,
        source_guid="src-1",
        intended_target_guid="tgt-1",
        summary="phoneme p",
        match_basis=_basis("PhPhoneme", "src-1"),
    )
    report = _report(_plan(actions=[action]))

    assert report.matched_by_class == {"PhPhoneme": 1}
    assert report.identity_substituted == 1


def test_add_whose_basis_found_nothing_is_not_a_match():
    """`MatchBasis.NONE` means the matcher ran and found NO counterpart. That is
    evidence of a create, not of a match."""
    action = PlannedAction(
        category=GrammarCategory.PHONEMES,
        source_guid="src-1",
        intended_target_guid="tgt-1",
        summary="phoneme q",
        match_basis=MatchBasisRecord(
            basis=MatchBasis.NONE,
            object_class="PhPhoneme",
            source_guid="src-1",
        ),
    )
    report = _report(_plan(actions=[action]))

    assert report.matched_by_class == {}


# ---------------------------------------------------------------------------
# Attribution -- the part that must never guess
# ---------------------------------------------------------------------------


def test_unattributable_match_goes_to_its_own_bucket():
    """An overwrite with neither a match_basis nor an enrichment names no class.
    It is still a match, so it must be COUNTED -- just never credited to a
    class."""
    ow = PlannedOverwrite(
        category=GrammarCategory.AFFIXES,
        source_guid="src-1",
        target_guid="tgt-1",
        summary="affix",
    )
    report = _report(_plan(overwrites=[ow]))

    assert report.matched_by_class == {}
    assert report.matches_unattributed == {GrammarCategory.AFFIXES: 1}
    assert report.matched_to_source_total == 1, (
        "an unattributable match must not vanish from the total -- that is how "
        "an understated matched count silently manufactures a shortfall"
    )


def test_enrichment_supplies_the_class_when_no_match_basis_does():
    """`EnrichmentRecord` carries an LCM class too, so an enrichment is
    attributable even on an overwrite whose matcher record is absent."""
    ow = PlannedOverwrite(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid="src-1",
        target_guid="tgt-1",
        summary="pos",
        write_mode="merge",
        enrichment=EnrichmentRecord(
            object_class="PartOfSpeech",
            source_guid="src-1",
            target_guid="tgt-1",
            label="pos",
            fields_updated=("Description",),
        ),
    )
    report = _report(_plan(overwrites=[ow], enrichments=()))

    assert report.matched_by_class == {"PartOfSpeech": 1}
    assert report.matches_unattributed == {}


def test_match_basis_wins_over_enrichment():
    """Both present: the matcher's own record is the stronger statement of what
    was matched, so it decides the class."""
    ow = PlannedOverwrite(
        category=GrammarCategory.PHONEMES,
        source_guid="src-1",
        target_guid="tgt-1",
        summary="phoneme",
        write_mode="merge",
        match_basis=_basis("PhPhoneme", "src-1"),
        enrichment=EnrichmentRecord(
            object_class="PhCode",
            source_guid="src-1",
            target_guid="tgt-1",
            label="code",
            fields_updated=("Representation",),
        ),
    )
    report = _report(_plan(overwrites=[ow]))

    assert report.matched_by_class == {"PhPhoneme": 1}


def test_counts_accumulate_per_class_not_per_category():
    """Two classes inside ONE category stay separate -- the exact split a
    per-category tally cannot express, and the reason this is keyed by class."""
    overwrites = [
        PlannedOverwrite(
            category=GrammarCategory.AFFIXES,
            source_guid=f"src-{i}",
            target_guid=f"tgt-{i}",
            summary="affix",
            match_basis=_basis(cls, f"src-{i}", basis=MatchBasis.IDENTITY),
        )
        for i, cls in enumerate(
            ["MoAffixAllomorph", "MoAffixAllomorph", "MoAffixProcess"]
        )
    ]
    report = _report(_plan(overwrites=overwrites))

    assert report.matched_by_class == {
        "MoAffixAllomorph": 2,
        "MoAffixProcess": 1,
    }


# ---------------------------------------------------------------------------
# Completeness -- the precondition for the baseline_matched basis (T024d-b)
# ---------------------------------------------------------------------------


def test_class_is_complete_when_present_and_nothing_unattributed():
    ow = PlannedOverwrite(
        category=GrammarCategory.PHONEMES,
        source_guid="src-1",
        target_guid="tgt-1",
        summary="phoneme",
        match_basis=_basis("PhPhoneme", "src-1", basis=MatchBasis.IDENTITY),
    )
    report = _report(_plan(overwrites=[ow]))

    assert report.matched_class_is_complete("PhPhoneme") is True


def test_absent_class_is_not_complete_because_absent_is_not_zero():
    """The rule `census.unmatched_starter` insists on. A class the matcher never
    evaluated has NO tally, and reading that as 0 would subtract the full gross
    baseline while claiming the trustworthy basis."""
    ow = PlannedOverwrite(
        category=GrammarCategory.PHONEMES,
        source_guid="src-1",
        target_guid="tgt-1",
        summary="phoneme",
        match_basis=_basis("PhPhoneme", "src-1", basis=MatchBasis.IDENTITY),
    )
    report = _report(_plan(overwrites=[ow]))

    assert report.matched_class_is_complete("MoStemMsa") is False


def test_any_unattributed_match_spoils_completeness_for_every_class():
    """An unattributed match cannot be proven to belong elsewhere, so while one
    exists every class's tally is potentially understated. Understating the
    matched count overstates `unmatched_starter`, which subtracts too much and
    invents a shortfall on a lossless run -- so the stronger basis is refused
    for ALL classes, not just the murky one."""
    overwrites = [
        PlannedOverwrite(
            category=GrammarCategory.PHONEMES,
            source_guid="src-1",
            target_guid="tgt-1",
            summary="phoneme",
            match_basis=_basis("PhPhoneme", "src-1", basis=MatchBasis.IDENTITY),
        ),
        PlannedOverwrite(
            category=GrammarCategory.AFFIXES,
            source_guid="src-2",
            target_guid="tgt-2",
            summary="affix",
        ),
    ]
    report = _report(_plan(overwrites=overwrites))

    assert report.matched_by_class == {"PhPhoneme": 1}
    assert report.matched_class_is_complete("PhPhoneme") is False


# ---------------------------------------------------------------------------
# Accounting invariants
# ---------------------------------------------------------------------------


def test_empty_tallies_mean_unmeasured_not_zero():
    """A directly-constructed report (sanctioned by RunReport's docstring, and
    what every pre-038 caller produces) carries no tallies. Cross-checking an
    unmeasured tally would reject valid reports and prove nothing."""
    report = RunReport(
        context=_ctx(),
        mode=RunMode.PREVIEW,
        per_category={GrammarCategory.PHONEMES: CategoryReport(
            added=1, identity_substitution=1,
        )},
    )

    assert report.matched_to_source_total == 0
    assert report.identity_substituted == 1  # no raise


def test_substitutions_cannot_outnumber_matches_once_measured():
    with pytest.raises(ValueError, match="identity_substituted"):
        RunReport(
            context=_ctx(),
            mode=RunMode.PREVIEW,
            per_category={GrammarCategory.PHONEMES: CategoryReport(
                added=5, identity_substitution=5,
            )},
            matched_by_class={"PhPhoneme": 2},
        )


def test_a_negative_tally_is_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        RunReport(
            context=_ctx(),
            mode=RunMode.PREVIEW,
            matched_by_class={"PhPhoneme": -1},
        )


# ---------------------------------------------------------------------------
# Snapshot surface
# ---------------------------------------------------------------------------


def test_snapshot_omits_the_block_entirely_when_nothing_matched():
    """038's omit-when-empty discipline: a run with no matches must produce a
    byte-identical snapshot to the pre-T024d build."""
    import json

    action = PlannedAction(
        category=GrammarCategory.PHONEMES,
        source_guid="src-1",
        intended_target_guid="tgt-1",
        summary="phoneme q",
    )
    payload = json.loads(_report(_plan(actions=[action])).to_snapshot_json())

    assert "matched_to_source" not in payload


def test_snapshot_reports_completeness_and_the_unattributed_split():
    import json

    overwrites = [
        PlannedOverwrite(
            category=GrammarCategory.PHONEMES,
            source_guid="src-1",
            target_guid="tgt-1",
            summary="phoneme",
            match_basis=_basis("PhPhoneme", "src-1", basis=MatchBasis.IDENTITY),
        ),
        PlannedOverwrite(
            category=GrammarCategory.AFFIXES,
            source_guid="src-2",
            target_guid="tgt-2",
            summary="affix",
        ),
    ]
    payload = json.loads(_report(_plan(overwrites=overwrites)).to_snapshot_json())
    block = payload["matched_to_source"]

    assert block["by_object_class"] == {"PhPhoneme": 1}
    assert block["total"] == 2
    assert block["complete"] is False
    assert block["unattributed_by_category"] == {"AFFIXES": 1}


# ---------------------------------------------------------------------------
# T024d-b: the census reads the tally and earns the baseline_matched basis
# ---------------------------------------------------------------------------


class TestCensusReadsTheMatchedTally:
    """`census_cli.matched_by_class_from_report` is the whole seam T024d names.

    Before it, `_row_for_entry` hardcoded `baseline_gross` on every path that had
    a baseline, so `baseline_matched` -- specified, validated, invariant-checked,
    cap-exempt and phase-trusted throughout `census.py` -- was emitted by nothing.
    """

    def _write(self, tmp_path, payload):
        import json

        path = tmp_path / "report.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_reads_a_complete_tally(self, tmp_path):
        from gramtrans import census_cli

        path = self._write(tmp_path, {
            "context": {"run_id": "GT-20260819-000000"},
            "matched_to_source": {
                "by_object_class": {"PhPhoneme": 23, "PartOfSpeech": 5},
                "total": 28,
                "complete": True,
            },
        })
        per_class, complete = census_cli.matched_by_class_from_report(path)

        assert per_class == {"PhPhoneme": 23, "PartOfSpeech": 5}
        assert complete is True

    def test_an_absent_block_is_no_evidence_not_a_zero(self, tmp_path):
        """A pre-T024d report, or a build whose matcher never ran, must leave
        every row on the gross basis rather than claiming 0 matched."""
        from gramtrans import census_cli

        path = self._write(
            tmp_path, {"context": {"run_id": "GT-20260819-000000"}})
        per_class, complete = census_cli.matched_by_class_from_report(path)

        assert per_class == {}
        assert complete is False

    def test_unattributed_matches_spoil_completeness(self, tmp_path):
        from gramtrans import census_cli

        path = self._write(tmp_path, {
            "context": {"run_id": "GT-20260819-000000"},
            "matched_to_source": {
                "by_object_class": {"PhPhoneme": 23},
                "total": 30,
                "complete": False,
                "unattributed_by_category": {"AFFIXES": 7},
            },
        })
        per_class, complete = census_cli.matched_by_class_from_report(path)

        assert per_class == {"PhPhoneme": 23}
        assert complete is False, (
            "an understated matched count overstates unmatched_starter, which "
            "subtracts too much and invents a shortfall on a lossless run"
        )

    def test_completeness_cannot_be_claimed_by_omission(self, tmp_path):
        """A hand-built block with no `complete` flag falls back to the
        unattributed split rather than being taken at its word."""
        from gramtrans import census_cli

        path = self._write(tmp_path, {
            "context": {"run_id": "GT-20260819-000000"},
            "matched_to_source": {
                "by_object_class": {"PhPhoneme": 23},
                "unattributed_by_category": {"AFFIXES": 1},
            },
        })
        _, complete = census_cli.matched_by_class_from_report(path)

        assert complete is False

    def test_an_empty_tally_is_never_complete(self, tmp_path):
        """`complete: true` over an EMPTY tally proves nothing -- there is no
        class it could license the stronger basis for."""
        from gramtrans import census_cli

        path = self._write(tmp_path, {
            "context": {"run_id": "GT-20260819-000000"},
            "matched_to_source": {"by_object_class": {}, "complete": True},
        })
        per_class, complete = census_cli.matched_by_class_from_report(path)

        assert per_class == {}
        assert complete is False

    def test_a_negative_or_non_int_count_is_discarded(self, tmp_path):
        from gramtrans import census_cli

        path = self._write(tmp_path, {
            "context": {"run_id": "GT-20260819-000000"},
            "matched_to_source": {
                "by_object_class": {
                    "PhPhoneme": 23, "MoStemMsa": -1, "PhCode": "many",
                },
                "complete": True,
            },
        })
        per_class, _ = census_cli.matched_by_class_from_report(path)

        assert per_class == {"PhPhoneme": 23}


# ---------------------------------------------------------------------------
# T024d-b: the basis a row actually emits
# ---------------------------------------------------------------------------


class TestRowBasisIsEarnedNotAssumed:
    """The row-level payoff. `starter_subtraction_basis` is PER ROW, so the cap
    lifts exactly where evidence exists and nowhere else.

    The scenario throughout is `fidelity-census.md` 5.2's own worked example and
    T024d's claim 3: a target restored blank ships 23 starter phonemes; a correct
    transfer matches all 23 to source phonemes and leaves the destination at 41.
    Gross subtraction gives 41 - 23 = 18 and reports `difference` -23 -- a
    23-object shortfall on a LOSSLESS run. On the matched basis the subtraction is
    23 - 23 = 0 and the difference is 0.
    """

    def _entry(self, object_class="PhPhoneme", owning_feature_system=None):
        from gramtrans.Lib import census as census_mod

        return census_mod.ClassListEntry(
            object_class=object_class,
            in_class_list_via="coverage_floor",
            gate_scope="required",
            engine_can_create=True,
            owning_feature_system=owning_feature_system,
        )

    def _baseline(self, counts):
        from gramtrans.Lib import models as models_mod

        return models_mod.StarterBaseline(
            kind=models_mod.StarterBaselineKind.PRE_TRANSFER_CENSUS,
            captured_from="Tgt",
            flex_version="9.3.10",
            captured_at="2026-08-19T08:31:00",
            entries=tuple(
                models_mod.StarterBaselineEntry(object_class=cls, count=n)
                for cls, n in counts.items()
            ),
        )

    def _row(self, *, matched=None, complete=False, dest=41, src=41,
             baseline_count=23, owner=None):
        from gramtrans import census_cli

        return census_cli._row_for_entry(
            self._entry(owning_feature_system=owner),
            {"PhPhoneme": src},
            {"PhPhoneme": dest},
            self._baseline({"PhPhoneme": baseline_count}),
            matched or {},
            complete,
        )

    def test_gross_basis_reports_a_phantom_shortfall(self):
        """Baseline behaviour, kept as the control: this is the mis-report."""
        row, kwargs = self._row(dest=41)

        assert kwargs["starter_subtraction_basis"] == "baseline_gross"
        assert row.starter_excluded == 23
        assert row.difference == 41 - 23 - 41 == -23
        assert "starter_matched_to_source" not in kwargs, (
            "on the gross basis the matched count is UNKNOWN; emitting 0 would "
            "be the absent-read-as-zero error census.unmatched_starter refuses"
        )

    def test_matched_basis_subtracts_only_unmatched_starters(self):
        row, kwargs = self._row(
            matched={"PhPhoneme": 23}, complete=True, dest=41)

        assert kwargs["starter_subtraction_basis"] == "baseline_matched"
        assert kwargs["starter_matched_to_source"] == 23
        assert row.starter_excluded == 0, "23 baseline - 23 matched"
        assert row.difference == 0, "the lossless run finally reads as lossless"

    def test_a_partially_matched_class_subtracts_the_remainder(self):
        """10 of 23 starters matched: the other 13 are genuinely still surplus
        starter content and must still be subtracted."""
        row, kwargs = self._row(
            matched={"PhPhoneme": 10}, complete=True, dest=51)

        assert kwargs["starter_matched_to_source"] == 10
        assert row.starter_excluded == 13
        assert row.difference == 51 - 13 - 41 == -3

    def test_an_incomplete_tally_is_refused_even_when_the_class_is_present(self):
        """Wrong in the safe direction: capped and advisory beats a confidently
        wrong number."""
        _, kwargs = self._row(matched={"PhPhoneme": 23}, complete=False)

        assert kwargs["starter_subtraction_basis"] == "baseline_gross"

    def test_a_class_missing_from_the_tally_stays_on_the_gross_basis(self):
        _, kwargs = self._row(matched={"MoStemMsa": 4}, complete=True)

        assert kwargs["starter_subtraction_basis"] == "baseline_gross"

    def test_a_split_row_never_reaches_the_matched_basis(self):
        """A1 split rows are keyed by feature system, not by class. A run report
        tallies by CLASS and cannot say which system a matched FsFeatStrucType
        belonged to, so crediting the class tally to either half would
        double-count it."""
        _, kwargs = self._row(
            matched={"PhPhoneme": 23}, complete=True, owner="phon-fs-guid")

        assert kwargs["starter_subtraction_basis"] == "baseline_gross"

    def test_the_matched_basis_says_so_in_a_note(self):
        _, kwargs = self._row(matched={"PhPhoneme": 23}, complete=True)
        notes = " ".join(kwargs["notes"])

        assert "starter_matched_to_source=23" in notes
        assert "gross baseline of 23" in notes
