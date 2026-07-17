# Domain Expert Review — Feature 030 (cycle 1)

**Date:** 2026-07-16
**Worktree:** `GramTrans-030-sense-appendix-thesaurus-refs` @ d6132ff
**Score:** 91/100 — **APPROVED** (two low-severity, non-blocking recommendations)

**Tool note:** FLExToolsMCP was not exposed to this subagent (Read/Grep/Glob/WebFetch only), so live GUID/API claims were cross-checked against research.md's already-cited live evidence and 024's live-proven REFERENCE_FIELD_MAP rather than independently re-run. Recommend a spot re-run of the two GUID checks via MCP if independent re-confirmation is wanted before merge.

## Section A — LexSense.AppendixesRC → LexAppendix, link-by-GUID: PASS
- No `ILexAppendixFactory.Create(...)` anywhere in the diff — target-absent GUID is never created (FR-002/G-A2).
- `_target_appendix_by_guid` linear-scans `LexDb.AppendixesOC` (not `Repository.GetObject`), so an absent GUID cannot raise (G-A6) — correct, since GetObject throws on a bad GUID and LexAppendix has no name/fingerprint fallback.
- `ContentsOA` (owned IStText) never touched — correctly out of scope.
- DroppedItemRecord fires unconditionally on a GUID miss with a scope-naming reason — matches contract C-A step 3b.
- Preview (new_sense=None) and Move wired at the identical point in both sense loops → drop decision is a pure function of target ownership; FR-008/G-A5 holds by construction.
- **GUID-only is correct and effectively the only feasible choice**: LexAppendix has no Name/Abbreviation (so no fingerprint fallback exists). GUID stability across an independent source→target copy is a narrow assumption (holds only for shared provenance — common scaffold, LIFT round-trip, S/R history). The spec is explicit this is the deliberate narrow scope, and the honest default for the common case is DROP_REPORT, never a false "linked". Domain-correct.
- **Rec (non-blocking):** appendix drop `item_name` is always "" (no `.Name`), so a linguist sees only a raw GUID. A human-legible label (e.g. ContentsOA first-paragraph snippet) would improve report usability — out of current scope, backlog note.

## Section B — LexSense.ThesaurusItemsRC → CmPossibility, dynamic-owner: PASS
- Owner-class + OwningFlid, never list GUID — correct and confirmed necessary (research Finding 3; consistent with 024's REFERENCE_FIELD_MAP resolving every row by fixed accessor path, never list GUID). Section B is the dynamic-owner generalization of that already-live-proven principle.
- `.Owner`-walk discovery is right; `_cast_possibility_list` correctly distinguishes `ICmPossibilityList` (PossibilitiesOS) from `ICmPossibility` (SubPossibilitiesOS); depth-capped + null-guarded → never raises/spins (G-B3).
- **Wrong-list risk checked, contained:** `_target_list_by_owner_flid` uses `sda.get_ObjectProp` (atomic/OA accessor); if flid is a many-valued OC it returns nothing and falls to Name fallback — it cannot return the wrong sibling from a collection. No silent misresolution.
- **Coverage gap (non-blocking, inherited):** `_iter_target_possibility_lists` enumerates only the fixed standard singleton-owned lists (same universe as 024), NOT arbitrary custom lists. A custom-list thesaurus item would fall to DROP_REPORT even if a same-named target list exists. This mirrors 024's pre-existing scope boundary and fails safe (never-silent, never wrong-list). Contract phrasing ("a target ICmPossibilityList whose Name matches") reads more general than delivered — recommend a one-line contract clarification.
- Name-collision risk (two lists sharing a Name) is genuine but low and is the same class 024 already accepts.
- Hierarchical CREATE correct: `ICmPossibilityFactory` against `PossibilitiesOS` for root, `parent.SubPossibilitiesOS` for nested (G-B1).

## Section C — Implement a legacy/0-populated field at all? Sound.
Consistent with the constitution ("everything that hangs off the Lexicon eventually needs handling") and the never-silent invariant. Reuses 024's full create/link/update machinery; adds only minimal model-stable discovery; introduces no new factory-GUID table (Principle I). Correct if a populated project ever appears; the spec's "essentially never runs on real data" framing is honest.

## Requirement verdicts
| Area | Verdict |
|---|---|
| FR-001/002 (A link-by-GUID, never-create) | PASS |
| FR-003/004/005 (B discover+resolve+drop) | PASS |
| FR-006 (non-destructive empty-source) | Not re-tested this cycle (relies on 024 carry-over; structure consistent) |
| FR-007 (dedup / no per-ref dup) | PASS (`_collection_already_has` both fields; shared resolver_cache) |
| FR-008 (Preview/Move parity) | PASS (identical call sites) |
| FR-009 (census reclassification) | Not directly inspected this cycle — recommend follow-up spot-check |

**Recommendations (both non-blocking):** (1) human-legible identifier in Section A drop records (deferred by scope); (2) one-line contract clarification that the Name-fallback candidate set is bounded to 024's known standard-list universe.

**2-line summary:** Section A PASS — GUID-only is the correct and only feasible fidelity choice, never-creates confirmed. Section B PASS — owner+flid mirroring correct and consistent with 024 precedent; one low-severity non-blocking doc gap (Name-fallback doesn't cover arbitrary custom lists — an inherited 024 limitation, not new).
