# Implementation Plan: Preview Coverage Completion for Grammar Categories

**Branch**: `032-preview-coverage-completion` | **Date**: 2026-07-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/032-preview-coverage-completion/spec.md`

## Summary

The per-item Merge-Preview pane is the enforcement surface of the Preview-before-Move
contract, but eight grammar categories fail it today: four render a **blank pane**
(Writing System, Complex Form Type, Ad hoc/Compound rule, Text), three render a
**thin pane** of only Name/Abbreviation/Description (Phonological Feature, Phonological
Rule, Slot), and one is a **regression** where resolved content never reaches the user
(Natural Class). This feature closes all eight gaps, adds a related-languages default to
the writing-system mapping step, and runs a read-only investigation of Ad hoc rule
transfer loss.

**Technical approach** — the preview core (`Lib/merge_preview.py`) already has a stable
two-stage architecture: **Stage 1** `props_for` dispatches a `(category, guid)` to a
per-category reader that returns a plain `{field: value}` / `{ws_id: text}` props dict;
**Stage 2** `diff_props` + `to_html` turn source/target props into the rendered pane. The
diff/render layer is Qt-free and correct; **this feature adds and enriches Stage-1
readers only** and feeds them through the existing Stage-2 layer unchanged. Concretely:

1. **Blank categories (US1)** — register `texts`, `writing_systems_check`,
   `complex_form_types`, `adhoc_compound_rules` in the dispatch tables
   (`_CATEGORY_VALUE_TO_KEY`, `_PROPS_TABLE`) with new reader functions, reusing
   read helpers already in `Lib/texts.py` (baseline excerpt) and `Lib/references.py`
   (possibility-list / morpheme-reference resolution).
2. **Thin categories (US2)** — extend the gap direct-read (`_direct_read_gap`) or add
   enrichment hooks (mirroring the natural-class/phoneme enrich pattern) so Phon Feature
   surfaces type + permissible values, Phon Rule surfaces structural content, and Slot
   surfaces its occupying affixes.
3. **Natural Class regression (US3)** — the resolvers (`_natural_class_members`,
   `_natural_class_features`, `_enrich_natural_class`) already exist and are wired on the
   covered path; Phase 0 pins the exact drop point (finder/ops-resolution vs render) with
   a failing test first, then makes the fix load-bearing.
4. **WS-mapping default (US4)** — add a primary-vernacular concept and suffix-based
   sub-WS correspondence to `Lib/ws_mapping.py` so the mapping step pre-fills real
   target mappings (primary→primary, sub→sub by subtag suffix), never "create"/"skip",
   and leaves ambiguous rows unresolved with confirmation gated.
5. **Ad hoc loss (US5)** — a read-only live probe characterizes the loss (leading
   hypothesis: `to_ws_map_dict` silently drops source WSs whose mapped target Id is
   absent) and produces a root cause + scope decision; reproduction is out of scope,
   and any in-scope residual loss becomes never-silent user-facing reporting.

All preview work is **read-only** (FR-010); US1–US4 DoD is offline tests plus a
read-only live-render proof via FLExToolsMCP; US5 uses a read-only probe. No destructive
Move is required, so the project's attended `needs_human` Move gate does not apply.

## Technical Context

**Language/Version**: Python 3 (FlexTools host runtime).

**Primary Dependencies**: flexicon (dist `pyflexicon>=4.1`) Operations-class API
(`project.NaturalClasses`, `project.PhonRules`, `project.WritingSystem`,
`project.MorphRule`, etc.); LCM interfaces read via lazy `import SIL.LCModel` inside
functions (`IPhNaturalClass`/`IPhNCSegments`/`IPhNCFeatures`, `IPhRegularRule`,
`IFsClosedFeature`, `IMoInflAffixSlot`, `IMoMorphSynAnalysis`, `IText`/`IStText`,
`ILexEntryType`, `IMoAdhocProhib`/`IMoMorphAdhocProhib`/`IMoAlloAdhocProhib`); PyQt only
in the UI pane, never in the render core.

**Storage**: FLEx project `.fwdata` (LCM object graph) — source and target projects,
read-only for this feature.

**Testing**: pytest offline unit suite under `tests/unit/` (per-renderer props/html
tests, Qt-free guard, ws_mapping tests); double-gated live integration under
`tests/integration/` (`flexicon` importable + `GRAMTRANS_E2E=1`) against the
`Ejagham Mini` → `Ejagham Full GT-Test` pair, plus other read-only test projects
(`Esperanto`, `Mbugwe Lizzie HCPractice`) exercised via FLExToolsMCP.

**Target Platform**: Windows, FlexTools host.

**Project Type**: Single project — FlexTools-compatible module (`src/gramtrans/`).

**Performance Goals**: N/A (interactive per-item preview; content is bounded/excerpted
per FR-018 so large texts and large member/affix lists never dump unbounded).

**Constraints**: Read-only (no project writes, no Move-plan change — FR-010); render core
stays Qt-free (SC-007); graceful degradation to label-level detail on enrichment read
failure, logged not surfaced (FR-011); bounded/truncated excerpts (FR-018); WS default
never false-maps and keeps confirm gated on ambiguity (FR-014/FR-015); never-silent loss
reporting (FR-017).

**Scale/Scope**: One core module (`Lib/merge_preview.py`) gains ~4 new readers + ~3
enrichment paths; `Lib/ws_mapping.py` gains primary-vernacular + suffix-correspondence
defaulting; read helpers in `Lib/texts.py`/`Lib/references.py` reused, not rewritten;
one read-only probe script for US5. Reference-pair inventories are small (tens of items
per category).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. FLEx Domain Fidelity (NON-NEGOTIABLE)** — PASS. All work is read-only preview
  rendering; it neither transfers nor mutates objects, so GUID identity, GOLD-as-ordinary
  treatment, and the concept↔GUID binding are untouched. US4 directly serves the
  principle's "writing-system identity … MUST be validated and explicitly mapped before
  any string-bearing field is written" by improving the map defaults; it still leaves
  ambiguous rows unresolved (FR-015), so no false WS identity is asserted. US5
  characterizes a cross-reference loss (Principle's "resolve to real objects … or fail
  loudly") and converts silent drop into never-silent reporting.
- **II. FlexTools-Compatible Output, flexicon-Direct** — PASS. All changes live in
  `src/gramtrans/Lib/` importing flexicon/LCM directly (lazy `import SIL.LCModel` inside
  functions, matching existing idiom); no adapter, no new optional dependency. New render
  logic stays in the Qt-free core; the UI pane is unchanged except to route the new
  categories it already dispatches by string.
- **III. Preview-Before-Mutate (NON-NEGOTIABLE)** — PASS / directly served. This feature
  *strengthens* Preview: it makes the pane truthfully describe what a Move would transfer
  for eight categories that currently tell the user nothing. Nothing here writes; it does
  not touch `Lib/preview.py` (plan-builder) or `Lib/transfer.py` (plan-executor) write
  paths. (Note: the T-Spike refactor of `transfer_verb_vertical()` is a separate,
  pre-Layer-3 obligation and is **not** in this feature's scope.)
- **IV. Phased Merge Discipline** — PASS. No new merge mode, no phase reordering; this is
  preview-coverage work within already-shipped phases. The preview correctly reflects the
  existing NEW / OVERWRITE / MERGE_KEEP / LINK_ONLY modes via the unchanged `diff_props`
  layer (FR-009 "new to target vs differs").
- **V. Referential Completeness** — PASS / directly served. Enriched previews expose the
  dependency-bearing content the principle cares about (slot→affixes, ad-hoc→morphemes,
  natural-class→segments/features), and the edge cases (referenced targets outside the
  current closure) are rendered as "what can be described" without crashing (spec Edge
  Cases; FR-011). US5 turns a silent closure loss into a reported one ("MUST be reported,
  not silently transferred in a broken state").

**Result: PASS — no violations, Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/032-preview-coverage-completion/
├── plan.md              # This file
├── research.md          # Phase 0 output — per-category shape decisions (live-verified)
├── data-model.md        # Phase 1 output — props-dict shapes per category + WS entities
├── quickstart.md        # Phase 1 output — offline + read-only live-render validation guide
├── contracts/
│   ├── preview-props.md         # Per-category Stage-1 props-dict contract (8 categories)
│   ├── ws-mapping-default.md     # Primary→primary / suffix sub→sub defaulting contract
│   └── adhoc-loss-probe.md       # US5 read-only probe output + scope-decision contract
├── checklists/
│   └── requirements.md  # From /speckit-specify (all items pass)
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
src/gramtrans/
├── gramtrans.py                 # MainFunction entry (unchanged)
└── Lib/
    ├── merge_preview.py         # EDIT: register texts/writing_systems_check/complex_form_types/
    │                            #       adhoc_compound_rules in _CATEGORY_VALUE_TO_KEY (~1148-1160)
    │                            #       + _PROPS_TABLE (~1087-1119); NEW reader fns (Text baseline
    │                            #       excerpt, WS identity+role, complex-form-type, ad-hoc rule);
    │                            #       enrich hooks for phon_rule structure, phon_feature values,
    │                            #       slot affixes (mirror _enrich_natural_class ~1797); FIX the
    │                            #       natural-class drop point (finder/ops path ~1268-1294)
    ├── ws_mapping.py            # EDIT: primary-vernacular selection in _enumerate_ws (~158);
    │                            #       suffix-based sub-WS correspondence (new helper);
    │                            #       apply real-mapping defaults, leave ambiguous unresolved
    │                            #       (detect_ws_mismatches ~213 / fold_choices ~245)
    ├── texts.py                 # REUSE: capture_vernacular / _walk_paragraphs for Text excerpt
    ├── references.py            # REUSE: possibility-list + morpheme-ref resolvers for CFT/ad-hoc
    └── ui/merge_preview_pane.py # (likely unchanged — already dispatches by category string)

tests/unit/
├── test_merge_preview_props.py       # EXTEND: props shape per new/enriched category
├── test_merge_preview_html.py        # EXTEND: non-blank HTML per category
├── test_merge_preview_enrichment.py  # EXTEND: phon_rule/phon_feature/slot enrich; NC regression
├── test_merge_preview_qt_free.py     # (guard — must still pass)
├── test_ws_mapping.py                # EXTEND: primary→primary default
├── test_ws_mapping_detect.py         # EXTEND: suffix sub→sub + ambiguous-unresolved
└── test_032_preview_coverage.py      # NEW: eight-category non-blank + NC before/after regression

tests/integration/
├── test_e2e_all_categories.py        # EXTEND: read-only live-render assert (non-blank per category)
├── test_phase2_us2_ws_wizard.py      # EXTEND: WS default pre-fill live
└── (harness/full_run.py reused for read-only preview render)

debug/
└── probe_adhoc_loss.py               # NEW: US5 read-only live probe (characterization only)
```

**Structure Decision**: Single-project FlexTools module. The feature is deliberately
confined to Stage-1 readers in `Lib/merge_preview.py` plus defaulting in
`Lib/ws_mapping.py`; the Qt-free diff/render layer and the write paths
(`Lib/preview.py`, `Lib/transfer.py`) are not modified. Read helpers in `Lib/texts.py`
and `Lib/references.py` are reused rather than duplicated. Exact drop point for the
Natural Class regression and the precise LCM cast for each new reader are confirmed in
Phase 0 against live projects before edits.

## Complexity Tracking

> No Constitution Check violations — section intentionally empty.
