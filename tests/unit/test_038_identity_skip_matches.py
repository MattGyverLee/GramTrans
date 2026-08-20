"""T048b: an `ALREADY_PRESENT_BY_GUID` skip is a starter MATCH.

Why this exists. The 2026-08-20 gate run
(`specs/038-transfer-fidelity-gaps/journal/T038-T048-live-gate-rerun.md`) proved
against the raw `.fwdata` that `PartOfSpeech` transferred perfectly -- 20 source
GUIDs, 20 destination GUIDs, none missing, no destination-only leftovers -- and
the census still reported `difference: -2`, so the gate exited 1 and P1 could
not report green no matter how correct the transfer was.

The destination starter held 5 parts of speech and the run matched all five, by
two different mechanisms:

  * 3 matched by natural key and then ENRICHED, which reach
    `matched_to_source.by_object_class` through the plan item carrying the
    enrichment record;
  * 2 matched by GUID and then SKIPPED, which land in `skips[]` as
    `ALREADY_PRESENT_BY_GUID` and reach nothing at all, because
    `report.build_from_plan` calls `_count_matched` on the actions and
    overwrites loops and not on the skips loop.

So `starter_matched_to_source` read 3, `unmatched_starter` read 5 - 3 = 2, and
two starter objects the run had positively identified by GUID were subtracted
from the destination as though they were surplus.

An identity skip is a match, and the strongest kind. Nothing was written
because nothing needed to be -- a statement about the disposition, not about
whether the object was found.

Two invariants get their own tests here because each one, if broken, turns this
fix into a worse defect than the one it closes:

  * ATTRIBUTION IS NEVER GUESSED. A skip whose category is not one-to-one with
    an LCM class is counted for NO class, and withholds the `baseline_matched`
    basis from the classes it might have been. Crediting the wrong class
    subtracts the wrong number from the wrong row.
  * THE TALLY IS CAPPED AT THE STARTER BASELINE. `census.unmatched_starter`
    does not clamp, so an uncapped tally on a re-run (T039 run 2 matched 164
    `MoStemMsa` against a starter baseline of 0) would subtract a NEGATIVE and
    inflate the net count -- hiding a real shortfall, the one direction this
    instrument must never be wrong in.
"""

from __future__ import annotations

import json

import pytest


# ---------------------------------------------------------------------------
# Reading the skips
# ---------------------------------------------------------------------------


def _write(tmp_path, payload, name="report.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _skip(category, guid, reason="ALREADY_PRESENT_BY_GUID"):
    return {
        "category": category,
        "source_guid": guid,
        "reason": reason,
        "detail": "GUID %s... present in target; all WS slots equal." % guid[:8],
    }


class TestIdentitySkipIsAMatch:
    """`census_cli.identity_skips_from_report` -- the whole of the reader."""

    def test_a_skip_in_a_one_to_one_category_is_counted(self, tmp_path):
        from gramtrans import census_cli

        path = _write(tmp_path, {"skips": [
            _skip("GRAM_CATEGORIES", "46e4fe08-ffa0-4c8b-bf98-2c56f38904d9"),
            _skip("GRAM_CATEGORIES", "a4fc78d6-7591-4fb3-8edd-82f10ae3739d"),
        ]})
        tally = census_cli.identity_skips_from_report(path)

        assert tally.measured is True
        assert tally.by_class == {"PartOfSpeech": 2}
        assert tally.total() == 2
        assert tally.withheld == frozenset()
        assert tally.unbounded is False

    def test_a_skip_for_any_other_reason_is_not_a_match(self, tmp_path):
        """`ALREADY_PRESENT_BY_GUID` is the ONE reason that denotes a match.
        Every other skip is a genuine non-event and counting it would assert a
        match the run never made."""
        from gramtrans import census_cli

        path = _write(tmp_path, {"skips": [
            _skip("GRAM_CATEGORIES", "g-1", reason="EXCLUDED_LOSSY"),
            _skip("GRAM_CATEGORIES", "g-2", reason="NOT_REPRODUCIBLE"),
            _skip("GRAM_CATEGORIES", "g-3", reason="INTERACTIVE_SKIP"),
            _skip("GRAM_CATEGORIES", "g-4", reason="BARE_BONES_MISSING_CLOSURE"),
        ]})
        tally = census_cli.identity_skips_from_report(path)

        assert tally.by_class == {}
        assert tally.measured is True, "the list was present and was read"

    def test_an_absent_skips_list_is_unmeasured_not_zero(self, tmp_path):
        """A report predating the surface must leave every row exactly where it
        was, not claim "no identity skips" -- the absent-read-as-zero error
        `census.unmatched_starter` refuses to make."""
        from gramtrans import census_cli

        tally = census_cli.identity_skips_from_report(
            _write(tmp_path, {"context": {"run_id": "GT-20260820-094825"}}))

        assert tally.measured is False
        assert tally.by_class == {}
        assert tally.withheld == frozenset()
        assert tally.unbounded is False

    def test_an_ambiguous_category_withholds_only_its_candidates(self, tmp_path):
        """`VARIANT_TYPES` covers `LexEntryType` AND `LexEntryInflType`, so the
        class cannot be named -- but the match cannot have been a
        `PartOfSpeech` either, and withholding the stronger basis from a row
        that was never in doubt is its own mis-report."""
        from gramtrans import census_cli

        path = _write(tmp_path, {"skips": [
            _skip("VARIANT_TYPES", "v-1"),
            _skip("GRAM_CATEGORIES", "g-1"),
        ]})
        tally = census_cli.identity_skips_from_report(path)

        assert tally.by_class == {"PartOfSpeech": 1}, "the bounded one still counts"
        assert tally.unattributed_by_category == {"VARIANT_TYPES": 1}
        assert tally.withheld == frozenset({"LexEntryType", "LexEntryInflType"})
        assert tally.unbounded is False
        assert "PartOfSpeech" not in tally.withheld

    def test_an_unknown_category_withholds_from_everything(self, tmp_path):
        """No bound on which class it could have been means no class's tally
        can be trusted -- the pre-T048b behaviour of
        `RunReport.matched_class_is_complete`, and the honest answer when the
        damage cannot be located."""
        from gramtrans import census_cli

        path = _write(tmp_path, {"skips": [_skip("AFFIXES", "a-1")]})
        tally = census_cli.identity_skips_from_report(path)

        assert tally.by_class == {}
        assert tally.unbounded is True
        assert tally.unattributed_by_category == {"AFFIXES": 1}

    @pytest.mark.parametrize("guid_field", ["target_guid", "source_guid"])
    def test_deduped_against_an_enrichment(self, tmp_path, guid_field):
        """An identity skip's `source_guid` IS its target GUID -- that is what
        matching by GUID means -- so it can be compared against the
        enrichments the report's own tally already counted. Double-counting
        would OVERSTATE the matched tally, which under-subtracts and can hide a
        real shortfall."""
        from gramtrans import census_cli

        path = _write(tmp_path, {
            "enrichments": [{
                "object_class": "PartOfSpeech",
                "source_guid": "shared-guid" if guid_field == "source_guid" else "x",
                "target_guid": "shared-guid" if guid_field == "target_guid" else "y",
                "is_empty": False,
            }],
            "skips": [
                _skip("GRAM_CATEGORIES", "shared-guid"),
                _skip("GRAM_CATEGORIES", "fresh-guid"),
            ],
        })
        tally = census_cli.identity_skips_from_report(path)

        assert tally.by_class == {"PartOfSpeech": 1}, (
            "the enriched object was already counted by the report's tally"
        )
        assert tally.deduped == 1

    def test_the_same_guid_twice_is_one_match(self, tmp_path):
        from gramtrans import census_cli

        path = _write(tmp_path, {"skips": [
            _skip("GRAM_CATEGORIES", "g-1"),
            _skip("GRAM_CATEGORIES", "g-1"),
        ]})
        tally = census_cli.identity_skips_from_report(path)

        assert tally.by_class == {"PartOfSpeech": 1}
        assert tally.deduped == 1

    def test_the_class_table_is_previews_and_not_a_copy(self):
        """One authority for "which LCM class does this category name". A
        second table next to a CLI is the drift feature 038 exists to end."""
        from gramtrans import census_cli
        from gramtrans.Lib import preview

        table, available = census_cli.identity_skip_class_table()

        assert available is True
        assert table == {
            cat.name: cls
            for cat, cls in preview._LCM_CLASS_FOR_CATEGORY.items()
        }

    def test_no_ambiguous_category_is_also_in_the_one_to_one_table(self):
        """The two tables answer different questions and must not overlap: a
        category the one-to-one table names is attributable, so it can never
        need a candidate set."""
        from gramtrans import census_cli

        table, _ = census_cli.identity_skip_class_table()
        overlap = set(table) & set(census_cli._AMBIGUOUS_IDENTITY_SKIP_CLASSES)

        assert overlap == set(), (
            "a category cannot be both one-to-one and ambiguous: %r" % (overlap,)
        )


class TestMergingWithTheReportTally:
    """The report's tally and the skip tally count DISJOINT dispositions of
    disjoint objects, so they add rather than override."""

    def test_the_two_sources_add(self, tmp_path):
        from gramtrans import census_cli

        tally = census_cli.identity_skips_from_report(
            _write(tmp_path, {"skips": [
                _skip("GRAM_CATEGORIES", "g-1"),
                _skip("GRAM_CATEGORIES", "g-2"),
            ]}))
        merged = census_cli.merge_identity_skip_matches(
            {"PartOfSpeech": 3, "PhPhoneme": 21}, tally)

        assert merged == {"PartOfSpeech": 5, "PhPhoneme": 21}

    def test_a_class_only_the_skips_name_still_appears(self, tmp_path):
        from gramtrans import census_cli

        tally = census_cli.identity_skips_from_report(
            _write(tmp_path, {"skips": [_skip("SEMANTIC_DOMAINS", "s-1")]}))

        assert census_cli.merge_identity_skip_matches({}, tally) == {
            "CmSemanticDomain": 1
        }

    def test_merging_does_not_mutate_the_report_tally(self, tmp_path):
        from gramtrans import census_cli

        tally = census_cli.identity_skips_from_report(
            _write(tmp_path, {"skips": [_skip("GRAM_CATEGORIES", "g-1")]}))
        original = {"PartOfSpeech": 3}
        census_cli.merge_identity_skip_matches(original, tally)

        assert original == {"PartOfSpeech": 3}


# ---------------------------------------------------------------------------
# The row arithmetic
# ---------------------------------------------------------------------------


class TestRowConsumesTheIdentitySkips:
    """`_row_for_entry`'s two new behaviours: the withheld basis and the cap."""

    def _entry(self, object_class="PartOfSpeech", owning_feature_system=None):
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

    def _row(self, *, object_class="PartOfSpeech", matched=None, complete=True,
             dest=20, src=20, baseline_count=5, withheld=frozenset()):
        from gramtrans import census_cli

        return census_cli._row_for_entry(
            self._entry(object_class),
            {object_class: src},
            {object_class: dest},
            self._baseline({object_class: baseline_count}),
            matched or {},
            complete,
            withheld_classes=withheld,
        )

    def test_the_measured_partofspeech_row_reads_zero(self):
        """THE ROW THAT BLOCKED P1. Source 20, destination 20, starter 5, and
        all five starters matched (3 enriched + 2 identity skips). Before
        T048b this row read `difference: -2` on a transfer that lost nothing."""
        row, kwargs = self._row(matched={"PartOfSpeech": 5})

        assert kwargs["starter_subtraction_basis"] == "baseline_matched"
        assert kwargs["starter_matched_to_source"] == 5
        assert row.starter_excluded == 0, "5 baseline - 5 matched"
        assert row.difference == 0

    def test_without_the_identity_skips_the_same_row_reads_minus_two(self):
        """The control: this is exactly the mis-report, reproduced. Keeping it
        beside the fix is what proves the -2 came from the accounting and not
        from the transfer."""
        row, kwargs = self._row(matched={"PartOfSpeech": 3})

        assert kwargs["starter_matched_to_source"] == 3
        assert row.starter_excluded == 2
        assert row.difference == -2

    def test_a_withheld_class_stays_on_the_gross_basis(self):
        row, kwargs = self._row(
            object_class="LexEntryType",
            matched={"LexEntryType": 4},
            withheld=frozenset({"LexEntryType", "LexEntryInflType"}),
            baseline_count=5, dest=20, src=20,
        )

        assert kwargs["starter_subtraction_basis"] == "baseline_gross"
        assert "starter_matched_to_source" not in kwargs, (
            "on the gross basis the matched count is UNKNOWN; emitting one "
            "would claim a tally the unattributed skip has already spoiled"
        )
        assert row.starter_excluded == 5, "the gross baseline"

    def test_withholding_is_never_silent(self):
        """T023c's rule: a capped or withheld verdict that says nothing is a
        verdict nobody can act on."""
        from gramtrans.Lib import census as census_mod

        row, kwargs = self._row(
            object_class="LexEntryType",
            matched={"LexEntryType": 4},
            withheld=frozenset({"LexEntryType"}),
        )
        artifact = census_mod.class_row_artifact(
            row, self._entry("LexEntryType"), **kwargs)
        notes = " ".join(artifact.get("notes", ()))

        assert "WITHHELD" in notes
        assert "T048b" in notes

    def test_the_tally_is_capped_at_the_starter_baseline(self):
        """T039 run 2 matched 164 `MoStemMsa` against a starter baseline of 0.
        `census.unmatched_starter` does not clamp, so an uncapped tally
        subtracts a NEGATIVE and inflates the net -- hiding a shortfall."""
        row, kwargs = self._row(
            object_class="MoStemMsa",
            matched={"MoStemMsa": 164},
            baseline_count=23, dest=164, src=164,
        )

        assert kwargs["starter_matched_to_source"] == 23, "capped, not 164"
        assert row.starter_excluded == 0, "23 baseline - 23 capped, never -141"
        assert row.difference == 0

    def test_an_uncapped_tally_would_have_inflated_the_net(self):
        """States the defect the cap prevents, in the arithmetic rather than in
        a comment: a negative `starter_excluded` ADDS to the destination count
        and can turn a real shortfall into a clean row."""
        from gramtrans.Lib import census as census_mod

        uncapped = census_mod.unmatched_starter(23, 164)
        assert uncapped == -141, "the unclamped helper really does go negative"

        row, _ = self._row(
            object_class="MoStemMsa",
            matched={"MoStemMsa": 164},
            baseline_count=23, dest=100, src=164,
        )
        assert row.starter_excluded >= 0
        assert row.difference == 100 - 0 - 164 == -64, (
            "the 64-object loss is still reported; an uncapped basis would "
            "have read 100 + 141 - 164 = +77 and hidden it"
        )

    def test_the_cap_is_never_silent(self):
        from gramtrans.Lib import census as census_mod

        row, kwargs = self._row(
            object_class="MoStemMsa",
            matched={"MoStemMsa": 164},
            baseline_count=23, dest=164, src=164,
        )
        artifact = census_mod.class_row_artifact(
            row, self._entry("MoStemMsa"), **kwargs)
        notes = " ".join(artifact.get("notes", ()))

        assert "CAPPED" in notes
        assert "164" in notes and "23" in notes

    def test_an_exact_tally_is_not_reported_as_capped(self):
        from gramtrans.Lib import census as census_mod

        row, kwargs = self._row(matched={"PartOfSpeech": 5})
        artifact = census_mod.class_row_artifact(
            row, self._entry("PartOfSpeech"), **kwargs)

        assert "CAPPED" not in " ".join(artifact.get("notes", ()))
