# Contract: Segment Alignment (`Lib/wordforms.py`) — US2 FR-012, SC-006

Reproduce each segment's `AnalysesRS` — the ordered per-token alignment — on the target so the
copied interlinear renders with each analysis attached to the correct baseline token. Preserves
punctuation and bare-wordform tokens for positional fidelity (edge case). This is the one place 026
legitimately drops to the raw LCM interface (R5, Principle II fallback clause).

## `plan_alignment(segment, ctx, dropped) -> list[AlignmentToken]`

Pure/decision pass, produced alongside the segment's `AnalysisPlan`s.

**Behavior**
- Read the source token sequence via `SegmentOperations.GetAnalyses(segment)`.
- For each token, classify (`AlignmentTokenKind`) and record its intended target referent:
  - `ANALYSIS` → the target analysis chosen for that human-evaluated source analysis (from the
    source→target analysis map built by `apply_analyses`, R7).
  - `WORDFORM` → the target wordform (bare, no copied analysis) — occupies its slot.
  - `PUNCTUATION` → the punctuation token — occupies its slot.
- The token order and count mirror the source so the baseline stays aligned even where a token has
  no copied analysis.

## `apply_alignment(target_segment, tokens, ctx, dropped) -> None`

Move-mode only.
- Rebuild the target `AnalysesRS` in source order, appending each token's resolved target
  `IAnalysis`/`IWfiWordform`/punctuation object.
- Where the flexicon wrapper exposes no `AnalysesRS` setter, reach the raw sequence via
  `project.GetService(...)` + `CastingOperations.cast_to_concrete` and append (R5). `ReparseParagraph`
  MAY be used only to establish baseline tokens before attaching copied analyses — never as the
  mechanism that chooses analyses (it would re-derive parser output, not the human choice).

**Postconditions**
- For a copied text opened in FLEx, every copied analysis appears attached to the correct baseline
  token of the correct segment (SC-006).
- Punctuation and un-analyzed tokens keep their positions; no token silently disappears.

## Non-goals
- Does not re-parse to *invent* analyses (only reproduces the human-chosen alignment).
- Does not handle media/time-offset alignment (out of scope).

## [PROBE]
Verify the exact `AnalysesRS` write path (wrapper vs. raw `GetService`) on a live target once the
MCP `run_module` / CLR-init path is restored; the static surface confirms `GetAnalyses` (read) and
the factory fallback, not the precise mutator.
