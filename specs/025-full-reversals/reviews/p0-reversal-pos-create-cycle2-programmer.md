# P0 fix (reversal-category CREATE, ItemClsid 5049) -- Cycle 2 Programmer: GREEN

Worktree: `D:/Github/_Projects/_LEX/GramTrans-025-fix-reversal-pos-create`
Branch: `025-fix-reversal-pos-create`
Commit: `752a60c` — "fix(025): CREATE-arm owner-taking dispatch for reversal
categories (clsid 5049)" (parent `c617790`, the cycle-1 RED test).

**Note on filename:** the literal path requested (`cycle2-programmer.md`)
already exists in this feature's reviews directory, populated by the
unrelated main US1 thread (`GramTrans-025-full-reversals` worktree/branch).
This report is for the separate P0 hotfix sub-thread (`p0-reversal-pos-
create-*` naming, matching cycle 1's `p0-reversal-pos-create-cycle1-
programmer.md`), so it is written under that name instead of overwriting
the US1 cycle-2 report.

## Diff summary

`src/gramtrans/Lib/references.py`:
- ~line 1016-1025: added `IPartOfSpeechFactory` to the CREATE arm's
  unconditional `from SIL.LCModel import (...)`.
- ~line 1041-1057: added `5049: IPartOfSpeechFactory` to
  `factory_by_item_clsid`, with a comment explaining it is handled by a
  SEPARATE owner-taking branch, never the generic create-then-`_add_to_owner`
  idiom the other rows share.
- ~line 1076-1099 (ancestor loop): branched on `item_clsid == 5049` BEFORE
  the generic `factory.Create(parsed_guid)` + `_add_to_owner(...)` call.
  For 5049, calls the owner-taking overload directly and does NOT call
  `_add_to_owner` at all (the factory performs ownership itself).

Two sibling test fixtures needed their fake `SIL.LCModel` stub extended
with an `IPartOfSpeechFactory` attribute (the CREATE arm's import is
unconditional, so every fake stub of the module needs the name even if
that test never exercises clsid 5049): `tests/unit/test_027_entry_type_
resolve.py` (`_stub_lcm_full` fixture) and `tests/unit/test_reversal_
category_resolve.py` (`_install_fake_lcm`, whose `_FakePosList` defaults
to clsid 7 and never hits the new branch).

## Root vs. child Create call shapes

```python
owner = (
    ICmPossibilityList(target_list)          # root: the index's OWN PartsOfSpeechOA
    if parent_target_item is None
    else parent_target_item                   # child: the just-created parent IPartOfSpeech
)
new_obj = factory.Create(parsed_guid, owner)
```

Root -> `Create(guid, tgt_index.PartsOfSpeechOA)`, appended by the factory to
`owner.PossibilitiesOS`. Child -> `Create(guid, parent_pos)`, auto-owned by
the factory under `parent_pos.SubPossibilitiesOS`. Matches the live-confirmed
shape in `scratchpad/build025_fixture.py` (`fac.Create(guid, en_poslist)` /
`fac.Create(guid, parent)`). Never touches `LangProject.PartsOfSpeechOA` (R5)
since `target_list` is always `spec.target_list_path(target)` -- the target
REVERSAL INDEX's own list for this field.

## 030 thesaurus dynamic-owner coverage

The 030 dynamic-owner path (`discover_owning_possibility_list` /
`mirror_possibility_list_to_target`, ~1191-1413) delegates the actual
create/link/update to the SAME `apply_reference` CREATE arm via a synthetic
per-item `ReferenceFieldSpec` -- confirmed by reading through to its call
site, which constructs a spec and calls the shared resolver rather than any
separate factory-dispatch logic. Since the clsid-5049 branch lives inside
that shared CREATE arm (keyed purely off `target_list.ItemClsid`, with no
special-casing of which caller reached it), **this fix DOES cover that path
structurally**: if a project's `ThesaurusItemsRC` owner ever resolved to a
`PartsOfSpeechOA` list (vacuous-live today per the task's brief, 0/79
projects), the same owner-taking dispatch would fire. No additional code
change was needed or made for 030; this is stated explicitly per the task's
instruction rather than left as a silent assumption.

## Suite result

- Target RED test: GREEN
  (`test_create_path_reversal_category_hierarchical_owner_taking_factory`).
- `tests/unit/test_reference_create_paths.py` +
  `test_027_entry_type_resolve.py` + `test_reversal_category_resolve.py`:
  30 passed.
- Full `tests/unit`: **1719 passed**, 22 failed, 8 skipped, 14 xfailed, 14
  xpassed. The 22 failures are the SAME pre-existing set present before this
  change (verified via `git stash` baseline: 23 failed pre-fix, one of which
  was this feature's own RED test -- 23 - 1 = 22, identical file/test names
  in both runs). No new regressions introduced.

Not merged to main; no live-LCM Move executed, per instructions.
