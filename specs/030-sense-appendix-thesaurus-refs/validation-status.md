# Feature 030 — Live-Validation Status

**As of:** 2026-08-11 (originally 2026-07-16; updated for
[issue #42](https://github.com/MattGyverLee/GramTrans/issues/42)).

Both 030 fields are **vacuous-live across all 79 on-disk projects** (see
[research.md](./research.md) Finding 1), so — exactly as with lexrel / affix-MsEnv /
pictures in feature 024 — the offline suite proves the orchestration and a constructed
fixture is required for full end-to-end live proof. This document records what is
offline-proven, what is live-confirmed, and what remains fixture-only.

## Offline-proven (green, zero regressions)

`tests/unit/test_cycle16c_sense_scope_gaps.py` (38 tests: 20 from 030 + **18 added for
issue #42**) + `tests/verification/fidelity_census.py` (116 green). Full suite:
**27 failures, byte-identical to clean `main`** (verified by stash-and-rerun on
2026-08-10: baseline `27 failed / 1859 passed`, with #42 `27 failed / 1873 passed` —
the +14 are the new tests) — every failure pre-existing (suite-ordering `sys.modules`
pollution unrelated to 030); 030 and #42 add **zero** regressions.

- Section A: A-link, A-absent (no create), A-partial, A-empty (non-destructive),
  A-shared (no dup), Preview==Move.
- Section B: `.Owner` discovery (found / no-list), owner-list mirror (Name hit/miss),
  drop-on-failure (no-list, no-mirror), link-to-existing, empty-source non-destructive,
  shared-no-dup, Move==Preview parity.
- Census: both fields classify **COPIED**; never-silent classifier guard + single-member
  `OUT_OF_SCOPE_EXCLUDED` set intact.
- **Issue #42 (added 2026-08-10):**
  - `build_thesaurus_spec` derives `hierarchical` from the mirrored list's live
    `CmPossibilityList.Depth` (flat `Depth == 1` → `False`; `127`/`0`/absent/non-numeric
    → `True`, the conservative reading and the old hardcoded value), plus a guard that
    the derivation does **not** change `decide_reference`'s CREATE-ancestor decision
    (that logic is driven by the live `OwningPossibility` chain, never by the flag), a
    guard that the read survives an uncast object, and a regression guard for the
    live `Depth == 0`-but-nested shape (see the live section below).
  - Lookup **failure** vs genuine target **absence** is now distinguishable on both
    sides: a non-expected exception in the `AppendixesOC` scan or the owner+flid mirror
    is logged with a traceback and the drop reason says presence is **UNKNOWN, not
    confirmed absent**; the ordinary absent case keeps its original wording; the
    expected offline shapes (`ImportError`/`AttributeError`/`TypeError`/`ValueError`)
    stay quiet (no log spam); and a Name-fallback hit after a failed primary lookup
    still produces **no** drop. All paths remain fail-soft (never raise) and
    never-silent.
  - Appendix drops carry a human-legible `item_name` — a whitespace-collapsed,
    60-char-truncated snippet of the appendix's first non-empty `ContentsOA` paragraph
    — instead of a bare GUID. Read-only labelling; the appendix's owned `IStText` is
    still never reproduced into the target.

## Live-confirmed (read-only, FLExTools MCP on `Ejagham Full`, 2026-07-16)

The LCM-specific primitives fakes cannot exercise are live-proven (op-192927198-002):

- `_cast_possibility_list` discriminator: **rejects** a real `CmPossibility` and
  **accepts** a real `ICmPossibilityList` (cast + `PossibilitiesOS` post-check).
- `discover_owning_possibility_list`: reaches the owning list from a **top-level** item
  *and* from a **nested** sub-item (multi-hop `.Owner` walk).
- `_target_appendix_by_guid`: scanning an empty `LexDb.AppendixesOC` returns `None`
  with no throw (never uses `Repository.GetObject`).
- Owner-flid mirror inputs readable on a real list: `OwningFlid=6001049`,
  `Owner.ClassName=LangProject` (the exact inputs `_target_list_by_owner_flid` uses).
- Cross-project list-GUID instability (research Finding 3): source SemanticDomainList
  `c924bfce…` ≠ target `90aa3d0a…` — confirms mirroring by owner+flid, never by GUID.

### Issue #42 additions (read-only, FLExTools MCP on `Ejagham Mini`, 2026-08-10)

`CmPossibilityList.Depth` semantics and `LexAppendix`'s shape were live-probed rather
than taken from the liblcm sources alone:

- **`Depth == 1` really means flat.** Across **all 28** reachable possibility lists,
  **0** lists claiming `Depth == 1` actually have nesting — every one reports
  `tops_with_children = 0` (SenseTypes, MorphTypes, Roles, Status, Restrictions,
  TranslationTags, ExtendedNoteTypes, References, PublicationTypes, …).
- **`Depth == 127` is the tree flag but is *not* proof of live nesting** —
  `EducationOA` (7 tops), `ComplexEntryTypesOA` (7 tops) and `LocationsOA` (0 tops) are
  all `127` with zero children. This is precisely the "flagged hierarchical even when
  flat in this project" case the `decide_reference` comment describes, and independently
  confirms the flag must never gate the CREATE-ancestor walk.
- **`Depth == 0` occurs live AND can genuinely nest**: `LangProject.AnnotationDefsOA` is
  `Depth = 0` with **3 of 4** top items carrying children. Treating `0` as flat would
  have been **wrong** — the conservative `0 → hierarchical` choice is live-vindicated,
  not merely cautious. Pinned by a regression test.
- **`Depth` requires the `ICmPossibilityList` cast**: absent on an uncast `ICmObject`
  (as is `PossibilitiesOS` — they vanish and return together) and `127` again after
  re-casting. The two real call paths already pass a cast list, and
  `_iter_target_possibility_lists`' `hasattr(..., "PossibilitiesOS")` guard admits only
  objects exposing the same interface, so the derivation was already sound; it now casts
  defensively so a future bare-`ICmObject` caller cannot silently degrade to the default.
- **`LexAppendix` has no `Name`** — the live API reports exactly 4 properties
  (`ClassID`, `ClassName`, `OwnershipStatus`, and `ContentsOA : IStText` `owns_atomic`),
  confirming the appendix label must come from `ContentsOA`.
- `LexDb.AppendixesOC count = 0`, re-confirming the vacuous-live finding.

## Section A — LIVE-PROVEN on a constructed write-enabled fixture (2026-08-11)

Run on the disposable target **`Ejagham Full GT-Test`** (FLExTools MCP, `write_enabled=True`,
Phase-1 `undoable=False`). GT-Test has an **empty lexicon** (0 `LexEntry` / 0 `LexSense`,
302 `CmPossibility`), so the fixture created its own entry+sense plus one `LexAppendix`
carrying a real 84-char `ContentsOA` paragraph, then drove the **actual** resolver
functions against live LCM. A pre-write `.fwdata` snapshot was taken and restored
afterwards; the target is **byte-identical** to its pre-fixture state (`cmp` clean).

| Scenario | Result |
|---|---|
| `_appendix_label` on a real `LexAppendix` (#42c) | `'Appendix A: Ejagham loanword strata and their noun-class ref...'` — 63 chars (60 + `...`), so **truncation exercised live**. Was `''` before the fix. |
| `_target_appendix_by_guid` on a **NON-EMPTY** `AppendixesOC` | real GUID → **FOUND**, bogus GUID → **MISS**, `errors=[]` both ways. (030 had only ever proven the *empty*-collection case.) |
| A-present **LINK**, Move mode onto a real sense | **0 drops**; `AppendixesRC = 1` — the dedup guard held, the link was not re-added. |
| A-absent **DROP** | **1 drop** carrying the live label (not a bare GUID), correct absent-wording reason, ghost **not** linked, `AppendixesOC` still 1 — **never creates**. |

### A real bug this live pass caught

The uncast paragraph read in `_appendix_label` was **broken on every real project** and
could never have been caught offline. `StText.ParagraphsOS` is typed `IStPara`, which does
**not** carry `.Contents` — that lives on the `IStTxtPara` subtype — so the live read raised
`AttributeError: 'IStPara' object has no attribute 'Contents'`, and the `getattr` fallback
turned that into a silent `""`. The #42c label would have been empty in production while
the offline fakes (which expose `.Contents` directly) passed happily.

Fixed with `categories._as_st_txt_para` (cast, fail-soft) and pinned by two regression
tests whose fake **withholds** `.Contents` exactly as `IStPara` does — verified to FAIL
against the uncast implementation, so they are genuine guards rather than tautologies.
Swept the codebase: `texts.py:937` is the only other `ParagraphsOS` site and it is safe
(its paragraph comes straight from `IStTxtParaFactory`, already correctly typed).

> Note: `FLExProject.Transaction` logs *"no LCM rollback API found — transactions will
> execute but rollback on failure is not available"* in Phase 1. Partial writes therefore
> persist on mid-script failure (observed: an aborted run left 1 entry + 1 appendix behind).
> A pre-write snapshot is mandatory, not optional, for live fixture work.

## Fixture-only — deferred (not a defect)

Requires a **constructed fixture** (write-enabled) because no project on record
populates either field:

| Path | Why fixture-only |
|------|------------------|
| Section B thesaurus CREATE arm (item absent in mirrored target list, created with ancestor chain) through a real transfer | 0 `ThesaurusItemsRC` populated anywhere; "thesaurus" absent from every `.fwdata` |

Per the 024 convention ([024 validation-status.md](../024-lexicon-reference-fidelity/validation-status.md)):
a path staying on this list is **not** a defect — the offline suite proves the logic and
the gap is a fixture-availability limitation. Constructing the write-enabled fixture on a
disposable target (quickstart.md Part 2) and capturing pre/post evidence is the remaining
QA task before this row is cleared.

**Still open after issue #42 (2026-08-11).** Section A is now **cleared** (see the live
section above). The remaining Section B row is the sole unresolved #42 item. They are blocked on more than target availability: because
the fields are 0-populated *everywhere*, the fixture needs a **write-enabled source**
project — appendixes seeded into `LexDb.AppendixesOC` with senses referencing them, and
thesaurus items seeded into a possibility list with senses referencing those. That is a
destructive live LCM write to a source project, which per the crew protocol must be
human-authorized and must never run unattended. Deferred, not descoped.
