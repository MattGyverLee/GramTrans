# 026 Live Validation Log

## Attended live proof — 2026-07-15 (Ejagham Mini → Target, via FLExToolsMCP `run_module`)

The CLR `run_module` runtime (down 2026-07-12, see `probe-results.md`) is **restored**.
Ran the deferred T038 / R2 / R5 live validation by driving the real engine
(`gramtrans.Lib.api` compute_preview + execute_move, worktree code on branch
`026-texts-wordforms` @ `831eb68`) against a `harness.restore`-restored disposable `Target`.

### Result: US1 PASS · US2/US3 **FAIL — real defect surfaced** (026 NOT mergeable as-is)

**US1 (text structure) — PASS, persisted.**
- Preview: `PREVIEW_READY`, 9 `text_plans` (all 9 source texts), 164 actions, 0 skips.
- Move (TEXTS + STEMS): target texts **0 → 9**; on a FRESH re-open from disk: **9 texts,
  101 segments** persisted. (First Move attempt mis-committed due to a driver bug — an
  explicit `SaveChanges()` after `execute_move` → `Commit at wrong place`; removed it and
  let `execute_move`'s own UnitOfWork commit, then persistence was clean. Driver lesson,
  not a 026 bug.)
- Dropped items were only `MoForm` (187) + `CmTranslation` (72) — the known 024/025-era
  lexical backlog from STEMS, not text/wordform losses.

**US2/US3 (human-evaluated analyses ride along) — FAIL. Silent analysis loss (SC-003).**
- Source Ejagham Mini is analysis-rich: **279 WfiAnalyses, 219 human-approved, 540
  `AnalysesRS` refs across 101 segments.**
- After Move: **0 analyses** in Target (`segs_with_analyses=0`, `WfiAnalyses=0`), and **0
  DroppedItemRecords** for them. 219 human-approved analyses vanished with no report.

### Root cause (pinpointed live) — `wordforms._human_evaluation` live-vs-fake API divergence

Gather-side gap, not apply-side. The Preview `text_plan` segment objects carry an
`analyses` field but it is **empty for every segment** (`TOTAL analyses planned = 0`).
Direct probing of the gather path:

- `wordforms._iter_segment_wordforms(source, segment)` **works live** — yielded 8/8
  (wordform, analyses) pairs for a sampled 8-ref segment.
- **`source.Wordforms` has NO `GetHumanEvaluation` method live** (`hasattr → False`).
  So `wordforms._human_evaluation` (wordforms.py:246–264) falls through its preferred
  `WfiAnalyses.GetHumanEvaluation` path and the `getattr(analysis, "GetHumanEvaluation"/
  "human_evaluation", None)` fallbacks — all absent on a live `IWfiAnalysis` — and returns
  `None` for **every** analysis. `plan_analyses` (wordforms.py:337–343) then skips each as
  "parser-only" via a `_log.debug` **with no `DroppedItemRecord`** → silent loss.

The offline unit tests passed because the fakes expose `GetHumanEvaluation` /
`human_evaluation`; the live `IWfiAnalysis` approval must instead be read via
`ApprovalStatusIcon` (==1 approved / ==2 disapproved) or `GetAgentOpinion` over
`EvaluationsRC`. This is the **same class of defect** the 031 live run caught
(`get_object_by_guid` present on fakes, absent live).

### Fix required before 026 merge (proposed)

1. Rework `wordforms._human_evaluation` to read live approval via the real LCM surface
   (`IWfiAnalysis.ApprovalStatusIcon` / `GetAgentOpinion(EvaluationsRC)`), keeping the
   duck-typed fake path for offline tests. Confirmed live: 219 approved / 60 no-opinion.
2. Make the "excluded, no human evaluation" skip **never-silent** where the source analysis
   is genuinely human-evaluated but the gate returned None (guard against silently dropping
   real data). Parser-only exclusion (FR-008) stays intentional but should be distinguishable
   from a gate failure.
3. Add a live-shaped regression (an `IWfiAnalysis`-like fake WITHOUT `GetHumanEvaluation`,
   exposing only `ApprovalStatusIcon`/`EvaluationsRC`) so the offline suite catches this.
4. Re-run this live proof (R2/R5 then exercisable): confirm 219 analyses reproduced,
   `AnalysesRS` order preserved, needs-review left no-opinion (R2), notes handling (R5).

Target was restored to the clean backup after the run (left pristine).
