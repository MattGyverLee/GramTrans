# Feature 026 — Texts & Wordforms — HANDOFF

**Last updated:** 2026-07-15 (session 2)
**Worktree:** `../GramTrans-026-texts-wordforms` on branch `026-texts-wordforms` @ **`f4cfbee`**
**Not merged to `main`.** Full evidence: [verification-log.md](./verification-log.md).

---

## TL;DR

026 was fully implemented (T001–T040) but had **never been run end-to-end on live data** — it
was unit-tested entirely against fakes. Session 1 brought the branch up to date with `main`
(027 + 028 had merged) and ran the attended live proof, applying **six fixes**; it left an
**SC-005 idempotency blocker** plus two smaller items.

**Session 2 (this session) FIXED and LIVE-PROVED SC-005.** A re-Move is now a byte-identical
no-op. The blocker turned out to be *two* cascading idempotency gaps — analysis-level (fixed
per the checklist) **and** paragraph/segment-level (`_apply_paragraphs` re-created structure on
an existing text). The within-run dedup also corrected a latent over-production bug (the old
per-segment `Create` duplicated shared analyses even in a single run: 179→**143** analyses,
282→**231** glosses, with R5 wiring **206** and verdicts unchanged).

**Remaining before merge:** items 2 (verdict happy-path breadth) and 3 (positional AnalysesRS)
— both non-blocking; see the re-scoped checklist below.

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

## ✅ / ⛔ Remaining before merge (pickup checklist)

### 1. SC-005 idempotency (HIGH — the blocker) — ✅ DONE & LIVE-PROVEN (session 2)
Root cause was **two** cascading gaps, not one:
- **Analysis level** — `wordforms.apply_analyses` called `wa_ops.Create(wordform)`
  unconditionally. **Fixed** (commit `8691d67`): dedupe by source GUID within a run + a
  structural fingerprint (effective verdict + morph-bundle forms + gloss forms) across runs;
  the target carries no source GUID (Create mints a fresh one, there is no analysis-level
  `Find`), so structure is the durable key. Verdict is in the fingerprint so an approved and a
  disapproved analysis of the same empty form are not collapsed (would silently lose the deny).
- **Text-structure level** — `texts._apply_paragraphs` re-created paragraphs/segments on an
  existing text (disposition UPDATE), and segment/analysis/gloss creation all cascade from that
  loop. **Fixed** (commit `f4cfbee`): skip when the target text already has paragraphs.
- **LIVE PROOF** (Ejagham Mini → Target, fresh-disk reopen): Move #1 = Move #2 =
  `{texts:9, segments:101, analyses:143, glosses:231}` — **identical** (was growing on the
  re-run before). AnalysesRS slots wired = **206** (R5 unchanged); verdicts 1 approved / 142
  no-verdict / 0 disapproved (FR-014 correct). Offline: **1706 passed**, 7-fail env baseline.
- **Counts moved 179→143 / 282→231 vs session 1** because within-run dedup collapses a shared
  analysis referenced from several segment occurrences — the old per-segment `Create`
  over-produced duplicates even in a single run. Positional wiring (206) and verdict semantics
  are unchanged, so this is a **correction, not a loss**.

### 2. Verdict confirmation (MEDIUM) — mechanism proven n=1; breadth optional
142/143 analyses are needs-review-no-verdict because the target lexicon does not hold the
senses/MSAs the morph bundles reference. This is **correct per FR-014**. The HUMAN_APPROVED
happy path (ApproveAnalysis owned by the provisioned agent) IS exercised live — the 1 approved
analysis persisted with `ApprovalStatusIcon == 1` on the fresh reopen — but only with n=1, and
the **resolved-ref morph-bundle wiring** (`SetSense`/`SetMSA` on a referent that resolves) is
therefore barely exercised live.
- **Optional breadth:** re-proof against a **lexicon-complete** target (one already holding
  Ejagham Mini's entries/senses) and confirm the HUMAN_APPROVED share rises and morph bundles
  wire. Not a correctness blocker — the write mechanism is proven; this widens coverage of the
  resolved-ref path.

### 3. Positional `AnalysesRS` fidelity (LOW) — documented limitation
`apply_alignment` wires the 206 analysis-kind slots (confirmed live) but reports/skips
punctuation and bare-wordform tokens (`wordform_map` is keyed by analysis GUID, so bare
wordforms don't match). The target `AnalysesRS` is therefore analysis-complete but not
punctuation/bare-wordform-complete vs. source (SC-006).
- **Scoped out for merge** as a documented limitation. To close later: key a wordform map by the
  source wordform GUID for bare-wordform tokens; decide punctuation-slot handling.

### Then
4. Re-run offline gate + census (`pytest tests/unit tests/verification -q`). ✅ 1706 pass / 7-fail baseline.
5. Consider a lex-crew review (026 uniquely never had one).
6. Merge `026-texts-wordforms` → `main` (`--no-ff`); remove the worktree; update STATUS.md.

**Session-2 commits on the worktree:** `8691d67` (analysis dedup) → `f4cfbee` (text-structure
idempotency + this HANDOFF update).

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
