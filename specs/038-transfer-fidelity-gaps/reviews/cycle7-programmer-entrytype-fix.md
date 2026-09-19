# T123 acceptance line (b) -- entry-type factory choice fixed at the producer

**Date:** 2026-09-18. Worktree only (`GramTrans-038-transfer-fidelity-gaps`,
not committed). No live LCM writes, no transfer runs.

## Fix

New shared helper `_entry_type_factory_for_source(src_obj, target)`
(`categories.py`, immediately after `_source_possibility_parent_guid`)
casts `src_obj` and branches on its OWN `ClassName`: `"LexEntryInflType"`
keeps `ILexEntryInflTypeFactory`; anything else (plain `LexEntryType`) uses
`ILexEntryTypeFactory`. Returns `(factory, factory_label)`.

`variant_types_execute_action` (`:3620`) and `complex_form_types_execute_action`
(`:3793`) both now call this helper instead of hand-rolling a
per-list-unconditional factory choice; every downstream hardcoded
`"ILexEntryInflTypeFactory"`/`"ILexEntryTypeFactory"` label string (error
messages, `_log_possibility_demoted`, `_safe_add_to_owner`) now reads
`factory_label` so the error/log text tracks whichever factory actually ran.
One helper, not two hand-rolled copies -- the sweep instruction's point,
since three copies of a routing block is how this repo acquired the T123
owner-cast defect at three sites at once.

`complex_form_types_execute_action`'s branch is **latent, not confirmed
live**: this corpus shows no `LexEntryInflType` member under
`ComplexEntryTypesOA`. Said explicitly in both the helper's docstring and
the function's docstring; not claimed as "fixed" beyond duck-typed coverage.

## Test

New file `tests/unit/test_038_t123_entry_type_factory_choice.py`, 7 tests,
duck-typed via an offline `SIL.LCModel`/`System` stub (mirrors
`test_027_entry_type_resolve.py`'s `_stub_lcm_full`): a fake
`VariantEntryTypesOA` holding one plain non-Infl `LexEntryType`
(project-local GUID, the Ngoreme/mbugwe shape) alongside a GOLD-GUID
`LexEntryInflType`. Asserts the plain item is created via
`ILexEntryTypeFactory.Create` and NOT `ILexEntryInflTypeFactory.Create`
(and vice versa for the Infl item), via a spy-factory call log. Parametrised
inverse case for `complex_form_types_execute_action` (Infl item under
`ComplexEntryTypesOA`). A dedicated nesting test confirms owner/
`SubPossibilitiesOS` resolution for the plain item is unchanged under the
corrected factory (shared logic, not touched by this fix). Plus a
sweep-assertion that both sites call the one helper, and a direct
value-level test of the helper itself.

**Counts:** `tests/unit/test_038_t123_entry_type_factory_choice.py`: 7/7
passed. `tests/unit/` (full, not bare `pytest tests/`): 3888 passed, 79
skipped, 14 xfailed -- no regressions.

## Acceptance still open

Post-fix acceptance must measure BOTH `LexEntryType` exact-class MATCHED
(13/13 ngoreme, 12/12 mbugwe) AND `LexEntryInflType` exact-class MATCHED
(3/3, 4/4) on both pairs -- net cancellation (-1/+1 each) is NOT acceptance.
This requires a live re-census (restore `Target`, run transfer, re-census)
that is not authorized in this task. **T123 stays unchecked.**
