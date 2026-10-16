# Cycle 3 follow-up issue drafts (NOT filed)

## (1) Default category set silently yields no lexicon transfer (ENTRY/SENSE/MSA/ALLOMORPH not dispatched)

Selecting ENTRY, SENSE, MSA or ALLOMORPH (the default set) plans nothing. build_run_plan now reports a skip, "not dispatched; select AFFIXES and/or STEMS", but a FLEx user choosing "Entries" expects entries to transfer. Cause: the legacy verb-vertical path is disabled (supersede decision 2026-07-06, preview.py ~1129); entries now travel only inside AFFIXES and STEMS.

Proposed fix: in build_run_plan, expand ENTRY/SENSE/MSA/ALLOMORPH to AFFIXES+STEMS before dispatch, fixing every caller.

Risks: double transfer / GUID collisions if both paths ever run; STEMS may pull far more data than intended (2,015 entries in the Ngoreme source); needs a closure and POS-picks check; AFFIXES vs STEMS per category is ambiguous (MSA and ALLOMORPH belong to both). Verify live on restored Target with FLEXLIBS_REQUIRE_LIVE=1.

Link: split out of #49 (close #49 only after this is filed and cross-linked). Verified live in batch 67-72: entry/sense/msa/allomorph added 0, each with a visible "not dispatched" skip.

## (2) Run report: add a "blocked" outcome label (#68 classification follow-up)

PR #83 makes "added" equal objects that landed (GUID-reconciled; live counts matched for templates 13, slots 19, POS 21, environments 9). What remains is classification: several outcomes a user would call failed/blocked are reported as plain "skipped".

Needs a distinct "blocked" label (or at least a failure-style summary line) for:
- affix templates whose owner POS is unresolved in the destination (user selected them, none arrived);
- affix templates whose source object was not found (a data error, not a benign skip);
- stem names (and similar) skipped with DEPENDENCY_UNRESOLVED;
- a prominent report-level warning when lexicon categories were "not dispatched" (see draft 1), so a green-looking run is not read as "entries transferred".

Keep as is: UnverifiedWrite and LookupUnverified are failures; offline fakes with no GUID lookup are skipped as unverifiable. Touches report.py rendering and the no-silent-skips field table test. No LCM writes.

## (3) Re-baseline the object census under feature 038 (and restore the t126 run-report fixtures)

30 live-corpus tests fail on main and on the batch-67-72 branch, none touching that branch's code. Comparison run at base 44ed51d vs branch (specs/_reviews/batch-67-72/cycle3-lex-verification-census-base.md): base 31 failed, branch 29 failed with identical IDs (branch fixes 2 `snapshots_are_committed_repo_data` cases). 0 introduced.

The 29 test_object_census.py failures fall into three groups:
- **24 are environmental, not drift:** CensusError "no run report" for `_run_reports/038-t126-{ejagham,ngoreme,mbugwe}-report.json`. These run-report fixtures are untracked, so they are missing from any fresh checkout/worktree (T081 roster/reason/GateStops rows x3 projects).
- **3 are real drift:** `assert 'drifted' == 'match'` in T078 reproducible_against_live_projects[mbugwe], [ngoreme] and T107 artifacts_now_reproduce[census-038-t107-mbugwe-phase6.json]. The census baselines predate feature 038 (natural-key matching, FeaturesOA, closure edges, process rules).
- **2 others:** T101 every_committed_null_row_is_advisory (corpus-list mismatch) and T108 t107s_own_censuses_still_hash_to_their_projects (follows from T107).
Plus test_038_closure_edge_audit::test_every_link_in_the_chain_declares_whether_it_is_reproducible (reads census-038-mbugwe-phase6.json).

Proposed: (a) decide whether the t126 run reports become committed fixtures or the T081 tests regenerate/skip-with-reason when absent; (b) regenerate the drifted baselines from read-only corpora under 038, review each diff to confirm every change is explained by a 038 behaviour (not a regression), and commit the new census artifacts together; (c) fix the T101 corpus list. Also note the 75 REQUIRE_LIVE skips (E2E opt-ins, Ejagham Full GT-Test drift for affix_pos_picker) as separate baseline work.

## (4) Residue tagger re-stamps already-present objects on re-run (idempotency gap)

Found live in batch 67-72 (specs/_reviews/batch-67-72/cycle3-lex-verification.md item b). Transferring the same 3 untitled Texts from Mbugwe LizzieHC practice to a restored Target twice: run 2 adds 0 objects (object set identical, 10598), but each of the 3 Texts created by run 1 gains a second residue line in its Description, `[GT-Tag]: GT|GT-<run2 id>|Mbugwe Lizzie|<ts>`, appended after run 1's line. Nothing else changes.

Not corruption, but a re-run tags objects it did not create or update, so tags accumulate and the residue no longer means "this run wrote this object". Proposed: stamp the residue tag only on objects the current run created or updated (use the per-run added/updated GUID set), and audit whether other categories share the same tagger path. Verify live on restored Target with FLEXLIBS_REQUIRE_LIVE=1: run twice, assert the Target is byte-identical (or object-and-field identical) after run 2. Refs #45.
