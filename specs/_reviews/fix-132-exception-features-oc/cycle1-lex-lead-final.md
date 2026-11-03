# Issue #132 — ExceptionFeaturesOC never-silent — lex-lead cycle 1 (final)

## Issue selection

No open **P0** bugs. The only open **P1** without a PR is **#22** (conflict-mode epic — not a bounded fix). Selected **#132** (P2 never-silent audit; issue closed, acceptance batches continue) — **`IPartOfSpeech.ExceptionFeaturesOC` unchecked `.Add`** on the exception-features leaf executor (`impl-111` §5 HIGH list, ~4183).

No open PR covered this site (distinct from InflectableFeats single-writer / link pass fixes on #133).

## Diagnosis

`exception_features_execute_action` resolved the target POS and `IFsSymFeatVal`, then called `ExceptionFeaturesOC.Add(target_val)` with no per-item guard or read-back. A pythonnet/LCM rejection left the POS without the value and no `DroppedItemRecord` — the same silent-loss pattern batch 2 closed for `InflectableFeatsRC` via the link pass and for generic reference collections.

Live note (#58): `ExceptionFeaturesOC` may be absent on some LCM builds; the executor now skips with an explicit `ActionOutcome` when the collection is missing, instead of raising.

## Resolution

- Add `_try_add_exception_features_oc_member`: warning log + deduped `DroppedItemRecord` (`WRITE_FAILED`) when Add fails or read-back does not confirm membership; reuse `_infl_feat_in_collection` read-back helper.
- Route `exception_features_execute_action` through the helper; return `ActionOutcome.skipped(recorded=True)` when a drop was recorded.

## Verification

- `tests/unit/test_issue132_exception_features_oc_add.py` (new)
- `tests/unit/test_categories_exception_features.py` (happy-path execute unchanged)

**Verdict: GO** — refs #132.
