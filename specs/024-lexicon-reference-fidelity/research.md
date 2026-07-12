# Phase 0 Research: Lexicon Reference & Owned-Object Fidelity

All items below were resolved from the originating live-probe session (FLExTools MCP over
Ejagham Full/Mini) and code inspection of `src/gramtrans/Lib/`. No open NEEDS CLARIFICATION
remain.

## R1 — Why references are lost today; what to re-wire

**Decision**: Object references are dropped because `ApplySyncableProperties` emits each
object-ref as a GUID string and its apply-loop discards them (confirmed by the existing
`_resolve_target_status` / `_resolve_target_morph_type` re-wire comments in
`categories.py`). The fix is a **post-apply re-wire pass** that runs the generic resolver on
every reference field, not just the four currently handled (MorphType, Status, MSA/POS,
SemanticDomains).

**Evidence**: `GetSyncableProperties` returns 9 entry keys / 19 sense keys; sense keys
*include* `SenseTypeRA`, `DoNotPublishInRC`, `DoNotShowMainEntryInRC` but they are dropped on
apply and never re-wired → blanking bug (FR-006).

**Rationale**: Matches the proven pattern already in the codebase; minimal surface change.

**Alternatives rejected**: Patching `ApplySyncableProperties` upstream in flexicon —
out-of-repo, wider blast radius, and it would still not create absent target items.

## R2 — Preview-before-mutate integration (Principle III obligation)

**Decision**: The resolver is split into a **decision function** (pure: given source item +
target list, returns one of `LINK` / `CREATE` / `UPDATE` / `REPORT_DROPPED` with the target
item or reason) called from the plan-builder (`preview.py` path), and an **apply function**
called from `transfer.py`. Preview lists each referenced-item decision per owning object;
Move executes them.

**Rationale**: Principle III forbids hidden execute-time writes. Reusing the existing
plan/execute split keeps the resolver honest and testable without a live target.

**Alternatives rejected**: Resolve-and-write inline during the closure walk (simpler but
violates Preview-before-mutate).

## R3 — Custom vs. shared/default classification (FR-003/005)

**Decision**: Reuse `protection._is_protected(item)`. FieldWorks factory/GOLD possibility
items carry `IsProtected = true`; custom items do not. So: not-protected + diverged →
UPDATE the target item; protected (shared/default) + diverged → LINK + emit a dropped/
divergence record. No new factory-GUID table (FR-005 satisfied).

**Rationale**: `_is_protected` already encodes the GOLD/reserved identity the constitution
(Principle I, v7.0.0) uses; single source of truth.

**Alternatives rejected**: A hard-coded factory-GUID set (explicitly forbidden by FR-005);
heuristic on GUID prefix `d7f7…` (brittle, incomplete).

## R4 — Ancestor-chain creation for hierarchical lists (FR-002)

**Decision**: When creating an absent item, walk `source_item.Owner` up until the owner is
the possibility list; create any missing ancestors top-down first (each with its preserved
GUID), then create the leaf under the correct parent's `SubPossibilitiesOS`. Cache created
items by GUID within the run.

**Rationale**: Academic Domains / Anthropology / some Sense Types are trees; a leaf created
at the list root would misrepresent the hierarchy.

**Alternatives rejected**: Flatten to list root (loses hierarchy, fails the edge case).

## R5 — Owned-object creation surfaces (FR-009)

**Decision**: Use flexicon Operations where available, `project.GetService(IFooFactory)`
otherwise, for: `ILexExampleSentence` (+ `ICmTranslation` with `TypeRA` via the resolver),
`ILexPronunciation`, `ILexEtymology`, and recursive `ILexSense` sub-senses (recurse
`sense.SensesOS`, which the current entry loop skips — it only walks top-level `SensesOS`).
`residue.CARRIER_A_CLASSES` already registers `LexExampleSentence`, `LexPronunciation`,
`LexEtymology`, `LexReference`, so residue tagging of created children is already supported.

**Rationale**: The residue layer anticipated these classes; only the create/walk is missing.

**Alternatives rejected**: Copy owned children via a second `GetSyncableProperties` round
without recursion (misses sub-senses and child references).

## R6 — Allomorph-hung data: environments + APRs (FR-009a)

**Decision**: For each copied allomorph, resolve `PhoneEnvRC` members against the target's
phonological-environment list (already a transferable category, `PH_ENVIRONMENT`) via the
resolver. Ad-hoc prohibition rules are `IMoAlloAdhocProhib` / `IMoMorphAdhocProhib` owned by
`LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC`; discover those whose
`FirstAllomorphRA` / `RestOfAllosRS` / `MorphemesRS` reference a copied allomorph/morpheme
and reproduce them (or report if their other members were not copied).

**Rationale**: Principle I names "allomorph → environment, APR → category" as must-resolve
cross-references; this closes that clause for the lexicon path.

**Alternatives rejected**: Treat APRs as a separate grammar category (they are lexicon-
anchored to specific allomorphs, so they belong to the entry closure).

**Open sub-point (defer to tasks, not blocking)**: APRs referencing a mix of copied and
non-copied allomorphs → reproduce for copied members only, report the rest (mirrors the
lexical-relation partial-member rule, FR-008). APR members span `FirstAllomorphRA` +
`RestOfAllosRS` + `AllomorphsRS` (all confirmed on `IMoAlloAdhocProhib`).

**MCP validation (2026-07-11)**: all API surfaces cited in the contracts were confirmed live
via FLExTools MCP `get_object_api` — see data-model.md for the property list. Two extras
surfaced and were folded into the field map: `IMoStemAllomorph.StemNameRA` (→ existing
STEM_NAMES target) and `ILexEtymology.LanguageRS` (→ `LexDb.LanguagesOA`).

## R7 — Divergence fingerprint for a possibility item (FR-003)

**Decision**: Compare source vs. target item on Name and Abbreviation multistrings (all
writing systems present) plus, where relevant, Description. Reuse the multistring-compare
helpers already in `conflict.py` / `fingerprints.py`. "Identical" → LINK; any diverged
alternative → UPDATE (custom) or REPORT (shared/default).

**Rationale**: Name/abbr are the user-visible identity of a list item; matches the
renamed-default scenario in US1.

**Alternatives rejected**: Full field-by-field structural compare (overkill for list items;
their editable surface is small).

## R8 — MetaDataCache census mechanics (FR-011)

**Decision**: `IFwMetaDataCacheManaged.GetFields(clid, includeSuperclasses=true,
fieldTypes=kgrfcptAll)` → filter to owning/reference cpt values {23,24,25,26,27,28} via
`GetFieldType(flid)`. Populated test: atomic (23/24) → `ISilDataAccess.get_ObjectProp(hvo,
flid) != 0`; collection/sequence (25/26/27/28) → `get_VecSize(hvo, flid) > 0`. Include custom
fields (they surface as flids on the bounded classes). Run over source object + its target
copy; a populated-source-but-empty-target field is a gap.

**Rationale**: Model-driven, so it catches fields nobody hand-listed; complete because custom
fields are location-bounded (Q4).

**Alternatives rejected**: `dir()`-based reflection (no cpt/kind info, can't classify ref vs
owned vs value); hand-maintained field list (the very defect this replaces).

## R9 — Dropped-item report channel (FR-010/013)

**Decision**: Add a `DroppedItemRecord` dataclass (owning object identity, field name, source
item name + GUID, reason) and a per-object `FidelityStatus` to `models.py`; thread a
collector through the closure walk and fold it into `report.RunReport` so records render in
both Preview and the post-run statistics panel (satisfies the "No silent skips" gate).

**Rationale**: Reuses the existing RunReport rendering; one surfacing path for Preview + post-
run.

**Alternatives rejected**: Logging-only (fails FR-010's user-surfaced requirement).
