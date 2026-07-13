"""Text container + structure walk (Feature 026, US1 + genre + tags).

Reproduces the interlinear text container and structure: title / abbreviation /
source / translation-complete flag, paragraph/segment structure, baseline
vernacular content, free/literal translations, segment notes, genre
assignments (FR-002..005), and per-segment text-markup tags (US5, FR-017).

Plan-aware (Principle III): `plan_texts` is a pure decision pass that writes
nothing; `apply_texts` executes the plan in Move mode. Reuses feature 024's
`references.decide_reference`/`apply_reference` resolver (genres + tags),
`owned.py` owned-child walk (paragraphs → segments), `ws_mapping` gate for every
string-bearing field (FR-020), and the `DroppedItemRecord` never-silent channel
(FR-023). Delegates each segment's human-evaluated analyses and `AnalysesRS`
alignment to `Lib/wordforms.py` (see contracts/analysis-human-eval-walk.md and
contracts/segment-alignment.md).

flexicon Operations are imported lazily INSIDE the functions so this module
stays import-safe without a live LCM host (unit tests exercise the pure plan
shape with fakes; the offline suite runs without flexicon on the path).

Status: Phase 1/2 SCAFFOLD. `plan_texts` returns an empty plan list and
`apply_texts` is a no-op so the preview/transfer TEXTS dispatch hook is inert
until the US1 implementation (Phase 3, tasks T012–T014) lands. Signatures are
the contract's; do not change them without updating
contracts/text-structure-walk.md.
"""
from __future__ import annotations

from typing import List


def plan_texts(selection, source, target, ctx, resolver_cache, dropped) -> List:
    """US1 pure/decision pass — build one TextTransferPlan per selected text.

    Invoked from `Lib/preview.py.build_run_plan` when `GrammarCategory.TEXTS`
    is on. Enumerates the source's interlinear texts (`TextOperations.GetAll()`)
    filtered by `selection.text_picks` (the Model-A picker, FR-001), determines
    each text's disposition by identity (GUID → `Find(title)` → ADD/UPDATE/SKIP,
    FR-021), resolves `GenresRC` via the 024 resolver (create-allowed, FR-005),
    walks `ContentsOA.ParagraphsOS → SegmentOperations.GetAll` building
    ParagraphPlan/SegmentPlan with WS-gated baseline/translations/notes
    (FR-020), resolves per-segment text-markup tags (US5, FR-017), and delegates
    the human-evaluated analyses + alignment to `Lib/wordforms.py`.

    MUST NOT mutate the target. A text with zero human-evaluated analyses still
    yields a full plan (structure + translations + notes) — the analysis layer
    is simply empty (edge case).

    Returns a list of `models.TextTransferPlan`.

    SCAFFOLD (Phase 3, T012): returns [] until the US1 walk is implemented.
    """
    return []


def apply_texts(plans, source, target, ctx, tag, report_sink,
                resolver_cache, dropped) -> None:
    """US1 Move-mode apply — execute the TextTransferPlans.

    Creates each text (`TextOperations.Create`, preserving source GUID where
    permitted else recording the identity mapping, FR-022), sets
    abbreviation/source/`SetIsTranslated` (FR-002), creates paragraphs
    (`ParagraphOperations.Create`) and segments, writes baseline /
    free+literal translations / notes non-destructively (FR-021), applies genre
    and tag `ReferenceDecision`s (`references.apply_reference`), wires the
    human-evaluated analyses + alignment via `Lib/wordforms.py`, and residue-
    tags the created text/paragraph (Carrier B, R8).

    SCAFFOLD (Phase 3, T013): no-op until the US1 apply is implemented. The
    empty `plans` produced by the scaffold `plan_texts` make this inert.
    """
    return None
