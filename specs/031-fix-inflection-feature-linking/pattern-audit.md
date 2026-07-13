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

## Pattern audit (T024 bug shapes)

Formal sweep-pattern audit for the two NEW bug shapes fixed in worktree commit
`9e41a1f` (Phase 6, T024 live finding) plus the P1 hardening landed in cycle-1
review follow-up commit `b5cd49b`. Paste this section into the merge PR body
(T026) alongside the T022 audit above.

### Shape (a): unguarded live `target.get_object_by_guid(...)`

The T024 live Move surfaced this shaped bug: the Move wiring post-passes
call `target.get_object_by_guid(guid)`, but the **live flexicon `FLExProject` has no
such method** — it exists only on the offline test fakes. On the live target the call
raises `AttributeError`, which `transfer.execute` swallows, so the wiring silently does
nothing (031 wired 0/13 feature→category links before the fix). Correct live resolution
(verified read-only via FLExToolsMCP): `project.ObjectRepository(ICmObjectRepository)`
→ `IsValidObjectId(guid)` guard → `GetObject(guid)`.

| File:line | Function | In/out of bug class | Status |
|---|---|---|---|
| `src/gramtrans/Lib/categories.py` `_run_infl_feature_link_pass` | 031 US1 link pass | in-class | FIXED (worktree `9e41a1f`) via new `_resolve_target_by_guid` (getter for fakes, LCM object repo live). Cycle-1 hardening (`b5cd49b`): the live-repo `except Exception` fallback now logs the caught exception + guid before returning `None`, instead of a silent swallow. |
| `src/gramtrans/Lib/categories.py:4894` `_run_171_subpass` | MSA→slot wiring (`msa-slot-wiring`) | **in-class — SUSPECT** | Calls `target.get_object_by_guid` directly (unguarded); would no-op on a live target exactly like the fixed defect. Out of 031 scope (prevention-only, FR-011) — **ticketed as HIGH-PRIORITY follow-up below; SHIP-NOW decision for 031** (031 does not touch MSA→slot or LexEntryRef wiring). |
| `src/gramtrans/Lib/categories.py:4905` `_run_171_subpass` | MSA→slot wiring (`msa-slot-wiring`) | **in-class — SUSPECT** | Second unguarded call in the same function (slot resolution). Same ticket/decision as above. |
| `src/gramtrans/Lib/categories.py:4954` `_run_post_pass_a` | LexEntryRef wiring (024/FR-340) | **in-class — SUSPECT** | Unguarded call; route through `_resolve_target_by_guid` (or equivalent) and re-validate live. Same ticket/decision as above. |
| `src/gramtrans/Lib/categories.py:4972` `_run_post_pass_a` | LexEntryRef wiring (024/FR-340) | **in-class — SUSPECT** | Second unguarded call in the same function (component-entry resolution). Same ticket/decision as above. |
| `src/gramtrans/Lib/matcher.py:347` | GUID-preserving match lookup | **out-of-class — SAFE** | `getter = getattr(target, "get_object_by_guid", None)` guard before use, with a documented fallback path when absent (fail-soft, read-only lookup). Correctly outside the bug class. |
| `src/gramtrans/Lib/preview.py:523` | Preview-time GUID lookup | **out-of-class — SAFE** | Same `getattr(target, "get_object_by_guid", None)` guard pattern as matcher.py; fail-soft, read-only. Correctly outside the bug class. |

**Decision (031 scope):** these four in-class sibling sites (`_run_171_subpass` x2,
`_run_post_pass_a` x2) are a real, confirmed latent instance of the same shaped bug —
any prior "wiring post-pass" validated only offline may not actually wire on a live
target — but they are out of 031's prevention-only scope (FR-011: 031 fixes the
inflection-feature link pass only). **SHIP 031 now**; do not block this feature's merge
on fixing sibling call sites in unrelated wiring passes. File the follow-up ticket below
instead.

**Follow-up backlog note — "Unguarded get_object_by_guid on live target in
_run_171_subpass / _run_post_pass_a (silent no-op wiring failure) — HIGH":**
route all four sibling call sites (`categories.py:4894`, `4905`, `4954`, `4972`)
through `_resolve_target_by_guid` (or an equivalent shared, guarded resolver) and add
a live regression Move covering MSA→slot wiring and LexEntryRef wiring, mirroring the
031 T024 live-probe methodology (Ejagham Mini → restored target, read-only verify via
FLExToolsMCP first). **Filed as GitHub issue
[MattGyverLee/GramTrans#28](https://github.com/MattGyverLee/GramTrans/issues/28)
(`bug`, HIGH).**

### Shape (b): bare `IFsClosedFeature(src_feat)` cast

`inflection_features_execute_action` assumed every `IFsFeatDefn` in
`MsFeatureSystemOA.FeaturesOC` is an `IFsClosedFeature`. `Ejagham Mini` contains one
`FsComplexFeature`; the unconditional `IFsClosedFeature(src_feat)` cast raised and left a
nameless closed-feature twin. FIXED (worktree `9e41a1f`): an up-front type guard emits
`Skip(UNSUPPORTED_LCM_TYPE)` and creates nothing. Cycle-1 hardening (`b5cd49b`): the
guard's `except Exception` now logs the caught cast exception (source guid + LCM class
name) before emitting the Skip, so a non-cast failure is not silently mislabeled
`UNSUPPORTED_LCM_TYPE`. Full complex/open-feature transfer remains a documented
follow-up (not in 031 scope) — see the "Third defect" note below for detail; this is
the same defect, cross-referenced here as bug shape (b) for the sweep-pattern record.

Sibling sweep (`grep -n "IFsClosedFeature(" src/gramtrans/Lib/*.py`) — every
`IFsClosedFeature(...)` call site in `Lib/`:

| File:line | Note |
|---|---|
| `categories.py:676` | The fixed guard call itself (now logs on `except`, per `b5cd49b`). |
| `categories.py:732` | `new_feat = IFsClosedFeature(new_feat)` — cast of a fresh object returned by `IFsClosedFeatureFactory.Create(...)`, already known-closed by construction. Safe. |
| `categories.py:738` | `src_feat_typed = IFsClosedFeature(src_feat)` — post-guard; only reached after the line-676 guard already proved this cast succeeds. Safe. |
| `selection.py:3361` | `closed = IFsClosedFeature(feat)` — already wrapped in its own local `try/except TypeError: closed = feat` fallback (a pre-existing, independent safe pattern; not part of this bug class and not touched by 031). |

`categories.py:676` was the only **unconditional, unguarded** cast; it is now fixed
and hardened (this cycle). No further sibling sites need this fix.

## Third defect (T024 live finding): non-closed inflection features

`inflection_features_execute_action` assumed every `IFsFeatDefn` in
`MsFeatureSystemOA.FeaturesOC` is an `IFsClosedFeature`. `Ejagham Mini` contains one
`FsComplexFeature`; the unconditional `IFsClosedFeature(src_feat)` cast raised and left a
nameless closed-feature twin. FIXED (worktree `9e41a1f`): an up-front type guard emits
`Skip(UNSUPPORTED_LCM_TYPE)` and creates nothing. Full complex/open-feature transfer is a
documented follow-up (not in 031 scope) — **filed as GitHub issue
[MattGyverLee/GramTrans#29](https://github.com/MattGyverLee/GramTrans/issues/29)
(`enhancement`).**

## Coverage note

Verified: the three SUSPECTs above are the complete set of source-handle-into-target
string writes in `Lib/`. Every other `WritingSystems.GetAll()` use
(`config_views.py:174`, `reversals.py:139`, `merge_preview.py:1053`, `references.py`
~269-415, `ws_mapping.py`, `selection_wizard.py:4459`) is a read-only enumeration for
validation/gating, not a target string write.
