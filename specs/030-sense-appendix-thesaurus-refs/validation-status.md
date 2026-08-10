# Feature 030 — Live-Validation Status

**As of:** 2026-08-10 (originally 2026-07-16; updated for
[issue #42](https://github.com/MattGyverLee/GramTrans/issues/42)).

Both 030 fields are **vacuous-live across all 79 on-disk projects** (see
[research.md](./research.md) Finding 1), so — exactly as with lexrel / affix-MsEnv /
pictures in feature 024 — the offline suite proves the orchestration and a constructed
fixture is required for full end-to-end live proof. This document records what is
offline-proven, what is live-confirmed, and what remains fixture-only.

## Offline-proven (green, zero regressions)

`tests/unit/test_cycle16c_sense_scope_gaps.py` (34 tests: 20 from 030 + **14 added for
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
    (that logic is driven by the live `OwningPossibility` chain, never by the flag).
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

**Still open after issue #42 (2026-08-10).** Both rows above remain fixture-only and are
the sole unresolved #42 item. They are blocked on more than target availability: because
the fields are 0-populated *everywhere*, the fixture needs a **write-enabled source**
project — appendixes seeded into `LexDb.AppendixesOC` with senses referencing them, and
thesaurus items seeded into a possibility list with senses referencing those. That is a
destructive live LCM write to a source project, which per the crew protocol must be
human-authorized and must never run unattended. Deferred, not descoped.
