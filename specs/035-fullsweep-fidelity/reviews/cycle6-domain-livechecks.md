# Domain Expert Review -- Cycle 6 Live-Check Closure

**Date:** 2026-09-19
**Domain:** FLEx/LCM object identity + T045d field-reader dispatch
**Feature:** 035-fullsweep-fidelity

> Provenance note: FLExToolsMCP was NOT exposed to this agent's toolset this session
> (only Read/Grep/Glob/WebFetch), despite the dispatch instructions stating it would be.
> JOB 1's points therefore could not receive a true live-LCM confirmation; where possible
> they are corroborated instead against the liblcm v11.0.0 static API-surface index
> (`FlexToolsMCP/src/flextoolsmcp/index/liblcm/liblcm_api_v11.0.0.json`), which is
> method-signature/schema evidence, not live instance data -- flagged per item. JOB 2
> required checking the CURRENT flexicon source (pyflexicon 4.8.0 installed, above the
> 4.5.2 floor per `pyproject.toml:15`), which Read/Grep sufficed for directly.

## JOB 1 -- cycle5 live-check points

1. **CmAgent stock-template default identity (Section 1).** STILL-UNVERIFIABLE. No live
   project was queried this session; confirming a freshly-restored template ships stable
   default agent GUIDs needs an open project.

2. **Reversal-index one-container-per-WS + form-keyed dedup (Section 3).**
   STILL-UNVERIFIABLE against live data, but structurally CONFIRMED against the liblcm
   API surface: `IReversalIndexRepository.FindOrCreateIndexForWs(...)` and
   `.FindOrCreateReversalEntry` exist exactly as named -- the repository itself enforces
   "one index per WS" and "find-before-create by form" at the API level, not merely as UI
   convention. The cited Yi Sichuan figures (7 indexes, 25,116 entries) remain
   STILL-UNVERIFIABLE -- no live project of that scale reachable this session.

3. **WfiWordform (WS, form) natural key (Section 4).** STILL-UNVERIFIABLE against live
   data, but structurally CONFIRMED: `IWfiWordformRepository.GetMatchingWordform(Int32 ws,
   String form)` is a two-argument lookup keyed exactly on (writing-system, surface form)
   -- the dedup key cycle5 asserted is the repository's own declared contract.

4. **Complexity-preservation (Section 5).** Not a factual claim needing live confirmation
   -- it's a proposed new requirement. No action.

## JOB 2 -- T045d factual base (verified against installed flexicon 4.8.0)

**(a) NotImplementedError claim: CONFIRMED (current source).**
`BaseOperations.GetSyncableProperties` (`flexicon/code/BaseOperations.py:1286-1378`)
unconditionally `raise NotImplementedError(...)` at line 1373 unless overridden.
Unchanged at 4.8.0.

**(b) Which accessors implement it: CONFIRMED.** 41 concrete Operations classes define
their own `GetSyncableProperties`. Five more inherit it:
`GramCatOperations(POSOperations)`, and
`AgentOperations`/`ConfidenceOperations`/`OverlayOperations`/`PublicationOperations`/`TranslationTypeOperations`
(all subclass `PossibilityItemOperations`, itself an override) -- 46 effectively-covered
Operations classes, each reachable as a named `FLExProject` property (`proj.POS`,
`proj.Senses`, `proj.Allomorphs`, `proj.MorphRules`, `proj.PhonFeatures`, `proj.Agents`,
etc. -- 55 top-level accessors total).

**(c) Coverage of the 66 in-scope classes: CONFIRMED, with one hole.** Tracing
class->accessor against `coverage-floor.json`'s roster: the large majority resolve cleanly
(Fs* -> `Features`/`InflectionFeatures`; CmFile/CmFolder/CmPicture -> `Media`;
CmAnthroItem -> `Anthropology`; TextTag/PunctuationForm -> `Texts`/`Segments`; Lex*
subtypes -> `LexEntry`/`Senses`/`LexReferences`/`Pronunciations`/`Variants`; Ph*
context/rule classes -> `PhonRules`/`MorphRules`).

**One confirmed coverage hole: `MoAdhocProhibGr`, `MoAlloAdhocProhib`,
`MoMorphAdhocProhib`.** These are handled only by `Grammar/adhoc_prohibition.py`'s
`AdhocProhibition` wrapper, which subclasses `LCMObjectWrapper`, not `BaseOperations` --
no `GetSyncableProperties`/`ApplySyncableProperties` at all. `MorphRuleOperations.py` only
touches these three in its delete path (line 469, under the differently-spelled names
`MoAdhocProhibMorph`/`MoAdhocProhibAllomorph` -- worth a follow-up naming check against
the roster's `MoMorphAdhocProhib`/`MoAlloAdhocProhib`). T045d must report these three as
an explicit unreachable-coverage hole, not silently skip.

**(d) GetFieldID + metadata-cache route: CONFIRMED, and a better route exists but is
unbuilt.** `FLExProject.GetFieldID(className, fieldName)` (`FLExProject.py:4234`) is
public, generic, and works via `MetaDataCacheAccessor.GetFieldId(className, fieldName,
True)`. A fully generic enumeration primitive also already exists, used only internally
for custom fields today: `mdc.GetFields(classID, False, CellarPropertyTypeFilter.All)`
yields every flid for a class (`FLExProject.py:4706`, inside private
`__GetCustomFieldsOfType`), paired with `DomainDataByFlid` generic get/set keyed by flid +
`CellarPropertyType`. This is a genuinely more complete route than the Operations-accessor
dispatch table -- no per-class code needed at all -- but it's unexploited outside
custom-field discovery and would require building `CellarPropertyType`-keyed generic value
readers from scratch, a materially larger project than wiring the ~46-class dispatch table
T045d already scopes.

---

**Files consulted:** `specs/035-fullsweep-fidelity/reviews/cycle5-domain-identity.md`,
`specs/035-fullsweep-fidelity/tasks.md` (lines 662-682),
`specs/035-fullsweep-fidelity/contracts/coverage-floor.json`,
`flexicon/flexicon/code/BaseOperations.py`, `flexicon/flexicon/code/FLExProject.py`,
`flexicon/flexicon/code/Grammar/MorphRuleOperations.py`,
`flexicon/flexicon/code/Grammar/adhoc_prohibition.py`, `flexicon/pyproject.toml`,
`FlexToolsMCP/src/flextoolsmcp/index/liblcm/liblcm_api_v11.0.0.json`.
