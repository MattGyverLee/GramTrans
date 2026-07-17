# QC Report — Feature 030 (cycle 1)

**Date:** 2026-07-16
**Reviewed:** worktree `GramTrans-030-sense-appendix-thesaurus-refs` @ d6132ff, diff `main..HEAD` for `references.py` and `categories.py`
**Quality Score:** 84/100
**Status:** ISSUES (fix-before-merge for the P1; P2s advisory) — not reject

## Pattern-Audit Gate
Feature (not a bug-labelled fix) → pattern-audit N/A. Note: the feature touches a recurring pattern class (unguarded `.Owner`/typed-attribute walks, `ICmObject` casts) — see P1.

## Code Quality: 20/25
Readability strong (purpose-driven docstrings). Maintainability good — reuses 024's decide/apply via synthetic ReferenceFieldSpec. Consistent with file conventions (fail-soft "Never raises", `_append_dropped_once` dedup).
- **P2** `references.py` `build_thesaurus_spec` hardcodes `hierarchical=True` regardless of the mirrored list's shape. Harmless today (`.hierarchical` is documentation/census-only, not read by `decide_reference`'s CREATE-ancestor logic) but a misleading synthetic value forwarded through the same machinery as accurate REFERENCE_FIELD_MAP rows.

## Standards Compliance: 21/25
Consistent naming/organization; clear `# Feature 030` banners.
- **P1 (test-coverage gap)** The PRIMARY dynamic-owner matcher `_target_list_by_owner_flid` (owner-class + OwningFlid) — the mechanism the design docs treat as authoritative *because* list GUIDs aren't stable — is NEVER exercised by any unit test. Every `_FakePossList` sets `owner=object()`, which fails `ICmObject(src_owner).ClassName` and falls through to the Name-match fallback. So the fallback is well-tested; the primary path is only proven live. Add an offline unit test with a fake owner duck-typing the ICmObject/ILangProject/ILexDb shape so a future refactor can't silently regress to always-Name-match.

## Error Handling: 22/25
**Never-silent invariant verified intact.** Every drop path in both sections terminates in a `DroppedItemRecord` via `_append_dropped_once`; `dropped` is guaranteed non-None before either sense loop. Move/Preview parity by construction + unit-tested. All broad `except Exception` clauses in the new helpers funnel to a reported drop — no swallow-and-forget, no silent loss.
- **P2 (diagnosability)** `_target_list_by_owner_flid` / `_iter_target_appendixes` collapse "genuinely absent" and "real bug/COM failure during lookup" to the same None/empty result. Not silent (a drop is still reported), but the reason text ("no LexAppendix with this GUID…") could mislead triage when the true cause was an exception. Consider narrowing to expected exception types so an unexpected one propagates to the outer logged handler. Low priority — matches the module's existing fail-soft posture.
- **P2** Confirmed the 030 thesaurus call site routes through the shared `_call_apply_reference` (which correctly separates RuntimeError orphan-risk from benign duck-typing gaps) rather than reimplementing try/except — no duplication.

## Best Practices: 21/25
Excellent reuse (synthetic per-item ReferenceFieldSpec closed over the resolved list). No bare except, no swallowed RuntimeError, no duplicated dispatch tables. Linear AppendixesOC scan acceptable at documented scale.
- **P2** `_iter_target_possibility_lists` rebuilds an 11-lambda accessor tuple independently of `REFERENCE_FIELD_MAP` — a future list added to the dispatch table won't appear in the thesaurus Name-fallback search space unless someone remembers to add it here too. Manually-synced duplicate; derive from REFERENCE_FIELD_MAP in a follow-up.

## Final Assessment
**84/100 — FIX ISSUES (P1 test gap) before merge; P2s advisory/follow-up.**
No silent-loss bugs found; NEVER-SILENT invariant holds throughout. Move/Preview parity structurally guaranteed and unit-tested.

**2-line summary:** Score 84/100 — 1 P1 (primary owner-class+flid mirror path never unit-tested, only Name fallback), 4 P2 (misleading reason text on broad-except, hardcoded hierarchical=True, manually-duplicated accessor tuple). No silent-loss bugs; never-silent holds.
