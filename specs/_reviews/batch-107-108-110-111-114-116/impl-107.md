# impl-107: GitHub issue #107, a 0-action re-run still creates affix slots, templates and FsFeatStruc objects

- Branch: `fix-107-slot-template-idempotency` (worktree `D:/Github/_Projects/_LEX/GramTrans-fix-107`, based on origin/main c088d16)
- Commits: `05e7cf6` (the fix, `closes #107`), followed by a commit that only edits the #87 test's docstring
- PR: https://github.com/MattGyverLee/GramTrans/pull/125 (not merged)
- Verdict: [OK] Fixed and proven live. Run 2 now creates nothing and changes nothing, both in the issue's repro and in its wider scenario. The mutation check fails as expected.

## 0. Root cause: the issue's hypothesis was wrong

The issue described the objects as duplicates under fresh identities, caused by the comparison reporting slots and templates as "added" on every run. The live data refutes that.

- Every object run 2 added carries its **source GUID**. After run 2 the target holds 33 of 33 source slots, 18 of 18 templates and 335 FsFeatStruc, all under source GUIDs. No GUID fallback was logged.
- Run 3 is clean (`NEW={} CHANGED={}`). The transfer **converged one run late**; it did not re-create objects forever.

The real defect is in the create path:
- `categories.gram_categories_execute_action` creates a POS and copies its scalars only. It never fills the seven owned collections.
- Only the UPDATE enrichment pass (`transfer._enrich_owned_collections`) fills them, and it runs only for a POS the target **already** held. In run 1 that meant Noun and Verb.
- The 8 POS that run 1 created were therefore left as shells: Adjective, Diminutive, Modifier, Determiner, Numeral, Reduplicated determiner, Auxiliary and Copula.
- On run 2 those POS were present by GUID, so `_compare_pos_owned_collections` correctly found their collections empty, and enrichment filled them.

## 1. Live source

- Source: `Mbugwe LizzieHC practice`, opened read-only. Its `.fwdata` SHA-256 was `3fb29a294434f85301e2f2f75d704489cdf4495325252cfb0f8797137cd5436d` before and after every run (6 repro drivers plus 3 pytest runs).
- Target: `GT-Sandbox-107`, the only project written. Before every scenario it was restored with `restore_target("GT-Sandbox-107", backup_path=backups/Target 2026-07-06 0218.fwbackup)`. Each driver asserts the target name before writing.
- `gramtrans` resolved to `GramTrans-fix-107\src` (or to `GramTrans\src` for the main-code baselines). flexicon resolved to `D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py`. Both are printed in every log.
- No other agent's project was opened. The #31 live test, which opens Ngoreme, was NOT run.

## 2. Live write runs (`FLEXLIBS_REQUIRE_LIVE=1`)

The driver restores the target, runs `harness.full_run.run_full_transfer` N times, snapshots `.fwdata` after each run, and diffs the snapshots object by object.

| Scenario | Code | Run 1 actions | Run 2 actions | run1->run2 NEW | run1->run2 CHANGED | run2->run3 |
|---|---|---|---|---|---|---|
| POS+GRAM_CATEGORIES+TEXTS(4), closure | main | 17 | 0 | FsFeatStruc 47, MoInflAffixSlot 10, MoInflAffixTemplate 7 | PartOfSpeech 8 | clean |
| same | fix | 17 | 0 | **none** | **none** | clean |
| wide (+AFFIXES, ENTRY, SENSE, MSA, ALLOMORPH, INFLECTION_FEATURES) | main | 204 | 0 | same 64 | **MoInflAffMsa 98**, PartOfSpeech 8 | clean |
| wide | fix | 204 | 0 | **none** | **none** | clean |

Object counts after each run, with and without the fix:

| Object | Source | After run 1 (main) | After run 1 (fix) | After run 2 (both) |
|---|---|---|---|---|
| MoInflAffixSlot | 33 | 23 | 33 | 33 |
| MoInflAffixTemplate | 18 | 11 | 18 | 18 |
| FsFeatStruc, narrow scenario (all under source GUIDs) | - | 288 | 335 | 335 |

- In the wide scenario the 98 rewritten `MoInflAffMsa.SlotsRC` were the same late convergence. On main, an MSA could not link to a slot that did not exist yet in run 1, so it linked on run 2. With the fix the slots exist before the 17.1 sub-pass, so the MSAs link in run 1.
- The updated `test_issue87_residue_idempotent_live.py` was run with `GT_ISSUE87_TARGET=GT-Sandbox-107` and **1 passed** (37s). Its log shows run1 actions=17, run2 actions=0, and the target was restored around the test.

**Mutation check (not committed):**
- I wrapped the leaf-loop call to `_fill_created_pos_collections` in `if False:`.
- The #87 live test FAILED: `run 2 created objects (#107): [('FsFeatStruc', '020f1efc'), ..., ('MoInflAffixSlot', '23d810dd'), ('MoInflAffixTemplate', '24bd189a'), ...]`.
- The unit tests `test_execute_fills_each_created_pos_with_the_planned_guids` and `test_a_failing_fill_does_not_fail_the_pos_create` FAILED.
- I restored the file with `git checkout`, which put the committed version back. The worktree is clean.

**Second finding: the "intermittent" FsFeatStruc**
- In this scenario they are **deterministic**. They appeared in all 3 baseline repros: narrow, narrow over 3 runs, and wide.
- The 47 are the `ReferenceFormsOC` of three POS that run 1 created: Numeral 44, Adjective 2, Diminutive 1. That is the same root cause as the slots and templates.
- They do not occur in any run after the fix.
- My best explanation for the earlier "not seen" verification run is that its target already held those POS, which would let run 1's enrichment fill them. I could not reproduce that run, so this is an inference.

Logs (scratchpad, not committed), under `C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\9f84e243-5237-484f-a4c9-1d675dd0f416\scratchpad\r107\`:
- `baseline.out`, `baseline3.out`, `fixed.out`, `wide_base.out`, `wide_fixed.out`: repro driver output.
- `t87_fixed.out`, `t87_final.out`: passing #87 test runs.
- `t87_mutant.out`: the mutation run.
- `repro.py`: the driver itself.

## 3. Changes

- `src/gramtrans/Lib/transfer.py`:
  - Adds `_fill_created_pos_collections`. It runs the same `_enrich_one_collection` writer over all seven collections for a POS that was just created: same GUID-then-roster match, same GUID-preserving create, and same deferral of children that have their own `PlannedAction`.
  - `execute()`'s leaf loop calls it after each successful `GRAM_CATEGORIES`/`POS` create, inside its own try. A fill failure produces a Warning and a log entry; it is never counted as a leaf failure.
  - It produces no `EnrichmentRecord`, because FR-022 refuses `was_created=True`. Drops still go into `_dropped`.
- `tests/integration/test_issue87_residue_idempotent_live.py`:
  - `ISSUE_REF` now points to `#107`.
  - Removed `EXCLUDED_NEW_CLASSES`, `_normalise`/`_rebuild` and the owner-link regexes. Run 2 must now match object for object, with nothing new, deleted or changed.
  - The target can be overridden with `GT_ISSUE87_TARGET` (default `Target`).
  - The log now also prints flexicon and the target name.
  - The file never had an `EXCLUDED_CHANGED_CLASSES`; only the issue text mentioned it.
- `tests/integration/test_issue31_msa_slot_live.py`: new function `test_move2_creates_no_slot_or_template_objects`, appended at the end. It asserts that Move 2 neither plans nor performs any addition to `AffixSlotsOC`, `AffixTemplatesOS` or `ReferenceFormsOC`. Existing functions are untouched.
  - **Its live run is PENDING**: Ngoreme belongs to the #111 agent. I only checked that the file parses.
  - The module docstring's "Deliberately NOT asserted" note is now stale. I left it alone to avoid a conflict with #111's edits; the new test's docstring says it supersedes that note.
- `tests/unit/test_issue107_created_pos_collections.py`: 13 hermetic tests.
  - Every collection is filled and keeps its source GUIDs.
  - The run-2 planner (`_compare_pos_owned_collections`) then finds 0 to add; a negative control without the fill finds 6.
  - Deferral is preserved, drops are reported, and no-op cases do nothing.
  - Wiring through `execute()`, including that a fill failure does not fail the POS create.

**Unit suite:**
- Before (main c088d16): 5295 passed, 80 skipped, 14 xfailed.
- After: 5307 passed, 80 skipped, 14 xfailed.
- The collected test ids differ by +13 new tests, and −1 environment-only id (`test_034_fwglobals_only[src/gramtrans/_buildinfo.py]`), which exists only because the main checkout has an untracked `_buildinfo.py`. No regressions.

**Pattern audit** (sweep-pattern via Explore; details are in the PR body):
- HIGH sibling, `categories.py:17161` `_phon_rule_apply_body`: a rule's `InputPOSesRC` is wired at PHONOLOGICAL_RULES time, before GRAM_CATEGORIES creates the POS. The reference drops in run 1, and run 2's `structural_rebuild` wires it, one run late.
- MED sibling, `transfer.py:3217`: an `InflectableFeatsRC` child is deferred to the feature's `PlannedAction`, but that action never links the feature into the POS unless INFLECTION_FEATURES is selected.
- LOW siblings:
  - `resolve_or_create_target_pos` creates a POS shell outside the leaf loop.
  - `semantic_domains_execute_action` copies no Name, Abbreviation or Description, and no UPDATE executor is wired, so it never converges.
  - Two cases on error paths only.
- None of these is fixed here; they need selections outside #107's repro. Inflection classes, slots, templates, features, natural classes, environments, strata and phonemes were checked and cleared.

## 4. Residual risks and follow-ups

1. **Preview visibility gap (Principle III).** The owned children of a created POS are written without appearing in the Preview plan or in `RunReport.enrichments`; only the report sink and log show them. The planner's created-POS `PlannedAction` should project them. This is a documented follow-up and is not fixed here.
2. **#31 live assertion not run.** It needs Ngoreme, which another agent owns.
3. **Sweep siblings.** The HIGH `InputPOSesRC` ordering bug and the MED `InflectableFeatsRC` deferral each deserve their own issue.
4. **Sub-POS created by enrichment.** A sub-POS created via `SubPossibilitiesOS` that has no `PlannedAction` of its own (possible with pick-driven `POS` selections) gets scalars only, not its own collections. This scenario does not hit it, because GRAM_CATEGORIES plans every POS.
5. **Template slot references.** `_create_collection_child` copies scalars only, so a template created by enrichment gets no `PrefixSlotsRS`/`SuffixSlotsRS`. This does not affect idempotency, since both runs agree, but it may be a fidelity gap. Not investigated. The same applies to `ReferenceFormsOC`: an FsFeatStruc that the fill creates is a shell with no `FeatureSpecsOC`. That limitation already existed in enrichment, and idempotency still holds because both runs agree.
