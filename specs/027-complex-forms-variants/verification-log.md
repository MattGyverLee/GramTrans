# 027 — T025 Live Validation Log (attended)

## FINAL STATUS: PASS (after cycle-8 fix)

The first T025 run (HEAD `f1917fa`) proved `0 → 6` reproduction but surfaced a C4
drop-reporting defect (6 false-positive drops). Cycle 8 fixed it (worktree `02413b5` —
cast component members via `_cast_lcm` before `_affix_type_of`) and the **re-run at the
fixed HEAD is fully clean**: containers `0 → 6`, RefType 6/6, variant-type 6/6, component
lexemes 6/6, **EntryRefsOS drops 0** (Move #1 and #2), idempotent. Both the first
(defective) run and the passing re-run are recorded below.

---

## Re-run #2 (RESOLVED) — HEAD `02413b5`, attended, `run27_live_v2.log`

| Metric | Move #1 | Re-Move #2 |
|---|---|---|
| LexEntryRef containers on target | **6** (0 → 6) | 6 (stable) |
| RefType correct | 6/6 | 6/6 |
| variant-type wired (C3) | 6/6 | 6/6 |
| containers missing | 0 | 0 |
| component lexemes wired (probe) | **6/6** (1 each) | — |
| **EntryRefsOS drop records (C4)** | **0** ✅ (was 6) | 0 |

All driver self-checks PASS (SC-001/002/003/004); exit 0. The 6 false-positive drops from
run #1 are eliminated — reproduced in-closure refs are correctly NOT reported. Data
correctness (containers + components + types) is unchanged from run #1. (Note: the standalone
`probe27_components.py` VERDICT text still says "despite the 6 C4 drop reports" — that string
is hardcoded from run #1 and is stale; the current live drop count is 0.)

**C3 list-shape MCP re-confirmation:** still PENDING (domain `mcp_deviation`) — optional
belt-and-suspenders; the live CREATE-arm succeeded (6/6 types wired), which exercises the
same factory dispatch the shapes underpin.

---

## Run #1 (DEFECTIVE — superseded, kept for the record)

**Run:** 2026-07-13 ~23:32, attended (user-directed) · **Driver:** `debug/run27_live.py`
**Pair:** `Ejagham Mini → Target` (Target restored from `Target 2026-07-06 0218.fwbackup`)
**Worktree HEAD:** `f1917fa` · **Exit:** 0 (driver self-checks all PASS)

## Result summary

| Metric | Move #1 | Re-Move #2 |
|---|---|---|
| plan actions / skips | 336 / 1811 | 1 / 2132 |
| entryref_create_bindings | 6 | 6 |
| **LexEntryRef containers on target** | **6** (0 → 6) | 6 (stable) |
| RefType correct | 6/6 | 6/6 |
| variant-type wired (C3) | 6/6 | 6/6 |
| containers missing | 0 | 0 |
| **component lexemes wired** (follow-up probe) | **6/6** (1 each) | — |
| primaries wired | 0 (variants have none — correct) | — |
| EntryRefsOS drop records emitted (C4) | **6** | 0 |

## PASS — core reproduction (SC-001/002/003, #30 fix proven live)

- **SC-001 `0 → 6`**: all 6 `Ejagham Mini` variant `LexEntryRef`s reproduced on the
  target — container created (GUID-preserved), `RefType=0`, **1 component lexeme wired
  each** (confirmed by `debug/probe27_components.py`, reopen + `_cast_lcm`).
- **SC-002**: each reproduced ref carries a resolved variant-type (6/6).
- **SC-003 idempotent**: re-Move creates 0 net-new containers (stable at 6).
- The live path exercises `_resolve_target_by_guid` + `_cast_lcm` end-to-end — the #28
  layers 1+2 resolution/casting works for container creation and component wiring.

## FAIL — C4 never-silent drop reporting is INACCURATE (live-surfaced defect)

`_report_dropped_entry_refs` emitted **6 false-positive `DroppedItemRecord`s** on Move #1
— one for each of the 6 refs that the follow-up probe proves were **fully reproduced**
(container + component + variant-type). This contradicts contract C4 ("emits a record
only for a ref that is **not** reproduced; in-closure refs are reproduced and are NOT
reported") and SC-004.

**Root cause — #28 layer-2 casting gap in the new C4 heuristic.**
`_entry_ref_is_reproducible` (categories.py:4410-4417) calls `_affix_type_of(m)` on each
`m` taken straight from the source ref's `ComponentLexemesRS`, **without `_cast_lcm(m,
"ILexEntry")`**. On live LCM those members are bare `ICmObject`s, so
`getattr(m, "LexemeFormOA", None)` is `None` → `_affix_type_of` returns `(False, …)` →
the ref is wrongly judged "component out-of-closure / never STEMS/AFFIXES-eligible" and
reported dropped. The offline fakes (`_FakeEligibleEntry`) expose `LexemeFormOA`
directly, so no cast is needed and T019/T021 pass green — the suite **structurally cannot
catch this**. This is the exact latent-bug shape STATUS.md flagged for the #28 passes,
now recurring in the C4 code the drop-policy flip introduced.

**Secondary symptom — non-idempotent reporting.** The same 6 refs are reported dropped on
Move #1 (owners freshly copied → `_walk_lex_entry_closure` runs the report) but 0 on
re-Move #2 (owners already present → closure not entered). So the drop set is both
false-positive AND unstable across runs.

**Severity.** Data on disk is CORRECT and complete (no data loss; the transfer works).
The defect is in **fidelity *reporting***: `compute_fidelity_by_guid` will under-report
fidelity (mark fully-reproduced refs as dropped) — "crying wolf," the inverse of the
silent-loss the feature targets, but still wrong output that violates C4/SC-004.

**Relation to cycle-6/7 P1a.** Reviewers treated the `_entry_ref_is_reproducible`
scope gap as a rare leaf-pick edge and closed it at documented-limitation scope. The live
run shows the heuristic is unsound on the **full, un-narrowed** Ejagham Mini corpus (6/6
refs mis-reported) — a genuine bug, not a corner case. The doc-note (cycle-7) does not
cover this.

## Follow-up MCP re-confirmation (C3 list shapes) — PENDING

Domain's `mcp_deviation` (VariantEntryTypesOA/ComplexEntryTypesOA=5118/Depth=127;
PublicationTypesOA=7/Depth=1) not yet re-confirmed via FLExToolsMCP.

## Recommendation

**Do NOT merge (T027) as-is.** Core reproduction is proven and excellent, but the C4
drop-report defect must be fixed first (cast the component members via `_cast_lcm` before
`_affix_type_of`, or — better — base reproducibility on actual post-tail target
resolvability rather than the intrinsic `_affix_type_of` proxy) and covered by a live-shaped
regression test (bare-`ICmObject` component fake with no exposed `LexemeFormOA`). Re-run
T025 after the fix.
