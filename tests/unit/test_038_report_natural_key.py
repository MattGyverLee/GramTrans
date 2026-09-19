"""T037 (FR-006): the RUN REPORT must report every natural-key match as such,
distinguishable from an identity match -- on BOTH reporting surfaces.

Why this file exists, separately from `test_038_natural_key.py` (which tests the
MATCHER) and `test_038_matched_by_class.py` (which tests the CENSUS tally). Those
two prove that a `MatchBasisRecord` is produced and that a match is counted. They
prove nothing about whether a human reading the run report can tell the two bases
apart, and FR-006 is a REPORTING requirement: "Every match made on a natural-key
basis MUST be recorded in the run report as such, distinguishable from an
identity match."

The measured failure this closes is recorded verbatim in
`tests/integration/test_038_two_mode_and_tallies.py::
test_zero_substitutions_means_the_matcher_never_ran`, against the live
Ejagham/Ngoreme pair:

    "The opposite reading -- zero substitutions beside a non-zero NATURAL_KEY
     count -- would have meant the matcher ran and had nothing to substitute,
     and nothing in the tally distinguished the two."

On that run the report carried `matched_to_source.total == 1806` and
`identity_substituted == 0`, and BOTH surfaces were silent about the basis of
those 1,806 matches: the console printed no line at all (the substitution
section is gated on `substituted` being non-zero), and the JSON's
`matched_to_source` block carried only `by_object_class` / `total` /
`complete`. A reader therefore could not distinguish

  * "1,806 objects were found by GUID and the natural-key path found nothing"
    from
  * "the natural-key path never ran",

which is exactly the inference FR-006 forbids. T031 has since wired real
`MatchBasis.IDENTITY` records in `Lib/preview.py::_emit_present_outcome`, so
identity matches now arrive carrying positive evidence -- and the report has to
show it.

Register note: every assertion below constructs REAL `MatchBasisRecord`s rather
than duck-typed stand-ins, because `MatchBasisRecord.__post_init__` is what
guarantees a NATURAL_KEY record carries a `target_guid` -- and that guarantee is
the reason `report._count_substitution` and `report._action_matched_existing`
cannot disagree (see `test_the_two_counters_cannot_disagree_by_construction`).
A stand-in would silently drop the invariant this file relies on.
"""

from __future__ import annotations

import json

import pytest

import gramtrans.Lib.report as report_mod  # noqa: F401 -- attaches build_from_plan
from gramtrans.Lib.models import (
    CategoryReport,
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


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------

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


def _identity(object_class, source_guid, target_guid):
    """A GUID (or identity-remap) match -- what `preview._emit_present_outcome`
    attaches for `match_via in ("guid", "identity_remap")`."""
    return MatchBasisRecord(
        basis=MatchBasis.IDENTITY,
        object_class=object_class,
        source_guid=source_guid,
        target_guid=target_guid,
        candidate_count=1,
    )


def _natural_key(object_class, source_guid, target_guid,
                 key_expression="Name", key_value="p"):
    """A roster-admitted natural-key match -- the identity SUBSTITUTION."""
    return MatchBasisRecord(
        basis=MatchBasis.NATURAL_KEY,
        object_class=object_class,
        source_guid=source_guid,
        target_guid=target_guid,
        key_expression=key_expression,
        key_value=key_value,
        candidate_count=1,
    )


def _none(object_class, source_guid):
    """The matcher ran and found NO counterpart -- evidence of a create."""
    return MatchBasisRecord(
        basis=MatchBasis.NONE,
        object_class=object_class,
        source_guid=source_guid,
    )


def _plan(*, actions=(), overwrites=(), skips=()):
    return RunPlan(
        context=_ctx(),
        selection=None,
        ws_mapping=None,
        actions=tuple(actions),
        skips=tuple(skips),
        overwrites=tuple(overwrites),
    )


def _report(plan, mode=RunMode.MOVE):
    return RunReport.build_from_plan(plan, mode)


def _add(category, source_guid, basis=None):
    return PlannedAction(
        category=category,
        source_guid=source_guid,
        intended_target_guid=source_guid.replace("src", "tgt"),
        summary=f"add {source_guid}",
        match_basis=basis,
    )


def _overwrite(category, source_guid, target_guid, basis=None, match_via="guid"):
    return PlannedOverwrite(
        category=category,
        source_guid=source_guid,
        target_guid=target_guid,
        summary=f"overwrite {source_guid}",
        match_via=match_via,
        match_basis=basis,
    )


def _text(report):
    return "\n".join(report_mod.render_text_summary(report))


def _json(report):
    return json.loads(report.to_snapshot_json())


# ---------------------------------------------------------------------------
# 1. The counter itself: NATURAL_KEY counts, IDENTITY does not
# ---------------------------------------------------------------------------

def test_natural_key_add_counts_as_a_substitution_identity_add_does_not():
    """The whole point of the counter (FR-006 / FR-187): an object claimed by
    NAME is counted; an object claimed by GUID is not. Both arrive as ADDs, so
    the action verb cannot be what distinguishes them -- only the basis can."""
    plan = _plan(actions=[
        _add(GrammarCategory.PHONEMES, "src-nk",
             _natural_key("PhPhoneme", "src-nk", "tgt-nk")),
        _add(GrammarCategory.PHONEMES, "src-id",
             _identity("PhPhoneme", "src-id", "tgt-id")),
    ])
    report = _report(plan)

    assert report.per_category[GrammarCategory.PHONEMES].identity_substitution == 1
    assert report.identity_substituted == 1
    # Both claimed a destination object that already existed, so both are
    # matches -- that is what makes the basis the ONLY discriminator.
    assert report.matched_to_source_total == 2
    assert report.matched_by_class == {"PhPhoneme": 2}


def test_natural_key_overwrite_counts_as_a_substitution_identity_one_does_not():
    """Same discrimination on the OVERWRITE path. Every overwrite is a match,
    so here too the basis is the only thing that separates the two."""
    plan = _plan(overwrites=[
        _overwrite(GrammarCategory.POS, "src-nk", "tgt-nk",
                   _natural_key("PartOfSpeech", "src-nk", "tgt-nk",
                                key_value="Adverb"),
                   match_via="natural_key"),
        _overwrite(GrammarCategory.POS, "src-id", "tgt-id",
                   _identity("PartOfSpeech", "src-id", "tgt-id")),
    ])
    report = _report(plan)

    assert report.per_category[GrammarCategory.POS].identity_substitution == 1
    assert report.matched_to_source_total == 2


def test_basis_none_counts_as_neither_a_substitution_nor_a_match():
    """`MatchBasis.NONE` means the matcher RAN and found nothing. It is
    evidence of a create, and must not be mistaken for either basis."""
    plan = _plan(actions=[
        _add(GrammarCategory.PHONEMES, "src-1", _none("PhPhoneme", "src-1")),
    ])
    report = _report(plan)

    assert report.identity_substituted == 0
    assert report.matched_to_source_total == 0
    assert report.matched_by_class == {}


def test_a_plain_add_with_no_basis_at_all_counts_as_neither():
    """A pre-038 producer emits no record. Absence is not evidence of a GUID
    match, and it is not evidence of a substitution either."""
    report = _report(_plan(actions=[_add(GrammarCategory.PHONEMES, "src-1")]))

    assert report.identity_substituted == 0
    assert report.matched_to_source_total == 0


# ---------------------------------------------------------------------------
# 2. Distinguishable in the JSON snapshot
# ---------------------------------------------------------------------------

class TestSnapshotSurface:
    """The artifact is what a linguist consults after the console scrolls away,
    so it carries the FULL basis accounting -- never a number the reader has to
    derive by subtraction and then hope about."""

    def _mixed(self):
        """1 natural-key match + 2 identity matches, all PhPhoneme."""
        return _report(_plan(overwrites=[
            _overwrite(GrammarCategory.PHONEMES, "src-nk", "tgt-nk",
                       _natural_key("PhPhoneme", "src-nk", "tgt-nk"),
                       match_via="natural_key"),
            _overwrite(GrammarCategory.PHONEMES, "src-i1", "tgt-i1",
                       _identity("PhPhoneme", "src-i1", "tgt-i1")),
            _overwrite(GrammarCategory.PHONEMES, "src-i2", "tgt-i2",
                       _identity("PhPhoneme", "src-i2", "tgt-i2")),
        ]))

    def test_the_substitution_block_names_its_basis_and_its_denominator(self):
        payload = _json(self._mixed())
        block = payload["identity_substitution"]

        assert block["total"] == 1
        assert block["per_category"] == {"PHONEMES": 1}
        # The basis is STATED, never inferred from the key's name.
        assert block["basis"] == MatchBasis.NATURAL_KEY.name
        # ...and so is the scale. "1" alone cannot be read: 1 of 3 and 1 of
        # 1806 are very different fidelity claims.
        assert block["of_matched_to_source_total"] == 3

    def test_the_matched_block_splits_the_basis_both_ways(self):
        """The reader must be able to read BOTH numbers off the artifact --
        `by_natural_key` positively counted, and the remainder named."""
        payload = _json(self._mixed())
        block = payload["matched_to_source"]

        assert block["total"] == 3
        assert block["by_natural_key"] == 1
        assert block["not_by_natural_key"] == 2
        assert block["by_natural_key"] + block["not_by_natural_key"] == block["total"]

    def test_zero_substitutions_beside_real_matches_is_stated_not_implied(self):
        """The Ejagham/Ngoreme reading this task exists to fix. With every
        match found by GUID, the artifact must SAY `by_natural_key: 0` next to
        a non-zero total -- so "the matcher ran and substituted nothing" is
        readable, and is not confusable with "the matcher never ran"."""
        report = _report(_plan(overwrites=[
            _overwrite(GrammarCategory.PHONEMES, "src-i1", "tgt-i1",
                       _identity("PhPhoneme", "src-i1", "tgt-i1")),
        ]))
        payload = _json(report)

        # The substitution block stays OMITTED when it is empty (038's
        # omit-when-empty snapshot discipline) ...
        assert "identity_substitution" not in payload
        # ... so the zero has to be legible from the matched block, which is
        # present because matches were measured.
        block = payload["matched_to_source"]
        assert block["total"] == 1
        assert block["by_natural_key"] == 0
        assert block["not_by_natural_key"] == 1

    def test_an_unmeasured_denominator_is_null_and_says_so(self):
        """A hand-built report carries a substitution count with NO matched
        tally. The denominator is emitted as `null` -- NOT 0 -- so a consumer
        doing `block["of_matched_to_source_total"] or 0` cannot read
        "unmeasured" as "measured, and it was zero". Same rule
        `census.unmatched_starter` applies to an absent baseline."""
        report = RunReport(
            context=_ctx(),
            mode=RunMode.PREVIEW,
            per_category={GrammarCategory.PHONEMES: CategoryReport(
                added=3, identity_substitution=3,
            )},
        )
        payload = _json(report)
        block = payload["identity_substitution"]

        assert block["total"] == 3
        assert block["of_matched_to_source_total"] is None
        assert "absent is not zero" in block["denominator_note"]
        assert "matched_to_source" not in payload

    def test_a_run_with_no_matches_still_adds_no_keys(self):
        """038's omit-when-empty discipline is not weakened by this task: a
        report with nothing matched must produce a snapshot with neither
        block, so pre-038 goldens keep comparing byte-identically."""
        payload = _json(_report(_plan(actions=[
            _add(GrammarCategory.PHONEMES, "src-1"),
        ])))

        assert "matched_to_source" not in payload
        assert "identity_substitution" not in payload

    def test_an_unproven_basis_is_never_counted_as_an_identity_match(self):
        """A fingerprint match carries NO record at all (see
        `preview._emit_present_outcome`'s docstring: recording one as IDENTITY
        would claim a GUID hit that never happened). It lands in
        `matches_unattributed`, and the artifact must say so rather than let
        `not_by_natural_key` be read as "found by GUID"."""
        report = _report(_plan(overwrites=[
            _overwrite(GrammarCategory.PHONEMES, "src-nk", "tgt-nk",
                       _natural_key("PhPhoneme", "src-nk", "tgt-nk"),
                       match_via="natural_key"),
            # fingerprint match: matched, but no basis record
            _overwrite(GrammarCategory.AFFIXES, "src-fp", "tgt-fp",
                       match_via="fingerprint"),
        ]))
        block = _json(report)["matched_to_source"]

        assert block["total"] == 2
        assert block["by_natural_key"] == 1
        assert block["not_by_natural_key"] == 1
        assert block["complete"] is False
        assert block["unattributed_by_category"] == {"AFFIXES": 1}
        # The caveat has to be in the artifact, not only in a reviewer's head.
        assert "unproven" in block["basis_note"]


# ---------------------------------------------------------------------------
# 3. Distinguishable in the console text
# ---------------------------------------------------------------------------

class TestConsoleSurface:
    """The console may truncate detail but may never hide the SIZE or the BASIS
    of what it summarises (SC-010). ASCII only, per the Windows console rule."""

    def test_a_substitution_is_labelled_weaker_and_carries_its_denominator(self):
        report = _report(_plan(overwrites=[
            _overwrite(GrammarCategory.PHONEMES, "src-nk", "tgt-nk",
                       _natural_key("PhPhoneme", "src-nk", "tgt-nk"),
                       match_via="natural_key"),
            _overwrite(GrammarCategory.PHONEMES, "src-i1", "tgt-i1",
                       _identity("PhPhoneme", "src-i1", "tgt-i1")),
            _overwrite(GrammarCategory.PHONEMES, "src-i2", "tgt-i2",
                       _identity("PhPhoneme", "src-i2", "tgt-i2")),
        ]))
        text = _text(report)

        assert "Identity SUBSTITUTION (matched by NATURAL KEY, not by GUID)" in text
        # The denominator: 1 of 3, not a bare "1".
        assert "1 of 3" in text
        # The remainder is named, so "found by GUID" is visible too.
        assert "2 matched without a natural key" in text
        assert "weaker identity claim than a GUID match" in text

    def test_zero_substitutions_beside_real_matches_is_printed(self):
        """The console half of the Ejagham/Ngoreme defect: before T037 this
        report produced NO match-basis line whatsoever, so a run in which
        every object was found by GUID looked exactly like a run in which the
        natural-key path had never been built."""
        report = _report(_plan(overwrites=[
            _overwrite(GrammarCategory.PHONEMES, f"src-{i}", f"tgt-{i}",
                       _identity("PhPhoneme", f"src-{i}", f"tgt-{i}"))
            for i in range(4)
        ]))
        text = _text(report)

        assert "Match basis" in text
        assert "4" in text
        assert "no identity substitution" in text

    def test_a_run_with_no_matches_prints_no_match_basis_line(self):
        """Unmeasured is not zero: with nothing matched there is no basis to
        report, and inventing a `0 of 0` line would claim the matcher ran."""
        report = _report(_plan(actions=[_add(GrammarCategory.PHONEMES, "src-1")]))

        assert "Match basis" not in _text(report)
        assert "Identity SUBSTITUTION" not in _text(report)

    def test_an_unmeasured_report_omits_the_denominator_rather_than_faking_it(self):
        """A hand-built report (sanctioned by `RunReport`'s docstring, and what
        every pre-038 caller produces) carries a substitution count with NO
        matched tallies. Printing "3 of 0" would be nonsense; the section must
        fall back to the bare total."""
        report = RunReport(
            context=_ctx(),
            mode=RunMode.PREVIEW,
            per_category={GrammarCategory.PHONEMES: CategoryReport(
                added=3, identity_substitution=3,
            )},
        )
        text = _text(report)

        assert "Identity SUBSTITUTION" in text
        assert "3 total" in text
        assert " of 0" not in text

    def test_the_console_stays_ascii_only(self):
        report = _report(_plan(overwrites=[
            _overwrite(GrammarCategory.PHONEMES, "src-nk", "tgt-nk",
                       _natural_key("PhPhoneme", "src-nk", "tgt-nk"),
                       match_via="natural_key"),
        ]))
        text = _text(report)

        assert text.isascii(), "the Windows console renders non-ASCII as mojibake"


# ---------------------------------------------------------------------------
# 4. The accounting invariant must not fire on a legitimate plan
# ---------------------------------------------------------------------------

class TestTheInvariantDoesNotSpuriouslyFire:
    """`RunReport.__post_init__` rejects `identity_substituted > matched_total`.
    That is a real invariant -- every natural-key match lands on a destination
    object that already existed -- but it is only safe if the two counters in
    `report._build_from_plan` count the SAME objects. If they can diverge, a
    legitimate plan raises `ValueError` mid-run and the whole transfer dies
    with an accounting message instead of a report."""

    def test_an_all_natural_key_plan_reaches_the_equality_boundary(self):
        """The tightest legitimate case: EVERY match is a substitution, so
        `identity_substituted == matched_total`. The invariant is `>`, not
        `>=`, precisely so this plan is legal."""
        report = _report(_plan(overwrites=[
            _overwrite(GrammarCategory.PHONEMES, f"src-{i}", f"tgt-{i}",
                       _natural_key("PhPhoneme", f"src-{i}", f"tgt-{i}"),
                       match_via="natural_key")
            for i in range(23)   # the measured Ejagham starter-phoneme count
        ]))

        assert report.identity_substituted == 23
        assert report.matched_to_source_total == 23

    def test_natural_key_adds_reach_the_boundary_too(self):
        """The ADD path is the one that can diverge: `_count_substitution` has
        no `target_guid` guard while `_action_matched_existing` does. It is
        `MatchBasisRecord.__post_init__` (NATURAL_KEY => non-empty
        `target_guid`) that keeps them in step, so this must hold for adds as
        well as overwrites."""
        report = _report(_plan(actions=[
            _add(GrammarCategory.PHONEMES, f"src-{i}",
                 _natural_key("PhPhoneme", f"src-{i}", f"tgt-{i}"))
            for i in range(23)
        ]))

        assert report.identity_substituted == 23
        assert report.matched_to_source_total == 23

    def test_a_mixed_plan_across_categories_and_verbs_does_not_raise(self):
        """Adds, overwrites, both bases, several categories, plus matches with
        no basis at all -- built in one plan, because the invariant is checked
        once over the whole report and a per-case test would not exercise it."""
        report = _report(_plan(
            actions=[
                _add(GrammarCategory.PHONEMES, "src-a1",
                     _natural_key("PhPhoneme", "src-a1", "tgt-a1")),
                _add(GrammarCategory.POS, "src-a2",
                     _identity("PartOfSpeech", "src-a2", "tgt-a2")),
                _add(GrammarCategory.AFFIXES, "src-a3"),
                _add(GrammarCategory.PHONEMES, "src-a4",
                     _none("PhPhoneme", "src-a4")),
            ],
            overwrites=[
                _overwrite(GrammarCategory.POS, "src-o1", "tgt-o1",
                           _natural_key("PartOfSpeech", "src-o1", "tgt-o1",
                                        key_value="Adverb"),
                           match_via="natural_key"),
                _overwrite(GrammarCategory.AFFIXES, "src-o2", "tgt-o2",
                           match_via="fingerprint"),
            ],
        ))

        assert report.identity_substituted == 2      # a1 + o1
        # a1, a2, o1, o2 -- a3 is a create and a4's matcher found nothing.
        assert report.matched_to_source_total == 4
        assert report.identity_substituted <= report.matched_to_source_total

    def test_the_two_counters_cannot_disagree_by_construction(self):
        """The structural reason the invariant is safe, asserted rather than
        assumed: a NATURAL_KEY record cannot exist without a `target_guid`, so
        the substitution counter can never count an object that the matched
        counter refuses."""
        with pytest.raises(ValueError, match="non-empty target_guid"):
            MatchBasisRecord(
                basis=MatchBasis.NATURAL_KEY,
                object_class="PhPhoneme",
                source_guid="src-1",
                key_expression="Name",
                key_value="p",
                target_guid="",
            )

    def test_every_substitution_counted_is_also_counted_as_a_match(self):
        """The invariant restated as the property that makes it hold, checked
        over the same plan shapes `_build_from_plan` walks. A regression here
        (a new producer, or a guard added to one counter and not the other)
        turns a valid run into a `ValueError` at report time."""
        for label, plan in (
            ("natural-key add", _plan(actions=[
                _add(GrammarCategory.PHONEMES, "src-1",
                     _natural_key("PhPhoneme", "src-1", "tgt-1"))])),
            ("natural-key overwrite", _plan(overwrites=[
                _overwrite(GrammarCategory.PHONEMES, "src-1", "tgt-1",
                           _natural_key("PhPhoneme", "src-1", "tgt-1"),
                           match_via="natural_key")])),
        ):
            report = _report(plan)
            assert report.identity_substituted == 1, label
            assert report.matched_to_source_total >= 1, label


# ---------------------------------------------------------------------------
# 5. The second, weaker record of the same fact: `match_via`
# ---------------------------------------------------------------------------

class TestMatchViaFallback:
    """`PlannedOverwrite` carries natural-key-ness TWICE: as the structured
    `match_basis` record and as the plain `match_via` string, whose legal
    values models.py documents as
    "guid"|"identity_remap"|"fingerprint"|"natural_key" -- the last added by
    feature 038 itself, for the Phase 2 policy code that switches on the
    string. A producer that sets only the string must not have its
    substitution counted as an ordinary match: that would make the report
    assert a GUID-strength claim the matcher never made, which is the exact
    defect FR-006 exists to remove.
    """

    def test_match_via_natural_key_alone_is_still_reported_as_a_substitution(self):
        report = _report(_plan(overwrites=[
            _overwrite(GrammarCategory.POS, "src-1", "tgt-1",
                       match_via="natural_key"),
        ]))

        assert report.identity_substituted == 1
        assert report.matched_to_source_total == 1, (
            "an overwrite is unconditionally a match, which is what keeps the "
            "identity_substituted <= matched_to_source_total invariant safe "
            "when the fallback fires"
        )

    def test_the_structured_record_wins_and_nothing_is_double_counted(self):
        """With both present the `match_basis` record is authoritative and the
        string is not consulted, so one object can never be counted twice."""
        report = _report(_plan(overwrites=[
            _overwrite(GrammarCategory.POS, "src-1", "tgt-1",
                       _natural_key("PartOfSpeech", "src-1", "tgt-1",
                                    key_value="Adverb"),
                       match_via="natural_key"),
        ]))

        assert report.identity_substituted == 1

    def test_an_identity_record_beside_a_natural_key_string_is_not_counted(self):
        """The structured record is the stronger evidence and is trusted on
        its own; the string is a fallback, never an override. Counting both
        would let one contradictory item inflate the substitution tally."""
        report = _report(_plan(overwrites=[
            _overwrite(GrammarCategory.POS, "src-1", "tgt-1",
                       _identity("PartOfSpeech", "src-1", "tgt-1"),
                       match_via="natural_key"),
        ]))

        assert report.identity_substituted == 0

    def test_the_other_match_via_values_are_not_substitutions(self):
        report = _report(_plan(overwrites=[
            _overwrite(GrammarCategory.POS, "src-1", "tgt-1", match_via="guid"),
            _overwrite(GrammarCategory.POS, "src-2", "tgt-2",
                       match_via="identity_remap"),
            _overwrite(GrammarCategory.POS, "src-3", "tgt-3",
                       match_via="fingerprint"),
        ]))

        assert report.identity_substituted == 0
        assert report.matched_to_source_total == 3
