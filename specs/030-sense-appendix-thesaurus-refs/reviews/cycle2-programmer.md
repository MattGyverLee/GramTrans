# Cycle-2 programmer report -- feature 030 (sense appendix + thesaurus refs)

Worktree: `D:\Github\_Projects\_LEX\GramTrans-030-sense-appendix-thesaurus-refs`
Branch: `030-sense-appendix-thesaurus-refs`
Commit: `92a9e64` (parent `d6132ff`)

Three changes made, exactly as scoped by the cycle-1 review. The three
deferred P2 advisories (hardcoded `hierarchical=True`, broad-except reason
text, appendix `item_name=""`) were **not** touched.

## FIX 1 -- must-fix latent gap (correctness + simplification)

`src/gramtrans/Lib/references.py:1282-1318` -- `_iter_target_possibility_lists`
rewritten to derive its Name-fallback candidate set from `REFERENCE_FIELD_MAP`
instead of the hand-written ~11-lambda accessor tuple.

Before: a separately maintained tuple of 11 `lambda target: ...` accessors
had drifted out of sync with `REFERENCE_FIELD_MAP` -- `CmTranslation.TypeRA`
(-> `TranslationTagsOA`), `LexEntryRef.VariantEntryTypesRS`
(-> `LexDbOA.VariantEntryTypesOA`) and `LexEntryRef.ComplexEntryTypesRS`
(-> `LexDbOA.ComplexEntryTypesOA`) were missing. A thesaurus item whose
owning list is one of those three would DROP-report instead of Name-match
LINK.

After: the function walks `REFERENCE_FIELD_MAP` directly, calling each row's
`spec.target_list_path(target)`, skipping any row whose `target_list_path` is
`None` or whose call raises, and yielding only results that
`hasattr(lst, "PossibilitiesOS")` (de-duplicated by `id()`). Confirmed this
naturally (no special-casing) excludes:
- `MoForm.PhoneEnvRC` -> `PhonologicalDataOA.EnvironmentsOS` (a flat owned
  sequence, no `PossibilitiesOS`)
- `MoForm.StemNameRA` -> `target_list_path` is literally `lambda target: None`

Module comments (docstring on the function itself) updated to explain the
derivation and why those two rows are naturally skipped. Fake-target
short-circuit (`target.possibility_lists`) preserved unchanged for existing
tests.

## FIX 2 -- test coverage: owner+flid primary matcher hit

`tests/unit/test_cycle16c_sense_scope_gaps.py` -- added
`test_B_owner_flid_primary_matcher_hit_wins_over_name_fallback` plus its
supporting fakes (`_install_fake_lcm_for_owner_flid`,
`_FakeOwnerFlidLexDb`, `_FakeOwnerFlidLangProject`,
`_FakeDomainDataByFlid`, `_FakeObjectRepository`, `_FakeServiceLocator`,
`_FakeOwnerFlidCache`, `_FakeOwnerFlidTarget`).

Every pre-existing Section B fake set `owner=object()` on the source list,
so only the Name-fallback path was exercised offline; the authoritative
owner-class + `OwningFlid` matcher (`_target_list_by_owner_flid`) was only
live-proven. The new test stubs `SIL.LCModel` (`ICmObject`,
`ICmPossibilityList`, `ILangProject`, `ILexDb`, all identity-cast, mirroring
`test_reference_create_paths.py::_install_fake_lcm`) via
`monkeypatch.setitem(sys.modules, ...)` so the stub is reverted after the
test -- no suite pollution. It builds a minimal owner+flid duck-typed shape
(`target.Cache.LangProject.LexDbOA.Hvo`,
`target.Cache.DomainDataByFlid.get_ObjectProp`,
`target.Cache.ServiceLocator.ObjectRepository.GetObject`) that resolves to
`owner_flid_list`, while ALSO registering a **different** list object
(`name_fallback_list`, same Name "Thes") on `target.possibility_lists` --
so the test fails if the resolver silently falls through to the Name match
instead of taking the owner+flid hit. Asserts
`mirror_possibility_list_to_target(src_list, target) is owner_flid_list`
and `is not name_fallback_list`.

## FIX 3 -- test coverage: Move==Preview parity, LINK-SUCCESS branch

`tests/unit/test_cycle16c_sense_scope_gaps.py` -- added
`test_move_and_preview_parity_for_link_success_thesaurus_item`, reusing the
existing B-link fake setup (`target.possibility_lists` with a matching list
containing the item, same shape as `test_B_link_present_in_mirrored_list`).
Runs `_resolve_sense_thesaurus_items` once in Move mode (`new_sense` set)
and once in Preview mode (`new_sense=None`), asserting both produce an
identical (empty) drop set, and that Move actually links the resolved
target item onto `new_sense.ThesaurusItemsRC` -- extending the pre-existing
parity test (`test_move_and_preview_drop_sets_identical_for_sense_scope_gaps`,
which only covers the all-drop branch) to the link/create decision branch.

## Test results

```
python -m pytest tests/unit/test_cycle16c_sense_scope_gaps.py tests/verification/fidelity_census.py -q
135 passed in 0.47s
```

```
python -m pytest -q
22 failed, 1861 passed, 72 skipped, 14 xfailed, 14 xpassed in 7.77s
```

Failure set unchanged from the pre-existing baseline (all 22 failures are in
`test_adjacent_data.py`, `test_analysis_idempotency.py`,
`test_analysis_verdict.py`, `test_human_eval_gate.py`,
`test_morph_bundle_wiring.py`, `test_residue_tagging_026.py`,
`test_segment_alignment.py`, `test_wizard_pos_grammar_wiring.py` -- none
touched by this change, none new). No `SIL.LCModel` stub leak: the new
owner+flid stub uses `monkeypatch.setitem`, reverted automatically at test
teardown; full-suite failure count/set confirms no pollution.

## Files changed

- `src/gramtrans/Lib/references.py` (`_iter_target_possibility_lists`,
  ~line 1282)
- `tests/unit/test_cycle16c_sense_scope_gaps.py` (new imports `sys`/`types`;
  two new tests + supporting fakes)

Committed as `92a9e64` on branch `030-sense-appendix-thesaurus-refs`.
