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

### Fix attempt #1 (gate) + re-proof — surfaced a SECOND, deeper layer

Applied the gate fix: `wordforms._human_evaluation` now falls back to
`_live_human_evaluation` reading `IWfiAnalysis.ApprovalStatusIcon` (1/2/0), with a
duck-typed `ApprovalStatusIcon` fallback for offline live-shaped fakes; added regression
tests (`test_gate_reads_live_approval_status_icon`,
`test_gate_live_path_survives_source_without_wfianalyses_attr`). Offline suite
**1698 passed** (7-fail env baseline unchanged). Re-ran the live Move — **still 0 analyses
planned/reproduced**.

Root cause of the residual gap (classified all 540 segment `AnalysesRS` tokens on Ejagham
Mini):

| token kind | count | note |
|---|---|---|
| **IWfiGloss** | **204** | human-glossed; owning `IWfiAnalysis` **approved** (icon 1 ×204) |
| IAnalysis (uncast) | 231 | punctuation forms (non-analyses) |
| IWfiWordform | 103 | bare unanalyzed baseline tokens |
| IWfiAnalysis (direct) | 2 | directly-referenced approved analyses |

**The human-approved content in a real FLEx interlinear is carried as `IWfiGloss` tokens
(204 here), not bare `IWfiAnalysis` (only 2).** 026's `_iter_segment_wordforms` /
`plan_analyses` treat each `Segment.AnalysesRS` token as an analysis and read approval via
an `IWfiAnalysis` cast — which **fails on a gloss token**, so 206 human-approved tokens are
excluded. The offline fakes modelled segment tokens as bare `IWfiAnalysis`, so this shape
was never exercised.

### Remaining work before 026 merge (larger than a hotfix)

The gate fix (kept) is necessary but insufficient. 026's live analysis walk needs to
**normalize segment tokens**: an `IWfiGloss` token → reproduce its owning `IWfiAnalysis`
(+ the chosen gloss); an `IWfiAnalysis` token → as-is; `IWfiWordform` → bare/unanalyzed
(no human analysis); punctuation → skip. Morph-bundle / category / gloss planning must then
operate on the resolved owning analysis. This needs: (1) token-normalization in the walk,
(2) offline fakes that model gloss tokens (not just bare analyses), (3) re-proof against
this corpus (expect ~204 gloss-backed + 2 direct analyses reproduced), (4) then R2/R5.
This is a design-level rework of the wordform walk, tracked here for a dedicated session.

### Fix attempts #2 + #3 (gloss-token gather + wordform grouping) — big progress, two layers remain

Two further fixes landed (both with offline regression tests; suite **1700 passed**, 7-fail
env baseline):

- **Fix #2 — gloss-token normalization** (`_normalize_token_to_analysis`, wired into
  `plan_analyses`): a `Segment.AnalysesRS` token that is an `IWfiGloss` now resolves to its
  owning `IWfiAnalysis` (deduped per wordform); bare-wordform / punctuation tokens skip.
  → the plan now gathers **179 analyses** (was 0; 204 gloss + 2 direct tokens dedupe to 179).
- **Fix #3 — owning-wordform grouping** (`_iter_segment_wordforms`): group each token by the
  owning wordform of its *analysis* (not of the raw gloss token), so the wordform form is
  captured and the target wordform can be found/created.
  → the Move now **creates all 179 analyses** on Target (was 2).

Re-proof after #2+#3 (Ejagham Mini → Target, fresh disk open):
- texts `0 → 9` (persisted), **target WfiAnalyses = 179** (created), `dropped_items = 1532`
  (never-silent now active over morph-bundle refs the target lexicon doesn't yet hold).

**Two layers still NOT working live (tracked for a dedicated session):**
1. **Segment `AnalysesRS` wiring (R5 alignment):** only **2/179** created analyses are wired
   back into the segments' `AnalysesRS` token sequence (`segs_with_analyses = 2`). The
   alignment/rebuild step (`apply_alignment` / `_analyses_rs`) is not re-linking the created
   analyses into the target segments on live data.
2. **Gloss reproduction (US4):** **0** `WfiGloss` created on Target — `_apply_glosses` /
   `WfiGlosses.Create` not producing glosses live.
3. **Verdict (likely correct-by-design, confirm):** 178/179 analyses are no-opinion, 1 approved.
   This is *probably* the intended needs-review path (FR-014): the STEMS closure did not
   reproduce every sense/MSA the morph bundles reference, so most analyses lost ≥1 referent and
   are written no-verdict (the 1532 drops corroborate). Confirm against a target that already
   holds the referenced lexicon, where more should land HUMAN_APPROVED.

**Net:** 026's analysis reproduction went from **0 analyses (silent loss)** to **179 created +
fully reported** across three fixes — the core gather + create path now works live. Remaining
before merge: fix the segment-`AnalysesRS` re-wiring and gloss reproduction, then re-proof
against a lexicon-complete target (R2/R5/US4 fully green), then merge.

Target was restored to the clean backup after every run (left pristine).
