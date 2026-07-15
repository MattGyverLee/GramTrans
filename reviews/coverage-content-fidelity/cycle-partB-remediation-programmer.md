# Coverage Content-Fidelity Part B remediation: PHON_FEAT_TYPES reclassification + B.2 doc corrections

Branch: `coverage-content-fidelity-v2`. Small, low-risk model-consistency fix
approved by domain + QC review (see `cycle-partB-domain.md` / `cycle-partB-qc.md`).

## Change 1: `GrammarCategory.PHON_FEAT_TYPES` reclassified gold_reserved -> multi_instance

`src/gramtrans/Lib/models.py`, `_build_default_conflict_modes()`:

- Removed `GrammarCategory.PHON_FEAT_TYPES` (and its stale explanatory comment
  block, which cited the ec9891ae port reference as justification for the
  GOLD_RESERVED placement) from the `gold_reserved` set.
- Added `GrammarCategory.PHON_FEAT_TYPES` to the `multi_instance` set,
  immediately after `GrammarCategory.STRATA`, with a new comment explaining
  the reclassification: PHON_FEAT_TYPES is structurally identical to its
  sibling `FEATURE_STRUCT_TYPES` (already MULTI_INSTANCE), and under v7.0.0
  both buckets resolve to `ConflictMode.UPDATE`, so this is a pure
  model-consistency correction with **no runtime behavior change**.
- Did **not** touch `_GOLD_RESERVED_CATS` or the `_iterators` maps in
  `transfer.py` -- `PHON_FEAT_TYPES` is correctly absent from both by design
  (the same POS precedent that governs `FEATURE_STRUCT_TYPES`'s absence),
  and this task explicitly excluded touching those maps.

## Change 2: Test lock-in updated

`tests/unit/test_conflict_mode_model.py`, `TestLayer1DefaultTable`:

- `test_multi_instance_default_update`: added `GrammarCategory.PHON_FEAT_TYPES`
  to the `multi` list (asserts `ConflictMode.UPDATE`).
- `test_gold_reserved_default_update`: removed `GrammarCategory.PHON_FEAT_TYPES`
  from the `gold` list.
- Net effect: `PHON_FEAT_TYPES`'s expected conflict mode is still asserted as
  `ConflictMode.UPDATE` in both cases (no assertion value changed), only
  which bucket-list it's locked into moved. Confirms the "no runtime
  behavior change" claim mechanically.

## Change 3 & 4: B.2 programmer report doc corrections

`reviews/coverage-content-fidelity/cycle-partB2-programmer.md`:

- **Cross-sub-part notes** (TypeRA convergence claim): replaced the
  inaccurate "will only resolve on a **second** run (once
  `FEATURE_STRUCT_TYPES` has landed the type)" claim with the corrected
  statement: it does NOT converge without an explicit repair pass, because
  the idempotent GOLD `ALREADY_PRESENT_BY_GUID` skip never re-calls
  `execute_action` for a struct-type that already exists by GUID in the
  target, and the GOLD merge path has no `TypeRA` logic to run instead. Left
  a note flagging this as a post-merge follow-up requiring an explicit
  two-phase shell/wire tail pass (analogous to the existing
  `InflectableFeatsRC` tail-pass used by `INFLECTION_FEATURES`).
- **Registration sites touched** list: added item 10, the previously-missing
  `src/gramtrans/Lib/merge_preview.py:1153`
  `_CATEGORY_VALUE_TO_KEY["feature_struct_types"] = None` entry (confirmed
  present, value `None`, same posture as its `"inflection_classes"` /
  `"exception_features"` neighbors). Noted this site was not touched by
  B.2's original diff (already present) but was missing from the
  inventory for completeness.

## Scope discipline

No dispatch-order changes. No `TypeRA` wiring logic added -- the corrected
doc text explicitly defers that to a separate follow-up ticket, per the
brief.

## Verification

- `python -m py_compile src/gramtrans/Lib/models.py` -- clean.
- `python -m pytest tests/unit/test_conflict_mode_model.py -q` -- **41
  passed**.
- `python -m pytest tests/unit/test_category_registry.py
  tests/unit/test_categories_phon_feat_types.py -q` -- **21 passed**
  (confirms the reclassification did not break PHON_FEAT_TYPES's own
  registry/category tests; note `test_categories_phon_feat_types.py`'s
  header/inline comments still describe PHON_FEAT_TYPES as "classified
  GOLD_RESERVED in models.py" -- this is now a stale comment, but it was
  out of scope for this remediation task, which named only
  `test_conflict_mode_model.py`'s lock-in lists for editing. Flagging for a
  future doc-only follow-up if desired.)

## Files changed

- `src/gramtrans/Lib/models.py` -- `_build_default_conflict_modes()`:
  removed `PHON_FEAT_TYPES` from `gold_reserved`, added to `multi_instance`.
- `tests/unit/test_conflict_mode_model.py` -- `TestLayer1DefaultTable
  .test_multi_instance_default_update` / `.test_gold_reserved_default_update`:
  moved `PHON_FEAT_TYPES` between the two lock-in lists.
- `reviews/coverage-content-fidelity/cycle-partB2-programmer.md` -- two doc
  corrections (Cross-sub-part notes TypeRA convergence claim; registration
  sites list item 10).
