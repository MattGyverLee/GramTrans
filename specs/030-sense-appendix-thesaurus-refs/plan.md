# Implementation Plan: Sense Appendix & Thesaurus References

**Branch**: `030-sense-appendix-thesaurus-refs` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/030-sense-appendix-thesaurus-refs/spec.md`

## Summary

Promote the two `LexSense` reference fields that feature 024 currently
DROP_REPORTs (never-silent) from **DROP_REPORTED** to **COPIED**:

- **Section A — `LexSense.AppendixesRC`** (target `LexAppendix`, a bespoke owned
  class in `LexDb.AppendixesOC`, NOT a possibility list): **link-by-GUID only**. If
  the target already owns a `LexAppendix` with the source appendix's GUID, wire the
  copied sense's reference to it; otherwise emit a `DroppedItemRecord` (never create
  the appendix or reproduce its owned `IStText` graph).
- **Section B — `LexSense.ThesaurusItemsRC`** (generic `CmPossibility`, dynamic
  home list): **dynamic-owner resolver**. Walk the source item's `.Owner` chain up to
  its owning `ICmPossibilityList`, resolve the equivalent list in the target, then
  resolve/create/link the item there through feature 024's existing possibility-list
  resolver (`references.decide_reference` / `apply_reference`). If the owning list
  cannot be discovered or has no target equivalent, emit a `DroppedItemRecord`.

Both fields must flip to **COPIED** in `tests/verification/fidelity_census.py` with
the never-silent classifier guard and the single-member `OUT_OF_SCOPE_EXCLUDED` set
left intact. Because both fields are vacuous-live across every available project,
live proof requires **constructed fixtures**.

## Technical Context

**Language/Version**: Python 3 (FlexTools-hosted), per constitution Technology
constraints.

**Primary Dependencies**: flexicon (`pyflexicon>=4.1.1`), imported directly (no
adapter shim) per Principle II. Reuses 024's `Lib/references.py` resolver,
`Lib/preview.py` / `Lib/transfer.py` Preview/Move split, and the
`DroppedItemRecord` machinery.

**Storage**: LCM (FieldWorks project `.fwdata`), accessed via flexicon Operations
classes.

**Testing**: pytest offline suite (fakes / unit) + FLExTools MCP live proof against
constructed fixtures (both fields are vacuous-live everywhere, so no harvested-data
live proof is possible).

**Target Platform**: Windows FlexTools installation; LCM-bound paths exercised under
a live host / the integration suite.

**Project Type**: Single project (library/CLI-style FlexTools module).

**Performance Goals**: N/A — per-transfer field resolution; both fields near-never
populated in practice.

**Constraints**: Preview/Move parity (Principle III); never-silent guarantee
(SC-004); non-destructive (never blank a populated target field).

**Scale/Scope**: Two `LexSense` fields; ~one new resolver path (Section B) + one new
link-by-GUID leg (Section A); one census reclassification; fixture-backed tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. FLEx Domain Fidelity** — PASS. Section A links to an existing target
  `LexAppendix` by GUID (concept↔identity preserved; nothing created). Section B
  reuses 024's resolver, which preserves the GOLD/custom identity binding when
  creating/linking possibility items. No new factory-GUID table introduced.
- **II. flexicon-Direct** — PASS. New code imports flexicon (and `SIL.LCModel`
  interfaces for casts) directly; no `flavors/` adapter. Owning-list discovery uses
  `.Owner` on live LCM objects.
- **III. Preview-Before-Mutate** — PASS. Both legs plug into the existing Preview
  (`_plan_entry_reference_decisions` sense loop) and Move
  (`_walk_lex_entry_closure` sense loop) call sites that already invoke
  `_report_dropped_sense_scope_gaps`; FR-008 requires the two paths' decisions and
  drop sets remain identical by construction.
- **IV. Phased Merge Discipline** — PASS. Section A uses `LINK` semantics (present
  by GUID → reference, else report; never blanks). Section B uses the existing
  resolver's `LINK`/`ADD`/`UPDATE` dispositions. No new mode introduced.
- **V. Referential Completeness** — PASS. Section B pulls a thesaurus item's
  hierarchical ancestor chain (024 `_ancestor_chain`); an item whose dependency
  (owning list) cannot be satisfied is reported, not silently transferred broken.

**Result**: No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/030-sense-appendix-thesaurus-refs/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── appendix-link-by-guid.md
│   └── thesaurus-dynamic-owner.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
src/gramtrans/Lib/
├── references.py        # 024 resolver: decide_reference / apply_reference,
│                        #   _find_in_possibility_list, _ancestor_chain,
│                        #   REFERENCE_FIELD_MAP, ReferenceFieldSpec  (REUSED;
│                        #   Section B adds a dynamic-owner resolution entry point)
├── categories.py        # sense loops (Preview + Move) + _report_dropped_sense_
│                        #   scope_gaps + _SENSE_SCOPE_GAP_FIELDS  (EDITED: appendix
│                        #   link-by-GUID leg + thesaurus resolve leg replace the
│                        #   two drop-only rows; PicturesOS row stays DROP_REPORTED)
├── preview.py           # plan-builder (unchanged call site)
└── transfer.py          # plan-executor (unchanged call site)

tests/
├── verification/
│   └── fidelity_census.py   # EDITED: AppendixesRC + ThesaurusItemsRC -> COPIED
├── unit/
│   └── test_cycle16c_sense_scope_gaps.py  # EDITED/EXTENDED: appendix/thesaurus
│                                          #   link+resolve cases (fakes)
└── integration/              # NEW fixture-backed live-parity tests (if present)
```

**Structure Decision**: Single-project FlexTools module. All 030 work lands in the
existing `Lib/references.py` + `Lib/categories.py` pair and the census; no new
top-level module is introduced. Implementation happens on a dedicated worktree
(`../GramTrans-030-sense-appendix-thesaurus-refs` on branch
`030-sense-appendix-thesaurus-refs`) per the repo Git protocol; spec artifacts stay
on `main`.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.
