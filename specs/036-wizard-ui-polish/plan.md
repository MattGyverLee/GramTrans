# Implementation Plan: Wizard UI Polish Pass

**Feature**: 036-wizard-ui-polish
**Spec**: [spec.md](spec.md)
**Date**: 2026-08-17
**Research**: [research.md](research.md) | **Data model**: [data-model.md](data-model.md) | **Contracts**: [contracts/](contracts/)

## Summary

Eight presentation-layer stories against the existing `QWizard` selection
wizard, delivered inside the stack the wizard already uses (Python 3 + PyQt6,
flexicon for project reads, pytest with `QT_QPA_PLATFORM=offscreen` for UI
tests). No new dependency is introduced, which matters here because the
constitution forbids one without an amendment.

Seven of the eight are edits to values, labels and layout: one declared page
order replaces twelve hand-written `Step N of 10` titles, splits project selection
from writing-system mapping, and lets a page with nothing to decide drop out of
the run — numbers are assigned as the operator walks, and no total is displayed,
because how many pages a run will show is not knowable when it starts; the
minimum width drops from 1100 to 900 and the shared tree/preview splitter is
taught to survive it; the floating zoom and
colour-mode strip moves into a laid-out per-page header that also owns the
wrapping step description; the dark palette's accent family turns green while the
selection highlight stays blue; and the preview stops adding quote characters
around list entries. The eighth — progress feedback — is the only new mechanism:
a Qt-free progress sink threaded into the inventory builders, driven by a single
modal indicator that appears up front when a cheap count predicts a wait over
500 ms and otherwise after 500 ms of elapsed time.

Everything here is observation and presentation. FR-045 is the governing
constraint: for an identical set of selections the objects transferred and their
content must be byte-identical before and after, so each change to a module on
the transfer path (`Lib/selection.py`, `Lib/merge_preview.py`) is additive and
default-off.

## Project Structure

```
src/gramtrans/Lib/
  progress.py                     # NEW  Qt-free sink protocol + the one 500 ms threshold
  selection.py                    # EDIT optional progress= kwarg on 7 inventory builders
  merge_preview.py                # EDIT FieldDiff.multiline; str() not repr(); affix label; list caps
  ui/
    progress_indicator.py         # NEW  Qt sink: one modal indicator, pumps the loop on tick
    page_header.py                # NEW  laid-out header: wrapping description + controls slot
    selection_wizard.py           # EDIT flow declaration + nextId() skipping, project/WS split,
                                  #      title, 900 px, headers, Finish guard
    theme.py                      # EDIT dark green accents; "Zoom:" label; +/- glyphs; controls detach
tests/unit/
  test_036_progress_sink.py       # NEW  thresholds, triggers, nesting, no-flash, dismissal
  test_036_wizard_flow_numbering.py # NEW  consecutive from 1 on full AND skipping runs; no page
                                    #      title matches 'of N'; skips never drop a non-empty page;
                                    #      Affix/Stem pickers shown when empty
  test_036_page_header_layout.py  # NEW  wrapping, and no overlap at 900 px x max text scale
  test_036_preview_list_fields.py # NEW  one entry per line, no added quotes, data quotes kept
  test_036_finish_guard.py        # NEW  the FR-038..FR-044 matrix
  test_theme_manager.py           # EDIT extend _CONTRAST_PAIRS; add the three DeltaE floors
  test_034_flextools_contract.py  # EDIT subtitle literal follows the project/WS split
  test_034_step1_source_picker.py # EDIT same
  test_wizard_page_order.py       # EDIT accessor table gains page_writing_systems
  test_032_preview_coverage.py    # EDIT truncation note now states the true total
```

**Structure Decision**: The two new mechanisms get their own modules rather than
growing `selection_wizard.py`, which is already 5,204 lines; the split follows
the boundary the repo already enforces — `Lib/*.py` stays Qt-free and `Lib/ui/*`
owns Qt — so the progress protocol can be unit-tested without a `QApplication`,
the same way `Lib/merge_preview.py` is kept Qt-free and fed colours by
`Lib/ui/theme.py`.

## Constitution Check

Assessed against constitution v8.0.0.

| Principle | Assessment |
|---|---|
| **I. FLEx Domain Fidelity** | **PASS.** Nothing here writes. The only reads added are two count calls (`LexiconNumberOfEntries`, `TextsNumberOfTexts`) and the progress ticks inside walks that already happen. GUID handling, ontology mappings, WS identity and cross-reference resolution are untouched; the project/WS split moves *where* the WS mapping is chosen, not what it maps (FR-007 keeps the same `WSMapping` payload). |
| **II. FlexTools-Compatible Output, flexicon-Direct** | **PASS.** No new runtime dependency: PyQt6 and flexicon only. The count calls are flexicon `FLExProject` methods, verified through the FLExToolsMCP. Both hosts keep the same surface — the standalone's `source_binder` path and the FlexTools host-supplied-source path are preserved and still distinguished on the projects page (spec assumption "the standalone and the FlexTools-hosted path share this surface"). |
| **III. Preview-Before-Mutate** | **PASS — strengthened.** US5 tightens the Preview gate rather than relaxing it: Execute stays disabled until a successful dry run, now says why (FR-039), and a stale dry-run result stops being presented as current (FR-041). The `confirmation_gate` consulted immediately before `execute_move` is untouched, as is the read-only refusal. Conditional pages cannot reach the write path: the Finish page is declared non-skippable, so no run can route around the dry run. |
| **IV. Phased Merge Discipline** | **PASS.** No mode, disposition or write semantic is touched. Progress feedback observes the existing plan/execute path (FR-022) and adds no branch to it. |
| **V. Referential Completeness** | **PASS.** Closure computation is unchanged, and the per-item deselection UI is never taken away: a page is skipped only when it has nothing to decide (FR-009c), so there is no closure on it to deselect. The conservative predicate is what makes this sound — unsure shows the page, so the failure mode is a wasted click, never a removed deselection. Two presentation improvements *help* this principle: capped affix lists now disclose the true total (FR-037), so an operator never judges a slot on a fraction of its contents, and list entries become individually readable (FR-033). |
| **Gate — "no silent skips"** | **PASS.** FR-020 requires a failed operation's indicator to be dismissed *and* the failure surfaced; FR-037 replaces a silent cap with a disclosed one. Both move in the direction this gate asks for. |
| **Gate — verification on a project pair** | **PASS.** SC-001/SC-002/SC-011 are verified against the `Ejagham Mini` → `Ejagham Full GT-Test` pair already used for this purpose, with SC-011 as the FR-045 equality check. |
| **Gate — UI constraint (PyQt, hosted in the FlexTools window)** | **PASS.** The wizard stays a `QWizard` inside the host window. Notably *not* taken: replacing the native window frame to put controls in the title bar, which is why FR-004 places them in the wizard's own header instead. |

No violations. **Complexity Tracking** is therefore omitted.

Re-checked after Phase 1 design: the design adds one defaulted dataclass field
(`FieldDiff.multiline`), one defaulted keyword argument per inventory builder,
and two new modules. No principle's assessment changes.

## Phase notes

**Sequencing.** The stories are independent (spec assumption), with two
exceptions worth respecting. US2's renumbering and US6/US8's header both edit the
top of every page, so land US2 first and build the header on the numbered flow.
And US2's conditional pages reuse the cheap counts US1 establishes for its
progress totals (`TextsNumberOfTexts()`, possibility-list `.Count`) — so build
that count layer once, in US1, and have US2's `has_content` predicates read the
same cached values rather than growing a second set. US5, US4 and US7 are fully
independent of the rest.

**The one place to be careful.** `Lib/selection.py` and `Lib/merge_preview.py`
are on the transfer path. Both changes are shaped so that an unchanged call site
produces the identical value it produces today: `progress=None` means no sink
and no tick, and `multiline` defaults to `False`. SC-011 is the check that this
held.
