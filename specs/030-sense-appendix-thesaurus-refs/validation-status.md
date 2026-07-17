# Feature 030 — Live-Validation Status

**As of:** 2026-07-16.

Both 030 fields are **vacuous-live across all 79 on-disk projects** (see
[research.md](./research.md) Finding 1), so — exactly as with lexrel / affix-MsEnv /
pictures in feature 024 — the offline suite proves the orchestration and a constructed
fixture is required for full end-to-end live proof. This document records what is
offline-proven, what is live-confirmed, and what remains fixture-only.

## Offline-proven (green, zero regressions)

`tests/unit/test_cycle16c_sense_scope_gaps.py` (17 tests) +
`tests/verification/fidelity_census.py`. Full suite: **22 failures, byte-identical to
clean `main`** — every one pre-existing (suite-ordering `sys.modules` pollution
unrelated to 030); 030 adds **zero** regressions.

- Section A: A-link, A-absent (no create), A-partial, A-empty (non-destructive),
  A-shared (no dup), Preview==Move.
- Section B: `.Owner` discovery (found / no-list), owner-list mirror (Name hit/miss),
  drop-on-failure (no-list, no-mirror), link-to-existing, empty-source non-destructive,
  shared-no-dup, Move==Preview parity.
- Census: both fields classify **COPIED**; never-silent classifier guard + single-member
  `OUT_OF_SCOPE_EXCLUDED` set intact.

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

## Fixture-only — deferred (not a defect)

Requires a **constructed fixture** (write-enabled) because no project on record
populates either field:

| Path | Why fixture-only |
|------|------------------|
| Section A end-to-end LINK through a real GramTrans transfer | `LexDb.AppendixesOC` = 0 and no sense references an appendix anywhere |
| Section B thesaurus CREATE arm (item absent in mirrored target list, created with ancestor chain) through a real transfer | 0 `ThesaurusItemsRC` populated anywhere; "thesaurus" absent from every `.fwdata` |

Per the 024 convention ([024 validation-status.md](../024-lexicon-reference-fidelity/validation-status.md)):
a path staying on this list is **not** a defect — the offline suite proves the logic and
the gap is a fixture-availability limitation. Constructing the write-enabled fixture on a
disposable target (quickstart.md Part 2) and capturing pre/post evidence is the remaining
QA task before this row is cleared.
