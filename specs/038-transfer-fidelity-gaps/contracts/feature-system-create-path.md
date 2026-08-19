# Feature-system create path (Phase 0 research, feature 038)

Resolves research.md R7, carried verbatim from census-evidence.md section 3:
"FsFeatStrucType / FsComplexFeature -- feature-system classes with no create path?"
Measured: FsFeatStrucType 4 -> 0 and FsComplexFeature 1 -> 0 (Ejagham); 4 -> 0 and 2 -> 0
(Ngoreme). Governing requirements for a report-only class: FR-013 and SC-005.

**Instrument status: FLExToolsMCP AVAILABLE and used as the primary instrument.** Same session
as `process-morphology-create-path.md`: server 2.9.1, liblcm 11.0.0 index `exact`, flexicon
installed 4.5.0 / index 4.4.1 (`fallback_latest`, so wrapper answers were re-checked against the
working tree). Every run used `write_enabled=False`; every result reported
`write_certification.is_certified_readonly = true`. Projects: `Ejagham Mini`, `Esperanto`,
`Mbugwe LizzieHC practice`. `Target` was never opened.

Op ids: `op-043616616-018` (factory reflection, Ejagham Mini feature systems, FsFeatStruc
ownership, POS reachability), `op-043655215-019` (Ejagham Mini FsFeatStruc detail),
`op-043716755-020` (Esperanto), `op-043743387-021` (Mbugwe LizzieHC practice).

## Summary verdict

**R7's premise is refuted. Both classes have a create path, and GramTrans already implements
it.** `src/gramtrans/Lib/categories.py` carries three complete, GUID-preserving category
pipelines for this graph: `feature_struct_types_*` (`:1507-1735`, MsFeatureSystem types),
`phon_feat_types_*` (`:1738-1900`, PhFeatureSystem types), and `inflection_features_*`
(`:488-946`, which creates `FsClosedFeature`, `FsSymFeatVal` **and** `FsComplexFeature`). All
three are registered in `models.py` and dispatch-ordered in both `preview.py:246-260` and
`transfer.py:303-317`.

So `4 -> 0` is **not** a missing create path. It is a selection/closure gap: nothing declares
these categories as dependencies of the MSAs and POSes that reference them
(`feature_struct_types_dependencies` returns `()` at `categories.py:1522-1525`), and per the
brief's G2 the closure bundle is never read anyway. **Phase 5 therefore cannot stay report-only
for FsFeatStrucType** -- but the fix is a Phase 2 dependency edge, not new create code.

## 1. Does a create path exist?

**Yes, at both layers. VERIFIED.**

- MCP `find_wrappers_for_lcm`: `IFsFeatStrucType` -> `found: true`, covered by flexicon
  `InflectionFeatureOperations`; `IFsComplexFeature` -> `found: true`, same class. Both report
  `0 methods` because the 4.4.1 index does not attribute individual methods; neither is wrapped
  in `flexlibs_stable`. Contrast `IMoAffixProcess`, which returned `found: false` outright.
- flexicon working tree: `InflectionFeatureOperations.TypeCreate(self, name, abbreviation)` at
  `flexicon/flexicon/code/Grammar/InflectionFeatureOperations.py:621` creates an
  `IFsFeatStrucType` and attaches it to `MsFeatureSystemOA.TypesOC`. **But it mints a fresh
  identity**: `new_guid = System.Guid.NewGuid()`, no `guid=` kwarg, and the docstring says so
  outright ("A fresh random GUID is generated"). `FeatureCreate(self, name, type)` at `:1062`
  uses `IFsComplexFeatureFactory` with a bare `factory.Create()` -- also identity-destroying --
  and raises `FP_ParameterError` when the name already exists.
- **The flexicon wrappers are therefore unusable for a transfer** (Principle I: GUIDs are
  primary identity). The usable path is `ServiceLocator.GetService(IFsFeatStrucTypeFactory)` /
  `GetService(IFsComplexFeatureFactory)` plus `Create(Guid)` -- exactly what GramTrans already
  does at `categories.py:1631`, `:1864` and `:719`.
- flexicon records the pythonnet trap at `InflectionFeatureOperations.py:687-694`: the interface
  declares a 2-arg `Create(Guid, owner)` that pythonnet cannot bind; only the concrete factory's
  1-arg form works. Independently confirmed in section 2.

## 2. Is identity preservable?

**Yes for all 13 Fs* factories. VERIFIED live** (`op-043616616-018`, read-only reflection over
each concrete factory implementation). Every one of `FsFeatStrucTypeFactory`,
`FsComplexFeatureFactory`, `FsClosedFeatureFactory`, `FsFeatStrucFactory`,
`FsClosedValueFactory`, `FsSymFeatValFactory`, `FsComplexValueFactory`,
`FsFeatureSystemFactory`, `FsOpenFeatureFactory`, `FsNegatedValueFactory`,
`FsDisjunctiveValueFactory`, `FsSharedValueFactory` and `FsFeatStrucDisjFactory` reports exactly
`['Create()', 'Create(Guid guid)']`.

Reflection over the *interfaces* confirms the trap: `IFsFeatStrucTypeFactory`,
`IFsComplexFeatureFactory` and `IFsClosedFeatureFactory` each declare only
`Create(Guid guid, IFsFeatureSystem owner)`, and `IFsSymFeatValFactory` only
`Create(Guid guid, IFsClosedFeature owner)` -- forms the concrete types do not expose. Code must
call `Create(Guid)` and then `Add()` to the owning collection, in that order.

## 3. Owning property and object graph

Owner, VERIFIED (liblcm index, corroborated live): `IFsFeatStrucType` is owned **only** by
`IFsFeatureSystem.TypesOC`; `IFsComplexFeature`, an `IFsFeatDefn` subclass, **only** by
`IFsFeatureSystem.FeaturesOC` (observed as `FsFeatureSystem.flid49003`). Critically there are
**two feature systems**, not one: `ILangProject.MsFeatureSystemOA` and
`ILangProject.PhFeatureSystemOA`, both typed `IFsFeatureSystem`. GramTrans' two parallel
pipelines (`FEATURE_STRUCT_TYPES`, `PHON_FEAT_TYPES`) exist for exactly this reason, and any
census reporting a single `FsFeatStrucType` count is summing across both.

- `FsFeatStrucType`: `Name`, `Abbreviation`, `Description`, `CatalogSourceId` (writable String),
  and `FeaturesRS` -- a reference *sequence* to `IFsFeatDefn`, i.e. to members of the same
  system's `FeaturesOC`. There is no `Default`-ish member on the type; `DefaultOA`
  (`-> IFsFeatureSpecification`) lives on `IFsFeatDefn`, and was `None` on all 5 Ejagham
  features.
- `FsComplexFeature`: one own property, `TypeRA -> IFsFeatStrucType`. Its structure is entirely
  by reference -- it names a type whose `FeaturesRS` lists the component features.
- Sibling `FsClosedFeature` owns `ValuesOC -> IFsSymFeatVal` (observed
  `FsClosedFeature.flid50001`).
- Instance side: `FsFeatStruc` has `TypeRA -> IFsFeatStrucType` plus
  `FeatureSpecsOC -> IFsFeatureSpecification`; `FsClosedValue.ValueRA -> IFsSymFeatVal`;
  `FsComplexValue.ValueOA -> IFsAbstractStructure` (a nested `FsFeatStruc`);
  `IFsFeatureSpecification.FeatureRA -> IFsFeatDefn`.

## 4. Live corroboration

All three sanctioned projects contain these classes. This is not a null result.

| Project | MsFeatSys TypesOC | MsFeatSys FeaturesOC | PhFeatSys types/features | FsFeatStruc |
|---|---|---|---|---|
| `Ejagham Mini` | 3 (BantuNounClass, Noun agreement, Infl) | 5 = 4 closed + **1 FsComplexFeature** | 0 / 0 | 42 |
| `Esperanto` | 4 (Infl, Article/Adjective/Noun agreement) | 11 = 8 closed + **3 FsComplexFeature** | 0 / 0 | 102 |
| `Mbugwe LizzieHC practice` | 6 | 5 = 4 closed + **1 FsComplexFeature** | **1 (Phon) / 17 closed** | 429 |

Observed structure (`op-043616616-018`): Ejagham's `FsComplexFeature` "noun
agreement(Bantu_noun_class, number)" `a45b03d4-...`, `CatalogSourceId='cNounAgr'`,
`TypeRA -> FsFeatStrucType "Noun agreement" 135f8aa2-...`, whose `FeaturesRS[2]` lists
`FsClosedFeature "Bantu_noun_class"` (21 `FsSymFeatVal`) and `FsClosedFeature "number"` (2).
Mbugwe's is "noun agreement(number)" `df4a248b-...` -> type "Noun agreement". Types carry
`CatalogSourceId` values (`tNounAgr`, `Infl`, `fBantuClass`, `fNum`).

`Esperanto` shows the nested case: of 102 `FsFeatStruc`, 49 are owned by
`FsComplexValue.flid53001` (`ValueOA`) and 51 have `TypeRA` unset -- so nesting is real and
`TypeRA` is optional one level down.

## 5. Reachability from what Phase 1 restores

R7 predicted "the bulk of the Fs* cascade hangs off the POSes R1 restores". **Refuted as
stated, and the correction makes the dependency stronger, not weaker** (`op-043616616-018`,
`op-043655215-019`).

`FsFeatStruc` ownership in `Ejagham Mini` (42 total): `MoStemMsa.flid5001001` (`MsFeaturesOA`)
x23, `MoInflAffMsa.flid5038001` (`InflFeatsOA`) x17, `PartOfSpeech.flid5049010` x2 -- so
**40 of 42 hang off MSAs, only 2 off POS.** `Mbugwe` (429) spreads wider: MSAs 216,
`PhNCFeatures.flid5094001` 112, `PhPhoneme.flid5092002` 42, `CmBaseAnnotation.flid34008` 39,
`PartOfSpeech.flid5049010` 19, `MoAffixAllomorph.flid5027001` 1. Owner class and flid are
VERIFIED; the property names in parentheses are INFERRED from the index's owning-property table,
and `PartOfSpeech.flid5049010 = ReferenceFormsOC` by elimination -- the same op measured
`DefaultFeaturesOA=0`, `InherFeatValOA=0`, `EmptyParadigmCellsOC=0`, `ReferenceFormsOC
members=2`.

The decisive measurement: **42 of 42 Ejagham `FsFeatStruc` have `TypeRA` set** (38 to
"BantuNounClass", 4 to "Infl"), and all 63 of their `FeatureSpecsOC` members are `FsClosedValue`
whose `FeatureRA` resolves to a `FsClosedFeature` owned by `FsFeatureSystem.flid49003` and whose
`ValueRA` resolves to a `FsSymFeatVal` owned by `FsClosedFeature.flid50001`. Neither the type nor
the feature is owned by the MSA or the POS -- both are project-level objects the MSA merely
points at.

Consequence: Phase 1 restoring 1,949 `MoStemMsa` + 134 `MoInflAffMsa` also restores their
`MsFeaturesOA` / `InflFeatsOA` feature structures, each carrying a `TypeRA` and value references
into a feature system a blank destination does not have. Without the types and features present
first, every one of those references is unsatisfiable, which under Principle I and FR-013 must
fail loudly or be reported, never silently blanked.

## Consequence for Phase 5 scoping

**Phase 5 can remain report-only for `FsComplexFeature`, but NOT for `FsFeatStrucType`.**

- `FsFeatStrucType` becomes a **hard prerequisite of Phase 1**. Nothing new needs writing:
  `feature_struct_types_*` and `phon_feat_types_*` already create it GUID-preserved. What is
  missing is a closure edge -- MSA/POS -> the `FsFeatStrucType` its `FsFeatStruc.TypeRA` names,
  and MSA/POS -> the `FsClosedFeature` / `FsSymFeatVal` its `FeatureSpecsOC` reference -- which
  is Phase 2's job. Both feature systems must be walked, not only the morphosyntactic one.
- `FsComplexFeature` (1 to 3 objects per project) is referenced only *by* `FsFeatStrucType`
  membership, and no `FsFeatStruc` in any sanctioned corpus reaches it directly. It can stay
  report-only under FR-013 / SC-005 provided each non-transferred instance gets a report line
  naming the class and its GUID, and provided `inflection_features_execute_action` keeps
  handling it when the category *is* selected.
- SC-005's "either zero or accounted for by a line in the run report" is satisfiable for both,
  but only if the census counts the two feature systems separately; a single summed count cannot
  distinguish "type missing" from "type landed in the wrong system".

## Open questions

- **`CatalogSourceId` as a natural key.** Types and features carry stable catalog ids
  (`tNounAgr`, `fNum`, `Infl`). Whether FR-005's roster should add `FsFeatStrucType` /
  `FsClosedFeature` keyed on `CatalogSourceId` is a live question for 035's roster, unsettled
  here -- note it was `None` on 2 of 3 Ejagham types, so it is not unique-by-construction.
- **Which feature system a type belongs to** is not derivable from the type itself, only from the
  owning `TypesOC`. A transfer must carry that provenance or it can land a phonological type in
  the morphosyntactic system. Whether the two existing pipelines keep this straight across a
  re-run was not tested.
- **`TypeRA` optionality.** 51 of 102 Esperanto `FsFeatStruc` have it unset, all nested under
  `FsComplexValue.ValueOA`. Whether LCM validation requires `TypeRA` on a top-level
  `FsFeatStruc` (all 42 Ejagham top-level ones had it) is unverified.
- **Why the measured runs did not select these categories.** The pipelines exist and are
  dispatch-ordered; whether the selection wizard surfaces `FEATURE_STRUCT_TYPES` /
  `PHON_FEAT_TYPES` at all, or whether they were merely left unchecked, was not investigated and
  should be before Phase 2 designs the edge.
- **`PhFeatureSystemOA` on a blank target.** Mbugwe populates it (1 type, 17 features); Ejagham
  and Esperanto leave it empty. Whether a freshly created FLEx project ships a non-empty starter
  here -- relevant to FR-002's duplicate-vs-drop problem -- is unverified.
