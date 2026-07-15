# Feature 026 — Texts & Wordforms — HANDOFF

**Last updated:** 2026-07-15
**Worktree:** `../GramTrans-026-texts-wordforms` on branch `026-texts-wordforms` @ **`4f99523`**
**Not merged to `main`.** Full evidence: [verification-log.md](./verification-log.md).

---

## TL;DR

026 was fully implemented (T001–T040) but had **never been run end-to-end on live data** — it
was unit-tested entirely against fakes. This session brought the branch up to date with `main`
(027 + 028 had merged) and ran the attended live proof, which surfaced a **cascade of
live-vs-fake defects** in the wordform/analysis path. **Six fixes** later, 026 reproduces
texts + analyses + AnalysesRS wiring + glosses live. **Three items remain before merge**, the
most important being an SC-005 idempotency bug.

**Do NOT merge yet.** Finish the three remaining items below, then merge.

---

## Current state

### Conflict merge (done)
`main` was merged into `026-texts-wordforms` (merge commit in history); 4 additive conflicts
resolved keep-both (`models.py`, `preview.py`, `transfer.py`, `fidelity_census.py` — 024 census
total `75`→`79` for the merged `counts` incl. `ReversalIndexEntry`). Branch is 0 behind `main`.
Offline suite **1702 passed** / 7-fail **environment baseline** (see "Environment gotchas").

### Live proof — final state (single Move, Ejagham Mini → Target, fresh disk re-open)

| Aspect | Before session | Now |
|---|---|---|
| Texts (US1) | 9 (never proven) | **9, persisted** ✓ |
| Segments | — | **101** ✓ |
| Analyses created (US2) | **0 — silent loss of 219 approved** | **179** ✓ |
| `AnalysesRS` wired (R5) | 2 | **206** ✓ |
| Glosses (US4) | 0 | **282** ✓ |
| Verdicts (R2/FR-014) | — | 1 approved / 178 needs-review — **correct** given the target lacks the referenced senses/MSAs (1532 morph-bundle drops) |

---

## The six fixes (all with offline regression tests)

All in `src/gramtrans/Lib/wordforms.py` unless noted. Each was a live-vs-fake API divergence the
fakes could not express.

1. **Analysis human-eval gate** — `_human_evaluation` → added `_live_human_evaluation` reading
   `IWfiAnalysis.ApprovalStatusIcon` (1/2/0). The old `WfiAnalyses.GetHumanEvaluation` /
   `GetHumanEvaluation()` / `human_evaluation` hooks are all **absent live**.
2. **Gloss-token gather** — `_normalize_token_to_analysis` + `plan_analyses`: a `Segment.AnalysesRS`
   `IWfiGloss` token resolves to its owning `IWfiAnalysis` (deduped per wordform); bare-wordform /
   punctuation tokens skip. Real interlinear tokens are mostly glosses (204/540), not bare
   analyses (2/540).
3. **Owning-wordform grouping** — `_iter_segment_wordforms` groups each token by the owning
   wordform of its *analysis*, so the wordform form is captured and the target wordform is
   found/created.
4. **`AnalysesRS` wiring (R5)** — `plan_alignment` keys an ANALYSIS-kind token by its
   **owning-analysis GUID** (matches `apply_analyses`'s `_wf_analysis_map`); gloss tokens used to
   carry the gloss GUID and never matched.
5. **Gloss human-eval gate** — `_gloss_human_evaluation` → `_live_gloss_human_evaluation`: a live
   `IWfiGloss` is human content iff its owning `IWfiAnalysis` is human-evaluated.
6. **Gloss `Create` signature** — `_apply_glosses`: live `WfiGlosses.Create(analysis, form,
   wsHandle=None)` requires the form up front; the old `Create(analysis_obj)` raised `TypeError`
   on all 283 glosses (swallowed by `_safe`). Now creates with the first mappable (form, handle)
   then `SetForm`s the rest. Fake `FakeWfiGlossOps.Create` updated to the 3-arg signature.

Commit trail on the worktree: `df4b30e` (fix 1) → `24a6b0b` (2+3) → `c917d3a` (4+5) →
`4f99523` (6). STATUS.md on `main` @ `de71fe5`.

---

## ⛔ Remaining before merge (pickup checklist)

### 1. SC-005 idempotency (HIGH — the blocker)
A **second Move** against the already-populated target (no restore) grows
**WfiAnalyses 179 → 329** and **WfiGlosses 282 → 522** (texts correctly stay 9). Root cause:
`wordforms.apply_analyses` calls `wa_ops.Create(wordform)` **unconditionally** — no find-or-skip
for an analysis already present on the target wordform. Wordforms dedupe
(`_find_or_create_wordform` uses `Find`); analyses/glosses do not.
- **Fix:** dedupe at the analysis level — skip (or match) when the target wordform already
  carries an equivalent analysis (by source GUID / residue tag, or an analysis-level `Find`), so
  a re-Move is a no-op. Cascade the skip to its morph bundles + glosses.
- **Prove:** re-run the live proof twice; counts must be identical on run #2 (SC-005). Add an
  offline regression driving `apply_analyses` twice over the same fakes → no duplication.

### 2. Verdict confirmation (MEDIUM)
178/179 analyses are needs-review-no-verdict because the target lexicon does not hold the
senses/MSAs the morph bundles reference (1532 drops). This is **correct per FR-014**, but the
happy path (HUMAN_APPROVED written) is only exercised by 1 analysis here.
- **Prove:** re-proof against a **lexicon-complete** target (one that already holds Ejagham
  Mini's entries/senses, or select the full lexical closure so referents resolve) and confirm the
  HUMAN_APPROVED share rises and morph bundles wire.

### 3. Positional `AnalysesRS` fidelity (LOW)
`apply_alignment` wires the 206 analysis-kind slots but reports/skips punctuation (231) and bare
wordform (103) tokens (`wordform_map` is keyed by analysis GUID, so bare wordforms don't match).
The target `AnalysesRS` therefore isn't positionally complete vs. source (SC-006).
- **Fix (optional for merge):** key a wordform map by the source wordform GUID for bare-wordform
  tokens; decide punctuation-slot handling. Or scope out with a documented limitation.

### Then
4. Re-run offline gate + census (`pytest tests/unit tests/verification -q`).
5. Consider a lex-crew review (026 uniquely never had one).
6. Merge `026-texts-wordforms` → `main` (`--no-ff`); remove the worktree; update STATUS.md.

---

## How to run the live proof (non-obvious — read this first)

The prior drivers (`scratchpad/run0NN_live.py`) assume **flexicon is installed in the local
Python**. On this machine it is NOT (see Environment gotchas), so run the proof **through the
FLExToolsMCP `run_module`** host, which has its own working CLR/flexicon:

- Inject the worktree onto `sys.path` inside the module:
  ```python
  WT = r"C:\Github\GramTrans-026-texts-wordforms"
  for p in (WT+r"\src", WT+r"\tests\integration", WT+r"\debug"): sys.path.insert(0, p)
  from gramtrans.Lib import api
  from harness import restore
  ```
- Use the `run_module`-provided `project` (open as **Ejagham Mini**) as the **source**;
  `api.bind_target(...)` opens **Target** writable.
- `restore.restore_target("Target", backup_path=WT+r"\backups\Target 2026-07-06 0218.fwbackup")`
  resets Target programmatically (no FLEx GUI needed). Restore before every Move.
- Selection: `{GrammarCategory.TEXTS: True, GrammarCategory.STEMS: True}`; identity WS map
  (`etu`→`etu`). Then `api.compute_preview` → `api.execute_move`.
- **Do NOT call `th.SaveChanges()`** — `execute_move` owns the UnitOfWork/commit; a manual
  SaveChanges raises "Commit at wrong place" and nothing persists. Let `_close_project_watchdog`
  close/persist.
- `execute_move` emits ~250–500 KB of log; the tool result exceeds the token cap. Log your own
  `[MARKER]` lines and `grep` them out of the saved tool-result file afterward.
- Verify on a **fresh** open (`project_name="Target"`, read-only): count via
  `project.project.ServiceLocator.GetService(I…Repository).AllInstances()` — `ISegmentRepository`,
  `IWfiAnalysisRepository`, `IWfiGlossRepository`. `ApprovalStatusIcon` needs an `IWfiAnalysis`
  cast. **Always restore Target when done** (it is the shared disposable target).

The verification driver code is captured verbatim in the session transcript and can be lifted
into a `scratchpad/run026_live.py` if a reusable driver is wanted.

---

## Environment gotchas

- **flexicon is NOT pip-installed locally**, so the offline baseline is **7 failures**, not 1:
  6 × `test_013_apply_syncable_signature` (assert against the absent flexicon source tree at
  `D:/Github/_Projects/_LEX/flexicon/...`) + 1 documented `test_wizard_pos_grammar_wiring`.
  Measure regressions against this 7-fail baseline. 026's tests use fakes and don't depend on it.
- The MCP `run_module` CLR runtime **works** (it was down 2026-07-12 per probe-results.md, now
  restored — same runtime that ran 028's live proof).
- `Target` is the shared disposable target (also used by 025/031); restore from the backup above.

---

## Key files

- `src/gramtrans/Lib/wordforms.py` — all six fixes; the wordform/analysis/gloss/alignment walk.
- `src/gramtrans/Lib/texts.py` — `apply_texts` (segment loop calls `apply_analyses` +
  `apply_alignment`, texts.py:869).
- `tests/unit/test_human_eval_gate.py`, `test_segment_alignment.py`, `test_adjacent_data.py` —
  regression homes; `tests/unit/_fakes_texts.py` — fakes (note the 3-arg `FakeWfiGlossOps.Create`).
- `tests/verification/fidelity_census.py` — 024 total `79`, 026 section `25`.
