# Cycle 3 QC re-check (batch 67-72)

> Saved by the main session on lex-qc's behalf (no Write/shell tool; files read at cited
> lines, no git diff / pytest run; 5067-pass figure is the programmer's claim).

**Score 91/100. APPROVE for code and unit tests, conditional on the live-LCM gate (Gate 2).**

## Prior findings

| Finding | Status | Evidence |
|---|---|---|
| P1 stems missing source (categories.py:12803-12843) | RESOLVED | returns ActionOutcome.skipped, tail passes still run; tests test_issue68_action_outcomes.py:214, :226 (nit: _run_tail_once not asserted called) |
| P1 reconcile ignores identity_remap (transfer.py:702-710, 1498-1504) | RESOLVED | expected = identity_remap.get(src, src) after dispatch; resolved destination still wins; tests test_issue49_reconciliation.py:149, :167, :176, :188 |
| P1 lookup exception swallowed (transfer.py:1507-1520, 782-791) | RESOLVED | WARNING log; LeafExecutionFailure "LookupUnverified", removed from added; tests :202, :227 |
| P2 recorded=True (1444, 2495, 3145, 12427, 12651) | RESOLVED | all use `_exec_skips is not None`; tests test_issue68_action_outcomes.py:281, :289, :297 |
| P2 preview plan_action exception (preview.py:1372-1383) | RESOLVED | Skip with UNSUPPORTED_LCM_TYPE + exception text; test test_issue49_reconciliation.py:237 |
| P2 already-present overcount (categories.py:1353) | OPEN by design | documented known limitation |
| P2 conftest guard / CI skip-count floor / regression.yml scoping | not re-reviewed | scoping recorded in PR body; skip-count floor not addressed |

## Pattern audit

No execute_action handler returns bare None as a decline except documented exceptions
(gram_categories already-present :1353, custom_fields stub :2337). Other `return None`
hits are in helpers (:4487-4490, :4912-4919, :14781-14789). Spot-checked clean: phonemes,
natural_classes, ph_environment, strata, phonological_rules (13517-end); variant_types,
complex_form_types, semantic_domains (3694-4129). All eight recorded= args follow the
exec_skips pattern.

## New issues

- **P1 (process):** no live-LCM evidence artifact for the cycle 3 write-path changes (stems, execute, reconcile, texts.py). Gate 2 is a HARD BLOCK until live evidence exists (run_mode live, FLEXLIBS_REQUIRE_LIVE=1, pre/post read-back). test_issue45_untitled_texts_live.py updated but not run. (Cycle 3 lex-verification is running in parallel to cover this.)
- **P2:** reconcile resolved-destination path and stems skip rely on stub targets; real `_lookup_target_guid` repo path (transfer.py:1470-1474) untested until the live run.
- **P2 (nit):** test_stems_* don't assert tail passes still run.
- **P2 (not checked):** #45-a naming change and apply_texts per_category fold-in not re-read; covered by test_texts_untitled_collision.py:94, :115, :134. Name uniqueness argued from flexicon source, not FLExToolsMCP.
