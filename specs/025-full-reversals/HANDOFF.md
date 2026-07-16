# Feature 025 — Full Reversals — HANDOFF

**Date:** 2026-07-13 | **Status:** `feature_complete` — live-validated end-to-end and **merged to
`main` @ `cb88b00`**. Nothing left to do. | **Worktree:** `025-full-reversals` @ `9d1266b` (now
merged; safe to remove).

This doc is the single pickup point. Machine-readable state:
[.crew-handoff.json](./.crew-handoff.json). Session log: [../../STATUS.md](../../STATUS.md).

---

## TL;DR — DONE (2026-07-13 attended session)

The single `needs_human` blocker (attended live re-Move + merge) is closed. Evidence:
[reviews/cycle14-verification-t037-remove.md](./reviews/cycle14-verification-t037-remove.md).

1. **Restored** `Target` from its clean pre-Move auto-backup `Target.bak` (0 reversal entries;
   polluted fwdata preserved as `Target.fwdata.partialmove-evidence`).
2. **Re-ran the T037 Phase-2 live Move** (`scratchpad/t037_move_driver.py`, `Ejagham Mini` →
   restored `Target`, code @ `9d1266b`): 164 added / 0 skipped; en index `ab4d4345` reused (R4);
   134 top-level + 10 sub-entries persisted (144 total, confirmed on fresh re-open + on-disk).
3. **Verified** — PASS: all 10 sub-entries' post-Move `SensesRS` match the Preview plan exactly
   (9× senses=1, 1× senses=0 for `CLS8,14` which legitimately had none). Pre-fix left 9/10 at 0.
4. **Merged** `025-full-reversals` → `main` @ `cb88b00`. Offline suite on merged tree:
   1 pre-existing baseline fail (not a 025 regression) / 1510 passed / 9 skipped / 14 xf / 14 xp.

> The Ralph loop had been cancelled (it correctly refused the destructive live write unattended).
> This attended session completed it.

---

## What shipped (all on the worktree, offline-green)

All 37 tasks (T001–T037) implemented; QC gate GREEN. Full unit suite: **1508 passed / 1 failed
(pre-existing, unrelated) / 9 skipped / 14 xfailed / 14 xpassed**.

- **US1 (T009–T020)** — reversal entries ride along with copied senses: `reversals.py`
  `plan_reversals` / `apply_reversals`, per-WS index create/reuse (R4), `ReversalForm` carry,
  copied-only `SensesRS` linking, recursive `SubentriesOS`, WS gate, never-silent drops.
- **US2 (T021–T027)** — `PartOfSpeechRA` resolved against the **per-index** `PartsOfSpeechOA` via
  the 024 three-way resolver (CREATE+ancestors / UPDATE / LINK+REPORT / LINK), shared cache.
- **US3 (T028–T033)** — `config_views.py`: `.fwdictconfig` Add/Overwrite/Skip via `filecmp`,
  absent-reference scan, `.gtbak` backup, Preview/Move wiring.
- **Polish (T034–T036)** — census extended (79 fields, `ReversalIndexEntry`), unified never-silent
  cross-cutting assertion, empty-project regression gate.
- **QC gate remediation** — two P0s from the first gate closed (config-views Preview read-only;
  reversal + config-view plan surfaced before Move).

## Live validation (T037) — what actually happened

Run against **Ejagham Mini → Target** (disposable, user-confirmed). Reusable drivers in
`scratchpad/`: `t037_driver.py` (Preview), `t037_move_driver.py` (Move).

- **Phase 1 (read-only Preview) — PASS.** Scenario 1 verified end-to-end: 134 reversal Add
  decisions, correct R4 index reuse, sub-entry recursion + `ReversalForm`; read-only guarantee held
  (Target byte-unchanged, no new source dirs). Surfaced 2 latent bugs → **both fixed + re-gated
  GREEN** (Finding 1: never-silent `divergence_fingerprint` mixed-key `TypeError` swallow; Finding
  2: Preview didn't thread `_ws_map` into the reversal walk).
- **Phase 2 (destructive Move) — RAN, Scenario 1 write-half PARTIAL → P0 fixed.**
  - **PASS:** 134/134 top-level entries persisted (fresh re-open confirmed); top-level single- AND
    multi-sense linking; `ReversalForm`; sub-entry recursion *structure*;
    `LangProject.PartsOfSpeechOA` untouched (13/13); config `en.fwdictconfig` SKIP (no write).
  - **P0 FOUND & FIXED (`9d1266b`):** `reversals.py::_apply_one_entry` computed
    `remaining_senses = target_senses[1:]` assuming the create linked sense #1 — true for
    `_create_top_level_entry`, **false** for `_create_sub_entry` (linked no sense). 1-sense
    sub-entries silently ended with empty `SensesRS`. Fix threads `first_sense` into
    `_create_sub_entry` and links it via `_link_remaining_senses`; 3 RED-confirmed regression
    tests; tripwire-verified (cycle 13). **This fix has NOT been re-validated live — that's step 2.**

## Scenario coverage status

| Scenario | Offline | Live (T037) |
|---|---|---|
| S1 reversal ride-along | ✅ | Preview ✅; Move top-level ✅; **sub-entry sense re-Move ✅ (cycle 14)** |
| S2 per-index category resolve | ✅ | Not exercisable — no reversal `PartOfSpeechRA` in Ejagham Mini (needs fixture) |
| S3 WS gate | ✅ | Not exercisable — identity `en`/`etu` WS pair (needs unmapped-WS fixture) |
| S4 config views | ✅ | ✅ **ADD / OVERWRITE / `.gtbak` / `missing_refs`(WS+style+custom-field) / idempotent-SKIP all live-proven 17/17 via FLExToolsMCP (2026-07-16)** — surfaced + fixed a real live-vs-fake bug (custom-field missing-ref silently dropped; `GetAllFields` needs `owner_class`). See `reviews/live-proof-configviews.md` |
| S5 unified never-silent | ✅ | ✅ (channel confirmed; now surfacing real 024 gaps — see backlog) |

## Non-blocking backlog (tracked, out of the critical path)

- **Sentinel-prefix hardening** for `_multistring_dict` fallback key (`f"~unresolved~{wh}"`) — domain
  ruled the current `str(wh)` SAFE (BCP-47 forbids bare-digit WS Ids); near-zero-cost belt-and-suspenders.
- **Finding 2 (024-era):** `categories.py::_run_post_pass_a` calls non-existent
  `FLExProject.get_object_by_guid` → `AttributeError` logged WARN but NOT emitted as a
  `DroppedItemRecord` (invisible to never-silent). Fix/remove + emit a dropped record.
- **Finding 3 (024-era fidelity backlog):** the never-silent channel now correctly reports
  pre-existing `MoForm.MorphTypeRA` / `CmTranslation.TypeRA` "shared-default diverged" and
  ~72 `LexExampleSentence.TranslationsOC` gaps (`FLExProject` has no attribute `Translations`).
- **P1-1** reuse `RunPlan.reversal_decisions` at Move instead of recomputing; **P1-2** DRY
  `_target_ws_ids` (reversals.py == config_views.py).
- **UI wiring** — `render_reversal_decisions` / `render_config_view_records` are surfaced via
  `render_preview_extra_lines` → `main_window._on_preview`; confirm in the actual PyQt Preview pane
  during a GUI run (headless driver bypasses the UI).
- **Live re-confirm of WS Id/handle shapes** (domain cycle 11 relied on recorded evidence, lacked live MCP).

## Reports (chronological)

`reviews/cycle1..8-programmer.md` (build), `cycle5-qc/verification` (first gate, RED),
`cycle6-programmer` (P0 remediation), `cycle7-qc/verification` (gate GREEN),
`cycle9-verification-t037-preview` (live Preview + 2 findings),
`cycle10-programmer` (findings fix), `cycle11-qc/verification/domain` (re-gate GREEN),
`cycle12-verification-t037-move` (live Move + P0 found),
`cycle13-programmer` + `cycle13-verification` (P0 fix + verify).

## Git

- Implementation branch `025-full-reversals` @ `9d1266b` **merged to `main` @ `cb88b00`**
  (2026-07-13). Worktree `D:/Github/_Projects/_LEX/GramTrans-025-full-reversals` is safe to remove.
- All spec artifacts (this doc, reviews incl. cycle14, handoff json, STATUS.md) are on `main`.
- Live re-Move validated sub-entry sense counts (cycle 14) — merge done. **Feature complete.**
