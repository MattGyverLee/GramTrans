# Cycle-8 Programmer Report -- #28 layer-2 cast gap fix

**Worktree:** `../GramTrans-027-complex-forms-variants` (branch `027-complex-forms-variants`)
**Commit:** `02413b5` -- "fix(027): cast component/primary members before _affix_type_of (#28 layer-2)"

## Bug

`_entry_ref_is_reproducible` (categories.py) called `_affix_type_of(m)` on each
`ComponentLexemesRS`/`PrimaryLexemesRS` member without casting. On live LCM,
`ComponentLexemesRS`/`PrimaryLexemesRS` are declared as `ICmObject` sequences
(components can be senses or entries), so pythonnet exposes only `ICmObject`
members -- `getattr(m, "LexemeFormOA", None)` reads `None`, `_affix_type_of`
returns `(False, ...)`, and every ref was misjudged out-of-closure. T025's
attended live proof confirmed this: all 6 Ejagham Mini variant refs were fully
reproduced yet all 6 were reported dropped (false positives).

## RED -> GREEN

Added `test_entry_ref_reproducible_casts_bare_component_before_affix_check` to
`tests/unit/test_027_never_silent.py`, modeling the component as a `_Bare`/
`_Typed` pair (mirrors T009's cast tripwire in
`test_027_entryref_reproduction.py`) under the file's existing `_stub_lcm_full`
fixture.

RED (pre-fix, observed):
```
>       assert dropped == []
E       assert [DroppedItemRecord(...)] == []
1 failed in 0.35s
```

GREEN (post-fix): fixed `_entry_ref_is_reproducible` to
`_affix_type_of(_cast_lcm(m, "ILexEntry"))[0]` for each member -- same `_cast_lcm`
idiom used elsewhere in this module.
```
1 passed in 0.30s
```

## Test results

- Targeted 027 suite (`test_027_entryref_reproduction.py`,
  `test_027_entry_type_resolve.py`, `test_027_never_silent.py`,
  `test_phase3c_post_pass_a.py`): **61 passed** (was 60; +1 new regression test).
- Full `python -m pytest tests/unit -q`: **1580 passed, 9 skipped, 14 xfailed,
  14 xpassed, 1 failed** -- the failure is the documented pre-existing baseline
  `test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`,
  unrelated to this change.
- `python -m py_compile src/gramtrans/Lib/categories.py`: OK.

## Pattern audit (sweep-pattern: uncast-typed-attribute-access-after-resolution)

| Site | Needs cast? | Notes |
|---|---|---|
| `_entry_ref_is_reproducible` (categories.py, `_affix_type_of(m)` over Component/PrimaryLexemesRS members) | **Yes -- FIXED** | The bug; now casts via `_cast_lcm(m, "ILexEntry")`. |
| `_lex_entry_ref_identity_label` (categories.py:4398, `_owner_label_for("LexEntry", comps[0])` on the first uncast component) | Same shape, **not fixed** | Cosmetic only -- on live LCM the label falls back to the component's GUID string (`_owner_label_for` returns "" when `CitationForm` is invisible), it does not create additional false-positive drops. Left out of scope per the surgical-fix instruction; flagged as a follow-up if live dropped-ref report label quality becomes a concern. |
| `_affix_type_of` call sites in `stems_enumerate_source`/`affixes_enumerate_source` (categories.py:5480, 5858) | No | `entry` there comes from `_iter_lex_entries(source)` (`lexdb.EntriesOC`/`Entries`), already typed `ILexEntry` at iteration -- not the bare-`ICmObject` shape. |
| `_lex_entry_ref_kind` (`ref.RefType`) | No | `ref` is a typed `ILexEntryRef` from `src_entry.EntryRefsOS` (a typed OS collection); `RefType` is declared directly on that interface. |

No deeper target-resolvability redesign or leaf-pick run-scoping change was
made; the CAVEAT/Decision-5-addendum note in `_entry_ref_is_reproducible`'s
docstring is left intact.
