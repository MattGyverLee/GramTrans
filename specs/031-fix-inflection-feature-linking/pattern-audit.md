# Pattern Audit: source-handle-into-target WS bug class (T022)

**Feature**: 031-fix-inflection-feature-linking | **Date**: 2026-07-13

This is the sweep-pattern audit required for the shaped bug fixed in US2 (Defect 2,
nameless features). Paste this section into the `031-fix-inflection-feature-linking`
merge PR body (T026) under a **Pattern audit** heading.

## Bug shape

Build `{Id: Handle}` (or `{Handle: Id}`) from `source.WritingSystems.GetAll()`, then
call `tgt_prop.set_String(<source_handle>, MakeString(text, <source_handle>))` —
writing a **source** WS handle straight into a **target** multistring with no
source→target WS-Id translation. LCM handles are per-project integers, so the string
lands on a wrong/absent target WS and renders as a bare GUID.

**Correct pattern**: the fixed helper `_copy_multistrings_ws_mapped`
(`src/gramtrans/Lib/categories.py:576`) or
`ApplySyncableProperties(..., ws_map=ws_mapping)` — both key by WS **Id** and resolve
the target handle internally.

## SUSPECT — same bug, not fixed by this feature (prevention-only, FR-011)

| File:line | Function | Confidence | Note |
|---|---|---|---|
| `src/gramtrans/Lib/categories.py:1388-1400` | `stem_names_execute_action` | SUSPECT (high) | Builds `all_ws = {Id: Handle}` from source and writes each SOURCE handle directly into the target `IMoStemName` Name/Abbreviation/Description; the received `ws_mapping` is never used for the string copy. Exact sibling of the fixed defect. |
| `src/gramtrans/Lib/categories.py:5265-5276` | `slots_execute_action` | SUSPECT (high) | Same `{Id: Handle}` construction on `IMoInflAffixSlot` Name/Description; SOURCE handle written into target, `ws_mapping` ignored. |
| `src/gramtrans/Lib/transfer.py:2392-2436` | `_execute_gold_reserved_merge` | SUSPECT (high) | GOLD-reserved owned-write merge fills empty Name/Abbreviation/Description on the target using SOURCE handles; the function takes no `ws_mapping`/`ws_map` param at all, so no translation is possible. Same class, different module. |

These three are the **only** raw `set_String`/`set_MultiString` calls in `Lib/` that
iterate SOURCE writing-system handles. They are **out of 031's scope** (031 is
prevention-only for the *inflection-feature* defect) and should be filed as a
follow-up spec so the same WS-mapping fix (route through `_copy_multistrings_ws_mapped`
or add a `ws_map` param) is applied globally.

## SAFE (route through ws_map / target-resolved handle)

- `categories.py:576` `_copy_multistrings_ws_mapped` — corrected reference impl (this feature).
- `categories.py:473` `gram_categories_execute_action` (POS) — `ApplySyncableProperties(..., ws_map=ws_mapping)`.
- `inflection_classes` (1245), `adhoc_compound_rules` (2516), `affix_templates` (5410),
  `phonological_features` (5768), `phonemes` (5826), `natural_classes` (5906),
  `ph_environment` (5998), `strata` (6056), `phonological_rules` (6390) — all via
  `ApplySyncableProperties(..., ws_map=ws_mapping)`.
- `stems_execute_action` (5536) / `affixes_execute_action` — delegate to the LexEntry
  owned-closure which calls `ApplySyncableProperties(..., ws_map=ws_map)`
  (categories.py:4500/4573/4695).
- `reversals.py:519-520` `_set_reversal_form_alt` — `ws_handle = target.WSHandle(ws_id)`
  (resolved from the TARGET by Id, never a raw source handle).

## N/A (reference-only wiring, or writes a computed tag / default-WS string)

- `exception_features_execute_action` (1504) — GUID-resolves an existing `IFsSymFeatVal`
  and adds a reference into `POS.ExceptionFeaturesOC`; no string write.
- `variant_types` (1670), `complex_form_types` (1805), `semantic_domains` (1916) —
  create + `apply_carrier_b(new_obj, ws, tag)`; no per-WS source string copy. (Side
  note, out of scope: these appear not to copy source Name/Abbreviation at all.)
- `residue.py:235`/`:264` (`apply_carrier_a`/`_b`) — `set_String(ws, ...)` with
  `ws = cache.DefaultAnalWs` (TARGET handle), text = computed residue tag.
- `transfer.py:836` `_create_slot_with_guid` — `Name.set_String(ws, ...)` with
  `ws = cache.DefaultAnalWs` (TARGET handle) and a plain passed-in name.
- `transfer.py:807` — `ApplySyncableProperties(new_template, src_props)` WITHOUT
  `ws_map`; keys by Id internally so not a raw-handle defect (noted as a missing-remap
  nuance only).

## Coverage note

Verified: the three SUSPECTs above are the complete set of source-handle-into-target
string writes in `Lib/`. Every other `WritingSystems.GetAll()` use
(`config_views.py:174`, `reversals.py:139`, `merge_preview.py:1053`, `references.py`
~269-415, `ws_mapping.py`, `selection_wizard.py:4459`) is a read-only enumeration for
validation/gating, not a target string write.
