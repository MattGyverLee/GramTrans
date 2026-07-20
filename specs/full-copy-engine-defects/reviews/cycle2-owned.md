# Cycle 2 — Finding #3 fix: delete the redundant `TranslationsOC` OwnedObjectSpec row

**Worktree:** `D:\Github\_Projects\_LEX\GramTrans-fullcopy-defects` (branch `fullcopy-defects`)
**File touched (per task scope):** `src/gramtrans/Lib/owned.py`
**Tests touched:** `tests/unit/test_owned_object_walk.py`, `tests/verification/fidelity_census.py` (documentation-string fix only)

## What was deleted

Removed the `OwnedObjectSpec` row for `LexExampleSentence.TranslationsOC` /
`ICmTranslationFactory` from `OWNED_OBJECT_MAP` (was `owned.py:119-129`). This
row was redundant with — and actively conflicted with — the Examples-level
sync: flexicon's `ExampleOperations.GetSyncableProperties`/
`ApplySyncableProperties` already owns `TranslationsOC` end-to-end (serializes
each `ICmTranslation`'s `Translation` multistring + `TypeRA`, and on apply
clear-and-rebuilds via `ICmTranslationFactory` itself) whenever the owning
`LexExampleSentence` is synced. `walk_owned_children`'s unconditional
recursion into every newly-created child then re-matched this row and:

1. Created a **second, duplicate, near-empty** `ICmTranslation` (type set, no
   text) via `ICmTranslationFactory.Create(new_owner, resolved_type, guid)`
   (auto-added to `TranslationsOC`).
2. Triggered a subsequent syncable-properties attempt against a
   `getattr(source, "Translations")` namespace that does not exist on the
   live `FLExProject` handle (only `Examples`/`Pronunciations`/`Etymology`/
   `Senses` exist), producing a **false-positive "dropped" record** on top of
   the duplicate object.

No alternate "Translations ops" object was substituted — none exists and none
is needed; the fix is deletion only.

## `_TRANSLATION_REF_SPECS` disposition

Grepped the whole `src/` tree for `_TRANSLATION_REF_SPECS` before touching it:
its only two occurrences were its own definition (`owned.py:100`, now removed)
and its single use inside the now-deleted row's `child_refs=` field. No other
module referenced it, so it was deleted outright rather than left dangling.
`_references.field_specs_for("CmTranslation")` (the `REFERENCE_FIELD_MAP`
row it wrapped) is untouched — that table entry still legitimately describes
`CmTranslation.TypeRA`'s reference shape for any future caller, it is just no
longer wired into `owned.py`.

`OwnedCreateKind.OWNER_PLUS_TYPE` and its dispatch code
(`_create_owner_plus_type_child` etc.) were left in place as generic,
currently row-less infrastructure — it is dispatch machinery, not
translation-specific, and future owned-child kinds could still need the
"resolve a type ref before create" shape. Its module-level docstring
(`Lib/owned.py`, `_create_owner_plus_type_child`) and `models.py`'s
`OwnedCreateKind` docstring still reference `ICmTranslationFactory` as the
historical example of that shape; left as-is per the task's file-scope
instruction (`models.py` not touched).

Also updated stale doc comments in `owned.py` (module docstring, the
`OWNED_OBJECT_MAP` header comment, and one docstring inside
`walk_owned_children` that used "an example's `TranslationsOC`" as its
recursion example) so nothing in the file still implies a live
`TranslationsOC` row exists.

## Out of scope, confirmed and left untouched

Per task instructions, `LexSense.ExtendedNoteOS` was **not** touched. It is a
genuinely different, still-open sibling gap: unlike `TranslationsOC`/
`Examples`, there is no flexicon `ExtendedNoteOperations`-equivalent
sync-ops surface for `LexExtendedNote` content at all — `_sync_ops_name`
derives `"ExtendedNote"` from `"ExtendedNoteOS"`, but no such attribute
exists on the live `FLExProject` handle. It cannot be fixed by row deletion
the way `TranslationsOC` was; it would need either a new flexicon-side ops
class or an inline dict-based copy inside `owned.py`. Documented here as a
follow-up, not addressed this cycle.

## Test changes

`tests/unit/test_owned_object_walk.py`:
- Renamed/rewrote Case 1
  (`test_examples_reproduced_ordered_with_translations_and_publication_refs`
  → `test_examples_reproduced_ordered_with_publication_refs`) to prove the
  regression directly: an example carrying a source-side `_FakeTranslation`
  now asserts (a) `ICmTranslationFactory` is never requested via
  `GetService` (`"ICmTranslationFactory" not in target_handle.
  requested_services`), (b) the newly-created example's `TranslationsOC`
  stays empty (`len(new_ex1.TranslationsOC) == 0`), and (c) no
  `DroppedItemRecord` is emitted (`dropped == []`) — covering both halves of
  finding #3 (duplicate-object creation and the false-positive drop) in one
  assertion set. `_FakeTranslationFactory`/`ICmTranslationFactory` stay
  registered in `_FakeProject._factories` purely as the negative fixture
  this test exercises.
- Updated the module docstring and header comments to stop describing a
  `TranslationsOC` row that no longer exists, and to explain the new
  negative-fixture role of the translation fakes.
- `test_owned_object_map_rows_are_disambiguable_by_owner_class` (the generic
  QC P1a guard) needed no change — it iterates whatever rows remain in the
  table.

`tests/verification/fidelity_census.py`:
- Updated the `("LexSense", "ExamplesOS")` `Classification` doc-string
  (documentation only, no code path change) to stop claiming
  `TranslationsOC` is copied "via `_EXAMPLE_REF_SPECS`"/this `owned.py` row,
  and to note it is copied by the Examples-level sync instead. `CmTranslation`
  and `LexExampleSentence` are not tracked classes in this census's
  `EXPECTED_MODEL_FIELDS`/`CLASSIFICATION` tables, so no classification entry
  needed adding/removing.

## Test results

- `pytest tests/unit/test_owned_object_walk.py tests/verification/fidelity_census.py -q`
  → **123 passed**.
- Full-suite regression check: `pytest tests/ -q` → **27 failed, 1970 passed,
  72 skipped, 14 xfailed, 14 xpassed**, both *before* this change (verified by
  `git stash`-ing the edits and re-running) and *after* — identical failing
  test list in both runs (pre-existing failures in `test_029_*`,
  `test_adjacent_data.py`, `test_analysis_idempotency.py`,
  `test_human_eval_gate.py`, `test_morph_bundle_wiring.py`,
  `test_residue_tagging_026.py`, `test_segment_alignment.py`,
  `test_wizard_pos_grammar_wiring.py` — unrelated to `owned.py`/translations).
  This fix introduces no new failures.

## Commit

Committed on the worktree's `fullcopy-defects` branch (not merged to `main`).
