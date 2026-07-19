# Phase 0 Research: Preview Coverage Completion

**Feature**: 032-preview-coverage-completion | **Date**: 2026-07-19

The spec carries no unresolved `[NEEDS CLARIFICATION]` markers (four questions were
resolved in the 2026-07-19 clarify session). This research resolves the *implementation*
unknowns: the exact Stage-1 props shape for each category, the drop point for the Natural
Class regression, the WS-default correspondence rule, and the US5 root-cause hypothesis —
each verified (or scheduled for verification) against live projects via FLExToolsMCP per
FR-019, never by code inspection alone.

## Architectural constraint (fixed, not researched)

- **Decision**: Add/enrich **Stage-1 readers only**; feed the existing Stage-2 layer
  (`diff_props` → `to_html`) unchanged by emitting the same `{field: value}` /
  `{ws_id: text}` props-dict shapes it already consumes.
- **Rationale**: The diff/render layer is Qt-free, tested, and already implements
  new-vs-differs (NEW / OVERWRITE / MERGE_KEEP / LINK_ONLY), removed→added collapse, and
  color/segment styling. Touching it risks the SC-007 Qt-free guarantee and the existing
  diff tests for no benefit.
- **Alternatives rejected**: (a) per-category bespoke HTML — duplicates the render layer,
  breaks diff consistency (FR-009); (b) moving enrichment into the UI pane — violates
  SC-007 (Qt-free core) and the pane's dispatch-only role.

## R1 — Natural Class regression root cause (US3)

- **Decision**: Reproduce the empty state with a failing test first, then locate the drop
  along the covered/finder path. The two candidate drop points are: (a) the finder
  `_find_target_natural_class_by_guid` returning `None` or the `NaturalClasses` ops
  wrapper lacking `GetSyncableProperties`, so `props_for` returns empty *before* the
  enrich hook at `~1293-1294` ever runs (whole-pane blank); or (b) the enrich output
  (`raw["Members"]` / `raw["Features"]`) being ordered/rendered such that it is dropped
  downstream. The resolvers themselves (`_natural_class_members` ~1759,
  `_natural_class_features` ~1771, `_enrich_natural_class` ~1797) are present and correct.
- **Rationale**: Spec calls this a regression (resolved-but-not-shown), so the fix must be
  load-bearing (FR-008, SC-003): the test must show members/features absent before and
  present after on the same data. Establishing the failure first prevents a no-op "fix."
- **Verification**: Live read of a segment-based and a feature-based natural class in
  `Ejagham Mini` (or `Esperanto`) via FLExToolsMCP; confirm members/features resolve in
  isolation, then confirm whether the finder or the render is where they vanish.
- **Alternatives rejected**: Assuming it is purely cosmetic `repr()` rendering
  (`_added_segments` ~321) — plausible but must be proven, not assumed, because a
  finder/ops miss produces a different (whole-pane) failure with a different fix.

## R2 — Blank-category reader shapes (US1)

- **Decision** (per category, props-dict fields verified against live LCM):
  - **Text**: `{Title, Baseline (bounded excerpt of first paragraph/segments), Truncated
    (indicator)}`, reusing `texts.py` `capture_vernacular` / `_walk_paragraphs`; excerpt
    length bounded per FR-018.
  - **Writing System**: `{Name, Code/Tag, Kind (vernacular/analysis), Rank (primary/sub),
    Maps-to (target WS via the US4 mapping)}`.
  - **Complex Form Type** (`ILexEntryType`): `{Name, Abbreviation, Type/pattern detail}`
    resolved via `references.py` possibility-list helpers, diffed if a matching target
    type exists.
  - **Ad hoc / Compound rule** (`IMoMorphAdhocProhib` / `IMoAlloAdhocProhib` /
    compound-rule classes): `{Name/identity, Referenced elements (morphemes/classes)}`
    via `references.py` reference resolvers.
- **Rationale**: Each shape is the minimum content that lets a linguist recognize what
  will transfer without leaving GramTrans (SC-002). Reusing existing read helpers avoids
  duplicating multistring/possibility-list plumbing.
- **Verification**: FLExToolsMCP `get_object_api` / live reads to confirm the actual LCM
  property names and casts (e.g. which adhoc-prohib subclasses appear in the reference
  projects; where complex-form-type patterns live) — FR-019.
- **Alternatives rejected**: Label-only-plus-count for Text — fails the "readable
  excerpt" clarification (Q4); dumping full baseline — violates FR-018 bounding.

## R3 — Thin-category enrichment (US2)

- **Decision**:
  - **Phonological Feature** (gap category via `_direct_read_gap`): add an enrich hook
    surfacing `{Type, Values (permissible closed-feature values)}` from
    `IFsClosedFeature.ValuesOC`.
  - **Phonological Rule** (already on the `GetSyncableProperties` path, renders thin): add
    an enrich hook — mirroring `_enrich_natural_class` — surfacing structural content
    (StrucDesc / RHS / environment / ordering) so two same-named rules are
    distinguishable.
  - **Slot** (gap category): add an enrich hook surfacing the affixes occupying the slot
    (via the MSA/affix references), not just Name + Optional.
- **Rationale**: A label-only pane is decision-blind (spec US2); the enrich-hook pattern
  is the established, tested mechanism (natural-class/phoneme) and keeps props-dict shapes
  diff-compatible.
- **Verification**: Live reads of a phon feature (`Esperanto`/`Ejagham Mini`), a phon rule
  (`test_phonology_live` targets), and a populated slot to confirm the exact traversal.
- **Alternatives rejected**: Widening `_direct_read_gap`'s fixed field tuple globally —
  would leak irrelevant fields into other gap categories; per-category enrich is targeted.

## R4 — WS-mapping default correspondence (US4)

- **Decision**: Introduce a **primary-vernacular** concept in `ws_mapping.py`: the
  primary vernacular WS on each side is the map anchor. Source primary → target primary
  vernacular (FR-012). Sub-WSs match by **subtag suffix relative to each side's primary
  vernacular**: source `eja` primary + `eja-fonipa` sub → target `abc` primary +
  `abc-fonipa` sub, keyed on the shared suffix `-fonipa` even though base subtags differ
  (FR-013). The default is always a real target mapping, never "create"/"skip" (FR-014).
  Where zero or >1 target subs share a suffix, or the target has no primary vernacular,
  the row is left unresolved and confirm stays gated (FR-015, spec Edge Cases).
- **Rationale**: This is the clarified (Q1) suffix-relative-to-primary rule and covers the
  common related-languages case (SC-004) while refusing to guess on ambiguity.
- **Verification**: Live inspection of the reference pair's WS inventories (primary
  vernacular + sub variants) via FLExToolsMCP to confirm subtag structure and that suffix
  extraction is well-defined for real tags.
- **Alternatives rejected**: Full BCP-47 subtag matching on the whole tag — fails across
  differing base language subtags (the exact case Q1 addresses); first-N-char similarity
  (current `_similarity_rank`) — too coarse, would false-map.

## R5 — Ad hoc rule transfer-loss root cause (US5)

- **Decision**: Run a **read-only** live probe on a source/target pair that already
  received all stems and affixes; characterize exactly which portion of the ad hoc rules
  survives vs is lost, and record a root cause + scope decision. Reproduction is out of
  scope (FR-016); if warranted, it is recorded as a recommendation for a follow-up
  feature. Any in-scope residual loss becomes never-silent user-facing reporting (FR-017).
- **Leading hypothesis**: `to_ws_map_dict` (ws_mapping.py ~66-85) documents that
  `ApplySyncableProperties` **silently drops** any source WS whose mapped target Id is
  absent — a candidate silent-loss mechanism the probe must confirm or refute against the
  actual ad-hoc-rule transfer path.
- **Rationale**: The spec explicitly scopes US5 as investigation-with-decision, not
  guaranteed reproduction; the probe must be read-only (no destructive Move).
- **Verification**: FLExToolsMCP read-only probe producing evidence artifacts (what
  reproduced, what did not) plus a written root cause.
- **Alternatives rejected**: Attempting a live Move to observe loss — violates the
  read-only DoD and the non-destructive contract; building reproduction now — out of
  scope per FR-016.

## Cross-cutting decisions

- **Graceful degradation (FR-011)**: every new reader wraps its enrichment read so a
  failed cast/attribute logs (via `debuglog`) and falls back to the label-level props it
  already has — never a blank pane, never surfaced-as-broken output.
- **Bounding (FR-018)**: Text excerpt and any large member/affix list are truncated with a
  visible truncation indicator field in the props dict.
- **Read-only proof (SC-008)**: US1–US4 validated by offline unit tests + a read-only
  live-render pass (open real projects, render panes / exercise WS default, assert
  content); US5 by the read-only probe. No attended `needs_human` Move gate applies.

## T004 — Live-verified LCM shapes (FR-019, confirmed 2026-07-19 via FLExToolsMCP against `Ejagham Mini`)

`get_object_api` (read-only) confirmed the exact property surface for every new/enriched
category before any reader was written:

- **Text** — `IStText` exposes `Title` (IMultiAccessorBase / multistring), `ParagraphsOS`
  (ordered owned `IStTxtPara`), `Comment`, `Source`, `IsTranslation`. The IText container
  is enumerated via `project.Texts.GetAll()`; baseline/title/paragraphs are read through
  the existing `texts.py` wrappers (`Texts.GetName`, `Texts.GetParagraphs`,
  `Paragraphs.GetText`, `Segments.GetBaselineText`) rather than raw LCM. Reader reuses
  those helpers; excerpt is bounded (FR-018).
- **Writing System** — enumerated via `project.WritingSystems.GetAll()`; each WS has
  `.Id` (language tag — the stable identity; WS are not `ICmObject`s, so the finder keys
  on `Id`, not GUID), `.Handle`, and vernacular/analysis membership via
  `WritingSystems.GetVernacular()`/`GetAll()`. `MapsTo` is US4 (P2) → renders
  "unresolved" in P1.
- **Complex Form Type** — `ILexEntryType` is an `ICmPossibility` subtype: base
  `Name`/`Abbreviation`/`Description` (multistring) plus `ReverseName`/`ReverseAbbr`
  (IMultiUnicode). Enumerated via `_walk_possibilities_via_lexdb(project,
  "ComplexEntryTypesOA")`. Reader reuses the gap direct-read for Name/Abbrev/Desc and adds
  Reverse* + a Type label.
- **Ad hoc / Compound rule** — `IMoMorphAdhocProhib` exposes `FirstMorphemeRA` (single
  ref), `MorphemesRS`/`RestOfMorphsRS` (ordered ref collections); `IMoAlloAdhocProhib`
  uses `AllomorphsRS`; compound rules (`IMoEndoCompound`/`IMoExoCompound`) use
  `Left/Right/To/OverridingMsaOA`. Enumerated from
  `MorphologicalDataOA.AdhocCoProhibitionsOC` (recursing `IMoAdhocProhibGr.MembersOC`) +
  `CompoundRulesOS`. Base-typed collection elements MUST be cast to the concrete subclass
  (mirrors `categories._cast_rule_concrete`) or the subclass ref slots read back `None`.
  `ReferencedElements` = resolved labels of those referenced morphemes/allomorphs/MSAs.
- **Phonological Feature** — `IFsClosedFeature` exposes `ValuesOC` (unordered owned
  `IFsSymFeatVal`) + `ValuesSorted`. Type = "closed". Enrich adds `{Type, Values}` on top
  of the existing gap Name/Abbrev/Desc.
- **Phonological Rule** — `IPhRegularRule`/`IPhSegmentRule` exposes `StrucDescOS` (ordered
  owned structural-description contexts), `RightHandSidesOS` (RHS), `Direction` (Int32),
  `OrderNumber` (Int32), `FeatureConstraints`. `Structure` is a bounded structural summary
  (context/RHS counts + direction + order + any readily-resolved segment/NC labels) so
  same-named rules are distinguishable (FR-006) without re-implementing full phonological
  notation.
- **Slot** — `IMoInflAffixSlot` exposes `Affixes` (IEnumerable of occupying affix MSAs)
  and `OtherInflectionalAffixLexEntries`, plus `Name`/`Optional`/`Description`. `Affixes`
  is the occupying-affix list, labelled by owning-entry headword, bounded (FR-018).
- **Natural Class (US3 regression)** — shapes already confirmed in-code:
  `IPhNCSegments.SegmentsRC` (segment members) and
  `IPhNCFeatures.FeaturesOA.FeatureSpecsOC` (feature specs); resolvers
  `_natural_class_members`/`_natural_class_features`/`_enrich_natural_class` are present
  and correct. Regression is in delivery, not resolution (see R1).

## T023 — US3 Natural Class live-pin result (2026-07-19, read-only FLExToolsMCP)

**Finding: the described regression does NOT reproduce on `main`.** Read-only probes on
`Ejagham Mini` established, in order:

1. `NaturalClasses.GetSyncableProperties(nc)` returns `{Name, Abbreviation, Description}`
   only — it omits members entirely (the code comment claiming members arrive as
   `PhonemeGuids` is **stale** for this build; there is no such key to pop). All 5 NCs are
   segment-based (`PhNCSegments`); `IPhNCSegments.SegmentsRC` carries 22/4/4/7/7 members.
2. The covered-path enrich hook `_enrich_natural_class` (merge_preview ~1294) IS wired and
   runs; `_natural_class_members` resolves the SegmentsRC graphemes.
3. End-to-end, `merge_preview.props_for("natural_classes", guid)` on **current `main`**
   already returns `Members` (e.g. `['bh','ch','r','g',…]`, `['ny','ŋ','m','n',…]`).

Per R1's reproduce-first decision gate, an offline "absent-before / present-after" test that
*fails before a fix* cannot be written, because there is no live defect on the covered
segment path. US3 is therefore delivered as a **load-bearing guard** (T022 in
`tests/unit/test_032_preview_coverage.py`): it pins that `Members` is absent from the
resolved dict until the delivery step runs, present after, and survives `_filter_props`
(the R1 candidate downstream drop point). Any future change that drops NC members from
render fails that guard. No code change to the NC path was required (T024 = no-op fix;
guard + this evidence satisfy SC-003/FR-008 honestly). The feature-based path
(`IPhNCFeatures`) was not exercisable live (no feature-based NC in the pair); its resolver
is covered by the offline guard's design and the existing enrich code.

## Implementation findings (US1/US2 live validation, read-only)

All seven categories were validated by importing the worktree `merge_preview` into the live
FLEx runtime and calling `props_for` read-only:

- **Ejagham Mini**: `texts` → `{Title, Baseline (bounded), Truncated}`;
  `writing_systems_check` → `{Name, Code, Kind, Rank, MapsTo:"unresolved"}`;
  `complex_form_types` → `{Name, Abbreviation, Description}` (base ILexEntryType has no
  Reverse* — those appear only on the LexEntryInflType subtype).
- **Mbugwe Lizzie HCPractice**: `adhoc_compound_rules` →
  `{ReferencedElements:['Noun','Affix in np slot …']}`; `slots` →
  `{Name, Optional, Affixes:['Affix in (aug) slot …']}`; `phonological_features` →
  `{…, Values:['-','+'], Type:'closed'}`; `phonological_rules` →
  `{Name, Structure:['1 context(s)','1 RHS','direction=0','order=1']}` (order number
  distinguishes same-named rules, FR-006).

**Bug fixed en route (US2 enabling):** the `phon_feature` gap finder looked up
`handle.PhonologicalFeatureSystem` / `handle.FeatureSystem`, which do not exist on the
flexicon project handle, so phonological-feature previews were blank even before
enrichment. Fixed to resolve the feature system via
`ILangProject(handle.Cache.LangProject).PhFeatureSystemOA.FeaturesOC` (new
`_phon_feature_system` helper; the GUID enumerated by `project.PhonFeatures.GetAll()` was
live-verified to match members of that collection). Old attributes retained as fallbacks.
