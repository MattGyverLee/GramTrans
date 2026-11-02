# fix-132 post-pass safety nets — lex-lead cycle 1

**Issue**: #132 (P2 bug, never-silent audit)  
**Scope**: batch 1 — the seven `transfer.py` post-loop `_ensure_*` safety nets that only logged swallowed exceptions.

## Diagnosis

Leaf dispatch already records swallowed `execute_action` raises as
`LeafExecutionFailure` (feature 037). Post-loop repair passes (`_ensure_171_subpass`,
`_ensure_matched_nc_segments`, `_ensure_owner_feat_strucs`, `_ensure_infl_feature_links`,
`_ensure_entryref_passes`, `_ensure_complex_feature_type_ra`, `_ensure_struct_type_features_rs`)
follow the same swallow-and-continue policy but had **no report surface** — only
`_log.exception`. A Move could finish with `leaf_failed == 0` while entire tail
passes (InflectableFeatsRC, 17.1 wiring, LexEntryRef merge, etc.) never ran.

## Resolution

- Added `_record_post_pass_failure` with stable synthetic `source_guid`
  (`post-pass:<name>`) to satisfy `LeafExecutionFailure` validation.
- Each `_ensure_*` `except` path (plus missing-RunPlan on the infl link pass and
  reconciliation failure) appends one record when `post_pass_failures` is wired.
- `execute()` wraps the seven calls in `_run_post_pass_ensure` so `leaf_failed`
  stays aligned with `len(leaf_execution_failures)`.

## Out of scope (remaining #132 sites)

Issue body lists guarded writes inside `categories.py`, RA/RS `except: pass`
blocks, and the Add-raises-but-readback-present gap — separate batches per
issue acceptance.

## Verdict

**GO** for batch 1 — unit tests pin recording behaviour; live gates not required
for report-only wiring (no write-path semantic change when passes succeed).
