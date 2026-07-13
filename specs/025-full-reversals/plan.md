# Implementation Plan: Full Reversals

**Branch**: `025-full-reversals` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification (STUB) from `specs/025-full-reversals/spec.md`

> **Spec status note.** The 025 spec is a planned stub (no formal FR/user-story/SC block yet).
> This plan encodes the scope decisions its "Open Questions" flagged, resolved with the user on
> 2026-07-11: (1) copy **only** reversal indexes that have entries linking to copied senses
> (closure-scoped); (2) resolve each index's reversal categories **independently** via the 024
> resolver against the per-index `PartsOfSpeechOA` list; (3) surface drops through **one
> unified** 024 dropped-items report. **Amended scope (2026-07-11):** the user folded the
> configuration-view files IN — the stub had `.fwdictconfig` config copy as out-of-scope
> "unless a later decision folds config-file copy in"; that decision is now made. 025 therefore
> covers **two** things: (A) the reversal-index **content** (entries/forms/categories/
> sub-entries), and (B) copying the **dictionary and reversal configuration views**
> (`.fwdictconfig`). The user's expectation that reversal *entries* "come with the lexicon" is
> satisfied by (A): reversal entries are reproduced as part of the copied-sense closure. A
> follow-up `/speckit-specify` may formalize these into FRs; the design below is stable under
> that formalization.

## Summary

Feature 025 has two coordinated parts.

**Part A — Reversal-index content (LCM).** For every sense the transfer copies, find the
source reversal-index entries that point back at it (`IReversalIndexEntry.SensesRS` /
`IReversalIndex.EntriesForSense`), reproduce those entries on the target's matching
per-writing-system index (creating the index via `ReversalIndexOperations.Create` if absent),
carry the entry's reversal form and recurse its owned sub-entries (`SubentriesOS`), and resolve
each entry's reversal **category** (`PartOfSpeechRA`) against that index's own
`PartsOfSpeechOA` possibility list using feature 024's generic referenced-possibility resolver.
This is what makes reversal entries "come with the lexicon" — they ride along with the copied
senses. Reversal work is closure-scoped to copied senses — no wholesale reversal-index
duplication.

**Part B — Configuration views (files).** Copy the source project's dictionary and reversal
configuration views — the `.fwdictconfig` XML files under
`<project>/ConfigurationSettings/Dictionary/` and `.../ReversalIndex/` — into the target
project's corresponding directories. These are sidecar files, not LCM objects, so they are
handled by a file-copy path (outside the flexicon surface). Each config references writing
systems (`writingSystem="en"`, WS option ids), custom fields (by name), and paragraph/character
styles; the copy reports any such reference the target does not hold (a config referencing a
custom field or WS the target lacks), rather than silently importing a broken view.

Both parts participate in the Preview plan (Principle III) — reversal decisions and config-file
Add/Overwrite/Skip appear before any write — and anything unreproducible (unmapped writing
system, shared/default reversal-category divergence, sense not in the copy set, config
reference to an absent target item) is surfaced through 024's unified never-silent dropped-items
report.

**Hard dependency**: feature **024-lexicon-reference-fidelity** must land first. 025 reuses its
`Lib/references.py` resolver (`decide_reference`/`apply_reference`), its `Lib/owned.py` walk
pattern, its `DroppedItemRecord`/`FidelityStatus` channel in `Lib/report.py`, and
`protection._is_protected` for custom-vs-shared classification.

## Technical Context

**Language/Version**: Python 3 (CPython + pythonnet), hosted by a stock FlexTools install.

**Primary Dependencies**: flexicon (`pyflexicon>=4.1`) Operations API — validated live via
FLExTools MCP (2026-07-11): `ReversalIndexOperations.GetAll()` / `.Create(name,
writing_system)`, `ReversalIndexEntryOperations.GetAll(index)` / `.Create(index, form,
sense=None, wsHandle=None)`; LCM interfaces `IReversalIndex`
(`WritingSystem`, `EntriesOC`, `AllEntries`, `PartsOfSpeechOA`, `EntriesForSense`,
`FindOrCreateReversalEntry`) and `IReversalIndexEntry` (`SensesRS`, `PartOfSpeechRA`,
`ReversalForm` IMultiUnicode, `SubentriesOS`, `MainEntry`/`OwningEntry`), reached via the LCM
cache; `project.GetService(IFooFactory)` fallback; PyQt host UI/report panel.

**Storage**: FieldWorks `.fwdata` project pair via the LCM cache; no external store. The live
target project is the divergence baseline (inherited from 024 FR-005). Part B additionally
reads/writes the project's on-disk sidecar config directory —
`<ProjectsDir>/<ProjectName>/ConfigurationSettings/{Dictionary,ReversalIndex}/*.fwdictconfig`
(confirmed present on the Ejagham Mini / Ejagham Full GT-Test pair) — via plain file I/O.

**Testing**: pytest under `tests/unit/`; the offline fidelity harness (024) is extended with
reversal classes under `tests/verification/`.

**Target Platform**: Windows (FlexTools host); source → target between two FLEx projects.

**Project Type**: Single project — FlexTools-compatible module; helpers under
`src/gramtrans/Lib/`.

**Performance Goals**: Bounded per-sense overhead over the existing closure walk. Reversal
entries are discovered once per copied sense; per-index reversal-category items are resolved
once and cached per run (reuse 024's resolver cache) so cost is O(distinct reversal items),
not O(references).

**Constraints**: Preview-before-mutate (Principle III) — reversal decisions appear in the plan
as Add/Link/Update/Skip/Report before any write. Writing-system mapping (`Lib/ws_mapping.py`)
gates every reversal index: an index whose source WS cannot be mapped to a target analysis WS
is reported, never guessed. Non-destructive (never blank a target field from an empty source).
Graceful degrade: an unresolvable reversal item is reported, never thrown or silently dropped.
flexicon-direct only (Principle II).

**Scale/Scope**: Reversal-index entries linked to copied senses, their reversal forms,
recursive sub-entries, and each index's reversal-category list. Texts/wordforms (026) and
reversal-index `.fwdictconfig` configuration views are excluded.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. FLEx Domain Fidelity** (NON-NEGOTIABLE) | **Directly served.** A copied reversal entry's `PartOfSpeechRA` MUST resolve to a real item in the target index's `PartsOfSpeechOA` or fail loudly (the "APR → category … MUST resolve to real objects" clause, applied to reversals). GUID preservation on create; the concept↔GUID binding for reversal-category POS items honored via 024's create-time remap + `_is_protected`. Writing-system identity validated before any reversal string is written (Principle I WS clause). **PASS.** |
| **II. flexicon-Direct** | Part A uses `ReversalIndexOperations`/`ReversalIndexEntryOperations` wrappers (MCP-confirmed), `project.GetService(IFooFactory)` fallback, `CastingOperations.cast_to_concrete` for polymorphic access. Part B (config `.fwdictconfig` files) is **outside the LCM surface** — sidecar files are copied by plain file I/O; flexicon does not (and need not) model them. The flexicon-direct rule governs LCM access, which Part B does not perform, so this is not a deviation. **PASS.** |
| **III. Preview-Before-Mutate** (NON-NEGOTIABLE) | Reversal walk splits decision (plan-builder, `preview.py`) from apply (`transfer.py`); each reversal index/entry/category decision represented per item in Preview. Config-view copy is likewise planned: Preview lists each `.fwdictconfig` as Add / Overwrite / Skip (and any absent-target-reference report) before any file is written in Move mode. **PASS with design obligation** (tracked in research R2, inherited from 024). |
| **IV. Phased Merge Discipline** | Reuses ADD_NEW/LINK/UPDATE/OVERWRITE mode vocabulary and the `conflict.py` update semantic for the per-index reversal-category list. No new mode. **PASS.** |
| **V. Referential Completeness** | Reversal entries + their categories are pulled as the closure of copied senses, displayed in Preview, deselectable per item; unresolved items reported. A copied config view whose referenced WS / custom field / style is absent in the target is reported (not silently broken). **PASS.** |
| **Workflow: No silent skips** | Unified 024 dropped-item channel carries every non-reproduced reversal item into Preview + the post-run panel. **PASS** — the feature's backstop. |

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/025-full-reversals/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── reversal-walk.md
│   ├── reversal-category-resolution.md
│   └── config-view-copy.md
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
src/gramtrans/Lib/
├── reversals.py         # NEW (Part A): reversal closure walk — discover entries for copied
│                        #      senses, reproduce index/entry/form/sub-entries, route
│                        #      PartOfSpeechRA through the 024 resolver; emit DroppedItemRecords
├── config_views.py      # NEW (Part B): dictionary + reversal .fwdictconfig file copy —
│                        #      enumerate source configs, plan Add/Overwrite/Skip, scan each
│                        #      config's WS/custom-field/style references against the target,
│                        #      report absent references; copy files in Move mode
├── references.py        # REUSE (024): decide_reference/apply_reference for the per-index
│                        #      PartsOfSpeechOA list (reversal categories)
├── owned.py             # REUSE (024): recursive-child walk pattern for SubentriesOS
├── protection.py        # REUSE (024): _is_protected → custom-vs-shared reversal-category class
├── ws_mapping.py        # REUSE: source→target analysis-WS mapping gates each reversal index
│                        #      AND validates a config view's referenced writing systems
├── report.py            # REUSE (024): DroppedItemRecord + FidelityStatus (unified report)
├── residue.py           # MODIFY: register ReversalIndexEntry (+ index) as residue carriers
├── categories.py        # MODIFY: after a sense is copied, invoke the reversal walk
├── preview.py / transfer.py  # MODIFY: surface reversal + config-view decisions in plan + execute
└── models.py            # MODIFY: ReversalFieldSpec + ConfigViewRecord; reuse DroppedItemRecord

tests/
├── unit/
│   ├── test_reversal_walk.py            # NEW: entry discovery, form copy, sub-entry recursion,
│   │                                    #      WS-mapping gate, closure scoping
│   ├── test_reversal_category_resolve.py# NEW: create/update/link+report for per-index POS
│   └── test_config_view_copy.py         # NEW: enumerate/plan Add-Overwrite-Skip, absent-ref
│                                        #      report, Move-mode file copy (temp dirs)
└── verification/
    └── fidelity_census.py               # EXTEND (024): add reversal classes to the census map
```

**Structure Decision**: Single-project FlexTools module. Two new focused helpers:
`reversals.py` (Part A) keeps the reversal walk isolated and independently testable while
reusing 024's resolver, owned-walk pattern, and report channel wholesale; `config_views.py`
(Part B) isolates the file-based config copy — the only file-I/O path in the module — so it does
not entangle the LCM transfer code. The reversal-category list is *not* the main grammar POS
list (`LangProject.PartsOfSpeechOA`) — MCP confirms `IReversalIndexEntry.PartOfSpeechRA` points
into the per-index `IReversalIndex.PartsOfSpeechOA`, so it is resolved as its own possibility
list (scope decision 2).

## Complexity Tracking

> No Constitution Check violations — table intentionally omitted.
