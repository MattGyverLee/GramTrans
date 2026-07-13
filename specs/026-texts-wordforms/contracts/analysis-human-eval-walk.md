# Contract: Analysis Human-Evaluation Walk (`Lib/wordforms.py`) — US2/US3/US4

The feature's differentiating value: reproduce the wordform analyses a **human** approved or denied,
under the never-silent, non-destructive contract. Gates out machine/parser and un-evaluated items.
Closure-scoped to the selected texts (FR-001a). Reuses the 024 owned-walk pattern, WS gate, and
dropped-item channel; delegates morph-bundle wiring (`morph-bundle-identity-wiring.md`), alignment
(`segment-alignment.md`), and agent provisioning (`human-agent-provisioning.md`).

## `plan_analyses(segment, src_project, target, ctx, resolver_cache, dropped) -> list[AnalysisPlan]`

Pure/decision pass, invoked from the plan-builder per segment.

**Behavior**
- For each token/wordform in the segment, enumerate `WfiAnalysisOperations.GetAll(wordform)` and
  **keep only** analyses where `GetHumanEvaluation(a)` is non-null (R1, FR-006). Parser-only
  (`GetAgentEvaluation`/`IsComputerApproved` but no human eval) and un-evaluated analyses are
  excluded — no plan, no write, but the exclusion is countable in the report (SC-001).
- Set `verdict` from the human evaluation's `Approves` flag: `HUMAN_APPROVED` | `HUMAN_DENIED`
  (FR-007).
- Resolve `CategoryRA` via the **resolve-or-report** variant (see `resolve_or_report_category`
  below), FR-011.
- Build `MorphBundlePlan`s (delegated) and compute `needs_review`: True iff `verdict ==
  HUMAN_APPROVED` **and** ≥1 morph-bundle `IdentityRef` is unresolved (FR-014). A `HUMAN_DENIED`
  analysis is never downgraded (FR-015).
- Keep only human-evaluated `WfiGloss` (`GetGlosses` filtered by human eval, FR-008) as `GlossPlan`.
- Capture the wordform form (WS-gated) and `spelling_status` for find-or-create + FR-013.

## `resolve_or_report_category(analysis, target, resolver_cache, dropped) -> ReferenceDecision`

- Call `references.decide_reference` for `CategoryRA` against `LangProject.PartsOfSpeechOA`, then
  **downgrade any `CREATE` to `REPORT_DROPPED`**: if the matching POS is absent, leave the field
  unset and emit a `DroppedItemRecord` (owner_kind `WfiAnalysis`, field `CategoryRA`, reason
  `category not in target part-of-speech list`). A POS is **never** fabricated for an analysis
  (FR-011); it arrives, if at all, through the lexicon transfer.

## `apply_analyses(plans, target, ctx, resolver_cache, dropped) -> None`

Move-mode only.
- Find-or-create the target wordform by form+WS (global identity, R7); set `spelling_status`
  (`WordformOperations.ApproveSpelling` / status setter, FR-013), non-destructively.
- `WfiAnalysisOperations.Create(wordform)`, preserving source GUID where permitted (FR-022).
- Apply the category `ReferenceDecision` (`SetCategory` when resolved; unset + already-reported
  when dropped).
- Wire morph bundles + copy human-evaluated glosses (delegated).
- **Verdict write** (the crux):
  - `HUMAN_APPROVED` and not `needs_review` → attach a human-approve evaluation owned by the
    run's provisioned agent (`ApproveAnalysis` / evaluation write, R3).
  - `HUMAN_DENIED` → attach a human-deny evaluation (`RejectAnalysis` / evaluation write),
    including the deny-with-unresolvable-morphemes case (FR-015).
  - `NEEDS_REVIEW` → **write no human evaluation** (R2/FR-014): create the analysis and leave it in
    the platform's natural no-verdict state; the report entries convey needs-review. No in-FLEx
    marker, no proxy-deny.
- `apply_residue` the wordform/analysis via the Description-append carrier (R8).

**Postconditions**
- Exactly the human-approved and human-denied analyses appear on the target's matching wordforms;
  zero parser-only/un-evaluated analyses created (SC-001).
- Every verdict preserved except reported needs-review downgrades (SC-002).
- Every excluded/dropped item is countable in the unified report (FR-023, SC-003).

## Non-goals
- Does not create parts of speech (resolve-or-report only).
- Does not copy machine/parser analyses or glosses.
