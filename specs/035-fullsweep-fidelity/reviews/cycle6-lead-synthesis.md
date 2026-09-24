# Cycle 6 — Team Lead synthesis and user ratification: T045d field source

**Date:** 2026-09-24
**Inputs:** live probes `op-133436809-002`, `op-133459014-003` (main session);
[cycle6-domain.md](./cycle6-domain.md) (live, FLExToolsMCP, run by a general-purpose agent in
the lex-domain role, because the lex-domain agent type has no MCP or Write tools);
[cycle6-author.md](./cycle6-author.md) (lex-author; its prompt omitted the live measurements,
see its filing note).

## Verdict

**Option D.** The plane-2 census reads every stored, non-virtual LCM model field through one
class-agnostic metadata reader. flexicon `GetSyncableProperties` leaves the census path. This is
recorded as research.md **D-02a**, which supersedes D-02.

The user's framing, which this confirms: *"Syncable properties was more about merges, even if it is a
convenient listing of what can change."*

## The author's objection, resolved

lex-author rejected a *declared* not-carried list because a declaration cannot detect
regressions by itself. Its premise, that `model - syncable` measures what the engine carries, is false:
- The engine uses that surface for only 12 of the 69 classes.
- Even for those 12, the engine copies fields outside the surface.
- The surface is sparse per object.

The objection itself still stood and is answered by making the ledger self-checking (**FR-190**):
- Every stored field is compared every run. The ledger only *labels* measured losses and never
  removes a field from comparison.
- A measured loss that is not on the ledger is UNEXPLAINED_LOSS. This is the regression detector.
- An entry that matches no loss in a run is stale, and it invalidates the run.
- Each entry requires an exact (class, field) match, evidence, and an open issue. FR-121 still
  applies.
- If any entry is consumed, the best verdict is PASS_WITH_ALLOWLIST.

## User rulings (2026-09-24)

| Q | Question | Ruling |
|---|---|---|
| Q1 | Supersede D-02 with the metadata reader | **Yes** |
| Q2 | Handling of engine gaps | **Engine-gap ledger (FR-190, T045g)**; a consumed entry caps the verdict at PASS_WITH_ALLOWLIST (exit 0) |
| Q3 | FR wording | FR-052, FR-056 (last sentence), FR-065 and FR-066 amended; FR-190 added (shown to the user before commit) |
| Q4 | `StTxtPara.ParseIsCurrent`; `WfiWordform.SpellingStatus` | ParseIsCurrent goes **on the roster** (recomputed parser bookkeeping); SpellingStatus is **compared** |
| Q5 | Hyperlink run properties that embed the source project name | **Compared verbatim**; a link that still points at the source is a real defect |
| Q6 | Owned classes outside the 69 | **Extend `in_scope_classes`** with at least PhCode and CmTranslation; record an explicit exclusion for each of the rest (T045h) |

## Resulting chain

T044 → **T045d** (re-scoped) → **T045h** (new) → T045e → T045f → **T045g** (new) → T045a(c) → T045b →
T045 → T035.

## Findings outside feature 035

- **Engine:** custom-field *values* are not carried on the path cycle6-domain.md traced, although
  the definitions are created (`api._ensure_custom_fields`). `custom_fields_execute_action`
  (`categories.py:1289`) is a documented no-op. This should be filed as a GramTrans engine issue.
  Once T045d lands, the sweep will report these values as LOST, which is correct.
- **Crew tooling:** the lex-domain agent definition lacks FLExToolsMCP and Write, which explains the
  recurring "MCP unavailable to lex-domain" caveat from cycles 1-5.
