# GramTrans transfer engine -- complete object inventory

Derived from code only (`src/gramtrans/Lib/*.py`, `tests/integration/harness/full_run.py`,
`debug/audit_guid_preservation.py`), 2026-08-17. Read-only survey; no source file changed,
no FLEx project opened. Line numbers are as-of the working tree at survey time.

Scope of the survey: every site that creates an LCM object in the TARGET, every site that
assigns a reference (`*RA`) or adds to a reference/owning collection (`*RC` / `*RS` /
`*OC` / `*OS`), plus the non-LCM artifacts (writing systems, custom-field definitions,
`.fwdictconfig` files, picture binaries, residue tags).

Class names are given without the `I` interface prefix (`LexEntry`, not `ILexEntry`);
factory names keep the prefix because that is how they are imported.

---

## Category map (context for the tables)

`GrammarCategory` (`Lib/models.py:25-65`) has 29 members. 23 of them are "leaf" categories
registered in `categories.LEAF_CATEGORIES` (`Lib/categories.py:8979-9149`) and dispatched by
`transfer.execute` -> `categories.for_category(...)["execute_action"]`
(`Lib/transfer.py:415-424`).

The remaining work is NOT category-dispatched:

| work | trigger | file |
|---|---|---|
| lexical relations (`LexReference`) | single final pass over `ctx._copy_set` | `Lib/transfer.py:465` -> `categories.reproduce_all_lexical_relations` |
| reversals (`ReversalIndex`, `ReversalIndexEntry`) | single final pass over `ctx._copy_set` | `Lib/transfer.py:498` -> `categories.reproduce_reversal_entries` -> `Lib/reversals.py` |
| texts / wordforms | `plan.text_plans` (built when `categories[TEXTS]` is True) | `Lib/transfer.py:481` -> `Lib/texts.py` + `Lib/wordforms.py` |
| config views (`.fwdictconfig`) | `plan.config_view_records` | `Lib/transfer.py:519` -> `Lib/config_views.py` |
| sense pictures | inside the entry closure, per sense | `Lib/categories.py:6115` -> `Lib/pictures.py` |
| owned children (examples / pronunciations / etymologies / extended notes / sub-senses) | inside the entry closure | `Lib/categories.py:6046, 6079` -> `Lib/owned.py` |

`ctx._copy_set` is populated ONLY by `_walk_lex_entry_closure`
(`Lib/categories.py:6026, 6119, 6221`), which is reached only from
`affixes_execute_action` (`:7302`) and `stems_execute_action` (`:7690`).
This is load-bearing for the gap analysis: with `STEMS` excluded, the copy set contains
affix entries only, so every post-pass keyed on it is correspondingly narrowed.

---

## TABLE 1 -- PRIMARY OBJECTS (the engine CREATES these in the target)

Sorted by GrammarCategory, then class. "GUID preserved?" cites the create call.

| Object (class) | Human-readable | GrammarCategory | What creates it (file:line) | GUID preserved? | Notes |
|---|---|---|---|---|---|
| PartOfSpeech | Part of speech (grammatical category) | GRAM_CATEGORIES | `Lib/categories.py:453` (sub-POS), `:466` (top-level) | yes -- `IPartOfSpeechFactory.Create(Guid, parent)` / `Create(Guid, ICmPossibilityList)`; a failure `raise`s, it does not mint | Owner-taking factory; no 1-arg `Create(Guid)` overload exists. Same idiom re-used at `Lib/transfer.py:802`. |
| FsClosedFeature | Inflection feature (closed) | INFLECTION_FEATURES | `Lib/categories.py:843` (2-arg), `:854` (1-arg + `FeaturesOC.Add`) | yes -- `IFsClosedFeatureFactory.Create(Guid, featureSystem)`; 1-arg fallback also GUID-taking; raises if neither | Owner is `LangProject.MsFeatureSystemOA.FeaturesOC`. |
| FsComplexFeature | Complex inflection feature | INFLECTION_FEATURES | `Lib/categories.py:724` (2-arg), `:735` (1-arg) | yes -- same two-path idiom; raises rather than mint | |
| FsSymFeatVal | Feature value | INFLECTION_FEATURES | `Lib/categories.py:892` (2-arg), `:899` (1-arg) | yes | Created per `ValuesOC` member of each closed feature. |
| (no object created) | -- | CUSTOM_FIELDS | `Lib/categories.py:1289` `custom_fields_execute_action` returns `None` | n/a | Schema creation happens in `api._ensure_custom_fields` (`Lib/api.py:671`) -- see TABLE 4. |
| MoInflClass | Inflection class | INFLECTION_CLASSES | `Lib/categories.py:1465` | yes -- `IMoInflClassFactory.Create(Guid)` + `pos.InflectionClassesOC.Add` | Owned per-POS, not by the (flexicon-mistaken) `ProdRestrictOA` list -- see the note at `:1319`. |
| FsFeatStrucType | Feature structure type (inflection) | FEATURE_STRUCT_TYPES | `Lib/categories.py:1631-1637` | yes -- `IFsFeatStrucTypeFactory.Create(Guid)`, 1-arg only | Owner `MsFeatureSystemOA.TypesOC`; must `Add()` before writing any field. |
| FsFeatStrucType | Feature structure type (phonological) | PHON_FEAT_TYPES | `Lib/categories.py:1864-1870` | yes | Same class, different owner (`PhFeatureSystemOA.TypesOC`). |
| (no object created) | -- | POS_INFLECTABLE_FEATS | `Lib/categories.py:2034` | n/a | Pure reference wiring into `POS.InflectableFeatsRC`; see TABLE 2. |
| MoStemName | Stem name | STEM_NAMES | `Lib/categories.py:2208` | yes -- `IMoStemNameFactory.Create(Guid)` + `pos.StemNamesOC.Add` | |
| (no object created) | -- | EXCEPTION_FEATURES | `Lib/categories.py:2339-2386` | n/a | Adds an existing `FsSymFeatVal` to `POS.ExceptionFeaturesOC`; returns `None` if the value is not already in target. |
| LexEntryInflType | Variant type (irregularly inflected form) | VARIANT_TYPES | `Lib/categories.py:2557` | yes -- `ILexEntryInflTypeFactory.Create(Guid)` (1-arg) + explicit `_safe_add_to_owner` | |
| LexEntryType | Variant type | VARIANT_TYPES | `Lib/categories.py:2686` | yes -- `ILexEntryTypeFactory.Create(Guid)` | Owner `LexDbOA.VariantEntryTypesOA` (root) or a parent's `SubPossibilitiesOS`. |
| LexEntryType | Complex form type | COMPLEX_FORM_TYPES | `Lib/categories.py:2686` (shared helper) | yes | Owner `LexDbOA.ComplexEntryTypesOA`. |
| CmSemanticDomain | Semantic domain | SEMANTIC_DOMAINS | `Lib/categories.py:2797` | yes -- `ICmSemanticDomainFactory.Create(Guid)` | Hierarchical; walked via `_walk_possibilities` (`:3341`). |
| MoAlloAdhocProhib | Ad-hoc allomorph prohibition rule | ADHOC_COMPOUND_RULES | `Lib/categories.py:3346` via `_create_with_guid` (`:7845`) | yes -- `Create(Guid)` + owner `.Add`; falls back to a minted identity only if the overload is absent (logged) | Owner `MorphologicalDataOA.AdhocCoProhibitionsOC`. |
| MoMorphAdhocProhib | Ad-hoc morpheme prohibition rule | ADHOC_COMPOUND_RULES | `Lib/categories.py:3346` | yes | |
| MoAdhocProhibGr | Ad-hoc prohibition group | ADHOC_COMPOUND_RULES | `Lib/categories.py:3346` | yes | Children re-parented in the T011 pass. |
| MoEndoCompound | Endocentric compound rule | ADHOC_COMPOUND_RULES | `Lib/categories.py:3346` | yes | Owner `MorphologicalDataOA.CompoundRulesOS`. |
| MoExoCompound | Exocentric compound rule | ADHOC_COMPOUND_RULES | `Lib/categories.py:3346` | yes | |
| MoStemMsa | Grammatical info (stem MSA), compound-rule-owned | ADHOC_COMPOUND_RULES | `Lib/categories.py:3546` (`_create_owned_msa`) | yes -- `IMoStemMsaFactory.Create(parsed_guid)`; a failure `raise`s (caught non-fatally by the caller) | Assigned to `LeftMsaOA` / `RightMsaOA` / `OverridingMsaOA` / `ToMsaOA`. NOT the entry-owned MSA row below. |
| LexEntry | Entry | AFFIXES, STEMS | `Lib/categories.py:5987`; also `Lib/transfer.py:1385` | yes -- `ILexEntryFactory.Create(Guid, ILexDb)`, unguarded (an exception propagates) | The closure root. |
| LexSense | Sense | AFFIXES, STEMS | `Lib/categories.py:6058`; also `Lib/transfer.py:1412` | yes -- `ILexSenseFactory.Create(Guid, entry)`; wrapped in `try/except: continue`, so a failure silently skips the sense | Sub-senses are created by `owned.walk_owned_children` via the `LexSense.SensesOS` row. |
| MoStemMsa | Grammatical info (stem MSA) | AFFIXES, STEMS | `Lib/categories.py:6412-6441` -> `_create_msa_with_guid` (`:6298`) | yes -- `IMoStemMsaFactory.Create(Guid)`; on failure returns `None` and the flexicon wrapper mints (logged via `_log_guid_fallback`, and the new GUID is recorded in `plan.identity_remap`) | Owned by the ENTRY (`MorphoSyntaxAnalysesOC`), referenced by the sense. |
| MoInflAffMsa | Grammatical info (inflectional affix MSA) | AFFIXES | `Lib/categories.py:6412-6441`; also `Lib/transfer.py:1439` | yes (same path) | `SlotsRC` deferred to the 17.1 sub-pass (`_wire_msa_infl_feats` / `:6481`). |
| MoDerivAffMsa | Grammatical info (derivational affix MSA) | AFFIXES | `Lib/categories.py:6412-6441` | yes (same path) | |
| MoUnclassifiedAffixMsa | Grammatical info (unclassified affix MSA) | AFFIXES | `Lib/categories.py:6412-6441` | yes (same path) | |
| MoStemAllomorph | Stem allomorph | STEMS (and any affix entry whose form is a stem type) | `Lib/categories.py:6188` -> `create_with_guid` (`:6248`) -> `owned._create_owned_via_factory` (`:1877`) | yes -- `Create(Guid)`, minted fallback LOGGED and recorded in `identity_remap` | Live-unproven: `new=0 / missing=187` in the last audit because STEMS is excluded. |
| MoAffixAllomorph | Affix allomorph | AFFIXES | `Lib/categories.py:6188`; also `Lib/transfer.py:1556` | yes -- audit measured 106/106 preserved | `LexemeFormOA` first, then each `AlternateFormsOS` member. |
| FsFeatStruc | Feature structure (internal) | AFFIXES, STEMS | `Lib/categories.py:6719` (MSA `InflFeatsOA`/`MsFeaturesOA`); `Lib/owned.py:1852` (allomorph `MsEnvFeaturesOA`) | yes -- `IFsFeatStrucFactory.Create(Guid)` | (internal) -- has no Name, never surfaced as a dependency row (`Lib/selection.py:1608`). |
| FsClosedValue | Feature-value assignment (internal) | AFFIXES, STEMS | `Lib/categories.py:6752`; `Lib/owned.py:1861` | yes -- `IFsClosedValueFactory.Create(Guid)` | Wires `FeatureRA` / `ValueRA` to already-present target feature/value. |
| LexExampleSentence | Example sentence | AFFIXES, STEMS | `Lib/owned.py` `OWNED_OBJECT_MAP` rows (`:137`, `:208`) -> `_create_owned_via_factory` (`:1877`) | yes -- `Create(Guid)`; minted fallback logged | Two rows: sense-owned (`OWNER_TAKING`) and extended-note-owned (`UNOWNED_THEN_ADD`). |
| LexPronunciation | Pronunciation | AFFIXES, STEMS | `Lib/owned.py:145` row | yes -- `Create(Guid)` (`UNOWNED_THEN_ADD`) | |
| LexEtymology | Etymology | AFFIXES, STEMS | `Lib/owned.py:154` row | yes | Carries `LanguageRS` via the shared reference spec. |
| LexExtendedNote | Extended note | AFFIXES, STEMS | `Lib/owned.py:176` row | yes | Its own `ExamplesOS` is picked up by the recursive re-walk. |
| LexEntryRef | Complex-form / variant reference | AFFIXES, STEMS (created only in the STEMS tail) | `Lib/categories.py:6822` (`_create_entryref_container`), driven by `_run_entryref_create_pass` (`:6825`) | yes -- `ILexEntryRefFactory.Create(Guid)`; on failure returns `None` and the ref is DROP_REPORTED, never minted | The create pass is invoked ONLY from `stems_execute_action` (`:7714`) -- see G3. |
| LexReference | Lexical relation | (post-pass, no category) | `Lib/categories.py:5219` | yes -- `ILexReferenceFactory.Create(guid, targetLexRefType)`; failure -> logged + DroppedItemRecord | The factory itself adds it to `lexRefType.MembersOC`. |
| CmPicture | Sense picture | AFFIXES, STEMS (per sense) | `Lib/pictures.py:448` (raw path); `Lib/pictures.py:490` (`Senses.AddPicture` seam) | raw path: yes (`_create_owned_via_factory`). Seam path: NO -- `AddPicture` has no guid parameter | The seam is the happy path when the binary is present; the raw path is the dedup-reuse / missing-binary fallback. |
| CmFile | Picture file record | AFFIXES, STEMS (per sense) | `Lib/pictures.py:457` (raw path); implicitly by `AddPicture` | raw path: yes. Seam path: NO | Owned under the "Local Pictures" `CmFolder`; `InternalPath` must be set AFTER ownership. |
| CmFolder | Picture folder ("Local Pictures") | AFFIXES, STEMS (once per target) | `Lib/pictures.py:422` | NO -- deliberately EXEMPT, documented in-code at `:417-423` | Target-side container with no source counterpart. |
| MoInflAffixSlot | Affix slot | SLOTS | `Lib/categories.py:7414`; also `Lib/transfer.py:855` | yes -- `IMoInflAffixSlotFactory.Create(Guid)` + `_safe_add_to_owner` | Owner `POS.AffixSlotsOC`. |
| MoInflAffixTemplate | Affix template | AFFIX_TEMPLATES | `Lib/categories.py:7557`; also `Lib/transfer.py:828` | yes | Owner `POS.AffixTemplatesOS`. |
| FsClosedFeature | Phonological feature | PHONOLOGICAL_FEATURES | `Lib/categories.py:7930` | yes -- `_create_with_guid(IFsClosedFeatureFactory, ...)` | Owner `PhFeatureSystemOA.FeaturesOC`. Same class as the inflection-feature row; different feature system. |
| PhPhoneme | Phoneme | PHONEMES | `Lib/categories.py:7988` | yes | Owner `PhonologicalDataOA.PhonemeSetsOS[0].PhonemesOC`. Returns `None` (silently) when the target has no phoneme set. |
| PhNCSegments | Natural class (segment-based) | NATURAL_CLASSES | `Lib/categories.py:8068` | yes | |
| PhNCFeatures | Natural class (feature-based) | NATURAL_CLASSES | `Lib/categories.py:8067-8068` (same call, factory chosen by `ClassName`) | yes | |
| PhEnvironment | Environment | PH_ENVIRONMENT | `Lib/categories.py:8160`; also `Lib/transfer.py:1357` | yes | Owner `PhonologicalDataOA.EnvironmentsOS`. |
| MoStratum | Stratum | STRATA | `Lib/categories.py:8218` | yes | Deferred rule wiring drains in `_drain_phon_rule_stratum_wiring` (`:8237`). |
| PhRegularRule | Phonological rule (regular) | PHONOLOGICAL_RULES | `Lib/categories.py:8549` | yes | Owner `PhonologicalDataOA.PhonRulesOS`. |
| PhSegmentRule | Phonological rule (segment) | PHONOLOGICAL_RULES | `Lib/categories.py:8549` (factory chosen by `ClassName`, `:8543-8546`) | yes | |
| PhMetathesisRule | Phonological rule (metathesis) | PHONOLOGICAL_RULES | `Lib/categories.py:8549` | yes | |
| PhSegRuleRHS | Rule right-hand side (internal) | PHONOLOGICAL_RULES | `Lib/categories.py:8901` | yes | Owner `rule.RightHandSidesOS`. |
| PhSimpleContextSeg | Rule context: segment (internal) | PHONOLOGICAL_RULES | `Lib/categories.py:8741` | yes | |
| PhSimpleContextNC | Rule context: natural class (internal) | PHONOLOGICAL_RULES | `Lib/categories.py:8762` | yes | Wires `PlusConstrRS`/`MinusConstrRS`; `raise`s if a constraint is missing after the pre-pass. |
| PhSimpleContextBdry | Rule context: boundary (internal) | PHONOLOGICAL_RULES | `Lib/categories.py:8805` | yes | `FeatureStructureRA` left UNSET (with a `[WARN]` print, not a drop record) if the boundary marker is absent -- `:8811-8816`. |
| PhSequenceContext | Rule context: sequence (internal) | PHONOLOGICAL_RULES | `Lib/categories.py:8831`, `:8877` via `_create_with_guid_oa` (`:8458`) | yes | Members are owned in `PhPhonData.ContextsOS` and referenced from `MembersRS`. |
| PhFeatureConstraint | Feature constraint (internal) | PHONOLOGICAL_RULES | `Lib/categories.py:8668` | yes | Created in the constraint pre-pass into `FeatConstraintsOS`. |
| Text | Text | TEXTS | `Lib/texts.py:829` | yes -- `Texts.Create(name, None, guid=..., contents_guid=...)` (needs pyflexicon >= 4.3.1) | Reuses an existing text when `Exists(name)` hits (name-based, not GUID-based) -- `:809-823`. |
| StText | Text body | TEXTS | `Lib/texts.py:829` (`contents_guid=`) | yes | Created as `Text.ContentsOA` by the same wrapper call. |
| StTxtPara | Paragraph | TEXTS | `Lib/texts.py:1214` (wrapper) and `:1168` (raw `IStTxtParaFactory`) | yes on both paths -- raw path parses the guid at `:1163-1168`, wrapper takes `guid=` | Raw path exists to avoid flexicon's `strip()` and empty-content guard. |
| Segment | Segment | TEXTS | `Lib/texts.py:1027` (`ISegmentFactory.Create(para, offset, cache, guid)`), `:1299` (`Segments.AppendSentence(..., guid=)`) | yes as of the Option-A fix (audit: 101/101 preserved). Historically NO; a minted identity is logged per paragraph by `_log_segment_guid_loss`, never a drop record | LCM auto-segments when `Contents` is set; the code deletes and re-creates each segment at its existing offset. |
| TextTag | Text-markup tag | TEXTS | `Lib/texts.py:1114` (raw `ITextTagFactory` via `_create_owned_via_factory`), `:916` (`TextTags.Create` seam) | raw path: yes, from `SegmentPlan.tag_source_guids`. Seam path: NO | A short/absent `tag_source_guids` tuple yields `""` -> minted identity (logged), never a borrowed GUID. |
| WfiWordform | Wordform | TEXTS | `Lib/wordforms.py:1085` | yes -- `Wordforms.Create(form, handle, guid=wordform_guid)`; but `Find(form, handle)` runs FIRST and reuses any existing wordform regardless of GUID | Deliberate: a wordform IS its surface form. |
| WfiAnalysis | Analysis | TEXTS | `Lib/wordforms.py:998` | yes -- `WfiAnalyses.Create(wordform, guid=...)` | A structural-fingerprint dedup path (`_plan_analysis_fingerprint`) still runs as a legacy fallback. |
| WfiGloss | Word gloss | TEXTS | `Lib/wordforms.py:664-665` | yes -- `WfiGlosses.Create(analysis, form, handle, guid=...)` | Create requires the first mappable form up front; a gloss with no mappable WS is dropped with a record. |
| WfiMorphBundle | Morpheme bundle (parse slot) | TEXTS | `Lib/wordforms.py:1201` | yes -- `WfiMorphBundles.Create(analysis, guid=...)` | |
| CmAgent | Evaluation agent ("human") | TEXTS | `Lib/wordforms.py:198` | NO -- `Agents.Create(name)` takes no guid | Target-side singleton per run; cached on `ctx._wf_agent`. |
| ReversalIndex | Reversal index | (post-pass, no category) | `Lib/reversals.py:559` | NO -- `ReversalIndexes.Create(ws_id, ws_id)` has no guid parameter | One per mapped writing system; created only when absent. |
| ReversalIndexEntry | Reversal entry (top-level) | (post-pass, no category) | `Lib/reversals.py:642` | NO -- `ReversalEntries.Create(index, form, sense)` has no guid overload | Identity is the reversal FORM; `_find_existing_entry_by_form` dedups. |
| ReversalIndexEntry | Reversal entry (sub-entry) | (post-pass, no category) | `Lib/reversals.py:717` | yes -- raw `IReversalIndexEntryFactory` via `_create_owned_via_factory` | Form-based dedup runs first here too. |
| CmPossibility | List item (possibility) | (any category, via the reference CREATE arm) | `Lib/references.py:1119` | yes -- `factory.Create(parsed_guid)` + `_add_to_owner` | Created only when the referenced item is absent from the target list; the full root->leaf ancestor chain is created. |
| CmAnthroItem | Anthropology code | (reference CREATE arm) | `Lib/references.py:1119` (typed by `ItemClsid` 26) | yes | |
| MoMorphType | Morpheme type | (reference CREATE arm) | `Lib/references.py:1119` (`ItemClsid` 5042) | yes | |
| CmSemanticDomain | Semantic domain | (reference CREATE arm) | `Lib/references.py:1119` (`ItemClsid` 66) | yes | Same class as the SEMANTIC_DOMAINS row; different create site. |
| LexEntryType | Variant / complex-form type | (reference CREATE arm) | `Lib/references.py:1119` (`ItemClsid` 5118) | yes | |
| PartOfSpeech | Part of speech (reversal category) | (reference CREATE arm) | `Lib/references.py:1112` | yes -- owner-taking `Create(guid, owner)` special case | Scoped to `ReversalIndex.PartsOfSpeechOA`, never `LangProject.PartsOfSpeechOA`. |

**Distinct LCM classes in TABLE 1: 65.** (70 rows; `FsFeatStrucType`, `FsClosedFeature`,
`LexEntryType`, `CmSemanticDomain`, `PartOfSpeech`, `MoStemMsa`, `LexExampleSentence`,
`ReversalIndexEntry` each appear more than once because they are created at more than one
site or under more than one category.)

---

## TABLE 2 -- REFERENCED OBJECTS (the engine LINKS to these)

| Object (class) | Human-readable | Owning field(s) that point at it | How the target referent is resolved | If resolution fails |
|---|---|---|---|---|
| CmPossibility (`LexDbOA.SenseTypesOA`) | Sense type | `LexSense.SenseTypeRA` | by GUID over `PossibilitiesOS` + `SubPossibilitiesOS` (`references._find_in_possibility_list`); CREATED (with ancestors) if absent | target list absent -> `DroppedItemRecord` "target list absent"; diverged+protected -> LINK + report "shared-default diverged" |
| CmPossibility (`UsageTypesOA`) | Usage type | `LexSense.UsageTypesRC` | by GUID; created-if-absent | same |
| CmPossibility (`DomainTypesOA`) | Academic domain | `LexSense.DomainTypesRC` | by GUID; created-if-absent | same |
| CmAnthroItem (`AnthroListOA`) | Anthropology code | `LexSense.AnthroCodesRC` | by GUID; created-if-absent (typed factory, `ItemClsid` 26) | same |
| CmPossibility (`DialectLabelsOA`) | Dialect label | `LexSense.DialectLabelsRS`, `LexEntry.DialectLabelsRS` | by GUID; created-if-absent | same |
| CmPossibility (`StatusOA`) | Status | `LexSense.StatusRA` | by GUID; created-if-absent | same |
| CmSemanticDomain (`SemanticDomainListOA`) | Semantic domain | `LexSense.SemanticDomainsRC` | by GUID; created-if-absent | same |
| CmPossibility (`PublicationTypesOA`) | Publication | `LexSense.PublishIn` / `DoNotPublishInRC` / `DoNotShowMainEntryInRC`, `LexEntry.*` (same three), `LexExampleSentence.PublishIn` / `DoNotPublishInRC`, `LexEntryRef.ShowComplexFormsInRS` | by GUID; created-if-absent | same |
| LexEntryType (`VariantEntryTypesOA`) | Variant type | `LexEntryRef.VariantEntryTypesRS` | by GUID; created-if-absent (`ItemClsid` 5118) | same |
| LexEntryType (`ComplexEntryTypesOA`) | Complex form type | `LexEntryRef.ComplexEntryTypesRS` | by GUID; created-if-absent | same |
| MoMorphType (`MorphTypesOA`) | Morpheme type | `MoForm.MorphTypeRA` (stem + affix allomorphs) | by GUID; created-if-absent (`ItemClsid` 5042) | same |
| PhEnvironment | Environment | `MoForm.PhoneEnvRC` | deferred field (`_MOFORM_DEFERRED_FIELDS`), handled by `owned.reproduce_allomorph_hung_data` against the flat `PhonologicalDataOA.EnvironmentsOS` -- link only, never created there | `DroppedItemRecord`; the environment itself is created only by the PH_ENVIRONMENT category |
| MoStemName | Stem name | `MoForm.StemNameRA` | deferred field; resolved against the OWNING POS's own `StemNamesOC` (`references.py:248` target_list_path is `None` by design) | `DroppedItemRecord` |
| CmPossibility (`TranslationTagsOA`) | Translation type | `CmTranslation.TypeRA` | by GUID; created-if-absent. If unresolved and the target has >=1 type, the FIRST target type is substituted and reported; if the target has none, the translation is skipped and reported | `DroppedItemRecord` "translation type unresolved; substituted ..." or "no translation type available in target" |
| CmPossibility (`LexDbOA.LanguagesOA`) | Etymology language | `LexEtymology.LanguageRS` | by GUID; created-if-absent | standard reference drop |
| CmPossibility (`ExtendedNoteTypesOA`) | Extended note type | `LexExtendedNote.ExtendedNoteTypeRA` | by GUID; created-if-absent | standard |
| CmPossibility (`GenreListOA`) | Genre | `Text.GenresRC` | by GUID via the shared resolver (`texts._genre_spec`, hierarchical); created-if-absent | standard |
| CmPossibility (`TextMarkupTagsOA`) | Text-markup tag | `TextTag.TagRA` | by GUID via `texts._tag_spec`; created-if-absent | REPORT_DROPPED decisions are skipped at apply time; a `TextTag` that cannot be created gets its own drop record |
| CmPossibility (dynamic thesaurus list) | Thesaurus item | `LexSense.ThesaurusItemsRC` | dynamic owner discovery + list mirroring (`references.py:1491`), then by GUID | `_thesaurus_drop` record naming whether the list is absent or the lookup failed |
| PartOfSpeech (`LangProject.PartsOfSpeechOA`) | Part of speech | MSA `PartOfSpeechRA`, `FromPartOfSpeechRA`, `ToPartOfSpeechRA`; `MoAffixAllomorph.MsEnvPartOfSpeechRA`; `WfiAnalysis.CategoryRA`; slot/template/inflection-class/stem-name owners | by GUID (`_resolve_target_pos`, `wordforms._pos_spec`) | POS absent -> the owning object is created without the link, or the whole action returns `None`; wordform `CategoryRA` emits a drop record |
| PartOfSpeech (`ReversalIndex.PartsOfSpeechOA`) | Reversal category | `ReversalIndexEntry.PartOfSpeechRA` | by GUID against the INDEX's own POS list; created-if-absent via the owner-taking special case | `DroppedItemRecord` (owner_kind `ReversalIndexEntry`) |
| LexRefType (`LexDbOA.ReferencesOA`) | Lexical relation type | owner of `LexReference` (`MembersOC`) | by GUID only -- NEVER created | relation is reported and skipped (`_evaluate_lexical_relation` returns `None`) |
| LexAppendix (`LexDbOA.AppendixesOC`) | Appendix | `LexSense.AppendixesRC` | by GUID against target-owned appendixes only -- NEVER created, and its owned `StText` is never reproduced | `DroppedItemRecord` (field `AppendixesRC`), labelled by a contents snippet |
| PhBdryMarker (`PhonemeSetsOS[*].BoundaryMarkersOC`) | Boundary marker | `PhSimpleContextBdry.FeatureStructureRA` | by GUID against the target's own boundary markers -- NEVER created | `FeatureStructureRA` LEFT UNSET, with only a `[WARN]` print -- no drop record (`categories.py:8811-8816`) |
| PhPhoneme | Phoneme | `PhNCSegments.SegmentsRC`, `PhSimpleContextSeg.FeatureStructureRA` | by GUID; created only by the PHONEMES category | missing referent -> the collection member is omitted |
| PhNCSegments / PhNCFeatures | Natural class | `PhSimpleContextNC.FeatureStructureRA` | by GUID; created only by the NATURAL_CLASSES category | omitted |
| PhFeatureConstraint | Feature constraint | `PhSimpleContextNC.PlusConstrRS` / `MinusConstrRS` | by GUID against the map built by the in-rule constraint pre-pass | `RuntimeError` raised -- this one FAILS LOUD (`categories.py:8794`) |
| MoStratum | Stratum | `PhRegularRule.InitialStratumRA` / `FinalStratumRA`; `MoAdhocProhib*` / `MoEndoCompound` / `MoExoCompound` `StratumRA` | by GUID, in a DEFERRED drain (`_drain_phon_rule_stratum_wiring`) because PHONOLOGICAL_RULES dispatches before STRATA | left unset |
| FsClosedFeature / FsSymFeatVal | Inflection feature / feature value | `POS.InflectableFeatsRC`, `POS.ExceptionFeaturesOC`, `FsClosedValue.FeatureRA` / `ValueRA` | by GUID over `MsFeatureSystemOA.FeaturesOC` (and `ValuesOC`) | the whole execute_action returns `None` (no partial write); for `MsEnvFeatures` an unresolved spec yields a per-spec drop record |
| MoInflAffixSlot | Affix slot | `MoInflAffMsa.SlotsRC`; template `PrefixSlotsRS` / `SuffixSlotsRS` / `EncliticSlotsRS` / `ProcliticSlotsRS` / `SlotsRS` | by GUID in the 17.1 sub-pass (`_wire_msa_infl_feats` / `_run_171_subpass`), after all slots exist | `Skip(DEPENDENCY_UNRESOLVED)` folded into `context._exec_skips` |
| MoForm (allomorph) | Allomorph | `MoAlloAdhocProhib.FirstAllomorphRA` / `RestOfAllosRS`; `MoEndoCompound.LinkerOA` / `MoExoCompound.LinkerOA` | by GUID over all target allomorphs; APRs are reproduced ONLY when every member is already in `ctx._copy_set` | APR not reproduced; reported |
| LexEntry | Entry (as morpheme) | `MoMorphAdhocProhib.FirstMorphemeRA` / `RestOfMorphsRS` / `MorphemesRS` | by GUID | rule not reproduced; reported |
| LexEntry | Entry (as component) | `LexEntryRef.ComponentLexemesRS` / `PrimaryLexemesRS` | by GUID in post-pass A (`_run_post_pass_a`), after all entries exist | `Skip(DEPENDENCY_UNRESOLVED)` / drop record |
| LexSense | Sense | `WfiMorphBundle.SenseRA`; `ReversalIndexEntry.SensesRS` | by identity against the run's copied-sense map (`ctx._copy_set` / `IdentityRef`) | left unset; the analysis is downgraded to needs-review; reversal members not in the copy set get a "member not in copy set" drop record |
| MoMorphSynAnalysis (any MSA subclass) | Grammatical info | `WfiMorphBundle.MsaRA`; `LexSense.MorphoSyntaxAnalysisRA` | by identity via the run's MSA map / `identity_remap` | left unset; analysis downgraded |
| MoForm | Allomorph | `WfiMorphBundle.MorphRA` | by identity via the run's allomorph map | left unset |
| LexEntryInflType | Irregularly-inflected-form type | `WfiMorphBundle.InflTypeRA` | by identity/GUID | left unset |
| WfiAnalysis / WfiGloss / WfiWordform / PunctuationForm | Analysis / gloss / wordform / punctuation | `Segment.AnalysesRS` (alignment tokens) | positional token-by-token, resolved from the source->target map built during the walk | drop record "alignment token had no copied target referent" (103 of these in the last measured run) |
| CmAgent | Evaluation agent | `CmAgentEvaluation` owner; `WfiAnalysis` approval | by name (`Agents.Find(_AGENT_NAME)`), created if absent | agent `None` -> no verdict is stamped |
| CmFile | Picture file | `CmPicture.PictureFileRA` | reused by content-hash dedup within the target, else created | wiring wrapped in `try/except (AttributeError, TypeError): pass` |
| LexEntry / LexSense (copied) | Entry / Sense | `LexReference.TargetsRS` | by identity against `ctx._copy_set`, rebuilt in SOURCE order | partial-member policy in `_evaluate_lexical_relation`; members outside the copy set are reported |
| Writing system | Writing system | every multistring alt, `ws_map` translation | by language tag through `WSMapping`; created when `create_in_target=True` (`api._ensure_writing_systems`) | alt is dropped and reported; see TABLE 4 |

**Distinct referenced classes in TABLE 2: 24** (`CmPossibility`, `CmAnthroItem`,
`CmSemanticDomain`, `LexEntryType`, `MoMorphType`, `PhEnvironment`, `MoStemName`,
`PartOfSpeech`, `LexRefType`, `LexAppendix`, `PhBdryMarker`, `PhPhoneme`, `PhNCSegments`,
`PhNCFeatures`, `PhFeatureConstraint`, `MoStratum`, `FsClosedFeature`, `FsSymFeatVal`,
`MoInflAffixSlot`, `MoForm`, `LexEntry`, `LexSense`, `MoMorphSynAnalysis`,
`LexEntryInflType`), plus `WfiAnalysis` / `WfiGloss` / `WfiWordform` / `PunctuationForm` /
`CmAgent` / `CmFile` as alignment/agent/file referents. Of these, only `LexRefType`,
`LexAppendix` and `PhBdryMarker` are NEVER created by any path.

---

## TABLE 3 -- OWNED CHILDREN THAT RIDE ALONG

These have no independent plan entry. They are carried inside a parent's create/apply
step, mostly by flexicon's `GetSyncableProperties` / `ApplySyncableProperties` pair or by
an LCM side effect.

| Class or field | Parent class | How it is carried | Separately verifiable? |
|---|---|---|---|
| Name / Abbreviation / Description / Gloss / Definition multistrings | every synced class | `GetSyncableProperties` -> `ApplySyncableProperties(item, props, ws_map=...)` | yes -- field census (spec FR-051) |
| `CmTranslation` | `LexExampleSentence` | flexicon `ExampleOperations` owns `TranslationsOC` end-to-end. Deliberately NOT an `OWNED_OBJECT_MAP` row -- a second walk-driven path was removed as a duplicate-object bug (`Lib/owned.py:20-26`) | only by counting `TranslationsOC`; GramTrans has no create site and therefore no GUID guarantee |
| `FsFeatStruc` + `FsClosedValue` on `PhPhoneme.FeaturesOA` | `PhPhoneme` | flexicon `PhonemeOperations.__ApplyFeatures` creates them with a bare `factory.Create()` (flexicon `PhonemeOperations.py:1472`, `:1491`) | GUID is NOT preserved on this path; only the (feature,value) pair is |
| `PhCode` (`CodesOS`) | `PhPhoneme` | NOT CARRIED. flexicon's phoneme `GetSyncableProperties` explicitly states "Does not include CodesOS" | no -- and it is not reported as a drop either |
| `CmAgentEvaluation` | `WfiAnalysis` | created by LCM as a side effect of `WfiAnalyses.ApproveAnalysis` / `RejectAnalysis` (`Lib/wordforms.py:1034`) | only indirectly, via approval state |
| `StText` (`Text.ContentsOA`) | `Text` | created by `Texts.Create(..., contents_guid=)` | yes -- it has its own GUID |
| `Segment` free / literal translation | `Segment` | `Segments.SetFreeTranslation` / `SetLiteralTranslation` (`Lib/texts.py:1337`, `:1342`); these create the underlying `CmTranslation` internally | by content only |
| `Segment` notes (`NotesOS`) | `Segment` | NOT REPRODUCED. One `DroppedItemRecord` per note, reason "segment note not reproduced: no confirmed note write path (deferred to live-probe, T039)" (`Lib/texts.py:862-869`) | yes, via the drop record |
| `MoInflAffixTemplate` slot sequences (`PrefixSlotsRS`, `SuffixSlotsRS`, `EncliticSlotsRS`, `ProcliticSlotsRS`) | `MoInflAffixTemplate` | reference wiring inside `affix_templates_execute_action` | yes -- order-critical per spec FR-083 |
| `MoStemMsa` / affix-MSA scalar + reference fields not explicitly wired (`InflectionClassRA`, `FromProdRestrictRC`, `ProdRestrictRC`, `StemNameRA`, ...) | MSA subclasses | whatever flexicon `MSAOperations.GetSyncableProperties` returns; GramTrans wires only `PartOfSpeechRA`-family fields, `SlotsRC` (17.1 sub-pass) and `InflFeatsOA` | only by field census; the set flexicon omits is not enumerated anywhere in this repo |
| `LexEntryRef.RefType` | `LexEntryRef` | set inline in `_run_entryref_create_pass` right after create | yes |
| `HeadLast` (bool), `LinkerOA` | `MoEndoCompound` / `MoExoCompound` | set inline (`Lib/categories.py:3577`, `:3592`) | yes |
| `Direction` scalar | `PhRegularRule` | copied inline; explicitly called out in spec FR-053/FR-067 as needing fidelity checking | yes |
| Sub-senses | `LexSense` | `owned.OWNED_OBJECT_MAP` `LexSense.SensesOS` row with `recurse=True` | yes -- own GUID |
| `LexExtendedNote.ExamplesOS` | `LexExtendedNote` | second `OWNED_OBJECT_MAP` row for the same field name, disambiguated by real `ClassName` | yes |
| `CmPossibility` ancestor chains | any referenced possibility | `references._ancestor_chain` -> created root->leaf inside the CREATE arm | yes -- each ancestor keeps its source GUID |
| `identity_remap` entries | any object whose GUID could not be preserved | `plan.identity_remap[src_guid] = new_guid` (`Lib/categories.py:6203`) | yes -- this map IS the record of unpreserved identity |

---

## TABLE 4 -- WRITING-SYSTEM AND CONFIGURATION ARTIFACTS

| Artifact | Created or mutated | Where | Notes |
|---|---|---|---|
| Target writing system | created | `Lib/api.py:802-882` `_ensure_writing_systems`, for every `WSMappingEntry` with `create_in_target=True` | Runs BEFORE `transfer.execute`. Skips a tag already present. A failure is logged, not raised. |
| WS mapping / `ws_map` dict | in-memory only | `Lib/ws_mapping.py` (`to_ws_map_dict`, `fold_choices_into_ws_mapping`) | Threaded into every `ApplySyncableProperties` call as `ws_map=`. A source alt with no mapping is dropped and reported. |
| WS font settings | mutated | `Lib/ws_fonts.py` | |
| Custom field DEFINITION (schema) | created | `Lib/api.py:671-790` `_ensure_custom_fields` -> `IFwMetaDataCacheManaged.AddCustomField` | In-memory MDC mutation, persisted by a PATH-CLOSE-REBIND checkpoint before any value write. Flids renumber on reload, so they are never cached across the schema boundary. |
| Custom field VALUES | mutated | `custom_fields_execute_action` (`Lib/categories.py:1289`) is a documented NO-OP; values ride on the transferred objects | The category is registered so leaf dispatch does not warn. |
| `.fwdictconfig` dictionary configuration views | copied (ADD / OVERWRITE, with `.gtbak` backup) | `Lib/config_views.py:410-435` `apply_config_views`; planned by `plan_config_views` (`:357`) | Sidecar XML files under `<project>/ConfigurationSettings/Dictionary/`. Missing WS / custom-field / style references are scanned and reported as `DroppedItemRecord`s, never silently imported. |
| `.fwdictconfig` reversal configuration views | copied | same | `.../ConfigurationSettings/ReversalIndex/` |
| Directory creation on the target tree | created | `Lib/config_views.py` per-file `os.makedirs` right before each copy | Plan-time creates NO directories on either tree (P0-1). |
| Picture binaries in `LinkedFiles/Pictures` | copied | `Lib/pictures.py:608` `shutil.copy2` via a staging dir; `Senses.AddPicture` also copies on the happy path | Content-hash dedup; `GetLinkedFilesDir()` resolves the root. Spec FR-174 is the containment assertion for this. |
| Import Residue tag (`GT\|<run_id>\|<source>\|<iso_ts>`) | mutated onto transferred objects | `Lib/residue.py` -- Carrier A writes `LiftResidue` on 15 classes (`CARRIER_A_CLASSES`, `:35-49`); Carrier B appends a `[GT-Tag]: ` line to `Description` for everything else | Carrier B degrades with `strict=False` for text/wordform classes that have no `Description`. Spec FR-063 expects these fields to diverge. |
| `identity_remap` / `in_plan_entries` / `_copy_set` on the RunContext | in-memory run state | `Lib/categories.py`, `Lib/transfer.py` | Not persisted; but `identity_remap` is the only record of a minted identity inside a run. |

---

## GAP ANALYSIS

### G1. TABLE 1 classes NOT in `audit_guid_preservation.py`'s 26-class inventory

**First, a correction that changes how this question can be answered.**
`debug/audit_guid_preservation.py` contains **no hardcoded 26-class inventory**. It is a
purely empirical instrument: it enumerates `ICmObjectRepository.AllInstances()` before and
after a Move and buckets the delta by `obj.ClassName` (`:82-84`, `:161-180`). The "26
object-creating classes" is an **emergent count from one run** (Ejagham Mini -> Target,
recorded in `specs/033-guid-preservation/TODO.md:47`), not a roster. The run's own output
file (`scratchpad/guid_audit.json`) is **not committed** -- it does not exist in the working
tree -- so the actual 26 names are unrecoverable from the repo. Only 9 are named anywhere:
`Text`, `StText`, `StTxtPara`, `Segment`, `MoAffixAllomorph`, `WfiWordform`, `WfiAnalysis`,
`WfiGloss`, `WfiMorphBundle` (TODO.md:131-132, 140-146).

So the answer is a bound plus a provable subset, not a set difference.

**Bound:** TABLE 1 has 65 distinct classes. At most 26 were measured. **At least 39 primary
classes have never had their identity measured by that instrument.**

**Provably unmeasured** (structurally impossible for that run to have created them):

1. `MoStemAllomorph` -- TODO.md records `new=0 / missing=187`, explicitly because STEMS is
   excluded from `build_full_selection()`. Named in TODO.md as an open item.
2. `LexEntryRef` -- `_run_entryref_create_pass` is invoked only from
   `stems_execute_action` (`categories.py:7714`). With STEMS excluded it never runs, so no
   `LexEntryRef` is ever created in the audited configuration.
3. `MoStemMsa` (entry-owned variant) -- reachable only through a stem entry's sense.
4. `CmFolder` ("Local Pictures") -- explicitly EXEMPT from the GUID invariant
   (`pictures.py:417-423`); if it appeared in the audit it would show as a minted offender,
   and the audit reported zero offenders, so it did not appear.
5. `CmAgent` -- has no guid-taking create; would be a minted offender. Audit reported zero
   offenders, so no `CmAgent` was created (i.e. the target already had a human agent, or the
   texts path did not stamp verdicts).
6. `ReversalIndex` and `ReversalIndexEntry` (top-level) -- neither has a guid-taking create;
   both would show as minted. Zero offenders means neither was created.
7. `Segment` before commit `8cad0d7` was the one measured offender; it is now measured and
   passing. Listed here only to note that it is the sole class whose measurement history is
   fully documented.

**Additionally unmeasurable by construction:** any class the SOURCE project does not
contain. Ejagham Mini has no `PhSegmentRule`, `PhMetathesisRule`, `LexExtendedNote`, or
`CmPicture` data in evidence (the run's `dropped_breakdown` and 188-action plan show only
MoForm / Segment / WfiGloss traffic). Single-project measurement cannot cover a
class-per-class inventory; this is exactly the hole feature 035's corpus sweep exists to
close.

**Actionable:** commit the audit's per-class rows (`guid_audit.json`) as a git-tracked
roster so G1/G2 become a mechanical diff rather than an archaeology exercise.

### G2. Audited classes NOT in TABLE 1 (measured but possibly no longer created)

Cannot be enumerated exactly, for the same reason as G1 -- the 26 names are not recorded.
But the instrument's shape guarantees the audited set is a **superset** of what GramTrans
creates: it buckets *every* new object in the target, including objects GramTrans never
asks for. From the code survey, the classes that would appear in the audit with **no
GramTrans create site** are:

| class | why it appears | GramTrans create site? |
|---|---|---|
| `CmTranslation` | created by flexicon `ExampleOperations` and by `Segments.SetFreeTranslation` | none -- deliberately removed as a duplicate-object bug (`owned.py:20-26`) |
| `CmAgentEvaluation` | created by LCM on `ApproveAnalysis` / `RejectAnalysis` | none |
| `FsFeatStruc` / `FsClosedValue` (phoneme-owned) | created by flexicon `PhonemeOperations.__ApplyFeatures` with bare `Create()` | GramTrans creates these classes elsewhere (MSA / MsEnv), but not on the phoneme path |
| `PhCode` | would appear only if flexicon created one; it does not carry `CodesOS` at all | none, and no drop record either |
| `CmObject` subclasses auto-created by LCM `Contents` assignment (segments, `StTxtPara` parse artifacts) | LCM side effects | none |

These are the rows a naive reading of "26 audited classes" would mistake for engine
coverage. None of them is stale in the sense of "no longer created" -- rather, they were
never created by GramTrans in the first place, which is a different and more dangerous
misreading.

### G3. GrammarCategory values excluded by `build_full_selection()`

`tests/integration/harness/full_run.py:43-58`:

```python
def build_full_selection(exclude: frozenset = frozenset({GrammarCategory.STEMS})) -> Selection:
```

**Exactly one category is excluded: `GrammarCategory.STEMS`.** All 28 other members are set
`True`. All pick-sets (`pos_picks`, `affix_picks`, `stem_picks`, `leaf_item_picks`,
`text_picks`) are left empty, which the engine reads as "transfer all" (e.g.
`texts.py:653-655`: `if picks and src_guid not in picks: continue`).

**Consequence for coverage.** STEMS is not one category among 29. It is the category that
carries every non-affix `LexEntry`, i.e. the bulk of a lexicon. Excluding it removes:

- every stem `LexEntry` and its `LexSense`es;
- `MoStemAllomorph` (audit: 187 source objects, 0 transferred);
- entry-owned `MoStemMsa`;
- every `LexExampleSentence`, `LexPronunciation`, `LexEtymology`, `LexExtendedNote`,
  `CmTranslation` and sub-sense hanging off a stem sense;
- every `CmPicture` / `CmFile` on a stem sense (feature 029's entire deliverable);
- **`LexEntryRef` entirely** -- `_run_entryref_create_pass` and `_run_post_pass_a` are
  invoked ONLY from `stems_execute_action` (`categories.py:7714-7718`), so complex-form and
  variant reference containers, their `ComponentLexemesRS` / `PrimaryLexemesRS`, and their
  `VariantEntryTypesRS` / `ComplexEntryTypesRS` / `ShowComplexFormsInRS` wiring never
  execute in a "full" run;
- most of `LexReference` (lexical relations) and `ReversalIndexEntry`, because both are
  post-passes over `ctx._copy_set`, and the copy set is populated only by AFFIXES and STEMS
  entries. With STEMS off, relations and reversals covering stem senses simply have no
  member in the copy set and are reported as partial or skipped.

A run using `build_full_selection()` therefore exercises roughly the affix half of the
lexical model and none of the complex-form machinery. Spec FR-134 already names the
stem-allomorph half of this; the `LexEntryRef` consequence appears to be undocumented.

Note also that the default argument is exactly the "invisible default argument that a reader
of the results cannot see" that FR-135 forbids.

### G4. TABLE 1 / TABLE 2 classes not addressed by any requirement in spec.md

`specs/035-fullsweep-fidelity/spec.md` names **no LCM class at all** (a scan for
`Lex*`/`Mo*`/`Ph*`/`Fs*`/`Wfi*`/`Cm*`/`St*` class names returns one hit, the word
"Segment", used generically). The spec is deliberately class-agnostic: FR-051 mandates a
generic per-object field census "rather than a hand-listed set of domains or fields chosen
per class." That is a defensible design, so "not named" is not by itself a gap.

What IS a gap is a class whose known, code-visible failure mode is not reachable by the
census the spec describes. Those are:

1. **`CmFolder` ("Local Pictures")** -- a target-side container with a deliberately minted
   GUID. A NO-EXTRA check (FR-102: every object in the target must be accounted for) will
   flag it as an unexplained extra object on every single run. Nothing in the spec exempts
   it.
2. **`CmAgent`** -- same shape: minted identity, created only when absent, no source
   counterpart. Same FR-102 collision.
3. **`ReversalIndex` and top-level `ReversalIndexEntry`** -- identity is the writing-system
   tag / the reversal FORM, not the GUID. The spec's FR-085..FR-090 link-classification
   ladder is framed around "an object whose stable identifier equals the source"
   (FR-085). A form-deduped reversal entry has a *different* stable identifier and would be
   classified DANGLING or RESOLVED-BY-EQUIVALENCE with no rule saying which. FR-090 requires
   an equivalence rule; none is stated for form-identity objects.
4. **`WfiWordform`** -- same problem in a different place: `Find(form, handle)` runs before
   `Create(..., guid=)`, so a pre-existing target wordform is reused under a foreign GUID by
   design (`wordforms.py:1077-1087`). No requirement acknowledges deliberate
   identity-substitution as a legitimate outcome.
5. **`PhCode`** -- not carried at all, and not reported as a drop. A field census over
   `PhPhoneme` will see `CodesOS` missing in the target; without a requirement it will be
   scored as unexplained loss with no drop record to corroborate it (which FR-091 says
   should be treated as corroborating detail -- but there is nothing to corroborate).
6. **`PhBdryMarker`** -- referenced by `PhSimpleContextBdry.FeatureStructureRA`, never
   created, and its absence produces a `[WARN]` print rather than a `DroppedItemRecord`
   (`categories.py:8811-8816`). FR-087 (SILENTLY_UNSET) covers the symptom, but FR-091's
   corroboration path is unavailable because no record is emitted. This is a
   never-silent-principle violation in the engine that the sweep will surface as an
   uncorroborated silent unset.
7. **`Segment` notes (`NotesOS`)** -- reproduced as drop records only. Covered by FR-091 in
   principle, but the drop reason string ("deferred to live-probe, T039") is an engine-bug
   signature, and FR-107 / FR-121 require engine-bug-shaped reasons to be distinguished from
   genuine loss. Whether "deferred" counts as an engine-bug signature is not settled.
8. **`LexAppendix` and `LexRefType`** -- referenced-but-never-created. FR-088 covers "a
   matching object does not exist in the target", but neither class has a create path at
   all, so every source project that uses them will register a permanent, expected loss
   with no allowlist entry contemplated.
9. **`CmTranslation`, `CmAgentEvaluation`, phoneme-owned `FsFeatStruc`/`FsClosedValue`** --
   created by the dependency, not by GramTrans, with minted GUIDs. FR-052 excludes fields
   the syncable-properties surface omits, but says nothing about *objects* the dependency
   creates on the engine's behalf. These will show as minted identities against a GUID
   invariant that no requirement scopes to "objects GramTrans itself creates".

### G5. Creation paths with NO test reference anywhere under `tests/`

Method: case-sensitive and case-insensitive scan of every file under `tests/` for each
TABLE 1 class name.

| class | create site | test files mentioning it |
|---|---|---|
| `PhFeatureConstraint` | `Lib/categories.py:8668` | **0** (also 0 for `feature_constraint`, `FeatureConstraint`) |
| `CmFolder` ("Local Pictures") | `Lib/pictures.py:422` | **0** (also 0 for `CmFolder`, `Local Pictures`) |
| `PhCode` | not created -- carried by nothing | **0** |

Two more are borderline and worth flagging:

| class | create site | coverage |
|---|---|---|
| `CmAgent` / `CmAgentEvaluation` | `Lib/wordforms.py:198` | 1 test file each -- the thinnest coverage of any created class |
| `CmTranslation` | no GramTrans create site (flexicon-owned) | 1 test file |
| `LexPronunciation`, `LexEtymology` | `Lib/owned.py:145`, `:154` | 1 test file each |
| `PhSegRuleRHS`, `PhSimpleContextBdry`, `PhSequenceContext` | `categories.py:8901`, `:8805`, `:8831` | 1 test file each |

`PhPhoneme` and `MoStratum` show 0 hits on the exact class name but 21 and 9 hits
respectively on `phoneme` / `stratum` / `strata`, so they ARE tested -- the tests just use
the domain word rather than the interface name.

---

## Counts

- **65** distinct primary classes created (70 create rows across categories/sites)
- **24** distinct referenced classes (3 of them -- `LexRefType`, `LexAppendix`,
  `PhBdryMarker` -- are never created by any path)
- **18** ride-along owned children / carried fields (TABLE 3)
- **12** writing-system and configuration artifacts (TABLE 4)

Gap counts:

- **G1: >=39** primary classes never identity-measured (65 total minus at most 26
  measured); **7** provably unmeasured by name
- **G2: >=5** class families appear in the audit with no GramTrans create site
- **G3: 1** category excluded (`STEMS`), cascading to **>=10** object classes losing all
  coverage, including `LexEntryRef` entirely
- **G4: 9** classes / class groups with a code-visible failure mode no requirement reaches
- **G5: 3** created-or-carried classes with zero test references (`PhFeatureConstraint`,
  `CmFolder`, `PhCode`), plus **7** with exactly one
