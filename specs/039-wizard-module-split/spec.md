# Feature Specification: Split the Selection Wizard into Page Modules

**Feature Branch**: `039-wizard-split`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "The other agents are working on back-end work that doesn't touch the UI. Extract the monolithic selection_wizard.py into reasonable chunks."

## Overview

`src/gramtrans/Lib/ui/selection_wizard.py` is **6512 lines** holding 15 classes
and ~30 module-level functions. This is a pure structural change: it moves code,
removes exact duplication, and strengthens the structural test guards. It changes
nothing about what GramTrans transfers, plans, or writes.

Feature 036's own plan already named the problem — "the two new mechanisms get
their own modules rather than growing `selection_wizard.py`, **which is already
5,204 lines**" (`specs/036-wizard-ui-polish/plan.md:64`) — and the file has since
grown another 1300 lines. `specs/038-transfer-fidelity-gaps/plan.md:181` records
the 6512 as a standing fact about the repository.

Two costs, both measured rather than asserted:

1. **Exact duplication, ~505 lines.** `_get_source`/`_get_target` are
   byte-identical across 8 page classes; 7 of the 8 whole-block checkbox methods
   are identical **four** times over (`_PageCustomFields`, `_PageRules`,
   `_PagePhonology`, `_PageEntryTypes`).
2. **Defects that this file size conceals.** `_RULES_*` and `_ET_*` item-data
   roles both occupy `UserRole + 70/71/72` — harmless today only because the two
   pages own disjoint trees. `_PageEntryTypes._iter_item_rows` discards its own
   recursive generator (`_walk(child, False)` is called and thrown away) behind a
   permanently-true `if in_group_item or True`.

### Why now

Verified against every live branch: **no branch has touched
`src/gramtrans/Lib/ui/` since its merge-base.** `035-fullsweep-fidelity` is 13
commits ahead with zero UI changes; `033` and `034` are 0 ahead; `037`,
`038-affix-fidelity` and `038-transfer-fidelity-gaps` show no `Lib/ui/` diff at
all. The file is uncontested, and a 6512-line split is maximally merge-hostile
against any branch that later edits it.

## The governing constraint: source-scanning tests

20 test modules import this file, but there is exactly **one** production import —
`SelectionWizard` at `src/gramtrans/gramtrans.py:249`. The real coupling is the
test suite, and the hazard is not the import graph but the **~15 tests that read
the module's own text** via `Path(sw.__file__).read_text()` and assert over it.

| Behaviour if the code moves out | Tests |
|---|---|
| **Fails loudly** (pattern not found) | `test_036_finish_guard.py:623` (`execute_move` AST scan, carries `assert total > 0`), `test_036_min_width_layout.py:305` (`^MIN_WINDOW_WIDTH\s*=\s*900`), `test_036_page_header_layout.py:1037` (`self.resize(1300, 760)`), `test_wizard_page_order.py:146/199/213` (`flow()` attr strings, `def page_rules(`), `test_entry_types_display.py:93/112/134`, `test_phonology_inventory.py:207` (raises `StopIteration`) |
| **Silently stops asserting** — the worst case | `test_036_wizard_flow_numbering.py:512` (`Step \d+ of \d+` becomes `[]` vacuously), `test_wizard_page_order.py:110` (`\.page\(\d+\)` becomes `[]` vacuously) |
| **Safe** — follows the object | every `inspect.getsource(...)` site: `test_036_finish_guard.py:655`, `test_wizard_page_flow.py:244/246/337/348` |

Plus 14 `monkeypatch.setattr(sw, "NAME", ...)` sites that patch the **module
globals of the code that calls them**. A facade re-export does not fix these: a
caller in another module resolved that name in its own namespace at import time.

## Requirements

### FR-001 — Behaviour is unchanged

No page gains, loses, or alters a control, a label, a default, or a navigation
edge. `flow()`, page order, and every skip predicate are untouched.

### FR-002 — The write point does not move

`gt_api.execute_move` continues to be called from exactly one function,
`_PageFinish._on_move`, and `_PageFinish` stays in `selection_wizard.py`.
Constitution Principle III's "Preview before Mutate" guarantee is currently
checked *within one file*; this feature must not weaken that check.

### FR-003 — No module over ~1750 lines

No single module may again become the place where everything lands.

### FR-004 — Exact duplication is removed

The ~505 duplicated lines identified above are collapsed into shared bases. A
genuine divergence must be preserved as an explicit, documented override rather
than silently normalised.

### FR-005 — Structural guards become package-wide

The two invariants that would silently stop asserting (`Step N of M`, literal
`.page(N)`) must be checked across every wizard module, not just the facade. This
is strictly stronger than today.

### FR-006 — The compatibility surface stays reachable

Every name the suite binds off the module object — 13 page classes (including the
legacy `_PageProjectWS` probe), 13 functions, 7 constants, plus `gt_api`,
`StatsPanel`, `RunReport`, `SourcePickerDialog`, `build_selection`,
`build_deps_inventory` — remains importable as `selection_wizard.X`, and that is
enforced by a test rather than by convention.

### FR-007 — Both import modes keep working

Every new module carries the `if __package__:` / `else:` dual-mode guard in both
branches. This is constitutional (`.specify/memory/constitution.md:380-384`
mandates `site.addsitedir(r"Lib")`), and the flat branch is the FlexTools and
frozen-bundle path.

### FR-008 — New module names may not claim generic top-level names

`build/hiddenimports.py` exposes every `Lib/**/*.py` under its **bare stem**, and
`check_collisions()` fails the build if a stem shadows an installed distribution.
All new modules are prefixed `wizard_`.

### FR-009 — CI gates are satisfied

`.github/scripts/check_shared_exceptions.py` treats a **new** file under
`src/gramtrans/Lib/` as a shared-code change and fails unless it appears as a
numbered row in `specs/034-standalone-windows-app/plan.md`'s exception table.
`src/gramtrans/Lib/debuglog.py`'s hand-written `LOGGER_NAMES` tuple needs an entry
per new flat module name.

### FR-010 — Rationale comments survive

The existing "why, and why not the obvious alternative" commentary is load-bearing
institutional memory. It moves verbatim with the code it explains.

## Success Criteria

- **SC-001** The unit suite matches the recorded baseline exactly — no new
  failures, and no baseline entry starts passing.
  (`.github/known-failures.txt:47` is the one expected pre-existing failure.)
- **SC-002** `python -m pytest tests/unit/test_034_flextools_contract.py -q` passes
  standalone.
- **SC-003** `python .github/scripts/check_shared_exceptions.py --base main` is clean.
- **SC-004** `python build/hiddenimports.py` reports no flat-name collision.
- **SC-005** `python -m ruff check src/gramtrans/Lib/ui/` is clean (isort `I` and
  `F401` are on with no per-file-ignores).
- **SC-006** The wizard imports and constructs in **flat** mode, not only package mode.
- **SC-007** A live Preview walk of all 12 pages against read-only `Ejagham Mini`
  shows consecutive step numbers with no total, headers rendering with the theme
  strip following, splitters holding at a 900 px window, and correct block-page
  tristate at empty / partial / full.
- **SC-008** No module in `Lib/ui/` exceeds 1750 lines.

## Out of Scope

- Feature 036's open defect **SC-001b** (the progress indicator's total
  mismatching work performed on four operations). It touches `_page_progress`
  wiring, the fix may belong in `Lib/selection.py`, and it would confound the
  relocation diff.
- Normalising `_PageEntryTypes._get_source`, which reads `wizard._host` directly
  instead of going through `context.source_handle`. This looks like a defect but
  fixing it is a behaviour change; it is recorded as a follow-up question.
- Any change to `flow()`, page order, or the skip predicates.

## Notes for whoever picks this up

Five unchecked tasks in `specs/020-conflict-mode-field-merge/tasks.md`
(T008-T010, T015) and T072 in `specs/038-transfer-fidelity-gaps/tasks.md` still
target `selection_wizard.py` by line number. Many older specs cite line numbers in
this file (010, 014, 018, 019, 021, 022, 034, 036); those citations are already
stale and will become staler. Only the two live task lists above need re-pointing.
