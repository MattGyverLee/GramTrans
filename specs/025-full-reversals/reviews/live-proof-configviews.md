# Config-View Copy — Live Proof (S4 gap closed) — 2026-07-16

Closes the S4 live-proof gap in `HANDOFF.md`: the dictionary/reversal
configuration-view copy (`Lib/config_views.py`, feature 025 US3) had only its
**SKIP** path live-proven (the Ejagham pair carries one byte-identical
`ReversalIndex/en.fwdictconfig` and no `Dictionary` config). ADD / OVERWRITE /
missing-reference reporting were offline-only. This proof exercises all three on
real flexicon handles.

## Method

- **Disposable projects** (real Ejagham Mini / GT-Test untouched): `EjaghamCfgSrc`
  (source, restored from `Ejagham Mini.fwbackup`) + `Target` (restored from
  `Target 2026-07-06 0218.fwbackup`), headless zip-extract restore.
- **Constructed fixture** forcing every path:
  - `Dictionary/GT-Export-Test.fwdictconfig` in source, absent in target → **ADD**.
  - `ReversalIndex/en.fwdictconfig` present in both but differing (version 27 vs
    26) → **OVERWRITE** (+ `.gtbak` backup of the pristine target bytes).
  - the ADD file references `writingSystem="zz-XX"`, `style="GT-NoSuchStyle-QZ"`,
    and custom field `GTNoSuchField-QZ` — all absent in the target → **3
    missing_refs**, checked against the LIVE target WS / Styles / CustomFields.
- **Driven through FLExToolsMCP `run_module`** against the real `Target` handle
  (the live custom-field surface); source supplied via a directory stub (config
  views only needs the source folder path — no LCM). `config_views.plan_config_
  views` / `apply_config_views` called directly (the Preview→Move wiring at
  `preview.py:392` / `transfer.py:519` is already engine-proven by the S4 SKIP
  result). Also runnable standalone via `scratchpad/run_configview_live.py`.

## Result — 17/17 PASS

| Path | Result |
|---|---|
| ADD planned as ADD; file lands byte-for-byte on target | PASS |
| OVERWRITE planned; source bytes win; `.gtbak` holds pristine pre-overwrite bytes | PASS |
| missing_refs = WS + style **+ custom field** (all 3), vs live target sets | PASS |
| magic `vernacular` WS token NOT falsely reported | PASS |
| never-silent: all 3 missing refs reach the run `dropped` collector | PASS |
| idempotent re-plan → both files SKIP; missing_refs still reported on SKIP | PASS |

## Real bug found and fixed (live-vs-fake divergence)

**First run (direct flexicon) FAILED 15/18** — the custom-field missing-ref was
silently dropped. Root cause: `config_views._target_custom_field_names` called
`CustomFieldOperations.GetAllFields()` with **no argument**, but the live method
requires `owner_class` (confirmed via FLExToolsMCP `get_object_api`:
`GetAllFields(owner_class)`, raises on None/omitted). The `TypeError` was swallowed
into `None`, and `None` means "surface unknown, don't report" — so a config
referencing a target-absent custom field was silently copied. Offline fakes
exposed a no-arg `GetAllFields()`, so unit tests never caught it.

**Fix** (`fix(config-views)` @ `5aaaa0c`, merged `063859f`): enumerate the four
custom-field owner classes (`LexEntry`, `LexSense`, `LexExampleSentence`,
`MoForm` — mirrors `categories._CUSTOM_FIELD_OWNER_CLASSES`) and union labels;
return `None` only when every class read fails.

**Regression lock:** both config-view test fakes now require the `owner_class`
arg like live (a no-arg reversion fails the suite); added
`test_missing_ref_scan_does_not_report_present_custom_field` (positive union
path). Offline config-view cluster 76 passed.

**Pattern audit:** `config_views.py:202` was the ONLY no-arg `GetAllFields()` in
`src/`; `categories.py:1104` and `merge_preview.py:1562` already pass
`owner_class`. Two test fakes carried the matching no-arg shape and were
corrected. No other siblings.

## Residue

`Target` restored clean after the proof. `EjaghamCfgSrc` left on disk (disposable;
safe to delete, or re-restore from `Ejagham Mini.fwbackup`).
