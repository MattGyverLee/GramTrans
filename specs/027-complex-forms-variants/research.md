# Phase 0 Research: Complex Forms & Variants (027)

All LCM claims below were checked read-only via FLExToolsMCP (`flextools_get_object_api`,
`flextools_find_wrappers_for_lcm`) on 2026-07-13, per the repo rule "ALWAYS use
FLExToolsMCP instead of direct code inspection" for flexicon/liblcm.

## Decision 1 — `LexEntryRef` is created via the raw `ILexEntryRefFactory` (no flexicon wrapper)

- **Decision**: Create target `LexEntryRef` objects with
  `factory = ILexEntryRefFactory(target.GetFactory(ILexEntryRefFactory))`, GUID-preserving,
  owned into `ILexEntry(target_entry).EntryRefsOS`. This mirrors the existing raw-factory
  idiom already in `categories.py` (`ILexEntryTypeFactory`, `ILexEntryInflTypeFactory`,
  `ILexEntryFactory`, `IMoInflAffixSlotFactory` all obtained via `target.GetFactory(...)`).
- **Rationale**: `flextools_find_wrappers_for_lcm(ILexEntryRefFactory)` returned
  `found: false` — flexicon has **no** wrapper for this factory, so the raw LCM factory is
  the sanctioned path (constitution II: `GetService/GetFactory` fallback when no Operations
  wrapper covers a surface).
- **Open item confirmed-live-at-implementation**: the MCP index exposed no method list for
  `ILexEntryRefFactory` (`total_methods: 0`). The exact `Create` signature (bare `Create()`
  + `EntryRefsOS.Add`, vs. a GUID-taking overload, vs. an `ILexEntry` helper) MUST be
  confirmed live during implementation, following the GUID-preserving `Create(Guid)` +
  owning-slot pattern already proven for `IMoStemMsaFactory.Create(Guid)` and
  `ILexEntryFactory` in this file. If no GUID overload exists, create then set/assert the
  GUID via the same mechanism the entry/MSA creation paths use.
- **Alternatives rejected**: (a) an `ILexEntry` convenience creator — the only ref-creating
  ILexEntry member surfaced is `FindMatchingVariantEntryRef` (a *finder*, not a creator), so
  no wrapper shortcut exists; (b) deep-copying the source ref object — LCM factories don't
  support cross-cache object graft; GUID-preserving factory Create is the established idiom.

## Decision 2 — every `ILexEntryRef` member access MUST be cast (issue #28 layer 2)

- **Decision**: Cast with `_cast_lcm(ref, "ILexEntryRef")` before touching any of `RefType`,
  `ComponentLexemesRS`, `PrimaryLexemesRS`, `VariantEntryTypesRS`, `ComplexEntryTypesRS`,
  `ShowComplexFormsInRS`; cast `_cast_lcm(entry, "ILexEntry")` before `EntryRefsOS`.
- **Rationale**: MCP `get_object_api(ILexEntryRef)` reports **all 19 properties require
  casting** ("Preflight will reject uncast access"); `ILexEntry.EntryRefsOS` likewise
  requires `ILexEntry(obj)`. `_run_post_pass_a` already casts both — the creation step must
  do the same. This is exactly the layer-2 bug shape from issue #28; re-introducing an
  uncast access is a regression.
- **Alternatives rejected**: relying on pythonnet's runtime type — proven wrong live in #28
  (uncast `EntryRefsOS` → `None`).

## Decision 3 — `RefType` is the variant/complex discriminator (Int32)

- **Decision**: Carry the source `RefType` verbatim onto the created ref: `0 = variant`
  (`krtVariant`), `1 = complex-form` (`krtComplexForm`). Reuse the existing
  `categories._LEX_ENTRY_REF_KIND_BY_TYPE` / `_lex_entry_ref_kind` mapping; an unrecognized
  value is labelled and reported, never guessed.
- **Rationale**: MCP confirms `RefType` is a plain `Int32` property on `ILexEntryRef`; the
  024 drop-reporting code already interprets 0/1 with exactly this mapping.
- **Alternatives rejected**: inferring kind from which type-collection is populated —
  fragile; `RefType` is authoritative.

## Decision 4 — entry-type + publication refs resolve through 024's three-way resolver

- **Decision**: Resolve `VariantEntryTypesRS` / `ComplexEntryTypesRS` (both `ILexEntryType`
  possibility items) and `ShowComplexFormsInRS` (publication `ICmPossibility`) against the
  target lists using `references.decide_reference` / `apply_reference` — absent → create incl.
  ancestor chain; diverged custom → update; diverged shared/GOLD → link + report; identical →
  link. GOLD/reserved items are GUID-remapped at creation (Principle I) and never
  overwritten.
- **Rationale**: These are the same possibility-list-reference shape 024 already handles for
  lexical relations; reuse avoids a second resolver and keeps disposition semantics uniform
  (constitution IV). `ILexEntryTypeFactory` is already used in `categories.py` for the
  entry-type list.
- **Alternatives rejected**: a bespoke entry-type resolver — duplicates 024 and risks
  disposition drift.

## Decision 5 — reproduce in-closure, report the rest (flip the DROP_REPORTED policy)

- **Decision**: Change `_report_dropped_entry_refs` from "emit a DroppedItemRecord for
  *every* `LexEntryRef`" to "reproduce refs whose component/primary/type ends are all in the
  copy closure; emit a `DroppedItemRecord` only for refs (or members) whose other end is
  outside the closure or otherwise unresolvable." The Preview path
  (`_plan_entry_reference_decisions`) mirrors the same split read-only so Preview/Move
  drop-sets stay identical by construction (024/025 parity discipline).
- **Rationale**: This is the exact behavior change #30 asks for; the never-silent guarantee
  (Principle V) is preserved because unreproducible relationships still surface as drops.
- **Alternatives rejected**: keeping report-all and adding creation separately — would
  double-count (a reproduced ref reported as dropped) and break SC-004's drop-count parity.

## Decision 6 — creation runs as a post-pass after all closure entries exist

- **Decision**: Run `LexEntryRef` creation as the front half of the STEMS-tail post-pass
  (immediately before the existing `_run_post_pass_a` wiring), inside the same
  `_run_tail_once` idempotency guard. Endpoints resolve via `_resolve_target_by_guid`.
- **Rationale**: A ref's components must already exist on the target before the ref can point
  at them; the STEMS tail is where 024/031 already do this (both affix + stem entries stable).
  `_run_post_pass_a` already lives there and already consumes `plan.lexentry_ref_bindings`.
- **Alternatives rejected**: creating refs inline during `_walk_lex_entry_closure` — the
  other end may not be copied yet (ordering hazard); a separate standalone tail pass —
  needless second traversal of the same bindings.

## Decision 7 — idempotency via GUID + `FindMatchingVariantEntryRef`

- **Decision**: Before creating, skip if the target entry already owns a `LexEntryRef` with
  the source GUID (GUID guard); for variant refs additionally usable as a semantic check via
  `ILexEntry.FindMatchingVariantEntryRef(component, variantType)`. Membership guards on the
  `RS` collections (already present in `_run_post_pass_a`) prevent duplicate wiring.
- **Rationale**: MCP confirms `FindMatchingVariantEntryRef(IVariantComponentLexeme,
  ILexEntryType) -> ILexEntryRef|null` exists; combined with the GUID guard this satisfies
  SC-003 (0 duplicates on re-Move).
- **Alternatives rejected**: unconditional create — would duplicate refs on re-Move.

## Decision 8 — live-coverage split (US3 deferred)

- **Decision**: Live-prove US1 (variant) + US2 (variant-type) on `Ejagham Mini → Target` (6
  variant refs, per issue #28/#30 evidence). Ship US3 (complex-form) with offline coverage
  only; defer its live `0 → N` proof to a constructed complex-form fixture, tracked as a
  follow-up.
- **Rationale**: `flextools_list_projects` + the #30 evidence confirm `Ejagham Mini` has 0
  complex-form entries; no off-the-shelf corpus exercises `RefType`=1 live. This mirrors how
  issue #31 tracks the missing MSA→slot live source rather than blocking the code.
- **Alternatives rejected**: blocking the whole feature on a complex-form fixture — delays
  the live-provable US1/US2 fix for issue #28/#30 indefinitely.

## Resolved unknowns

- WS handling on created entry-types: inherited from 024's resolver (routes Name/Abbrev/Desc
  through `ApplySyncableProperties(ws_map=...)`); no new WS path. No NEEDS CLARIFICATION
  remains.
