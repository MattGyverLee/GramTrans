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

### Fix attempts #4 (R5 AnalysesRS wiring) + #5 (gloss gate) — R5 done; gloss apply is a 3rd layer

Two more fixes landed (offline suite **1702 passed**, 7-fail env baseline):

- **Fix #4 — segment `AnalysesRS` wiring (R5):** `plan_alignment` now keys an ANALYSIS-kind
  token (gloss or analysis) by its **owning-analysis GUID** (`_normalize_token_to_analysis`),
  matching the `_wf_analysis_map` key `apply_analyses` records. Before, gloss tokens carried
  the gloss GUID and never matched → only the 2 direct-analysis tokens wired.
  → re-proof: `segs_with_analyses` **2 → 77**, `AnalysesRS refs wired` **2 → 206** (all 204
  gloss + 2 direct tokens). **R5 wiring works.**
- **Fix #5 — gloss human-eval gate:** `_gloss_human_evaluation` gains a live fallback
  (`_live_gloss_human_evaluation`) — a live `IWfiGloss` has no `GetHumanEvaluation`, so it is
  human content iff its owning `IWfiAnalysis` is human-evaluated (reuses `_live_human_evaluation`).
  → the **plan now gathers 283 gloss plans** across 177/179 analyses (was 0).

**Residual — gloss APPLY (3rd layer, NOT fixed):** despite 283 gloss plans in the plan, the
Move persists **0 `WfiGloss`** on Target and emits **0 "gloss create failed" drops**. That
paradox (non-empty `plan.glosses`, no creates, no drops) means the Move's text-apply path is
**not materializing `plan.glosses`** — a plan-consumption gap in `apply_texts`/`apply_analyses`
(the gathered gloss plans aren't reaching `_apply_glosses`, or `_apply_glosses`'s creates aren't
persisting). `target.WfiGlosses.Create` exists and is callable. Needs a live write-trace of the
text-apply gloss path to pin (a bounded next step).

### Scorecard after 5 live-proof fixes (worktree)

| Aspect | Before | After |
|---|---|---|
| Text structure (US1) | 9 texts | 9 texts (persisted) ✓ |
| Analyses created | 0 (silent) | **179** ✓ |
| `AnalysesRS` wired (R5) | 2 | **206** ✓ |
| Glosses planned (US4 gather) | 0 | **283** ✓ |
| Glosses persisted (US4 apply) | 0 | **0** ✗ (3rd layer) |
| Verdicts | — | 1 approved / 178 no-opinion — *likely correct needs-review* (target lexicon incomplete → morph refs unresolved, 1532 drops); confirm on a lexicon-complete target |

**Net across the whole session:** 026's texts/wordforms transfer went from silently losing all
219 human-approved analyses to reproducing 179 analyses + wiring 206 segment slots + planning
283 glosses, all with regression tests. Remaining before merge: the gloss-apply consumption gap,
the verdict confirmation on a lexicon-complete target, and (minor) positional fidelity for
punctuation / bare-wordform `AnalysesRS` slots.

### Fix #6 (gloss Create signature) — US4 glosses now reproduce; + SC-005 idempotency finding

A monkeypatch trace of `_apply_glosses` during a live Move pinned the gloss-apply gap:
```
[TRACE] calls=179 with_glosses=177 gl_ops_none=0 exc=283
        exc_msg="TypeError: WfiGlossOperations.Create() missing 1 required positional argument: 'form'"
```
The live `WfiGlosses.Create(analysis, form, wsHandle=None)` requires the gloss form up front;
`_apply_glosses` called `Create(analysis_obj)` alone, so all 283 creates raised `TypeError`
(swallowed by `_safe`). **Fix #6:** create with the first mappable `(form, ws-handle)`, then
`SetForm` the remaining writing systems; the offline `FakeWfiGlossOps.Create` was updated to the
real 3-arg signature. Regression covered by `test_adjacent_data.py` (gloss reproduction).

Re-proof (Ejagham Mini → Target): **WfiGlosses 0 → 282** persisted. Both originally-requested
fixes are now proven end-to-end.

**Live proof — final state (single Move, fresh disk open):**

| Aspect | Result |
|---|---|
| Texts (US1) | 9 (persisted) ✓ |
| Segments | 101 ✓ |
| Analyses created (US2) | 179 ✓ |
| `AnalysesRS` wired (R5) | 206 refs / 77 segments ✓ |
| Glosses (US4) | 282 ✓ |
| Verdicts (R2/FR-014) | 1 approved / 178 needs-review-no-verdict — correct given the target lexicon does not hold the referenced senses/MSAs (1532 morph-bundle drops); confirm HUMAN_APPROVED share rises on a lexicon-complete target |

**NEW finding — SC-005 idempotency FAIL (not yet fixed):** a second Move against the
already-populated target (no restore) grew WfiAnalyses **179 → 329** and WfiGlosses
**282 → 522** (texts stayed 9). `apply_analyses` calls `wa_ops.Create(wordform)`
unconditionally with no find-or-skip for an analysis already present on the target wordform, so
re-runs duplicate analyses (and their glosses/bundles). Wordforms ARE deduped
(`_find_or_create_wordform` uses `Find` first); analyses are not. **Fix needed before merge:**
dedupe analyses by identity (e.g. skip when the target wordform already carries an equivalent
analysis, or key an analysis-level find) so a re-Move is a no-op (SC-005). Distinct from the two
gather/wiring fixes above.

### Remaining before 026 merge
1. **SC-005 idempotency:** analysis/gloss dedup on re-Move (above).
2. **Verdict confirmation:** re-proof against a lexicon-complete target (expect more HUMAN_APPROVED).
3. **Minor:** positional fidelity for punctuation / bare-wordform `AnalysesRS` slots.

Target was restored to the clean backup after every run (left pristine).
