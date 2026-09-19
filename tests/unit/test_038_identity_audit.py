"""T048d: a GUID-level comparison, for the class that arrives correct with no
record of arriving.

Why this exists. The 2026-08-20 re-run gate
(`specs/038-transfer-fidelity-gaps/journal/T048b-T048c-identity-skips-and-swallowed-writes.md`)
left exactly one blocker on T048's predicate P3: `MoMorphType` reported
`difference -19` while the two `.fwdata` files held the SAME 19 morph types by
GUID -- source 19, destination 19, 0 missing, 0 destination-only, identical GUID
sets. The loss was proven not to exist and the census reported it anyway.

This is NOT T048b's defect and T048b cannot reach it. `PartOfSpeech`'s starters
were matched and the run RECORDED the match as an identity skip, which is what
T048b reads. `MoMorphType` has no record of any kind -- no action, no overwrite,
no skip -- because the morph-types list is FW-global fixed content that needs no
transfer: `Lib/categories.py`'s `_resolve_target_morph_type` says so ("Morph
types live in the global (shared) list at LangProject.LexDbOA.MorphTypesOA and
carry identical GUIDs across every FW project") and `_entry_all_deps` adds
"MorphType is FW-global; no dependency edge is emitted for it". So the class
arrives correct, nothing happens, nothing is recorded, and the gross basis
subtracts all 19 starters as surplus.

No run report can ever close that, so the evidence comes from the two projects.
The bound `census.starter_matched_lower_bound` computes is
`B - |D \\ Q|`, clamped to `[0, B]`, and its derivation is in `census.py`'s
section header. Four properties get their own tests here because each one, if
broken, makes this fix worse than the defect it closes:

  * THE BOUND ERRS DOWNWARD. Understating `starter_matched_to_source`
    over-subtracts and can only manufacture a shortfall; overstating it
    under-subtracts and HIDES one. Every refusal below therefore refuses INTO
    the gross basis rather than guessing a number.
  * THE AUDIT IS SUBORDINATE TO THE RUN REPORT. It is consulted only on the
    branch where no report tally reached the row, so no row that already reads
    its matched count off the report can change behaviour.
  * A DELETED STARTER BREAKS THE PROOF, AND IS CAUGHT. `S subset of D` is the
    single assumption; `|D| < B` is its arithmetic signature and refuses.
  * NOTHING IS ATTRIBUTED. The audit reads GUID sets, never a plan, a
    disposition or a tally, so it cannot credit a match to a class on the
    strength of a record that does not exist -- T048d's explicit prohibition.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fakes: an LCM object is anything with `Guid` and `ClassName`
# ---------------------------------------------------------------------------


class _Obj:
    def __init__(self, guid, class_name):
        self.Guid = guid
        self.ClassName = class_name


class _NoGuid:
    ClassName = "MoMorphType"

    @property
    def Guid(self):
        raise RuntimeError("this object will not say what it is")


def _objects_for(by_class):
    """An `objects_for(handle, class_name)` seam over a plain dict."""

    def enumerate_objects(handle, class_name):
        if class_name not in by_class:
            raise KeyError("no such class " + class_name)
        return list(by_class[class_name])

    return enumerate_objects


def _guids(prefix, n, start=0):
    return ["%s-%04d" % (prefix, i) for i in range(start, start + n)]


# ---------------------------------------------------------------------------
# The bound itself -- pure arithmetic, no FLEx
# ---------------------------------------------------------------------------


class TestStarterMatchedLowerBound:
    """`census.starter_matched_lower_bound` -- the whole of the arithmetic."""

    def _bound(self, *, baseline, dest_count, dest, source):
        from gramtrans.Lib import census as census_mod

        return census_mod.starter_matched_lower_bound(
            baseline, dest_count, dest, source)

    def test_the_momorphtype_row_that_blocked_p3_reads_all_nineteen(self):
        """THE MEASURED ROW. Source 19, destination 19, starter 19, identical
        GUID sets. `|D \\ Q|` is 0, so the bound is the whole baseline and
        `unmatched_starter` is 0 -- the row reads MATCHED, which is what the
        two `.fwdata` files said all along."""
        shared = frozenset(_guids("mt", 19))
        assert self._bound(
            baseline=19, dest_count=19, dest=shared, source=shared) == 19

    def test_destination_only_objects_reduce_the_bound_one_for_one(self):
        """The general case. A destination object whose GUID is absent from the
        source might be an unmatched starter, so each one costs the bound
        exactly one -- the tightest claim the two sets support."""
        source = frozenset(_guids("x", 18))
        dest = frozenset(_guids("x", 18) + _guids("local", 2))
        assert self._bound(
            baseline=5, dest_count=20, dest=dest, source=source) == 3

    def test_the_bound_never_exceeds_the_baseline(self):
        """A re-run matches everything the previous run created (T039 run 2
        matched 164 `MoStemMsa` against a starter baseline of 0). Only STARTER
        objects may be subtracted, so the clamp is not cosmetic: without it
        `census.unmatched_starter` returns a negative and inflates the net
        count, hiding a real shortfall."""
        shared = frozenset(_guids("m", 164))
        assert self._bound(
            baseline=0, dest_count=164, dest=shared, source=shared) == 0

    def test_the_bound_never_goes_negative(self):
        """More destination-only objects than starters is arithmetically
        possible and means only "no starter is provably matched". Zero, not a
        negative, because a negative subtrahend would ADD to the net count."""
        dest = frozenset(_guids("d", 30))
        assert self._bound(
            baseline=5, dest_count=30, dest=dest, source=frozenset()) == 0

    def test_no_baseline_count_declines(self):
        """There is no B to bound. `absent_from_baseline` is a different
        statement from a measured zero, and the row keeps the gross basis."""
        shared = frozenset(_guids("mt", 19))
        assert self._bound(
            baseline=None, dest_count=19, dest=shared, source=shared) is None

    @pytest.mark.parametrize("dest,source", [
        (None, frozenset(_guids("mt", 19))),
        (frozenset(_guids("mt", 19)), None),
        (None, None),
    ])
    def test_an_unread_guid_set_on_either_side_declines(self, dest, source):
        """`guid_sets_for` records WHY a class could not be read. A missing set
        on either side is no evidence, and no evidence is the gross basis --
        never an assumed empty set, which would read as "nothing matched"."""
        assert self._bound(
            baseline=19, dest_count=19, dest=dest, source=source) is None

    def test_a_guid_set_disagreeing_with_the_row_count_declines(self):
        """The counts come from `repo.Count` minus subclasses; the GUIDs come
        from exact-class enumeration. If they disagree the audit is measuring a
        different population from the row it is about to change, and preferring
        one of them would be exactly the silent choice this instrument exists
        to avoid."""
        shared = frozenset(_guids("mt", 19))
        assert self._bound(
            baseline=19, dest_count=20, dest=shared, source=shared) is None

    def test_a_destination_smaller_than_the_starter_declines(self):
        """THE ONE ASSUMPTION, GUARDED. The proof needs `S subset of D` -- no
        starter object was deleted. `|D| < B` is that assumption's arithmetic
        signature failing, so the bound does not hold and the row falls back to
        gross subtraction rather than to a number it cannot justify."""
        shared = frozenset(_guids("mt", 18))
        assert self._bound(
            baseline=19, dest_count=18, dest=shared, source=shared) is None

    def test_the_bound_is_a_lower_bound_over_random_set_shapes(self):
        """The property, checked rather than argued. For every shape where the
        audit does NOT decline, the bound is <= the true `|S n Q|` for EVERY
        starter set S of size B contained in D. Enumerating all such S is what
        makes this a proof of direction and not an example."""
        import itertools

        from gramtrans.Lib import census as census_mod

        dest = frozenset(["a", "b", "c", "d", "e"])
        for source in (
            frozenset(),
            frozenset(["a"]),
            frozenset(["a", "b", "c"]),
            frozenset(["a", "b", "c", "d", "e"]),
            frozenset(["a", "z"]),
        ):
            for b in range(0, 6):
                bound = census_mod.starter_matched_lower_bound(
                    b, len(dest), dest, source)
                if bound is None:
                    continue
                for starters in itertools.combinations(sorted(dest), b):
                    truth = len(set(starters) & source)
                    assert bound <= truth, (
                        "bound %d exceeds the truth %d for B=%d, S=%s, Q=%s "
                        "-- an over-stated starter match under-subtracts and "
                        "HIDES a shortfall" % (
                            bound, truth, b, starters, sorted(source))
                    )


# ---------------------------------------------------------------------------
# Reading the GUIDs
# ---------------------------------------------------------------------------


class TestGuidSetsFor:
    """`census.guid_sets_for` -- one project's GUIDs, per class, honestly."""

    def test_it_reads_one_set_per_class(self):
        from gramtrans.Lib import census as census_mod

        by_class = {
            "MoMorphType": [_Obj(g, "MoMorphType") for g in _guids("mt", 19)],
            "PartOfSpeech": [_Obj(g, "PartOfSpeech") for g in _guids("pos", 5)],
        }
        found, unreadable = census_mod.guid_sets_for(
            object(), ("MoMorphType", "PartOfSpeech"),
            objects_for=_objects_for(by_class))
        assert unreadable == {}
        assert len(found["MoMorphType"]) == 19
        assert len(found["PartOfSpeech"]) == 5

    def test_an_empty_class_is_a_measured_empty_set(self):
        """Present with an empty set, not absent. The distinction is the whole
        point: absent means "could not look" and declines the audit, while an
        empty set is a measurement the bound can use."""
        from gramtrans.Lib import census as census_mod

        found, unreadable = census_mod.guid_sets_for(
            object(), ("MoStemName",),
            objects_for=_objects_for({"MoStemName": []}))
        assert found == {"MoStemName": frozenset()}
        assert unreadable == {}

    def test_one_unreadable_class_does_not_lose_the_others(self):
        """A whole-pass failure would push EVERY row back onto the gross basis
        for one class's sake. The failure is recorded against the class it
        belongs to and every other row keeps its evidence."""
        from gramtrans.Lib import census as census_mod

        by_class = {"MoMorphType": [_Obj(g, "MoMorphType")
                                    for g in _guids("mt", 19)]}
        found, unreadable = census_mod.guid_sets_for(
            object(), ("MoMorphType", "PhCode"),
            objects_for=_objects_for(by_class))
        assert set(found) == {"MoMorphType"}
        assert "PhCode" in unreadable
        assert "KeyError" in unreadable["PhCode"]

    def test_an_object_that_will_not_give_a_guid_makes_the_class_unreadable(self):
        """It is NOT dropped. A silently short GUID set shrinks `|D \\ Q|` and
        so OVERSTATES the bound -- the one direction this whole section must
        not be wrong in -- so the class declines instead."""
        from gramtrans.Lib import census as census_mod

        found, unreadable = census_mod.guid_sets_for(
            object(), ("MoMorphType",),
            objects_for=_objects_for({
                "MoMorphType": [_Obj("mt-0000", "MoMorphType"), _NoGuid()]}))
        assert found == {}
        assert "MoMorphType" in unreadable

    def test_each_class_is_enumerated_exactly_once(self):
        """`objects_in_class` is an O(n) walk. A duplicated class name in the
        request must not double the work."""
        from gramtrans.Lib import census as census_mod

        seen = []

        def enumerate_objects(handle, class_name):
            seen.append(class_name)
            return [_Obj("g-0", class_name)]

        census_mod.guid_sets_for(
            object(), ("MoMorphType", "MoMorphType", "PhCode"),
            objects_for=enumerate_objects)
        assert seen == ["MoMorphType", "PhCode"]


# ---------------------------------------------------------------------------
# Which classes get audited
# ---------------------------------------------------------------------------


class TestIdentityAuditClasses:
    """`census_cli.identity_audit_classes` -- derived from the baseline."""

    def _baseline(self, counts, missing=False):
        from gramtrans.Lib import models as models_mod

        if missing:
            return models_mod.StarterBaseline.missing()
        return models_mod.StarterBaseline(
            kind=models_mod.StarterBaselineKind.STARTER_CAPTURE,
            captured_from="Scratch",
            flex_version="9.3.10",
            captured_at="2026-08-20T09:46:07",
            entries=tuple(
                models_mod.StarterBaselineEntry(object_class=cls, count=n)
                for cls, n in counts.items()
            ),
        )

    def test_only_classes_with_a_nonzero_baseline_count(self):
        """A class the baseline counts as ZERO cannot carry a phantom: gross
        subtraction subtracts nothing from it, so the two bases already agree
        and the O(n) walk would buy nothing."""
        from gramtrans import census_cli

        classes = census_cli.identity_audit_classes(
            self._baseline({"MoMorphType": 19, "MoStemName": 0,
                            "PartOfSpeech": 5}),
            ("MoMorphType", "MoStemName", "PartOfSpeech"))
        assert classes == ("MoMorphType", "PartOfSpeech")

    def test_a_class_the_census_cannot_measure_is_not_audited(self):
        """Auditing a class with no row to change is pure cost."""
        from gramtrans import census_cli

        classes = census_cli.identity_audit_classes(
            self._baseline({"MoMorphType": 19, "StTxtPara": 86}),
            ("MoMorphType",))
        assert classes == ("MoMorphType",)

    def test_a_missing_baseline_audits_nothing(self):
        """There is no B to bound, so every row would decline anyway."""
        from gramtrans import census_cli

        assert census_cli.identity_audit_classes(
            self._baseline({}, missing=True), ("MoMorphType",)) == ()

    def test_the_set_is_sorted_so_two_runs_enumerate_alike(self):
        from gramtrans import census_cli

        classes = census_cli.identity_audit_classes(
            self._baseline({"PhCode": 25, "MoMorphType": 19, "CmAgent": 4}),
            ("PhCode", "MoMorphType", "CmAgent"))
        assert classes == tuple(sorted(classes))


# ---------------------------------------------------------------------------
# The row arithmetic
# ---------------------------------------------------------------------------


class TestRowConsumesTheIdentityAudit:
    """`_row_for_entry`'s new basis path, and its subordination to the report."""

    def _entry(self, object_class="MoMorphType", owning_feature_system=None):
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
            captured_at="2026-08-20T09:46:07",
            entries=tuple(
                models_mod.StarterBaselineEntry(object_class=cls, count=n)
                for cls, n in counts.items()
            ),
        )

    def _row(self, *, object_class="MoMorphType", matched=None, complete=True,
             dest=19, src=19, baseline_count=19, withheld=frozenset(),
             dest_guids=None, source_guids=None, owner=None):
        from gramtrans import census_cli

        return census_cli._row_for_entry(
            self._entry(object_class, owner),
            {object_class: src},
            {object_class: dest},
            self._baseline({object_class: baseline_count}),
            matched or {},
            complete,
            withheld_classes=withheld,
            source_guids=(
                {} if source_guids is None
                else {object_class: source_guids}),
            destination_guids=(
                {} if dest_guids is None
                else {object_class: dest_guids}),
        )

    def test_the_momorphtype_row_that_blocked_p3_now_reads_matched(self):
        """THE ROW T048d IS ABOUT. Source 19, destination 19, starter 19, no
        run-report tally of any kind, identical GUID sets. Before this fix the
        row read `difference -19` on a transfer that lost nothing, and it was
        the sole remaining blocker on T048's predicate P3."""
        shared = frozenset(_guids("mt", 19))
        row, kwargs = self._row(dest_guids=shared, source_guids=shared)
        assert kwargs["starter_subtraction_basis"] == "baseline_matched"
        assert kwargs["starter_matched_to_source"] == 19
        assert row.starter_excluded == 0
        assert row.difference == 0

    def test_without_the_audit_the_same_row_still_reports_the_phantom(self):
        """The control. Identical inputs minus the GUID sets reproduce the
        measured `-19`, so the test above is measuring the fix and not a
        coincidence of the fixture."""
        row, kwargs = self._row()
        assert kwargs["starter_subtraction_basis"] == "baseline_gross"
        assert "starter_matched_to_source" not in kwargs
        assert row.difference == -19

    def test_the_row_says_where_the_number_came_from(self):
        """A capped or bounded number is never silent (the T023c rule). The
        note has to name the audit, so a reader can tell this basis from the
        one the run report earns."""
        shared = frozenset(_guids("mt", 19))
        _, kwargs = self._row(dest_guids=shared, source_guids=shared)
        note = " ".join(kwargs["notes"])
        assert "IDENTITY AUDIT" in note
        assert "LOWER BOUND" in note
        assert "not from the run report" in note

    def test_the_run_report_wins_when_it_has_a_tally(self):
        """SUBORDINATION. The audit is consulted only on the branch where no
        report tally reached the row, so a row that already reads its matched
        count off the report cannot change behaviour -- and the two are never
        mixed by taking the larger, which is the one arithmetic that can hide a
        shortfall."""
        source = frozenset(_guids("x", 18))
        dest = frozenset(_guids("x", 18) + _guids("local", 2))
        row, kwargs = self._row(
            object_class="PartOfSpeech", baseline_count=5, dest=20, src=18,
            matched={"PartOfSpeech": 4},
            dest_guids=dest, source_guids=source)
        assert kwargs["starter_matched_to_source"] == 4
        note = " ".join(kwargs["notes"])
        assert "read from the run report" in note
        assert "IDENTITY AUDIT" not in note

    def test_a_declining_audit_leaves_the_gross_basis_untouched(self):
        """Every refusal in `starter_matched_lower_bound` has to land here as
        the pre-T048d behaviour, not as a partially-applied basis."""
        shared = frozenset(_guids("mt", 18))
        row, kwargs = self._row(
            dest=18, src=19, dest_guids=shared, source_guids=shared)
        assert kwargs["starter_subtraction_basis"] == "baseline_gross"
        assert "starter_matched_to_source" not in kwargs
        assert row.difference == 18 - 19 - 19

    def test_a_split_row_never_reaches_the_audited_basis(self):
        """A GUID set is per LCM CLASS. An `FsFeatStrucType` row split by
        owning feature system is not a class, so crediting one class's audit to
        a half would subtract the same starter objects twice -- the same reason
        a split row cannot reach the matched basis from the report."""
        shared = frozenset(_guids("fs", 4))
        _, kwargs = self._row(
            object_class="FsFeatStrucType", baseline_count=4, dest=4, src=4,
            dest_guids=shared, source_guids=shared,
            owner="LangProject.MsFeatureSystemOA")
        assert kwargs["starter_subtraction_basis"] != "baseline_matched"

    def test_the_audit_survives_a_withheld_class(self):
        """T048b withholds the stronger basis from a class whose TALLY may be
        understated by an unattributable identity skip. The audit does not read
        the tally, so the tally's incompleteness cannot corrupt it -- and
        refusing anyway would leave a GUID-proven row reporting a phantom."""
        shared = frozenset(_guids("mt", 19))
        _, kwargs = self._row(
            dest_guids=shared, source_guids=shared,
            withheld=frozenset({"MoMorphType"}))
        assert kwargs["starter_subtraction_basis"] == "baseline_matched"
        assert kwargs["starter_matched_to_source"] == 19

    def test_an_unresolved_bound_keeps_the_gross_basis(self):
        """THE CONCLUSIVENESS GATE. A lower bound on the matched count is an
        UPPER bound on the loss. When it still leaves a shortfall the audit has
        only narrowed an interval, and `census.is_gross_basis_row` is the single
        predicate 5.2's verdict cap turns on -- so promoting such a row would
        make an upper bound FAIL the run. Measured on CENSUS-20260820-125034,
        that took the verdict from CENSUS_ACCOUNTED to UNEXPLAINED_SHORTFALL on
        numbers that are bounds."""
        source = frozenset(_guids("p", 302))
        dest = frozenset(_guids("p", 302))
        row, kwargs = self._row(
            object_class="CmPossibility", baseline_count=302,
            dest=302, src=304, dest_guids=dest, source_guids=source)
        assert kwargs["starter_subtraction_basis"] == "baseline_gross"
        assert "starter_matched_to_source" not in kwargs
        assert row.difference == 302 - 302 - 304

    def test_an_unresolved_bound_still_says_what_it_narrowed_the_loss_to(self):
        """The finding is not thrown away, only kept out of the arithmetic. The
        note has to carry both figures so a reader can see the interval the
        audit established -- on the measured `CmPossibility` row, at most 2
        against the gross basis's 304."""
        source = frozenset(_guids("p", 302))
        dest = frozenset(_guids("p", 302))
        _, kwargs = self._row(
            object_class="CmPossibility", baseline_count=302,
            dest=302, src=304, dest_guids=dest, source_guids=source)
        note = " ".join(kwargs["notes"])
        assert "narrows this row's shortfall to AT MOST 2" in note
        assert "against the 304 the gross basis reports" in note
        assert "UPPER bound on the loss" in note

    def test_a_resolved_bound_says_so_explicitly(self):
        """The other half of the same rule: when the most negative the row can
        be is not negative, nothing of this class failed to arrive, and the
        note states that rather than leaving the reader to redo the
        arithmetic."""
        shared = frozenset(_guids("mt", 19))
        _, kwargs = self._row(dest_guids=shared, source_guids=shared)
        note = " ".join(kwargs["notes"])
        assert "RESOLVES this row" in note
        assert "no source object of this class failed to arrive" in note

    def test_a_bound_that_lands_on_a_surplus_resolves_too(self):
        """`>= 0`, not `== 0`. A destination legitimately holding more than the
        source is not a shortfall, and refusing to resolve it would leave a row
        on the gross basis for having too MUCH -- which the cap's rationale
        (that gross over-subtracts) says nothing about."""
        source = frozenset(_guids("m", 10))
        dest = frozenset(_guids("m", 10) + _guids("extra", 3))
        _, kwargs = self._row(
            object_class="MoStemName", baseline_count=3,
            dest=13, src=10, dest_guids=dest, source_guids=source)
        assert kwargs["starter_subtraction_basis"] == "baseline_matched"

    def test_the_audit_reads_no_plan_no_tally_and_no_disposition(self):
        """T048d's explicit prohibition: do NOT close this by attributing a
        match nothing recorded. The audited row is produced with an EMPTY
        matched tally and `matched_complete` False, so nothing in the run
        report can have contributed to it."""
        shared = frozenset(_guids("mt", 19))
        _, kwargs = self._row(
            matched={}, complete=False,
            dest_guids=shared, source_guids=shared)
        assert kwargs["starter_matched_to_source"] == 19
