# T114-T118 -- every row was a bucket

**Date:** 2026-08-26
**Tasks:** T114, T115, T116, T117, T118 (Phase 10 / US6, Wave 1)
**Instrument:** `debug/run038_phase10_owner_probe.py` (read-only)
**Artifacts:** `specs/038-transfer-fidelity-gaps/probes/owner-probe-*.json` (six)
**Projects read:** `Ejagham W Mini`, `Ngoreme FLEx`, `Mbugwe LizzieHC practice`
and their three T078 destinations. **Nothing was written.** `Ngoreme Target`
was not opened.

## The one sentence

Five tasks named five classes; not one of the five turned out to be a thing.
Each is a BUCKET -- a class name over a set of objects with different owners,
different routes, and in three cases different fates -- and in every case the
owner, not the class, is what decides whether the object transfers.

## Why one probe answered five tasks

T114/T115/T116/T118 ask one question in four costumes: *for class X, who owns
the instances?* So the probe asks it once per project and lets each task read
its own rows. That is not a shortcut, it is what makes the four answers
mutually consistent: "the contexts are lost because their owner is lost" is
arithmetic when the contexts' owner counts and the owner's own count come out
of the same pass, and inference when they do not.

**The probe validates against the census before it is believed.** Every
`exact_class` source count reproduces the corresponding T078 `source_count`
exactly, on all three pairs and all sixteen classes. An instrument that
disagreed with the census on the source side would have been measuring
something else.

**One methodological note, because it bit immediately.** `OwningFlid` and
`Owner` are declared on `ICmObject` and are INVISIBLE on the `ICmObjectOrId`
proxies the repositories yield; the first run failed the MCP casting gate and
needed `ICmObject(o)`. That is T088's defect exactly -- a cast that was
missing -- and it is the reason this probe reports the raw `flid` beside every
resolved field name. All 21 flids below were then re-resolved against the LCM
metadata cache directly, so no field name here is a guess.

## PROVENANCE, AND IT IS NOT UNIFORM

The destination projects are live, not frozen at the T078 snapshot. Compared
row by row against the T078 artifacts, **exactly five rows have drifted, all
on Ejagham, and all exactly the classes T107 touched**:

| row | T078 | live now |
|---|---|---|
| `MoAffixProcess` | 0 | **12** |
| `PhSequenceContext` | 1 | **35** |
| `PhSimpleContextNC` | 4 | **40** |
| `PhSimpleContextSeg` | 9 | **35** |
| `PhSimpleContextBdry` | 1 | **10** |

Ngoreme's and Mbugwe's destinations are byte-consistent with T078 on all
sixteen rows. So `GT038 Ejagham After` was re-run after T107 landed and the
other two were not. **T107's fix therefore WORKS and this is the measurement
of it**: the affix-process route went from near-total loss to 12 of 13 rules
and 92 of 97 contexts. It also means the Ejagham figures in the T078 artifact
for those five rows are HISTORICAL, and W2 must be scoped against the live
reading, not against them. Everything else below is current on all three pairs.

## T114 -- the `Fs*` cascade: ONE loss, NINE owners, and the two that were guessed

**`FsClosedValue` is not a second loss. It is the first one's shadow.** On all
three pairs it is 100% owned by `FsFeatStruc.FeatureSpecs`: 994/994,
2540/2540, 1352/1352. There is no route to a lost `FsClosedValue` that does not
run through a lost or hollow `FsFeatStruc`. T119 has one target, not two.

**The definitions/structures inversion R7 noticed has a structural cause.**
`FsClosedFeature` (owned by `FsFeatureSystem.Features`) and `FsSymFeatVal`
(owned by `FsClosedFeature.Values`) live in the feature SYSTEM, which the
engine transfers as a category -- and they are MATCHED on all three pairs.
`FsFeatStruc` lives on the CONSUMERS. The consumers are what fails.

Per-owner, source -> destination:

| owner (flid) | ejagham | ngoreme | mbugwe |
|---|---|---|---|
| `MoStemMsa.MsFeatures` (5001001) | 117 -> **0** | 782 -> **0** | 104 -> **0** |
| `FsComplexValue.Value` (53001) | -- | 825 -> **0** | -- |
| `MoInflAffMsa.InflFeats` (5038001) | 86 -> 86 | 38 -> 18 | 78 -> 78 |
| `PhPhoneme.Features` (5092002) | 41 -> 20 | 41 -> 21 | 42 -> 23 |
| `PhNCFeatures.Features` (5094001) | 15 -> 15 | 41 -> 41 | 112 -> 112 |
| `PartOfSpeech.ReferenceForms` (5049010) | 10 -> 10 | 44 -> **0** | 19 -> 18 |
| `CmAnnotation.Features` (34008) | -- | -- | 39 -> **0** |
| `MoDerivAffMsa.FromMsFeatures` (5031001) | -- | -- | 17 -> **0** |
| `MoDerivAffMsa.ToMsFeatures` (5031002) | -- | -- | 17 -> **0** |
| `MoAffixAllomorph.MsEnvFeatures` (5027001) | -- | -- | 1 -> **0** |

Four findings, in order of how much they change the work:

1. **`MoStemMsa.MsFeatures` is zero on every pair** -- 1,003 objects, the
   largest single block in the residue. And `MoStemMsa` itself is MATCHED
   (153/153, 139/139). **The MSAs arrive; they arrive HOLLOW.** Destination
   `MoStemMsa` feature-structure counts are `{(none): 153}`, `{(none): 1953}`,
   `{(none): 139}` -- not one stem MSA in any destination carries a feature
   structure. This is feature 037's natural-class defect in a new place, and
   the census cannot see it because the census counts MSAs.
2. **`FsComplexValue.Value` is 825 objects on Ngoreme and no task text names
   it.** It is Ngoreme's single largest owner and it is a NESTED feature
   structure (`FsComplexValue.Value -> FsAbstractStructure`, owning-atomic).
   Ngoreme's -1691 reconciles exactly as 825 + 782 + 44 + 20 + 20. A fix scoped
   to "MSA feature structures" would leave half of Ngoreme's loss standing.
3. **The task's own three guesses were 1 for 3.** It proposed "MSA
   `FeaturesOA`, inflection-template feature structures, or `PhFeatureConstraint`".
   MSA features: correct, and the biggest. Inflection templates: they own no
   `FsFeatStruc` at all. `PhFeatureConstraint`: owns **zero** -- it is itself
   owned by `PhPhonData.FeatConstraints` and belongs to T116, not here.
4. **`MoInflAffMsa.InflFeats` is perfect on two pairs and short on one**
   (86/86, 78/78, 38->18). So this is not a blanket "structures do not
   transfer" -- the inflectional-affix path demonstrably works, which makes it
   the reference implementation T119 should copy rather than reinvent.

**`PhPhoneme.Features` loses ~20 on every pair and the shape says why.** The
destination splits `{(none): 23, FeaturesOA: 20}` (ejagham) -- 23 is exactly
the starter phoneme count. **The CREATED phonemes get their features; the
phonemes MATCHED to the starter inventory do not.** That is the enrichment gap
(US4), measured from a new angle.

## T115 -- `CmPossibility`: 302 of the 308 were never lost

The task said to ask "what are they" before "why are they lost", and it was
right to. `subtree_total` is 3042 against `exact_class` 308 -- the T023b
polymorphism, still there.

**The destination reads 302, not 0.** The census row says
`destination_count_net: 0` because it subtracts a flat 302-object starter
baseline (`starter_subtraction_basis: baseline_gross`), and it already carried
a note bounding the real loss at "AT MOST 6". The probe converts that bound
into a measurement by naming the lists.

The row spans ~19 distinct possibility lists. The overwhelming majority are
canonical FLEx starter lists, identical on both sides -- `ChartMarkers` (67),
`DomainTypes` (55), `TextMarkupTags` (52), `UsageTypes` (26), `TimeOfDay`,
`RecTypes`, `Roles`, `Education`... The actual deltas:

| pair | real loss | `difference_raw` |
|---|---|---|
| ejagham | `GenreList` -6 | **-6** |
| ngoreme | `Scripture.NoteCategories` -115, `CheckLists` -5, `GenreList` -3, `DialectLabels` -2, `Status` -1, `MoMorphData.ProdRestrict` -1; surplus `ChartMarkers` +30, `ExtendedNoteTypes` +1 | **-96** |
| mbugwe | `LexDb.Languages` -15, `ChartMarkers` -10, `GenreList` -5, `ProdRestrict` -3, `ConstChartTempl` -1; surplus `ExtendedNoteTypes` +1 | **-33** |

**The per-list deltas sum to `difference_raw` exactly on all three pairs.**
Two independent derivations agreeing to the object is what makes this an
attribution rather than a story.

**Only one of these lists is unambiguously grammatical: `MoMorphData.ProdRestrict`**
(productivity restrictions), and it is 1 and 3 objects. The rest are Scripture
notes, dialect labels, genres and chart markers -- content this feature's
Assumptions do not claim. T122 must decide list by list, and "close
`CmPossibility`" is not a thing that can be done.

## T116 -- the contexts: three routes, and each corpus uses a different one

**The route profile is completely different per corpus, which is exactly why
the task demanded per-route attribution:**

| route | ejagham | ngoreme | mbugwe |
|---|---|---|---|
| affix-process (`MoAffixProcess.Input`) | 97 -> 92 | 1 -> 1 | 23 -> 23 |
| phonological-rule (`PhSegRuleRHS.*`, `PhSegmentRule.StrucDesc`) | 19 -> 18 | 68 -> 58 | 157 -> 111 |
| shared pool (`PhPhonData.Contexts` + `.FeatConstraints`) | 19 -> 16 | 105 -> 49 | 171 -> 104 |

**T107's route is closed.** Affix-process is ±0 on Ngoreme and Mbugwe and
-5 on Ejagham (tracking `MoAffixProcess` 13 -> 12, one rule short). T120's
task line predicted exactly this and it holds.

**The remaining loss is the other two routes, and the shared pool is the
larger.** `PhFeatureConstraint` is owned SOLELY by `PhPhonData.FeatConstraints`
-- a project-level shared pool, not a rule child -- and at -47 / -32 it is the
single biggest context-family loss. This is the "shared project-level contexts"
the recorded Phase-4b decision already anticipated, and it is where the
recorded decision to CO-CREATE `PhPhonData.ContextsOS` rather than register a
closure edge applies.

**`PhRegularRule` is MATCHED on all three (6/6, 21/21, 39/39) while its
`RightHandSides` are short on two** (21 -> 18, 39 -> 28). The rules arrive with
fewer right-hand sides, and each lost RHS takes its `LeftContext` /
`RightContext` / `StrucChange` children with it -- on Mbugwe, 11 lost RHS
account for 35 lost child contexts. **`PhSegmentRule.StrucDesc` is ±0
everywhere**, so the rule's own structural description is fine. The defect is
specifically an owned child COLLECTION on a matched parent: US4's enrichment
shape again, and the same `_plan_gold_reserved_edit` widening the recorded
decision describes.

## T117 -- `PhCode`: cause confirmed, and the route is in-tree

**Confirmed against flexicon 4.5.2**, which is what the task asked (the
omission could have moved since CP-4 was written; it has not).
`PhonemeOperations.GetSyncableProperties` returns exactly
`['BasicIPASymbol', 'Description', 'Features', 'FeaturesGuid', 'Name']`.
`CodesOS` is absent. `ApplySyncableProperties` handles the multistrings,
`BasicIPASymbol` and the feature specs -- and nothing else. Nothing carries
codes, and `grep` finds no `AddCode` / `CodesOS` write anywhere in `src/`.

The destination reads **25 on all three pairs**, and the probe explains the
number exactly: `PhTerminalUnit.Codes` splits by runtime owner into 23 codes on
starter `PhPhoneme`s and **2 on `PhBdryMarker`s**. 23 + 2 = 25 = the starter
baseline. Not one code was created, on any pair.

**Route: IN-TREE, no flexicon floor bump.** `PhonemeOperations` exposes
`AddCode(phoneme, representation, wsHandle=None)`, `GetCodes`, `FindCode`,
`ReplaceCode` and `RemoveCode` on 4.5.2 already. (Worth recording as a
process note: a filtered `get_object_api` call reported `total_methods: 2` and
briefly made this look like an upstream job -- the filter narrows the count,
not just the listing. The unfiltered class has 25 methods.)

**Two scope facts a naive fix would miss.** The 2 `PhBdryMarker` codes are
MATCHED (2 -> 2) and must not be swept into a phoneme-scoped loop that would
duplicate them. And the loss covers BOTH created phonemes and phonemes matched
to the starter inventory, so T121 is a create-path change AND an enrichment
change, exactly like `PhPhoneme.Features` above.

## T118 -- the stragglers: the `MoStemMsa` question has a third answer

The task expected `MoStemMsa -1` to prove one of two readings stale. **Neither
is stale.** P1 requires `MoStemMsa` MATCHED; it IS matched on ejagham (153/153)
and mbugwe (139/139), and Ngoreme is short by exactly one object under
`LexEntry.MorphoSyntaxAnalyses` (1951 -> 1950). T038's P1 reading and T078's
row are both correct -- they measure different pairs. The genuine finding is
the one in T114: every destination `MoStemMsa` is hollow. **Count-matched,
content-empty**, which no counts-only gate can see. That cost one object to
settle, as predicted.

* **`LexEntryType`** -- census says -12 / -12; the probe says **-1 / -1**
  (13 -> 12, 12 -> 11). The -12 is the gross starter basis again. **And there is
  a defect the count hides**: sibling `LexEntryInflType` is count-MATCHED
  (7 -> 7) while its items MOVE between `CmPossibility.SubPossibilities` and
  `CmPossibilityList.Possibilities` -- ejagham goes 6 nested / 1 top-level to
  2 nested / 5 top-level. **Variant types are arriving as siblings of their
  parent instead of children of it.** The census is structurally blind to this.
* **`LexReference`** -- ngoreme 5 -> 0, owned by `LexRefType.Members`. R7's
  "5 -> 0" reproduces exactly and is unchanged. Lexical relations.
* **`MoAffixProcess`** -- ejagham **13 -> 12, not 13 -> 0**. Post-T107. One
  rule short, and it is the one that also costs 5 affix-process contexts.
* **`CmFile` / `CmFolder` -- two different things wearing one class name**,
  the T115 lesson again. Mbugwe's 2,173 files are owned by `CmFolder.Files`
  under `LangProject.Pictures` and `LangProject.Media`. Ngoreme's 2 are owned
  by **`ScrImportSFFiles.Files`** -- Scripture import source files, not media
  at all. T109's measured conclusion (`CmPicture` 0 -> 0, so this is not sense
  pictures) is CONFIRMED and now has field names behind it.

## What this changes about W2

Every W2 line was written before its probe and four of the five needed
rewriting. In particular: T119 aims at one class with nine owners (not two
classes); T121 is in-tree and needs an enrichment half; T122 cannot close
`CmPossibility` as such and is now list-by-list; T123's `MoStemMsa` clause is
replaced, because the stale-reading hypothesis it was written around is false.
