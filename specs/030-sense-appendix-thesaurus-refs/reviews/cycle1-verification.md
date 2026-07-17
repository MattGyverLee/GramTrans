# Verification Report -- Feature 030 (Sense Appendix + Thesaurus Refs)

**Date:** 2026-07-16
**Verified worktree:** D:\Github\_Projects\_LEX\GramTrans-030-sense-appendix-thesaurus-refs
**Branch / commit:** 030-sense-appendix-thesaurus-refs @ d6132ff
**Status:** PASS

## Executive Summary

- Item 1 (unit tests): PASS -- 17/17 tests pass, file is 390 lines.
- Item 2 (fidelity census): PASS -- both fields confirmed COPIED, guards intact.
- Item 3 (regression claim): PASS -- worktree and clean-main FAILED sets are
  byte-identical (22 failures, diff empty). Zero 030-attributable failures.

**Recommendation:** APPROVE

## 1. Unit Test Verification

Command: python -m pytest -q tests/unit/test_cycle16c_sense_scope_gaps.py
Result: 17 passed in 0.32s. File length confirmed at 390 lines (matches claim).

**Test inventory (17 total), by path coverage:**

| Test | Path | Section |
|---|---|---|
| test_pictures_emit_one_dropped_record_each | n/a (unconditional drop) | PicturesOS |
| test_report_dropped_sense_scope_gaps_no_longer_touches_appendix_or_thesaurus | n/a | regression guard |
| test_A_link_present_by_guid_no_drop | MOVE (new_sense populated) | A |
| test_A_absent_drops_and_never_creates | MOVE | A |
| test_A_partial_links_present_drops_absent | MOVE | A |
| test_A_empty_source_no_write_no_drop | MOVE | A |
| test_A_shared_appendix_linked_once_per_sense_no_dup | MOVE | A |
| test_A_preview_new_sense_none_records_same_drops_no_write | PREVIEW (new_sense=None) | A |
| test_B_discover_owning_list_walks_owner_to_list | n/a (resolver primitive) | B |
| test_B_discover_returns_none_when_no_owning_list | n/a (resolver primitive) | B |
| test_B_mirror_by_name_hit_and_miss | n/a (resolver primitive) | B |
| test_B_nolist_drops_never_raises | MOVE | B |
| test_B_nomirror_drops_never_raises | MOVE | B |
| test_B_link_present_in_mirrored_list | MOVE | B |
| test_B_empty_source_no_write_no_drop | PREVIEW (new_sense=None) | B |
| test_B_shared_item_across_senses_resolves_to_same_target_no_dup | MOVE | B |
| test_move_and_preview_drop_sets_identical_for_sense_scope_gaps | MOVE and PREVIEW (both run, compared) | A + B + PicturesOS |

**MOVE-path coverage:** Section A has 5 MOVE-mode tests + 1 PREVIEW-mode test;
Section B has 4 MOVE-mode tests + 1 PREVIEW-mode test, plus 3 resolver-primitive
tests independent of Move/Preview.

**Explicit "Move == Preview parity" assertion for Section B:** YES, but with a
caveat. test_move_and_preview_drop_sets_identical_for_sense_scope_gaps runs
the same fixture through both _resolve_sense_appendixes and
_resolve_sense_thesaurus_items twice -- once with a real _FakeTargetSense()
(Move) and once with new_sense=None (Preview) -- then asserts
move == preview on the sorted (field_name, item_guid, reason) tuples, and
separately asserts the field-name set includes "ThesaurusItemsRC". This is
a genuine, executable Move==Preview parity assertion covering Section B.

**Caveat:** the parity test only exercises the drop (unresolvable) branch for
Section B (target owns no matching list, so both modes drop). There is no
test that runs a LINK-success case (test_B_link_present_in_mirrored_list
equivalent) through both Move and Preview and asserts parity on that branch.
Section A has a comparable gap (its parity coverage is also drop-only). This
is a minor coverage gap relative to full FR-008 branch coverage, not a defect
-- the LINK-branch code paths for both A and B are each independently unit-
tested in MOVE mode only (test_A_link_present_by_guid_no_drop,
test_B_link_present_in_mirrored_list), and the resolvers do not branch on
new_sense is None except at the final .Add() write (verified by
reading Lib/categories.py), so the parity risk on the untested branch is low
but not exercised by an explicit assertion.

## 2. Fidelity Census Verification

Command: python -m pytest -q tests/verification/fidelity_census.py
Result: 116 passed in 0.18s.

Confirmed via direct read of tests/verification/fidelity_census.py:

- ("LexSense", "AppendixesRC") -> Classification(Bucket.COPIED, ...)
  (line ~452), site = categories._resolve_sense_appendixes, note documents
  link-by-GUID semantics and "Was cycle-17 DROP_REPORTED (unconditional)."
- ("LexSense", "ThesaurusItemsRC") -> Classification(Bucket.COPIED, ...)
  (line ~546), site = categories._resolve_sense_thesaurus_items ->
  references.resolve_thesaurus_item, note documents the dynamic-owner
  mirror-by-owner-class+OwningFlid resolution and drop-on-failure.
- OUT_OF_SCOPE_EXCLUDED_FIELDS (line ~326) is confirmed to be exactly:
  frozenset({("LexEntry", "MainEntriesOrSensesRS")}) -- single member, as
  claimed. Comment block explicitly states the 4 former LexSense members
  (AppendixesRC, ThesaurusItemsRC, ExtendedNoteOS, PicturesOS) have all been
  reclassified to real terminal buckets.
- Never-silent classifier guard: targeted run of
  python -m pytest -q tests/verification/fidelity_census.py -k "never_silent or guard"
  -> 2 passed (guard-fires-LookupError tests for both the 024-era and
  026-era ledgers both pass).

## 3. Regression Verification

Ran full unit suite on both trees with python -m pytest -q from repo root.

**Worktree** (D:\Github\_Projects\_LEX\GramTrans-030-sense-appendix-thesaurus-refs):
22 failed, 1859 passed, 72 skipped, 14 xfailed, 14 xpassed in 8.05s

**Clean main** (D:\Github\_Projects\_LEX\GramTrans @ cf54d2b):
22 failed, 1847 passed, 72 skipped, 14 xfailed, 14 xpassed in 7.92s

**Failure-set diff:** captured both FAILED-line lists (sorted) from each run
and ran diff on them -- output was empty (exit 0). The failing test IDs are
byte-identical between worktree and main:

```
tests/unit/test_adjacent_data.py::test_human_gloss_reproduced_parser_gloss_excluded
tests/unit/test_adjacent_data.py::test_zero_human_glosses_reproduces_no_gloss
tests/unit/test_adjacent_data.py::test_spelling_status_reproduced_onto_target_wordform
tests/unit/test_adjacent_data.py::test_absent_spelling_status_not_written
tests/unit/test_adjacent_data.py::test_category_absent_left_unset_and_reported_never_created
tests/unit/test_adjacent_data.py::test_category_present_resolved_and_set
tests/unit/test_analysis_idempotency.py::test_reapply_analyses_is_idempotent
tests/unit/test_analysis_idempotency.py::test_same_analysis_across_two_segments_created_once_within_run
tests/unit/test_analysis_idempotency.py::test_distinct_analysis_is_still_created_on_reapply
tests/unit/test_analysis_verdict.py::test_approve_and_deny_verdicts_reproduced
tests/unit/test_human_eval_gate.py::test_only_human_evaluated_analyses_kept
tests/unit/test_human_eval_gate.py::test_verdicts_read_from_evaluation
tests/unit/test_human_eval_gate.py::test_gloss_tokens_reproduce_owning_analysis_deduped
tests/unit/test_human_eval_gate.py::test_normalize_token_maps_gloss_and_skips_non_analysis
tests/unit/test_human_eval_gate.py::test_gloss_gate_reads_owning_analysis_approval_live_shape
tests/unit/test_morph_bundle_wiring.py::test_approve_with_unresolved_ref_downgrades_to_needs_review
tests/unit/test_morph_bundle_wiring.py::test_deny_with_unresolved_ref_keeps_deny
tests/unit/test_morph_bundle_wiring.py::test_needs_review_downgrade_is_reported
tests/unit/test_morph_bundle_wiring.py::test_unresolved_ref_report_carries_locate_context
tests/unit/test_residue_tagging_026.py::test_residue_applied_to_every_added_object_kind
tests/unit/test_segment_alignment.py::test_gloss_token_alignment_keyed_by_owning_analysis_and_wires
tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos
```

Passed-count delta (1859 vs 1847 = +12) is consistent with the net new/rewritten
tests added by 030 (the rewritten test_cycle16c_sense_scope_gaps.py file plus
any small additions elsewhere), and is not evidence of any suite-count
mismatch or hidden skip.

**030-attributable failures found:** NONE.

## Final Assessment

**Overall Status:** PASS

**Blockers:** None.

**Minor observation (non-blocking):** the Move==Preview parity test for
Section B (and Section A) only exercises the drop/unresolvable branch, not the
LINK-success branch, in a combined Move-vs-Preview comparison. Code inspection
of Lib/categories.py resolvers shows no new_sense is None branching outside
the final .Add() write, so risk is low, but an explicit LINK-branch parity
test would close the gap for full FR-008 coverage.

**Recommendation:** APPROVE

---
**Verified By:** Verification Agent
**Date:** 2026-07-16
