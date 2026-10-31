# impl-114: GitHub issue #114, LexEntryRef `HideMinorEntry` and `Summary` were never copied (silent, no census row)

- Branch: `fix-114-entryref-hide-summary` (worktree `D:/Github/_Projects/_LEX/GramTrans-fix-114`), based on origin/main `c088d16`
- Commits: `0c670a9` (the fix) and `bb06edb` (documents the record shape and updates the shared fake). Both messages end with `closes #114` and then the Co-Authored-By line.
- PR: https://github.com/MattGyverLee/GramTrans/pull/124 (not merged)
- Verdict: [OK] Both fields are now copied on create and merged on re-run, and both have census rows. The live proof passes, and it fails under a mutation that disables the write.

## 1. Live source

- **Korean-GIAL probe (read-only).** I scanned the `.fwdata` text without opening the project. It has 41 LexEntryRefs. Every one has `HideMinorEntry=0` and none has a `Summary`, so it cannot exercise either field as it stands.
- **Private copy.** The live test therefore builds `GT-Src-114` as a file-level copy of Korean-GIAL on every run:
  - it uses `shutil.copytree` and skips `*.lock` and `*.bak`;
  - it renames the `.fwdata` to `GT-Src-114.fwdata`, so the file name matches the folder.
- **The copy opens.** The seeding step opens it write-enabled through flexicon, and the fresh read-only re-read opens it again.
- **Seeded values.** The copy is seeded on the four #32 complex-form refs:
  - `38751f5b`: HideMinorEntry=1, no Summary.
  - `ff749d17`: Summary in `en` and in `ko-fonipa`. The restored Target lacks `ko-fonipa`, so this ref exercises WS mapping.
  - `1c7a4f20`: HideMinorEntry=1 and an `en` Summary.
  - `5faa892d`: left at defaults (0 / empty).
- **Korean-GIAL unchanged.** It was never opened. Its `.fwdata` SHA-256 was `9ea5a4a49711c0fdb893941f21d6ecd4b2a79f3fb847f61d054e77bde594775c` before the work, after each live run, and at the end.
- **No locks left.** No `.lock` files remain in Korean-GIAL, GT-Src-114 or GT-Sandbox-114.

## 2. Live evidence

- **Test:** `tests/integration/test_issue114_entryref_value_fields_live.py`, run with `FLEXLIBS_REQUIRE_LIVE=1` and `PYTHONPATH` set to the worktree `src`.
- **Which code ran:** the log prints `gramtrans.__file__ = D:\Github\_Projects\_LEX\GramTrans-fix-114\src\gramtrans\__init__.py` and `flexicon.__file__ = D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py`.
- **Writes:** the only projects written were `GT-Src-114` (while seeding) and `GT-Sandbox-114`. The sandbox was restored from `Target 2026-07-06 0218.fwbackup` before and after each test. The target name is asserted before any write, and `_open(write=True)` refuses any other name.
- **Result:** 2 passed in 28.4s.

**Test 1: create, then a pure re-run.**
- Move 1 planned 18 actions. Afterwards all 4 refs match the seeded source values, both in the `.fwdata` XML and in a fresh read-only LCM open with an `ILexEntryRef` cast. That includes the `ko-fonipa` Summary alternative.
- 0 `HideMinorEntry`/`Summary` drops.
- Move 2 planned **0 actions**, and the XML of the 4 refs is byte-identical.

**Test 2: the merge arm (re-run against an existing target ref).**
- **Why a spare entry is needed.** A pure re-run never reaches C1's INV-1 arm, because the STEMS tail only runs when the plan contains a STEMS action. So each re-run adds a spare stem entry with no refs (`00e82a75`, then `02d00679`). The test also asserts that the spare was created, as proof that the tail ran.
- **Re-run A, values already equal.** 1 action. The XML of the 4 refs is byte-identical. "Re-run writes nothing" therefore holds even when the merge arm executes.
- **Making the target diverge.** I wrote these changes into GT-Sandbox-114:
  - `38751f5b`: hide set from 1 to 0.
  - `ff749d17`: `en` Summary changed to "TARGET EDIT".
  - `1c7a4f20`: `en` Summary blanked, and a target-only `ko-fonipa` alternative added.
  - `5faa892d`: target-only hide=1 plus a target-only `en` Summary.
- **Re-run B results:**
  - The hide on `38751f5b` is back to 1.
  - The `en` Summary on `ff749d17` is restored to the source text.
  - The blanked `en` Summary on `1c7a4f20` is refilled, and its target-only `ko-fonipa` alternative is kept.
  - On `5faa892d`, the target-only Summary is kept, because an empty source never blanks. The hide goes from 1 to 0, because an int 0 counts as data under `conflict._is_empty` (see section 6).
  - 0 drops.

**Mutation check (not committed).**
- I inserted `return []` at the top of `_merge_entryref_value_fields`.
- **Both live tests FAILED.** After Move 1, all 4 target refs read 0 / {}.
- I reverted the change; `grep MUTATION` finds 0 occurrences.
- The new unit module also fails against the pre-fix `categories.py`: it cannot import the new helper.

Logs (scratchpad, not committed):
- `C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\9f84e243-5237-484f-a4c9-1d675dd0f416\scratchpad\live114_1.log` (pass)
- `C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\9f84e243-5237-484f-a4c9-1d675dd0f416\scratchpad\live114_mut.log` (mutation, 2 failed)

## 3. Changes

### `src/gramtrans/Lib/categories.py` (LexEntryRef region only)

- **`_stash_entry_bindings`:** the per-ref record gains `hide_minor_entry` (an int, or None when the attribute is absent) and `summary` (`{source_ws_id: text}`, non-empty alternatives only). The ref is cast with `_cast_lcm(ref, "ILexEntryRef")` first. Source writing systems are enumerated once per entry.
- **New `_ws_id_by_handle(project)`.**
- **New `_multistring_alts_by_ws_id(ms, ws_id_by_handle)`.**
- **New `_merge_entryref_value_fields(rec, target_ref, target, ws_map, dropped)`:**
  - It is the single write path for both fields, and the decision is `conflict._merge_delta`.
  - Summary is written at the `ws_map`-translated target handle.
  - Every write is read back. An unmapped WS, a raising write, or a write missing on read-back becomes a `DroppedItemRecord(owner_kind="LexEntryRef", field_name="HideMinorEntry"|"Summary")`.
  - It returns the list of fields it wrote.
- **`_run_entryref_create_pass`:**
  - The `existing_guids` set becomes an `existing_refs` dict of cast refs.
  - The INV-1 arm now merges the value fields and then `continue`s. It still creates nothing.
  - The CREATE arm calls the same helper right after `RefType` is set.

### `tests/verification/fidelity_census.py`

- New value kind `"INT"`. `FieldSpec.prop` now leaves both `"MU"` and `"INT"` unsuffixed (`_VALUE_KINDS`).
- `EXPECTED_MODEL_FIELDS["LexEntryRef"]` gains `HideMinorEntry` (INT) and `Summary` (MU). Both have COPIED classifications that name the helper.
- The count test changes from 5 to 7 for LexEntryRef, and the total from 79 to 81.

### `src/gramtrans/Lib/models.py` and `tests/unit/_fakes_entryref.py` (commit `bb06edb`)

- The comment documenting the `entryref_create_bindings` record shape now lists `hide_minor_entry` and `summary`.
- `ref_record()` now emits both keys. The unit suite was re-run after this commit: 5309 passed, 80 skipped, 14 xfailed.

### Tests

- New `tests/unit/test_issue114_entryref_value_fields.py` (15 tests). They cover the stash, the create path, the WS-mapped handle, an unmapped WS becoming a drop, a re-run with equal values writing nothing, fill/update/target-only alternatives, an empty source never blanking, source 0 against target 1, a target-only ref left untouched, the two read-back drop cases, the helper's return value, and both arms sharing one helper.
- New `tests/integration/test_issue114_entryref_value_fields_live.py` (2 live tests).

## 4. Deferred items

| Item | Status |
|---|---|
| Stash and write both fields on create | DONE |
| Re-run merge (fill empty / update diverged / never blank) | DONE, through `conflict._merge_delta`, with read-back |
| Census rows | DONE (COPIED) |
| Unit tests for create and re-run of both fields | DONE (15) |
| Live proof: values match the source, and a re-run writes nothing | DONE, plus a merge-arm divergence proof and the mutation check |
| Sweep-pattern audit | DONE. Siblings listed in the PR body; none fixed. |

## 5. Tests

- **Unit** (`pytest tests/unit -q -p no:cacheprovider`, `PYTHONPATH` set to the fix-114 worktree `src`):
  - Baseline on the clean tree: **5294 passed, 80 skipped, 14 xfailed**.
  - After: **5309 passed, 80 skipped, 14 xfailed**. That is +15 tests and 0 failures.
- **Census:** `tests/verification/fidelity_census.py`, 118 passed (it is not part of `tests/unit`).
- **Live:** 2 of 2 pass under `FLEXLIBS_REQUIRE_LIVE=1`, and 2 of 2 fail under the mutation.
- **Note on an earlier baseline attempt:** the first baseline (with `-x`) reported a failure in `test_038_t081_phoneme_features.py::test_the_tail_pass_is_registered_under_its_own_flag`. That was a race: I was editing `categories.py` while the suite was running. Re-run on the stashed clean tree, it passes, and it passes with the fix too.

## 6. Pattern audit and residual risks

**Explicit semantic decision.** For `HideMinorEntry`, a source value of 0 counts as data, not as empty. I followed `conflict._is_empty`, the codebase authority for the #22 rule: "Non-empty scalars (int 0, bool False) are considered non-empty". So on a re-run, a source 0 overwrites a target-side 1. The test `test_rerun_hide_minor_entry_source_zero_updates_diverged_target` pins this, and the live proof shows it on `5faa892d`. If the lead prefers to treat 0 as unset ("never un-hide"), the change is one line in the helper.

**Pattern audit.** The sweep was done by an Explore agent; I spot-checked only the first two rows. The full list is in the PR body. HIGH siblings, listed as follow-ups and not fixed:
- `CmSemanticDomain` (`categories.py:4288`): the create path copies no fields at all.
- `LexReference.Name` / `Comment` (`categories.py:7628`).
- `MoAlloAdhocProhib` / `MoMorphAdhocProhib.Adjacency` (and `Disabled` on the owned create).
- `PhMetathesisRule.StrucChange`.
- `LexEntryInflType.GlossPrepend` / `GlossAppend`.
- `LexPronunciation.CVPattern` / `Tone`.
- `LexEtymology.Note` / `PrecComment`.
- `LexSense.AnthroNote` / `UsageNote`.
- `LexEntry.SummaryDefinition` / `Restrictions`.
- `Text.Source`.
- `FsClosedFeature` / `FsSymFeatVal.GlossAbbreviation` / `RightGlossSep` / `ShowInGloss`.

Several of these are gaps in flexicon's `GetSyncableProperties` sets rather than in GramTrans.

Cleared:
- `LexEntryRef.LiftResidue`: the Carrier-A residue tag overwrites it on purpose.
- `LexEntryRef.VariantEntryDialectLabels`: probably a computed property and a reference field (LOW; not confirmed through MCP).

**Residual risks:**
1. **Preview does not show the INV-1 value merge.** Preview has no line for a value merge on an already-present ref; Move does it inside the STEMS tail. C2's add-only wiring of existing refs already has the same gap. For created refs, the values ride on the ref create that Preview already shows.
2. **A pure 0-action re-run never runs the merge.** Without any STEMS action the tail does not run. A source edit to these fields therefore reaches an existing target ref only on a run that contains at least one STEMS action. This is the same limitation C2 has. The live test works around it with a spare entry.
3. **Summary is copied as plain text.** Rich-text run properties (styles) are not preserved; only the text is copied, at the target WS. This matches `_copy_multistrings_ws_mapped`.
4. **Drops Preview cannot predict.** A drop for an unmapped WS or a read-back miss is emitted only by Move. Under `ws_mapping_mode="full"`, none occurred live.
5. **Stale census note, out of my lane.** The #32 note on `("LexEntryRef", "ShowComplexFormsInRS")` still names `_run_entryref_create_pass` as the copy site. I did not touch it.
6. **Projects left in post-run state.** `GT-Src-114` remains on disk as the last seeded copy; the test rebuilds it on every run. `GT-Sandbox-114` is left restored.
7. **No spec artifacts touched.** This report is not committed.
