# 022 Disposition Model — Live Verification Log

**Date**: 2026-07-13
**Harness**: FLExToolsMCP `flextools_run_module` (flexicon process), using the real
`gramtrans.Lib.conflict` functions + the flexicon fork `POSOperations`.
**Target**: `Ejagham Full GT-Test` (throwaway; restored afterward). All writes were
reverted in-run.
**Scaffold**: [tests/integration/test_conflict_live.py](../../tests/integration/test_conflict_live.py)
(skip-by-default; `GRAMTRANS_E2E=1` to run).

## Scenario

Real target POS `'Adverb'`. `GetSyncableProperties` → `Name`, `Abbreviation`,
`Description` (multistring dicts keyed by WS `en`/`fr`), `CatalogSourceId` (str).
Built a source-props variant: `Name` diverged (non-empty), `Description` emptied
(`{"en": ""}`, i.e. source empty where target is non-empty).

## Results

### Disposition (op-010429129-012) — SC-004 + vocabulary

| Input | Intent | Disposition | Result |
|-------|--------|-------------|--------|
| identical | UPDATE | `SKIP` | PASS |
| diverged | UPDATE | `UPDATE` | PASS |
| diverged | OVERWRITE | `OVERWRITE` | PASS |

### UPDATE non-destructive (op-010429129-012) — SC-002 (safety core)

`apply_update_semantic(src, tgt, POSOperations, pos)` wrote **1** field:
- `Name` → updated to the source value (`'Adverb [SRC]'` / `'Adverbe [SRC]'`).
- `Description` → **preserved** (empty source never blanked the non-empty target).
- `Abbreviation` / `CatalogSourceId` → identical, skipped.

Original values restored afterward. **PASS** — this is the everyday-safe property
the feature exists to deliver.

## LIVE FINDING — SC-003 destructive-blank does NOT reproduce for multistrings

SC-003 / FR-004 state OVERWRITE blanks a target field from an empty source. Live,
this does **not** happen for multistring fields:

- `ApplySyncableProperties(pos, {"Description": {"en": ""}}, fill_gaps=False)` left
  the target `Description` **unchanged** (op-010429129-012, op-010803491-016).
- Root cause: the fork's shared loop skips empty multistring values
  **unconditionally**, before any write and regardless of `fill_gaps`:
  `for src_ws_id, text in value.items(): if not text: continue`
  (`BaseOperations.py:291`). So the OVERWRITE (source-wins `ApplySyncableProperties`)
  path cannot write an empty alt.
- The capability exists at the LCM level: a direct
  `prop_obj.set_String(handle, MakeString(""))` DID blank the alt (Text → `None`,
  `GetSyncableProperties` → `None`) — op-010650071-015.

Consequence: for the empty-source multistring case, **UPDATE and OVERWRITE are
behaviorally identical** (both preserve). The destructive contrast (SC-003) is only
demonstrated by the unit test `test_update_semantic.py` case (c), which fakes
`ApplySyncableProperties` and so does not exercise the `if not text` guard.

This is arguably safety-positive (OVERWRITE won't silently blank multistrings) but
it contradicts the spec's stated destructive contrast. Recorded as a tracked
follow-up (see STATUS.md). The scaffold encodes it as `xfail(strict=True)` so a
future fork change that writes empty alts flips the test red and forces a reconcile.

## Verdict

| Criterion | Result |
|-----------|--------|
| SC-004 true SKIP on identical item | PASS |
| Disposition vocabulary (SKIP/UPDATE/OVERWRITE) | PASS |
| SC-002 UPDATE non-destructive (diverged→source, empty-source preserved) | PASS |
| SC-003 OVERWRITE blanks from empty source (multistring) | **NOT REPRODUCED** — fork guard skips empty text (`BaseOperations.py:291`); documented follow-up |

Field-level UPDATE detection for PHONEMES / PH_ENVIRONMENT remains gated behind the
flexicon `ITsString.get_String` fix (T014, `_FLEXICON_ITSTRING_FIX_VERSION`) —
unchanged by this run.
