# Cycle 6 — lex-qc (merge-gate) review

**Feature:** 027 Complex Forms & Variants · **Gate:** T027 merge · **HEAD:** worktree `34be1ad`
**Score: 79/100 — FIX ISSUES** (not REJECT — happy-path US1/US2/US3 correct and
well-tested; two carried-forward P1s must close before "feature complete")

> Note: authored by the main session on behalf of lex-qc, which lacked a Write tool in
> its session and returned findings inline.

**Pattern-Audit Gate:** N/A — spec-driven feature implementation (full /speckit
workflow), not a `bug`-labelled `closes #N` commit. Asserted from spec-artifact shape
(no `gh`/git-log access in that session).

## Adjudications (three carried-forward items)

### 1. P1a — leaf-pick scope, `_entry_ref_is_reproducible` (categories.py:4410-4417) — MERGE-BLOCKING
Real correctness gap, confirmed live. `stems_enumerate_source`/`affixes_enumerate_source`
(categories.py:5817-5838, ~5447) genuinely narrow the copy set via
`selection.leaf_picks_for(...)` (selection.py:438-445) — an intrinsically-eligible entry
can be excluded from a given run. `_entry_ref_is_reproducible` only checks
`_affix_type_of(m)[0]` (intrinsic shape), never selection membership, and
`_report_dropped_entry_refs` doesn't even receive `context`/selection, so it structurally
cannot check pick membership. Contradicts spec.md's "copy closure" definition ("entries
actually copied") and research.md Decision 5 ("all in the copy closure"). Net effect: a
leaf-pick-narrowed run with a ref to an excluded component silently emits zero
`DroppedItemRecord`s, so `compute_fidelity_by_guid` (categories.py:3283) over-reports FULL
fidelity — the exact silent-loss shape Principle V and this feature exist to prevent.
`grep "leaf"` in research.md returns nothing — the documented-limitation note cycle-3 QC
recommended as the *minimum* fix was never added.
- **Minimum bar to unblock:** add the doc note (research.md Decision 5 addendum +
  corrected `_entry_ref_is_reproducible` docstring, which currently overclaims "will exist
  on the target ... regardless of processing order" with no caveat).
- **Preferred (post-merge OK once documented):** thread real selection/pick-set through
  so the check is run-scoped, not type-scoped.

### 2. P1b/c — stale `fidelity_census.py` + stale comment — MERGE-BLOCKING
Both statements now false: `("LexEntry","EntryRefsOS")`'s note still says "no
ILexEntryRefFactory create site exists anywhere in Lib/*.py" and all 5
`("LexEntryRef", field)` rows still say "no LexEntryRef is ever created"
(fidelity_census.py:59, 350-362, 622-662) — the real create site is now
`_create_entryref_container`/`_run_entryref_create_pass` (categories.py:4999-5170;
`ILexEntryRefFactory` ~5011-5016). In-code comment categories.py:4608-4611 is likewise
stale, and line-number citations throughout are stale (cite 4060/4089; actual 4420/4520+).
This file is the project's documented "closed map the census verifies against" for the
never-silent guarantee — shipping it stale directly undermines the audit trail this
feature produces. Low-effort fix (update CLASSIFICATION bucket/site/note/line-refs for the
6 affected rows + the categories.py:4608-4611 comment), fully scoped by cycle-3 QC.

### 3. P2 — test-fixture DRY — NON-GATING (confirmed)
`_FakeRefSeq`/guid-only fake/`_ctx_create_and_wire` duplicated across four 027 test files.
Pre-existing suite-wide pattern (`_FakeGuidObj`-shaped fakes in 7+ unrelated files,
predating 027), and test_027_never_silent.py's docstring documents the self-containment as
deliberate. Low-priority follow-up: shared `tests/unit/_fixtures_lexentry_ref.py`.

## T021/T022 test quality — strong, not shallow
- **T021** (`test_c5_preview_move_created_and_dropped_set_parity`,
  `test_c5_created_ref_set_is_disjoint_from_dropped_set`): exercises the real
  plan→preview→move pipeline end-to-end, asserts Preview writes nothing to the source
  (snapshot), created-set == planned-set with GUIDs preserved, and identical reproduce/drop
  partition across Preview/Move on a mixed selection. Genuine byte-parity proof. **Caveat:**
  only the intrinsic-eligibility axis — never a leaf-pick-narrowed selection — so it
  structurally cannot catch P1a.
- **T022** (`test_c7_empty_source_*`): asserts byte-level absence (`create_map == {}`, not
  `{"entry": []}`) and zero creates/drops across all three entry points. Genuine
  empty-source byte-equivalence.

## Summary
Score 79/100. **P1a (categories.py:4410) and P1b/c (fidelity_census.py + categories.py:4608
comment) both MERGE-BLOCKING** — neither fixed despite cycle-3 flagging both as required
before feature completion. P2 non-gating.
