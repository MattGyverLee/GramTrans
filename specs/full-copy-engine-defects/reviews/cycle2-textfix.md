# Cycle 2 — Programmer report: texts.py defect fixes (Site-1 finding #1, finding #2, Site-2 finding #1)

**Worktree:** `D:\Github\_Projects\_LEX\GramTrans-fullcopy-defects` (branch `fullcopy-defects`, NOT merged to `main`)
**Commit:** `844f465` — `fix(texts): duplicate-name reuse, untitled-text fingerprint idempotency, blank-paragraph raw create`
**File touched:** `src/gramtrans/Lib/texts.py` (+ `tests/unit/_fakes_texts.py`, new `tests/unit/test_texts_fullcopy_defects.py`)
**Instrumentation touched (main repo, scratchpad — not a spec/src file):** `D:\Github\_Projects\_LEX\GramTrans\scratchpad\run_fullcopy_live.py`

## FIX 1 — Site-1 duplicate-name collision

`_resolve_or_create_text` (texts.py) now calls `text_ops.Exists(name)` before
`Create`. On a hit it resolves the existing text via `Find(name)` and reuses
it (treated as UPDATE-by-name) instead of letting `TextOperations.Create`'s
generic `FP_ParameterError("A text with the name '...' already exists.")`
cascade into a misleading `"text create failed: FP_ParameterError"` drop that
silently discarded the whole text.

## FIX 2 — Idempotency for untitled texts (structural fingerprint)

`_text_disposition`'s title fallback was gated by `find is not None and
title` — an empty/blank title (the common shape for glossed/interlinear
practice texts) could never satisfy that condition, so such texts were
re-CREATEd on every Move (Esperanto's non-idempotency, per finding #2).

Since no GUID-preserving `TextOperations.Create` overload exists, added
`_text_fingerprint(project, text)`: `(paragraph_count, sha1(first
non-empty baseline string))`, preferring segment baseline text
(`Segments.GetBaselineText`) and falling back to paragraph `Contents`
(`Paragraphs.GetText`) when there are no segments yet. `_text_disposition`
now branches: titled texts still match via `Texts.Find(title)` (unchanged
behavior — the bare `and title` restriction is gone, but the title branch is
still title-gated since `Find("")` is undefined); **empty-titled** texts fall
back to fingerprint-matching each existing target text. A text with **no**
baseline text anywhere anywhere returns `None` from the fingerprint (never
matches on paragraph-count alone) to avoid merging unrelated blank texts.

## FIX 3 — Site-2 blank paragraph content (dominant drop bucket)

The paragraph loop in `_apply_paragraphs` called `para_ops.Create(target_text,
content or "", ...)` for paragraphs with no mappable baseline text, hitting
`ParagraphOperations.Create`'s empty-content guard
(`FP_ParameterError("Content cannot be empty")`) and cascading into the
generic `"paragraph create failed"` drop, which in turn orphaned downstream
Segment/alignment writes ("no copied target referent").

Added `_create_paragraph` (dispatches to the normal `ParagraphOperations.Create`
for non-blank content, else `_raw_create_blank_paragraph`) and
`_raw_create_blank_paragraph`, which reproduces `Create`'s OWN internal raw
path (`IStTxtParaFactory.Create()` → own under `ContentsOA.ParagraphsOS` →
set `Contents` to an empty TsString) — bypassing only the guard, using the
same idiom the flexicon method itself uses internally. A paragraph whose raw
create *also* fails (no confirmed write surface) now gets the DISTINCT reason
`"paragraph has no mappable baseline text"`, never the generic exception
label.

## Pattern audit (per prompt) — `Lib/wordforms.py`

Grepped all `.Create(` sites in `wordforms.py` (5 hits) for the same "no
GUID overload + name-only fallback" idempotency shape that finding #2
exhibited in `texts.py`:

| Site | Dedup mechanism | Same defect shape? |
|---|---|---|
| `Agents.Create(name)` (agent provisioning) | Finds ANY existing human agent (`GetHumanAgents`/`FindByType`) before creating — not name-keyed at all | No |
| `Wordforms.Create(form, handle)` | `Find(form, handle)` first — the wordform's literal **form string is its identity** (never blank-vs-title ambiguous; an empty form is already a distinct drop reason) | No |
| `WfiAnalyses.Create(wordform)` | Cross-run dedup via `_analysis_fp_index` / `_plan_analysis_fingerprint` — a **structural fingerprint** (morph-bundle forms + gloss forms) already, functionally identical in spirit to the FIX 2 mechanism just added for texts | No — already correctly shaped |
| `WfiGlosses.Create(analysis, form, handle)` | Only reached when the OWNING analysis's fingerprint dedup already said "new" — inherits the analysis-level structural dedup | No |
| `WfiMorphBundles.Create(analysis)` | Same — inherits analysis-level dedup | No |

**Conclusion:** no sibling sites share the Site-1/finding-#2 defect shape;
`wordforms.py`'s analysis-level structural fingerprint is in fact the
existing precedent the FIX 2 texts.py fingerprint was modeled after. No
follow-up needed.

## Instrumentation

`scratchpad/run_fullcopy_live.py`'s `_summarize()` now also returns
`per_category`: `{category_name: {"added": n, "skipped": n}}` built straight
off `report.per_category`, alongside the existing aggregate `added`/`skipped`
ints and the `dropped_breakdown` Counter — so a future re-proof can recover
the category-level breakdown finding #2 could not (the "146-by-category"
detail). No live Move was run (human-gated step, left untouched).

## Tests

New `tests/unit/test_texts_fullcopy_defects.py` (8 tests): duplicate-name
reuse (hit + miss), untitled-text fingerprint match/no-match/no-false-match
(two blank texts with no baseline never merge), titled-text-still-matches-by-
title sanity check, blank-paragraph distinct-drop-reason (offline, no LCM
host), and two tests exercising the actual raw-create idiom via a
monkeypatched fake `SIL.LCModel` / `SIL.LCModel.Core.Text` module pair
(mirrors `test_reference_create_paths.py`'s `_install_fake_lcm` pattern).

`_fakes_texts.py`'s `FakeTextOps` gained `Exists(name)` and `Create` now
raises on a duplicate name (mirroring `TextOperations.Create`'s real guard)
so FIX 1 is exercised realistically.

**Result:** `pytest tests/unit` in the worktree → **1827 passed, 27 failed**
(the 27 failures are pre-existing on `main` — verified byte-identical failure
list on `main` before any of this work; unrelated to `texts.py`), 8 skipped,
14 xfailed, 14 xpassed. The 8 new + all existing `texts.py`-related tests
(`test_text_structure_walk.py`, `test_text_markup_tags.py`,
`test_texts_fullcopy_defects.py` — 25 tests) pass clean.
