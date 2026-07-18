# P0 fix (reversal-category CREATE, ItemClsid 5049) -- Cycle 1 Programmer: worktree + TDD RED

## Worktree

- Path: `D:/Github/_Projects/_LEX/GramTrans-025-fix-reversal-pos-create`
- Branch: `025-fix-reversal-pos-create` (off `main` @ `dacbf78`)
- Confirmed builds/imports: `python -c "import gramtrans"` -> `import ok`;
  pre-existing suite `tests/unit/test_reference_create_paths.py` -> 6 passed
  before the new test was added.

## New failing test

`tests/unit/test_reference_create_paths.py:512` --
`test_create_path_reversal_category_hierarchical_owner_taking_factory`

Extends the existing BUG-2b pattern in that file (real
`ItemClsid -> factory` dispatch inside `apply_reference`'s CREATE arm, via
`_install_fake_lcm`'s `SIL.LCModel`/`System` module injection -- no fakes of
the dispatch itself). Also added a permanent `IPartOfSpeechFactory`
identity-cast class to `_install_fake_lcm`'s fake `SIL.LCModel` module
(needed by every test in the file, since `apply_reference`'s unconditional
`from SIL.LCModel import (...)` will eventually need it once 5049 is mapped).

New fakes (same file, immediately above the test):
- `_FakeReversalPOS` -- fake `IPartOfSpeech`, exposes `SubPossibilitiesOS`.
- `_FakeReversalIndexPOSList` -- fake per-index `PartsOfSpeechOA`
  (`ItemClsid=5049`).
- `_FakeLangProjectPOSList` -- a SEPARATE, independently-asserted fake
  standing in for `LangProject.PartsOfSpeechOA`, to lock R5 (never touched).
- `_FakeIPartOfSpeechFactoryOwnerOnly` -- the factory-overload contract (see
  below).
- `_FakeTargetForReversalPOS(_FakeTarget)` -- `GetFactory` dispatches the
  owner-only POS factory for the `IPartOfSpeechFactory` key, generic
  `_FakeFactory` otherwise (matches real `FLExProject.GetFactory`'s
  per-interface routing).

The test builds a 2-level ancestor chain (`parent_src`, `child_src`),
drives `references.apply_reference` directly with
`spec.target_list_path` -> a fake reversal index's own `PartsOfSpeechOA`,
and asserts: (1) the created child is returned and wired to
`entry.PartOfSpeechRA`; (2) `LangProject.PartsOfSpeechOA`
(`_FakeLangProjectPOSList`) stays empty (R5); (3) the root lands in the
index's own `PartsOfSpeechOA.PossibilitiesOS`; (4) the child is
auto-owned under the root's `SubPossibilitiesOS` (never appended flat).

## Exact factory-overload contract modeled

```python
class _FakeIPartOfSpeechFactoryOwnerOnly:
    def Create(self, guid, owner=None):
        if owner is None:
            raise TypeError(
                "IPartOfSpeechFactory.Create(Guid) has no 1-arg overload -- "
                "owner (ICmPossibilityList root or IPartOfSpeech parent) "
                "is required"
            )
        new_pos = _FakeReversalPOS(str(guid))
        new_pos.Owner = owner
        if isinstance(owner, _FakeReversalPOS):
            owner.SubPossibilitiesOS.Add(new_pos)   # child -> auto-owned
        else:
            owner.PossibilitiesOS.Add(new_pos)      # root -> list-owned
        return new_pos
```

No 1-arg `Create(Guid)` overload exists at all (matches
`scratchpad/build025_fixture.py`'s live-confirmed calls,
`fac.Create(guid, en_poslist)` / `fac.Create(guid, parent)`); a 1-arg call
raises `TypeError`, and the factory itself performs ownership (unlike the
generic `ICmPossibilityFactory.Create(Guid)` + separate `_add_to_owner`
idiom `apply_reference`'s CREATE arm uses today).

## RED failure (trimmed)

```
factory_by_item_clsid = {
    66: ICmSemanticDomainFactory,
    26: ICmAnthroItemFactory,
    5042: IMoMorphTypeFactory,
    5118: ILexEntryTypeFactory,
    7: ICmPossibilityFactory,
}
item_clsid = getattr(target_list, "ItemClsid", None)
factory_iface = factory_by_item_clsid.get(item_clsid)
if factory_iface is None:
    ...
>   raise UnmappedItemClassError(unmapped_dropped)
E   gramtrans.Lib.references.UnmappedItemClassError: unmapped item class 5049 for CREATE

src\gramtrans\Lib\references.py:1065: UnmappedItemClassError
1 failed, 6 passed in 0.37s
```

Fails today because `5049` is absent from `factory_by_item_clsid`
(`references.py` ~line 1041-1047), so the fail-loud "unmapped item class"
branch fires before the factory is ever consulted. Note for the green
cycle: because the fake's `Create` has no 1-arg overload either, a
*partial* fix (adding `5049: IPartOfSpeechFactory` to the map without also
replacing the create-then-add idiom with the owner-taking calls) would
still fail this test -- via the fake's `TypeError` instead of
`UnmappedItemClassError` -- so the test stays RED against either
half-fix.
