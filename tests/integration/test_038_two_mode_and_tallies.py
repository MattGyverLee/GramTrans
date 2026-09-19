"""T024e + T024h -- the two selection modes, and the two bare tallies.

Both are asserted against a COMMITTED MEASUREMENT
(`_snapshots/two-mode-038-ngoreme.json`, produced by `debug/two_mode_delta.py`
with `GT_WS_FULL=1` against `Ngoreme FLEx` -> `Ngoreme Target` restored blank
from `backups/Ngoreme Target 2026-08-19 0831.fwbackup`). Asserting against a
recorded run rather than re-running is the same discipline
`TestMeasuredCensusSnapshots` already uses in `test_object_census.py`: a live
two-mode run restores and rewrites a project twice and takes ~7 minutes, which
is not something a unit-suite invocation may do by surprise.

T024e -- the two modes and the EXACT difference between them
------------------------------------------------------------
`force-all` is `build_full_selection(exclude=frozenset())`: every category
True and every pick-set empty. `collapse_phonology` records
`leaf_item_picks[cat]` only when a category is TRIMMED, so empty pick-sets
mean transfer-all and the preselection heuristics are bypassed entirely.
`filtered` is what the GUI produces: build the inventory, keep the rows whose
`preselected` flag is True, fold through `collapse_phonology`.

The claim under test is that `after_forceall - after_filtered` is EXACTLY the
non-preselected GUID set. Larger means the filtered run dropped something the
heuristic never claimed; smaller means force-all is not actually forcing. Both
directions are real defects and neither is visible in a count-based census.

Measured, it is very nearly exact, and the residue is the finding:

  * The orphan-natural-class heuristic claimed 11 rows. All 11 are present in
    force-all and absent from filtered -- the heuristic honours its claim in
    both directions, with nothing left over on the filtered side.
  * ONE further natural class differs and the heuristic never claimed it:
    `ad5738e0-2a61-4e42-8f95-8db24e7b9881`. It is not "unchecked" because it
    is not IN the inventory at all -- `_phon_is_empty` removes it (T024f), and
    an inventory-level removal is by construction invisible to a contrast
    computed from preselection flags. This is exactly why T024f is a separate
    task and not a detail of this one.
  * Three classes -- `FsClosedValue`, `FsFeatStruc`, `CmTranslation` -- appear
    on BOTH sides of the contrast. A GUID that is only-in-forceall while
    another is only-in-filtered is not a mode difference at all: those objects
    are being RE-MINTED with fresh GUIDs on every run. They are excluded from
    the mode comparison and asserted separately, because reading them as a
    mode difference would inflate a 12-object difference into a 917-object
    one.

T024h -- the two unexplained tallies
------------------------------------
(a) `dropped_items: 10,749` broken down by (owner_kind, reason);
(b) `identity_substituted: 0` explained by the PLAN's `match_basis`;
(c) the filtered-only `leaf_failed: 1` attributed to a named rule.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_SNAPSHOT = (Path(__file__).parent / "_snapshots"
             / "two-mode-038-ngoreme.json")

#: The natural class `_phon_is_empty` drops from the inventory (T024f). Named
#: once, asserted from three directions below.
BLANK_NC_GUID = "ad5738e0-2a61-4e42-8f95-8db24e7b9881"

#: Classes whose objects are re-minted with fresh GUIDs on every run, so they
#: differ between ANY two runs and cannot be read as a mode difference.
REMINTED_CLASSES = frozenset({"FsClosedValue", "FsFeatStruc", "CmTranslation"})


@pytest.fixture(scope="module")
def measured() -> dict:
    if not _SNAPSHOT.is_file():
        pytest.skip("two-mode measurement snapshot absent: " + str(_SNAPSHOT))
    return json.loads(_SNAPSHOT.read_text(encoding="utf-8"))


def _non_preselected(measured: dict) -> set:
    out: set = set()
    for guids in measured["modes"]["filtered"]["unchecked_guids"].values():
        out |= set(guids)
    return out


def _contrast(measured: dict, *, exclude=frozenset()) -> tuple:
    only_fa: set = set()
    only_fi: set = set()
    for cls, block in measured["mode_contrast"].items():
        if cls in exclude:
            continue
        only_fa |= set(block["only_in_forceall"])
        only_fi |= set(block["only_in_filtered"])
    return only_fa, only_fi


# ---------------------------------------------------------------------------
# T024e
# ---------------------------------------------------------------------------

class TestT024eTheTwoModesDifferExactlyWhereClaimed:

    def test_both_modes_actually_persisted(self, measured):
        """The contrast is meaningless if either run rolled back (T024g). Both
        must have grown the destination from the same blank restore."""
        for mode, entry in measured["modes"].items():
            assert entry["before_objects"] == 11300, mode
            assert entry["after_objects"] > entry["before_objects"], mode
            assert not entry.get("persist_error"), mode
        assert measured["modes"]["forceall"]["after_objects"] == 28354
        assert measured["modes"]["filtered"]["after_objects"] == 28322

    def test_force_all_bypasses_the_heuristics_and_filtered_does_not(
            self, measured):
        """Force-all leaves every pick-set empty, so nothing is unchecked;
        filtered runs the heuristics and leaves natural classes unchecked."""
        assert measured["modes"]["forceall"]["unchecked_preselection"] == {}
        assert measured["modes"]["filtered"]["unchecked_preselection"] == {
            "GrammarCategory.NATURAL_CLASSES": 11}

    def test_nothing_is_in_filtered_but_missing_from_force_all(self, measured):
        """The "force-all is not actually forcing" direction. Once the
        re-minted classes are excluded, filtered must be a strict SUBSET."""
        _only_fa, only_fi = _contrast(measured, exclude=REMINTED_CLASSES)
        assert only_fi == set(), (
            "objects present in the FILTERED run but absent from FORCE-ALL: "
            + repr(sorted(only_fi)))

    def test_every_non_preselected_row_is_exactly_a_force_all_only_object(
            self, measured):
        """The heuristic's claim, honoured in full: all 11 rows it left
        unchecked are present in force-all and absent from filtered."""
        only_fa, _ = _contrast(measured, exclude=REMINTED_CLASSES)
        unchecked = _non_preselected(measured)
        assert len(unchecked) == 11
        assert unchecked <= only_fa, (
            "rows the heuristic left UNCHECKED that transferred anyway (or "
            "never transferred in either mode): "
            + repr(sorted(unchecked - only_fa)))

    def test_the_only_residue_is_the_inventory_level_drop(self, measured):
        """THE T024e finding. The difference is 12 objects, not 11, and the
        twelfth is not a preselection decision at all -- it is the item
        `_phon_is_empty` removed from the inventory (T024f), which no contrast
        computed from `preselected` flags could ever have surfaced."""
        only_fa, _ = _contrast(measured, exclude=REMINTED_CLASSES)
        unchecked = _non_preselected(measured)
        residue = only_fa - unchecked
        assert residue == {BLANK_NC_GUID}, (
            "the unexplained mode difference changed; expected exactly the "
            "blank natural class, got " + repr(sorted(residue)))
        assert len(only_fa) == 12

    def test_the_reminted_classes_are_non_determinism_not_a_mode_difference(
            self, measured):
        """A class appearing on BOTH sides of the contrast cannot be a mode
        difference -- it means each run created its own GUIDs. Pinned so the
        917-vs-12 gap is never read as preselection dropping 900 objects."""
        for cls in REMINTED_CLASSES:
            block = measured["mode_contrast"][cls]
            assert block["only_in_forceall"] and block["only_in_filtered"], cls
        only_fa_all, _ = _contrast(measured)
        assert len(only_fa_all) == 917
        assert len(only_fa_all) - 12 == 905


# ---------------------------------------------------------------------------
# T024h
# ---------------------------------------------------------------------------

class TestT024hTheTwoTalliesAreBrokenDown:

    def test_dropped_items_is_dominated_by_out_of_scope_owners(self, measured):
        """(a) 10,749 against a 205,979-object source is not readable as a
        count. By (owner_kind, reason) it is: 6,951 alignment tokens on
        `Segment` and 2,198 shared-default divergences on `MoForm` are the
        text/lexicon layer GramTrans does not claim, and together with the
        1,531 unmapped-writing-system senses they are 99.4% of the total."""
        for mode in ("forceall", "filtered"):
            b = measured["modes"][mode]["breakdown"]
            assert b["dropped_total"] == 10749
            by_kind = b["dropped_by_owner_kind"]
            assert by_kind["Segment"] == 6951
            assert by_kind["MoForm"] == 2193
            assert by_kind["LexSense"] == 1531
            assert sum(by_kind.values()) == 10749
            top3 = by_kind["Segment"] + by_kind["MoForm"] + by_kind["LexSense"]
            assert top3 / 10749 > 0.99

    def test_the_in_scope_residue_is_small_and_named(self, measured):
        """The part that IS GramTrans's business, and the reason the pair
        matters: 9 senses lose their part-of-speech analysis because the source
        MSA has an empty `PartOfSpeechRA` (US1/FR-002), and 3 phonological-rule
        right-hand sides silently lose a conditioning feature restriction."""
        b = measured["modes"]["forceall"]["breakdown"]
        by_kind = b["dropped_by_owner_kind"]
        assert by_kind["LexEntry"] == 10
        assert by_kind["PhSegRuleRHS"] == 3
        reasons = b["dropped_by_reason"]
        pos = [r for r in reasons
               if "PartOfSpeechRA" in r and "empty on source" in r]
        assert len(pos) == 1 and reasons[pos[0]] == 9
        rule_feats = [r for r in reasons if "RuleFeatsRC item absent" in r]
        assert sum(reasons[r] for r in rule_feats) == 3

    def test_zero_substitutions_means_the_matcher_never_ran(self, measured):
        """(b) THE reading `identity_substituted: 0` could not settle on its
        own. Not one planned action carries a `match_basis` AT ALL, and
        `plan_natural_key_by_class` is empty -- so the natural-key path did not
        run and find nothing, it does not exist yet (Phase 4, T028-T037). FR-006
        is unreachable on this pair TODAY, which is a sequencing fact, not a
        defect. The opposite reading -- zero substitutions beside a non-zero
        NATURAL_KEY count -- would have meant the matcher ran and had nothing
        to substitute, and nothing in the tally distinguished the two."""
        for mode, planned in (("forceall", 2243), ("filtered", 2231)):
            b = measured["modes"][mode]["breakdown"]
            assert b["report_identity_substituted"] == 0
            assert b["plan_match_basis"] == {"<no match_basis>": planned}
            assert b["plan_natural_key_by_class"] == {}

    def test_every_match_is_unattributed_so_no_row_can_use_the_matched_basis(
            self, measured):
        """The same fact from the report's side, and the reason a census that
        IS given `--run-report` still cannot leave the gross basis: 1,806
        matches exist, none carries an object class, so `by_object_class` is
        empty and `complete` is False."""
        b = measured["modes"]["forceall"]["breakdown"]
        assert b["report_matched_by_class"] == {}
        assert b["report_matches_unattributed"] == {
            "GrammarCategory.COMPLEX_FORM_TYPES": 7,
            "GrammarCategory.SEMANTIC_DOMAINS": 1792,
            "GrammarCategory.VARIANT_TYPES": 7}
        assert sum(b["report_matches_unattributed"].values()) == 1806

    def test_the_filtered_only_leaf_failure_is_the_blank_natural_class(
            self, measured):
        """(c) THE closing of the loop. Filtered mode reported `leaf_failed: 1`
        where force-all reported 0, and the preselection heuristic did not
        account for it. It is not a preselection effect: the failing rule
        references `PhSimpleContextNC` -> the natural class `_phon_is_empty`
        drops from the inventory (T024f), which force-all transfers anyway
        because empty pick-sets mean transfer-all, and filtered does not
        because the dropped item is in no pick set. So the silent
        inventory-level drop is not merely unobservable -- it BREAKS a
        phonological-rule transfer, and the record T024f added is what names
        the object."""
        assert measured["modes"]["forceall"]["report"]["leaf_failed"] == 0
        failures = measured["modes"]["filtered"]["breakdown"]["leaf_failures"]
        assert len(failures) == 1
        failure = failures[0]
        assert failure["category"] == "GrammarCategory.PHONOLOGICAL_RULES"
        assert failure["exception_type"] == "RuntimeError"
        assert BLANK_NC_GUID in failure["message"]
        assert "absent from target" in failure["message"]

    def test_the_blank_nc_explains_both_findings_at_once(self, measured):
        """One object, two symptoms: the unexplained mode difference (T024e)
        and the unexplained leaf failure (T024h). Pinned together so a future
        change that fixes one and not the other is loud."""
        only_fa, _ = _contrast(measured, exclude=REMINTED_CLASSES)
        residue = only_fa - _non_preselected(measured)
        failure = measured["modes"]["filtered"]["breakdown"]["leaf_failures"][0]
        assert residue == {BLANK_NC_GUID}
        assert BLANK_NC_GUID in failure["message"]
