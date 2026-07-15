# Implementation Plan: Complex Forms & Variants

**Branch**: `027-complex-forms-variants` | **Date**: 2026-07-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/027-complex-forms-variants/spec.md`

## Summary

Cross-project Move transfer never creates `ILexEntryRef` container objects on the target,
so a copied entry's `EntryRefsOS` is always empty and its complex-form / variant
relationships are silently lost (issue #30). Feature 024 made this fidelity-honest — it
emits a `DroppedItemRecord` for every un-reproduced `LexEntryRef`
(`categories._report_dropped_entry_refs`) — but never reproduced the data. The downstream
wiring post-pass `categories._run_post_pass_a` already exists and already consumes
`plan.lexentry_ref_bindings`, but is **unreachable**: it wires
`ComponentLexemesRS`/`PrimaryLexemesRS` into a *pre-existing* `LexEntryRef`, and none is
ever created.

**Technical approach:**

1. **Create the containers (US1).** Add an `ILexEntryRefFactory`-based creation step that
   runs as the *front half* of the STEMS-tail post-pass, immediately before the existing
   wiring. For each source entry in the copy closure whose `EntryRefsOS` holds a ref whose
   components are also in-closure, create a target `LexEntryRef` (GUID-preserving) owned into
   the target entry's `EntryRefsOS`, carrying `RefType`. Then `_run_post_pass_a` — now
   reachable because a container exists — wires the component/primary lexemes. Endpoint
   resolution uses the on-`main` `_resolve_target_by_guid` + `_cast_lcm` idioms (issue #28
   layers 1+2). No unguarded `get_object_by_guid`, no uncast interface access.

2. **Resolve entry-type references (US2).** `VariantEntryTypesRS`, `ComplexEntryTypesRS`,
   and `ShowComplexFormsInRS` are possibility-list references. Resolve them against the
   target lists with 024's three-way `references.decide_reference`/`apply_reference` (absent
   → create incl. ancestor chain; diverged custom → update; diverged shared/GOLD → link +
   report; identical → link). GOLD/reserved creation preserves the concept↔GUID binding
   (constitution Principle I) — GUID remapped at creation, existing target GOLD items never
   overwritten.

3. **Flip the drop policy from "report all" to "reproduce in-closure / report the rest"
   (cross-cutting, never-silent).** `_report_dropped_entry_refs` today reports *every*
   `LexEntryRef`. After this feature it reports only refs whose other end is outside the
   copy closure (or otherwise unresolvable). In-closure refs are reproduced. The Preview
   path (`_plan_entry_reference_decisions`) mirrors the same reproduce-vs-report split
   read-only, keeping Preview/Move drop-set parity (as 024/025 established).

4. **Complex-form parity (US3).** The same factory + resolver path handles
   `RefType`=complex-form (multi-component + primary subset, `ComplexEntryTypesRS`). Shipped
   with offline coverage; its live `0 → N` proof is deferred to a constructed complex-form
   fixture and tracked as a follow-up (parallel to issue #31's MSA→slot live source).

The feature is **prevention-only** (mirrors 031 FR-011): it does not remediate targets that
already lost their `LexEntryRef`s in a prior Move.

## Technical Context

**Language/Version**: Python 3 (FlexTools host runtime)

**Primary Dependencies**: flexicon (dist `pyflexicon>=4.1`) Operations-class API; LCM
interfaces/factories via `target.GetFactory(IFooFactory)` and `_cast_lcm` — specifically
`ILexEntryRef`, `ILexEntryRefFactory`, `ILexEntry`, `ILexEntryType`/`ILexEntryTypeFactory`
(variant + complex entry types share `LexEntryType`), `ICmPossibility` for publication
types, `ICmObjectRepository` (live GUID resolution). Reuses 024 `Lib/references.py`,
`Lib/owned.py`, `Lib/report.py`.

**Storage**: FieldWorks LCM project (`.fwdata`) via flexicon `FLExProject`.

**Testing**: pytest (offline unit suite, duck-typed fakes + fake `ICmObjectRepository`);
attended FLExToolsMCP live Move for the `0 → N` proofs.

**Target Platform**: Windows FlexTools host with flexicon + PyQt.

**Project Type**: Single-project library/CLI (the GramTrans transfer module).

**Performance Goals**: N/A (correctness-driven; the pass is O(closure entries × refs)).

**Constraints**: Preview writes nothing (Principle III); never-silent (Principle V);
concept↔GUID integrity (Principle I); idempotent re-Move; all live Moves attended.

**Scale/Scope**: `Ejagham Mini` corpus — 6 variant refs across 252 entries; 0 complex-form.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. FLEx Domain Fidelity (NON-NEGOTIABLE)** — PASS by design. GUIDs preserved on
  `LexEntryRef` creation (FR-001). Entry-type/publication GOLD refs remapped at creation so
  the concept↔GUID binding stays true; existing target GOLD items never overwritten
  (FR-005). Cross-references (component → entry, ref → entry-type) resolve to real target
  objects or the item is reported, never silently dropped (FR-007, FR-009). WS-bearing
  fields on any created entry-type route through 024's resolver's WS mapping.
- **II. FlexTools-Compatible, flexicon-Direct** — PASS. Uses `target.GetFactory(...)` +
  `_cast_lcm`, the established idioms; no `flavors/`, no LibLCM, degrades to
  report-only if a factory/interface is unavailable.
- **III. Preview-Before-Mutate (NON-NEGOTIABLE)** — PASS. All creation/wiring lives in the
  Move-path post-pass (`transfer.py` executor); the Preview path only computes the
  reproduce-vs-report decision set and writes nothing (FR-010). Preview lists Add/Link/Skip
  per ref with source GUID + closure.
- **IV. Phased Merge Discipline** — PASS. Entry-type resolution reuses 024's disposition
  vocabulary (ADD_NEW/LINK/UPDATE, UPDATE non-destructive default); no new write semantic.
- **V. Referential Completeness** — PASS. Every kept-but-unresolvable member yields a
  `DroppedItemRecord`; nothing is fabricated.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/027-complex-forms-variants/
├── spec.md              # DONE (fleshed out from stub)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── entryref-reproduction.md   # the post-pass create+wire+resolve contract
├── checklists/
│   └── requirements.md  # DONE (spec quality)
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Work is done on an implementation worktree per the repo git protocol
(`../GramTrans-027-complex-forms-variants` on branch `027-complex-forms-variants`); spec
artifacts stay on `main`.

```text
src/gramtrans/Lib/
├── categories.py        # PRIMARY: add LexEntryRef creation step; make _run_post_pass_a
│                        #   reachable; flip _report_dropped_entry_refs to in-closure/report
│                        #   split; entry-type resolution via references.decide/apply
├── references.py        # REUSED unchanged (024 three-way resolver)
├── owned.py             # REUSED unchanged (024 closure walker)
├── report.py            # REUSED unchanged (DroppedItemRecord)
├── preview.py           # gather lexentry_ref_bindings already present; add reproduce-vs-
│                        #   report decision rows; Preview stays read-only
├── models.py            # extend lexentry_ref_bindings shape to carry RefType + entry-type
│                        #   + primary-subset if not already sufficient
└── transfer.py          # wire the create step into the STEMS-tail (alongside _run_post_pass_a)

tests/unit/
├── test_phase3c_post_pass_a.py       # EXTEND: create-then-wire, idempotent, cast path
├── test_027_entryref_reproduction.py # NEW: US1 variant create; US3 complex-form; RefType
├── test_027_entry_type_resolve.py    # NEW: US2 three-way entry-type resolution + Pr.I
└── test_027_never_silent.py          # NEW: in-closure reproduced / out-of-closure reported

tests/integration/
└── test_027_complex_forms_live.py    # NEW scaffold: skip-by-default @integration live 0->N

scratchpad/
└── run27_live.py        # NEW: attended live driver (restore→diagnose→Move→re-Move→verify)
```

**Structure Decision**: Single-project. The change is concentrated in `categories.py`
(the LCM seam) plus thin Preview/Move wiring, reusing 024's fidelity infrastructure
verbatim. No new module is warranted — `LexEntryRef` reproduction is a peer of the existing
`_run_post_pass_a` / `_run_171_subpass` post-passes and belongs beside them.

## Complexity Tracking

> No constitution violations — section intentionally empty.
