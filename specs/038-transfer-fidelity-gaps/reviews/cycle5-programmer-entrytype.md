# T123/T124 LexEntryType -1/-1 -- mechanism, not two absences

**Date:** 2026-09-18 (read-only investigation, no transfer run, no writes)

## 1. Mechanism per object -- IDENTICAL, not two singletons

Both objects are plain `ILexEntryType` members of `LexDb.VariantEntryTypesOA`
(not `ComplexEntryTypesOA`), which in vanilla FLEx legitimately mixes plain
`LexEntryType` items (Dialectal Variant, Spelling Variant, Free Variant,
Unspecified Variant) with `LexEntryInflType` items ("Irregularly Inflected
Form" and its children). The category pipeline routes by **which possibility
list the object lives under**, not by the object's own class:

- `variant_types_enumerate_source` (`categories.py:3494`) walks
  `VariantEntryTypesOA` wholesale via `_walk_possibilities_via_lexdb`
  (`:3473`) -- every member, `LexEntryType` and `LexEntryInflType` alike.
- `variant_types_plan_action` (`:3567`) first tries GUID-equality against the
  target (`_plan_gold_reserved_edit`, `:899`, `tgt_obj = _find_target_obj_by_guid(...)`,
  `:958`). The four canonical defaults share the SAME GUID in every fresh
  FLEx project (confirmed: `Dialectal Variant`=`024b62c9...`,
  `Free Variant`=`4343b1ef...` etc. are byte-identical across ngoreme,
  mbugwe, and the destination probes), so they are found present and never
  fall through to creation. `Perfective` (ngoreme, GUID `e7983f52-...`) and
  `Periphrastic Form` (mbugwe, GUID `99e0cab9-...`) carry project-local GUIDs
  absent from a fresh target, so both fall through the natural-key match
  (`:3604`) to the plain `PlannedAction` at `:3611-3617`.
- `variant_types_execute_action` (`:3620-3732`) then **unconditionally**
  creates via `ILexEntryInflTypeFactory` (`:3681`, `factory.Create(parsed_guid)`
  at `:3688`) -- there is no branch on `src_obj`'s actual `ClassName`.

Result, evidenced by GUID: `e7983f52-77a7-4f0b-aa31-84678672e42d`
("Perfective") is `LexEntryType` in source
(`probes/t124/t124-supplements-Ngoreme-FLEx.json:135-140`) and arrives at
destination reclassified `LexEntryInflType`, same name, same nesting
(`probes/t126/owner-probe-GT038-T126-Ngoreme.json:281-286`).
`99e0cab9-f284-45fb-84a5-4cb2516d0bf4` ("Periphrastic Form") is `LexEntryType`
in source (`probes/t124/t124-supplements-Mbugwe-LizzieHC-practice.json:107-112`)
and arrives `LexEntryInflType` named `"***"`
(`probes/t126/owner-probe-GT038-T126-Mbugwe.json:282-283`).

The count math confirms the object is **not lost**: ngoreme `LexEntryType`
13→12 (-1) exactly offsets `LexEntryInflType` 3→4 (+1); mbugwe `LexEntryType`
12→11 (-1) exactly offsets `LexEntryInflType` 4→5 (+1). Zero net objects
missing -- this is a **create-time misclassification**, a fifth shape not in
the given four (never enumerated / not planned / refused / demoted): the
object IS enumerated, IS planned, IS created, GUID and nesting preserved --
but instantiated as the wrong LCM subclass, so it stops counting as
`LexEntryType` at all.

## 2. One mechanism or two: ONE

Same code path (`variant_types_execute_action`), same root cause (factory
choice keyed to possessing list, not object class), same evidence shape on
both pairs. Not two rulings.

## 3. RECOMMENDATION: FIX

**Patch site:** `categories.py:3675-3688`, before selecting the factory. Cast
`src_obj` (already available) and branch on its `ClassName`: if
`"LexEntryInflType"`, keep `ILexEntryInflTypeFactory`; otherwise use
`ILexEntryTypeFactory` (the same factory `complex_form_types_execute_action`
already uses at `:3842`). `complex_form_types_execute_action` (`:3786-3888`)
is the sibling site: `ComplexEntryTypesOA` shows no `LexEntryInflType`
members in this corpus, but the same list-not-class routing exists there
(`:3793`, `:3842-3846`) and should get the same defensive branch for
symmetry, per the sweep-pattern discipline already applied to the T123
owner-cast fix three sites over.

**Pinning test:** unit test with a fake `VariantEntryTypesOA` containing one
`_FakeLexEntryType` (plain, non-Infl, project-local GUID) alongside a
GOLD-GUID `_FakeLexEntryInflType`; assert `variant_types_execute_action`
creates the plain item via `ILexEntryTypeFactory.Create`, not
`ILexEntryInflTypeFactory.Create`. A second parametrised case for the
(currently unobserved) inverse under `complex_form_types_execute_action`.

## 4. What a live verification must measure

Everything above is reconstructed from static probe/census artifacts, not a
fresh run. Before closing T123's line: (a) restore `Target` from a known
clean backup, run a single transfer for ngoreme then re-restore and run for
mbugwe (no reused/stale Target between runs -- `Periphrastic Form` arriving
nameless as `"***"` while `Perfective` arrived correctly named is unexplained
by this mechanism alone and may be residue from an earlier partial run
against an unrestored Target, not a live behavior of `apply_carrier_b`); (b)
after the fix, confirm `LexEntryType` reads exact-class MATCHED (13/13,
12/12) AND `LexEntryInflType` reads exact-class MATCHED (3/3, 4/4) on both
pairs, not just the net cancellation; (c) confirm nesting is preserved for
`Perfective` (parent `Irregularly Inflected Form` via `SubPossibilities`)
under the corrected `ILexEntryTypeFactory` path, since owner-resolution logic
is shared and untouched by this fix.
