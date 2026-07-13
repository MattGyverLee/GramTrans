# Cycle 14 — Verification — T037 Phase-2 live re-Move (feature 025-full-reversals)

**Date:** 2026-07-13 | **Verdict:** **PASS** — feature 025 live-validated end-to-end;
merged to `main` @ `cb88b00`.

## Scope

Re-run of the T037 Phase-2 destructive live Move after the P0 sub-entry sense-loss
fix (`9d1266b`), which the fix had **not** yet been validated against live LCM. This
closes the single `needs_human` blocker from
[HANDOFF.md](../HANDOFF.md) / [.crew-handoff.json](../.crew-handoff.json).

- **Source:** `Ejagham Mini` (read-only)
- **Target:** `Target` (disposable), **restored to clean pre-Move state first**
- **Code:** worktree `025-full-reversals` @ `9d1266b`
- **Driver:** `scratchpad/t037_move_driver.py` (recovered from a prior session's
  scratchpad; reusable, self-contained), log `scratchpad/t037_move_rerun.log`
- **Runtime:** `py -3.13` (Python 3.13.12), FLExTools launcher, Target not open in FieldWorks

## Step 1 — Restore (attended, authorized)

The Target held the partial Move (144 `ReversalIndexEntry`: 134 top-level OK + 10
sub-entries with empty `SensesRS`). FieldWorks' own auto-backup `Target.bak`
(pre-Move) was provably clean.

- Guard: no FieldWorks GUI process, no `.lock` file.
- Preserved the polluted fwdata as `Target.fwdata.partialmove-evidence`.
- Restored `Target.bak` → `Target.fwdata`.
- Post-restore fwdata: **0 `ReversalIndexEntry`**, 1 (empty) `ReversalIndex`,
  11158 total `<rt>` — clean pre-Move state confirmed.

## Step 2 — Move (destructive write)

`transfer.execute` in 1.62s, `RunMode.MOVE`:
- `[stems] added=164 skipped=0`
- en index `ab4d4345-85c4-49c4-9726-ef39ce155e64` reused (R4) — source had 135
  top-level, target 0 pre-Move.
- Fresh re-open: en index **134 top-level** entries persisted.
- On-disk `Target.fwdata` after run: **144 `ReversalIndexEntry`** (134 + 10 sub),
  1 `ReversalIndex` — persistence confirmed independent of the LCM handle.
- `en.fwdictconfig` **SKIP** (byte-identical, no write, no `.gtbak`).
- `LangProject.PartsOfSpeechOA` untouched.
- `report.dropped_items = 337` — the known non-blocking 024-era backlog
  (`get_object_by_guid` Finding 2 + `MoForm.MorphTypeRA`/`CmTranslation.TypeRA`/
  `LexExampleSentence.TranslationsOC` Finding 3). Not a regression.

### Non-blocking traceback (expected)

`categories.py::_run_post_pass_a` (~4750) calls the non-existent
`FLExProject.get_object_by_guid` → `AttributeError`, swallowed by the per-action
try/except in `transfer.execute` and logged. This is **Finding 2** from cycle 12,
already tracked in the non-blocking backlog. No effect on reversal writes.

## Step 3 — Verification (THE P0 check): sub-entry `SensesRS` vs Preview plan

The P0 fix (`9d1266b`) threads `first_sense` into `_create_sub_entry`. Pre-fix, the
identical run left 9/10 sub-entries silently at `SensesRS=0`. Post-fix live result,
cross-checked against the pre-write Preview plan dump — **exact match, all 10**:

| Parent (en) | Sub-entry form | Preview `linked_senses` | Post-Move `SensesRS` |
|---|---|---|---|
| his | 3S CLS5 | 1 | 1 |
| POSS | 2S CLS6 | 1 | 1 |
| one | CLS2,CLS6 | 1 | 1 |
| one | CLS8,14 | **0** (`dropped_sense_members=0`) | **0** |
| they, them, their | 3p | 1 | 1 |
| three | CLS2,6 | 1 | 1 |
| three | CLS5,9 | 1 | 1 |
| two | CLS2,6 | 1 | 1 |
| two | CLS5,9 | 1 | 1 |
| your | 2S CLS5 | 1 | 1 |

Plan distribution: **9× `linked_senses=1`, 1× `linked_senses=0`**. Post-Move actual:
**9× `senses=1`, 1× `senses=0`**. The lone `0` (`one → CLS8,14`) was correctly
predicted — the source sub-entry had no sense to carry (`dropped_sense_members=0`),
so it is a faithful 0, not a silent drop.

Top-level linking (single + multi-sense), `ReversalForm` carry, and sub-entry
recursion structure were already PASS in cycle 12 and remain PASS here.

## Regression gate (merged tree)

`py -3.13 -m pytest tests/unit`: **1 failed / 1510 passed / 9 skipped / 14 xfailed /
14 xpassed**. The single failure
(`test_wizard_pos_grammar_wiring::test_plan_emits_pos_action_for_picked_pos`) is the
**pre-existing baseline** failure — confirmed failing on both branch `9d1266b` and
main `e033565` independently, so it is not introduced by the merge.

## Outcome

- All 5 quickstart scenarios: S1 now **fully live-validated** (Preview + Move,
  top-level + sub-entry). S2/S3/S4-ADD/OVERWRITE remain not-exercisable in this
  corpus (need fixtures — non-blocking backlog). S5 channel confirmed.
- Merged `025-full-reversals` → `main` @ `cb88b00`.
- **Feature 025 COMPLETE.**
