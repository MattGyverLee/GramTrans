# Cycle 8 -- Verification Postfix (final)

**Tree:** worktree `GramTrans-038-transfer-fidelity-gaps`, all uncommitted work in
place. No code edited, nothing committed, no stash, no transfer, no live LCM write.

## Test deltas

`python -m pytest tests/unit/ -q` -> **3894 passed, 79 skipped, 14 xfailed**.
Reconciled exactly: 3881 (cycle-6 baseline) +7 (cycle-7 LexEntryType fix,
`test_038_t123_entry_type_factory_choice.py`) +4 (cycle-8 natural-key MSA fix,
`test_038_t123_msa_naturalkey_reuse.py`) +2 (cycle-8 hardening,
`test_038_t123_msa_entry_owned_no_sense_latent.py`) = 3894.

Targeted selection -> **635 passed, 5 failed, 29 skipped**, identical count and
identical named failures to cycle-6's baseline (`TestT101...test_every_committed_null_row_is_advisory`,
`TestT078...[mbugwe]`, `TestT078...[ngoreme]`, `TestT107...[census-038-t107-mbugwe-phase6.json]`,
`TestT108...test_t107s_own_censuses_still_hash_to_their_projects`) -- all 5 pre-existing
live-`.fwdata` drift, confirmed byte-identical to the baseline's stash-probed set. No new
failure anywhere.

## Diff verification (located by name, not inherited line number)

1. **Entry-type factory:** shared helper `_entry_type_factory_for_source` at
   categories.py:12800, used at both `variant_types_execute_action` (call site
   line 3687) and `complex_form_types_execute_action` (line 3858). Keys the
   factory choice to `src_obj`'s own `ClassName`, not the possibility list --
   matches the claim.
2. **Natural-key MSA fix, BOTH halves confirmed:**
   - Half A (create not skipped/lost): `_create_via_wrapper_or_reuse` (9854)
     wraps the wrapper create in try/except; on raise it calls
     `_find_reusable_target_msa` (9807) which matches by subclass + POS-field
     GUIDs before falling back to a reported drop.
   - Half B (sense never dangles): at the `_walk_lex_entry_closure` per-sense
     call site (categories.py:8287-8293), `new_msa` -- whatever path produced
     it (GUID-preserving create, wrapper create, or reuse) -- is
     unconditionally assigned to `new_sense.MorphoSyntaxAnalysisRA` whenever
     non-None. Reuse path returns a real object, so this assignment fires on
     the legitimate-reuse path too. Both halves verified from code, not from
     the report.
3. **Hardening:** `_create_entry_owned_msas_without_sense` (10132) is called
   at categories.py:8306, between the sense loop's end (8294) and
   `return new_entry` (8310). `_create_msa_with_guid`'s `new_sense=None`
   guard confirmed at line 9779 (`if new_sense is not None:`).
4. **Token edits intact:** `git diff --stat` shows models.py (+37/-6),
   census.py (+10), test_object_census.py (+121/-32), plus the two
   `test_038_null_counts.py` / `test_038_t079...` files and the two `specs/`
   contract files all still carry their diffs, unreverted. No FLEx project
   written to this cycle.
5. **Labelling gate PASS:** hardening docstring cites `op-102227585-005`/
   `op-102255766-006`, states "MEASURED EMPTY," names T123(a)'s real fix
   (`_create_via_wrapper_or_reuse`/`_find_reusable_target_msa`) as a
   "DIFFERENT, already-diagnosed and already-fixed mechanism." `git diff`
   grep for "close/closes/fixes/resolved T123" -> zero hits. T123(b) is
   described only via "acceptance line (b)" as a misclassification (LCM
   class wrong, GUID/nesting preserved) -- never as an "absence."
6. **Pyright gate: BENIGN, mechanism demonstrated.** The two reported errors
   reproduce ONLY when pyright is invoked from the main tree's cwd (`cd
   GramTrans && python -m pyright <worktree test path>`), because the global
   editable install (`_editable_impl_gramtrans.pth` -> `GramTrans\src`, not
   the worktree) makes pyright resolve `gramtrans.Lib.categories` to main's
   STALE `_create_msa_for_closure(src_msa, new_sense, new_entry, context,
   tag, identity_remap)` -- no `dropped`/`src_entry` params at all -- and
   flags the test's kwargs as unknown. Invoked from the worktree's own cwd
   (this task's authoritative scope), pyright resolves the local `src/`
   correctly and reports zero errors at lines 151-152; the worktree's real
   signature (categories.py:9904) has `dropped=None, src_entry=None`, and the
   test's call matches it exactly. Confirmed by direct read plus two paired
   pyright runs (main-cwd reproduces, worktree-cwd clean).

## Verdict

**GO** -- 3881->3894 fully reconciled (+7/+4/+2), targeted 635/5/29 failures
identical and pre-existing, all four named code changes verified in place by
name, both MSA-fix halves confirmed independently, labelling gate clean, and
the Pyright complaint is a cwd/stale-editable-install artifact, not a real
call-signature defect in the worktree under test.
