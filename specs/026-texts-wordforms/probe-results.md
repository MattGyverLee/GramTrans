# Probe Results: Texts & Wordforms (026)

Tracks the deferred live `[PROBE]` confirmations (research R2 / R5 / R6) and the
quickstart live validation (T038). All are gated on the MCP `run_module` /
CLR-init runtime; the offline unit gate (T037) is the primary acceptance gate
and is fully green (see below).

## Runtime status (probed 2026-07-12, Phases 7–8 session)

`run_module` **still fails at CLR init** — `RuntimeError: Failed to initialize
Python.Runtime.dll` (pythonnet load, `flexicon/code/FLExInit.py: import clr`).
So every live-FLEx confirmation below remains **DEFERRED**; none blocks the
offline gate.

The **static** flexicon surface (`get_object_api` / `search_by_capability` /
`resolve_property`) IS available and was used to close the *interface-level*
half of R6 (accessors below). The *behavioural* half (does it render / write
correctly on a live target) still needs the runtime.

## Offline gate (T037) — GREEN

All 7 unit files + the extended fidelity census pass offline:

```
tests/unit/test_text_structure_walk.py  test_human_eval_gate.py
test_analysis_verdict.py  test_morph_bundle_wiring.py  test_segment_alignment.py
test_adjacent_data.py  test_text_markup_tags.py
tests/unit/test_residue_tagging_026.py            (T040)
tests/verification/fidelity_census.py             (T036 — 26 new 026 assertions)
→ 153 passed
```

(The 7 repo-wide failures in `test_013_apply_syncable_signature.py` and
`test_wizard_pos_grammar_wiring.py` are **pre-existing** on clean HEAD, require a
live flexicon install, and are outside the 026 gate — confirmed by `git stash`.)

## R6 — target-list / tag accessors (interface half RESOLVED, static surface)

| Item | Finding (static, MCP 2026-07-12) | Status |
|---|---|---|
| Genre list owner | `LangProject.GenreListOA` (`TextOperations.Get/SetGenre` confirmed) | ✅ confirmed static; live create/link **deferred** |
| Text-markup tag list owner | `LangProject.TextMarkupTagsOA` (`ILcmOwningAtomic → ICmPossibilityList`; casts on `ILangProject`) | ✅ confirmed static |
| Per-segment tag surface | No flexicon wrapper. Raw LCM: `IStText.TagsOC` owns `ITextTag`; `ITextTag.{TagRA, BeginSegmentRA, EndSegmentRA, BeginAnalysisIndex, EndAnalysisIndex}` | ✅ confirmed static; live write path **deferred** |

`Lib/texts.py` now resolves `TagRA` against `LangProject.TextMarkupTagsOA`
through the shared 024 resolver (create-allowed) and creates the per-segment
`ITextTag` via `ITextTagFactory` (raw, `_safe`-wrapped) — see `_tag_spec`,
`_decide_segment_tags`, `_apply_segment_tags`, `_raw_create_text_tag`. The exact
live `ITextTag` write path and multi-segment span / analysis-index fidelity
remain the deferred behavioural probe.

## R2 — needs-review renders as unanalyzed-but-present — DEFERRED

Confirm on a live target (SC-006 context) that an analysis created with **no**
human evaluation renders attached to its baseline token with no green
human-approved check when the text is opened in FLEx. Interface basis:
`IWfiAnalysis` exposes a genuine three-state approval (`ApprovalStatusIcon` /
`GetAgentOpinion`/`SetAgentOpinion(Opinions)`, `EvaluationsRC`), so the platform
has a native no-opinion state to leave the analysis in (`wordforms._write_verdict`
writes nothing for `NEEDS_REVIEW`). Live appearance unverified.

## R5 — exact `AnalysesRS` write path — DEFERRED

`ISegment.AnalysesRS` (reference sequence) is confirmed on the static surface;
`SegmentOperations` exposes `GetAnalyses` (read) but no `SetAnalyses` wrapper, so
`wordforms.apply_alignment` rebuilds the sequence via the raw surface
(`_analyses_rs` → `ISegment(seg).AnalysesRS.Add(...)`), non-destructive
(skips when already populated). The exact live mutator + token round-trip
(punctuation / bare-wordform slot fidelity) remain unverified.

Also newly surfaced this session and folded into the same deferral:
**`Segment.NotesOS` write path** — `SegmentOperations` has `GetNotes` but no note
setter/factory wrapper, and the raw `INoteFactory` path is unconfirmed. Until the
runtime is restored, `texts._apply_segment_notes` **reports** each captured note
as a `DroppedItemRecord` (never-silent, SC-003) rather than silently discarding
it; reproduction via the raw note factory is deferred here alongside R5. Census
bucket: `Segment.NotesOS = DROP_REPORTED`.

## T038 — quickstart live validation (US1–US5 + re-run) — DEFERRED

Cannot run Preview→Move against the `Ejagham Mini → Ejagham Full GT-Test` pair
while `run_module` is down. When restored, execute `quickstart.md` scenarios
US1–US5 + the non-destructive re-run check and confirm SC-001..SC-007 (re-run
shows SKIP/UPDATE not ADD, SC-005), then record the run here.

## Pickup checklist (when the CLR path is restored)

1. Re-run the offline gate to confirm no drift.
2. R6: live-create a genre + a text-markup tag absent from the target; confirm
   GUID preservation and per-segment `ITextTag` reproduction; confirm the
   multi-segment span + analysis indices.
3. R2: open a needs-review analysis in FLEx; confirm unanalyzed-but-present.
4. R5: confirm the `AnalysesRS` write path + token order; wire the raw
   `INoteFactory` note-reproduction path and flip `Segment.NotesOS` from
   DROP_REPORTED to COPIED in the census.
5. T038: run the quickstart scenarios; record SC-001..SC-007 here.
