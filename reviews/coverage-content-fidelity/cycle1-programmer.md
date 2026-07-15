# cycle1-programmer -- coverage-content-fidelity Part A (inflection_classes owner bug)

## Bug confirmed and fixed

`src/gramtrans/Lib/categories.py`, `inflection_classes_*` group (formerly
lines 1187-1281). Root cause: IMoInflClass is owned PER-POS via
`IPartOfSpeech.InflectionClassesOC` (confirmed via
`flexicon/code/Grammar/POSOperations.py:746 -- return list(pos.InflectionClassesOC)`),
but GramTrans's enumerate_source/plan_action/execute_action all went through
`source.InflectionFeatures.InflectionClassGetAll()` /
`...ProdRestrictOA.PossibilitiesOS.Add()`. Traced that flat wrapper into
flexicon itself (`InflectionFeatureOperations.py:178-183,241-255`): it reads
and writes `MorphologicalDataOA.ProdRestrictOA.PossibilitiesOS` -- the
production-restrictions/exception-features list, a **flexicon-side defect**,
out of scope here (separate dependency package). Fix: GramTrans now bypasses
that wrapper entirely and walks POS ownership directly, mirroring
stem_names_*/slots_execute_action's established per-POS pattern
(`_iter_pos`, `_as_pos`, `_resolve_target_pos`, `_safe_add_to_owner`).

Changes: enumerate_source/plan_action walk `pos.InflectionClassesOC` across
all target/source POS (via new `_inflection_classes_from_pos` helper, top-
level only, TODO(SubclassesOC) preserved); `inflection_classes_dependencies`
now yields `(GRAM_CATEGORIES, owner_pos_guid)` (was an unconditional leaf);
execute_action resolves the owner POS on target by source-POS GUID and adds
via `target_pos.InflectionClassesOC.Add()`, returning `None` on unresolved
owner (matches stem_names/slots convention) instead of writing to
`ProdRestrictOA.PossibilitiesOS`.

`GetSyncableProperties`/`ApplySyncableProperties` calls via
`InflectionFeatures` were **kept unchanged** -- confirmed correct for
IMoInflClass by reading flexicon source directly (docstring: "This
implementation focuses on inflection classes"; body reads/writes only
Name/Abbreviation/Description by WS handle, independent of the item's
owning collection; `ApplySyncableProperties` is the generic, item-agnostic
base-class implementation and forwards `ws_map`). The stale reference branch
commit 8fadc1e1's claim that no such wrapper exists was incorrect (or based
on an older flexicon); reusing it here is safer than the branch's manual
raw-WS-handle copy (which has no ws_map translation).

## RED -> GREEN

Rewrote `tests/unit/test_categories_inflection_classes.py` with POS-owned
fakes (mirrors `test_categories_stem_names.py`), plus a fully-mocked
execute_action test (mirrors `test_categories_phonology.py`'s
ServiceLocator/factory MagicMock pattern) asserting the new IMoInflClass
lands in the owner POS's `InflectionClassesOC` and never in a
`ProdRestrictOA.PossibilitiesOS` stand-in.

RED (pre-fix, `git stash` on categories.py only): 5/9 new tests failed --
`dependencies()` returned `()` unconditionally, enumerate/plan silently
found nothing (old code required a flat `InflectionFeatures` accessor absent
from POS-owned fakes -- reproduces the live symptom: arz-flex 0/1, Aweti
0/3, French-FLExTrans-Demo2025 0/5), and execute_action's unconditional
`from SIL.LCModel import IMoInflClassFactory` blew up under the mocked
import surface.

GREEN (post-fix): `tests/unit/test_categories_inflection_classes.py` 9/9
pass. Full suite: `1594 passed, 8 skipped, 14 xfailed, 14 xpassed, 1 failed`
-- the 1 failure is `test_wizard_pos_grammar_wiring.py::
TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos`,
confirmed identical on the unmodified baseline (`git stash` + rerun),
matching the documented pre-existing baseline. `py_compile` clean.

## Sweep audit (owned-object-added-to-wrong-collection / wrong ops-class)

Enumerated every `_safe_add_to_owner(...)` / `_create_with_guid(...)` call
site in categories.py (feature_system.FeaturesOC, ValuesOC,
InflectionClassesOC [fixed], StemNamesOC, SubPossibilitiesOS/
PossibilitiesOS for variant_types/complex_form_types/semantic_domains,
EntryRefsOS, AffixSlotsOC, AffixTemplatesOS, and the Phase-3a phonology
factories NaturalClassesOS/PhonemesOC/EnvironmentsOC/StrataOC/etc.). Every
collection name is semantically consistent with the item type it receives
(e.g. `pos.StemNamesOC` <- IMoStemName, `pos.AffixSlotsOC` <- IMoInflAffixSlot,
`target_entry.EntryRefsOS` <- ILexEntryRef). No other site shows the
name-mismatch pattern that flagged inflection_classes
(`ProdRestrictOA.PossibilitiesOS` receiving an unrelated item type). No
further fixes made under this scope.

## Flags for domain review (not decided here)

1. **SubclassesOC nesting deferral** -- `_inflection_classes_from_pos` only
   yields top-level `InflectionClassesOC`; nested `ic.SubclassesOC` is not
   recursed (TODO left in code).
2. **POS-dependency ordering** -- `inflection_classes_dependencies` now
   yields `(GRAM_CATEGORIES, owner_pos_guid)`, consumed by `closure.py`'s
   topological walk (confirmed it exists and orders dependencies before
   dependents). Note `stem_names_dependencies` still returns `()`
   unconditionally despite also being POS-owned -- inconsistent with the
   fix applied here; whether stem_names has the same latent
   execute-before-owner-exists risk is a separate question, not addressed
   in this scoped port.
3. **execute-time unresolved-owner contract** -- on unresolved owner POS,
   execute_action returns `None` (matching stem_names/slots convention)
   rather than emitting a formal `Skip(DEPENDENCY_UNRESOLVED)`; no leaf
   category in categories.py currently returns a Skip from execute_action
   (only from plan_action), so this preserves the existing architectural
   pattern rather than introducing a new return contract.

## Commit

Committed on worktree `coverage-content-fidelity-v2`.
