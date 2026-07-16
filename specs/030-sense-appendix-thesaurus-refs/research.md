# Research: Sense Appendix & Thesaurus References (030)

All findings below are from read-only investigation on 2026-07-16 via FLExTools MCP
(projects `Ejagham Full`, `Ejagham Full GT-Test`) and a direct `.fwdata` scan across
all on-disk projects.

## Finding 1 — Both subject fields are vacuous-live everywhere

**Decision**: Live proof for both sections uses **constructed fixtures**; no harvested
project data can exercise either field.

**Evidence**:
- `.fwdata` scan of all 79 on-disk projects: the string "thesaurus" appears in **zero**
  files; every "appendix" hit is prose inside a `<Definition>`/style description, never
  the `AppendixesOC` collection or an `AppendixesRC` reference.
- MCP census on `Ejagham Full` (4304 entries / 2491 senses): `LexDb.AppendixesOC` = 0;
  senses with `AppendixesRC` = 0; senses with `ThesaurusItemsRC` = 0.
- Consistent with 024's `validation-status.md` ("`LexAppendix` / `ThesaurusItems`
  possibilities: 0 populated; `LexDb.AppendixesOC` = 0").

**Alternatives considered**: harvesting from a real project — rejected, none exists.

## Finding 2 — `LexAppendix` is a bespoke owned class, not a possibility list

**Decision**: **Section A links by GUID only.** No create, no owned-graph reproduction.

**Evidence**: `get_object_api(LexAppendix)` shows only 4 members: `ClassID`, `ClassName`,
`ContentsOA : IStText` (owned atomic), `OwnershipStatus`. It owns a structured-text
document, not list items. 024's possibility-list resolver (which resolves by name /
fingerprint within a known `ICmPossibilityList`) does not apply. `LexAppendix` has no
`Name` usable by `references._item_label` (returns "" — already handled).

**Target lookup**: scan the target `LexDb.AppendixesOC` for an appendix whose `.Guid`
equals the source appendix's `.Guid`. Small collection (0 in every real project), so a
linear scan is fine and avoids `ICmObjectRepository.GetObject` throwing on an absent
GUID. If found → wire the reference; if absent → `DroppedItemRecord` (never create).

**Access path**: `ILexDb(ILangProject(target.Cache.LangProject).LexDbOA).AppendixesOC`
(both casts confirmed required by the MCP preflight).

**Out of scope (explicit)**: an appendix present by GUID but with diverged `IStText`
content is linked as-is; 030 does not mutate or report the content divergence.

## Finding 3 — Possibility-list GUIDs are NOT stable across projects

**Decision**: For Section B, discover the source item's owning list by walking `.Owner`,
but **do not** match the equivalent target list by the list's GUID. Match instead by the
list's **owner-class + owning-flid** (both model-stable), and delegate the *item*
resolution to 024's resolver.

**Evidence**:
- Source `Ejagham Full` SemanticDomainList GUID = `c924bfce-beed-4382-95e8-62b54951c83d`.
- Target `Ejagham Full GT-Test` SemanticDomainList GUID = `90aa3d0a-3573-418d-88c3-3a4aab48ef9b`.
- **Different GUIDs for the same standard list** → a cross-project "match list by GUID"
  would fail even for factory lists. This is exactly why 024's `REFERENCE_FIELD_MAP`
  resolves each list by a fixed **accessor path** (`_lp(target).SemanticDomainListOA`),
  not by list GUID, and matches the *item* by GUID/fingerprint within that list.

## Finding 4 — `.Owner` walk reaches the owning `ICmPossibilityList` cleanly

**Decision**: Section B's dynamic-owner discovery = walk `item.Owner` upward, casting each
hop to `ICmPossibilityList`; stop at the first successful cast (that is the owning list).
Guard the loop with a depth cap and a null-owner break (never raises).

**Evidence**: For a `CmSemanticDomain`, the chain is a single hop:
`CmSemanticDomain#… -> CmPossibilityList#…`. A nested item would add
`CmPossibility` hops before the list; the same loop handles both.

## Section B design (consolidated)

Given a source thesaurus `CmPossibility` referenced by `LexSense.ThesaurusItemsRC`:

1. **Discover source owning list**: walk `.Owner` to the first `ICmPossibilityList`
   (Finding 4). If none found within the depth cap → `DroppedItemRecord` (FR-005).
2. **Locate equivalent target list** (Finding 3) by mirroring the source list's location:
   read the source list's `Owner.ClassName` + `OwningFlid` (model-stable identifiers) and
   navigate the same owner+flid on the target. For the common singleton owners
   (`LangProject`, `LexDb`) the target owner is unique. Fallback: match a target
   `ICmPossibilityList` by Name. If neither resolves → `DroppedItemRecord` (FR-005).
3. **Resolve the item** against the discovered target list by constructing a synthetic
   `ReferenceFieldSpec` (owner_class `LexSense`, field `ThesaurusItemsRC`, cardinality
   `COLLECTION`, `hierarchical=True`, `target_list_path=lambda _: <discovered target
   list>`) and calling 024's `references.decide_reference` / `apply_reference`. This
   reuses create-with-ancestor-chain, link-when-present, and custom-vs-shared/default
   reconciliation unchanged (FR-004, FR-007, Principle V).
4. **Wire** the copied sense's `ThesaurusItemsRC` to the resolved target item.

**Rationale**: reuses the entire 024 resolver for the hard part (item create/link/dedupe)
and adds only the dynamic list-discovery step the field requires. No new factory-GUID
table (Principle I / 024 FR-005 preserved).

## Preview/Move parity (FR-008)

Both legs are invoked from the two existing sense-loop call sites that already share
`_report_dropped_sense_scope_gaps` (Preview: `_plan_entry_reference_decisions`; Move:
`_walk_lex_entry_closure`). The link/resolve decision is a pure function of
(source item, target project state), so the two paths' decisions and residual drop sets
stay identical by construction — the same invariant 024 already documents for the
drop-only case.

## Census reclassification (FR-009)

`tests/verification/fidelity_census.py`: move `("LexSense","AppendixesRC")` and
`("LexSense","ThesaurusItemsRC")` from `Bucket.DROP_REPORTED` to `Bucket.COPIED`. The
`PicturesOS` row stays DROP_REPORTED (029). The never-silent classifier guard and the
single-member `OUT_OF_SCOPE_EXCLUDED` frozenset (`LexEntry.MainEntriesOrSensesRS`) are
unchanged. `_SENSE_SCOPE_GAP_FIELDS` in `categories.py` drops the two promoted rows;
`PicturesOS` remains so the drop-only reporter still fires for pictures.
