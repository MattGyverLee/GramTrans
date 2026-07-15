# Coverage Content-Fidelity Part B sub-part 1: inflection_features complex/open

Commit: `2ab8a79` on worktree `GramTrans-coverage-content-fidelity-v2` (branch
`coverage-content-fidelity-v2`).

## Change

`inflection_features_execute_action` (src/gramtrans/Lib/categories.py) now
dispatches on `src_feat.ClassName` **before** the old unconditional
`IFsClosedFeature(src_feat)` cast:
- `FsComplexFeature` -> created via `IFsComplexFeatureFactory` (Path A 2-arg
  `Create(Guid, featureSystem)`, Path B `Create(Guid)` + guarded Add). Name/
  Abbreviation/Description copied via the ws-mapped Operations surface,
  falling back to main's `_copy_multistrings_ws_mapped` (kept -- did NOT
  regress to stale-branch ec9891ae's unmapped `_copy_multistring`). TypeRA
  wired by GUID match in `MsFeatureSystemOA.TypesOC` if resolvable; left
  unset (no crash) if not -- FEATURE_STRUCT_TYPES is a later sub-part, so
  target `TypesOC` is commonly empty today. No ValuesOC loop.
- `FsOpenFeature` -> clean `Skip(NEEDS_MANUAL)`, no crash, no orphan.
- `FsClosedFeature` / unknown -> unchanged GOLD Path A/B + ValuesOC path.

## Tests

`tests/unit/test_categories_inflection_features.py`: 4 new tests using
duck-typed fakes + an injected fake `SIL.LCModel`/`System` module set
(offline, no LCM host): (a) complex feature created not skipped, TypeRA
wired when resolvable; (a2) TypeRA left unset gracefully when target
struct-type absent; (b) closed-feature regression guard (service locator
deliberately omits `IFsComplexFeatureFactory` so cross-branch dispatch would
KeyError); (c) open feature -> `result is None`, no `FeaturesOC` attach,
exactly one `NEEDS_MANUAL` skip recorded.

RED confirmed via `git stash` of the source fix: 3/4 new tests failed
against pre-fix code (complex/open features reached
`IFsClosedFeatureFactory` or the removed cast-skip); closed-feature
regression test already passed pre-fix (unaffected code path). GREEN after
unstash: 14 passed, 1 skipped in this file. Full suite: 1598 passed, 8
skipped, 14 xfailed, 14 xpassed, 1 pre-existing failure
(`test_wizard_pos_grammar_wiring`, documented baseline, unrelated).
`py_compile` clean.

## Sweep audit

Searched all `*_execute_action` functions in categories.py for
ClassName-based or single-subtype-cast dispatch that silently drops
siblings. No other such dispatch exists in this file -- the new
`ClassName ==` checks added here are the only instance. One sibling of the
same *shape* exists **outside** categories.py:
`merge_preview.py:_closed_value_label` (~line 1826) casts every feature
spec to `IFsClosedValue` for its FLEx-style label; an `FsComplexValue` spec
would silently render an empty label. This is read-only/display-only (not a
transfer drop) and belongs to the MSA `InflFeatsOA` / FEATURE_STRUCT_TYPES
territory -- explicitly out of scope for this sub-part per the task brief;
flagging for whichever later sub-part touches complex feature *values*.

## Cross-sub-part note

Complex-feature `TypeRA` wiring degrades gracefully today because
FEATURE_STRUCT_TYPES (a later Part B sub-part) doesn't yet populate target
`MsFeatureSystemOA.TypesOC`. Once that sub-part lands, this same code will
start resolving TypeRA correctly with no further change needed here.

## Note

FLExToolsMCP was not available as a callable tool in this session; LCM API
shape (`IFsComplexFeatureFactory`, `IFsFeatStrucType`, `TypeRA`) was taken
from stale-branch commit `ec9891ae`'s already-MCP-verified findings (per
its commit message) rather than re-probed live. No live FLEx transfer was
run (per instructions).
