"""Human-evaluation gate + analysis reproduction (Feature 026, US2/US3/US4).

The feature's differentiating value: reproduce the wordform analyses a **human**
approved or denied, under the never-silent, non-destructive, Preview-before-
mutate contract. Machine/parser-only and un-evaluated analyses are gated out as
ephemeral (FR-006). Closure-scoped to the selected texts (FR-001a).

Covers (per specs/026-texts-wordforms/contracts/):
- analysis-human-eval-walk.md   — human-eval gate, verdict, category resolve-or-report
- morph-bundle-identity-wiring.md — GUID identity wiring + needs-review downgrade
- segment-alignment.md          — Segment.AnalysesRS reproduction (raw-LCM fallback)
- human-agent-provisioning.md   — one provisioned/reused human agent per run

Reuses feature 024's owned-walk pattern (analyses → morph bundles / glosses),
the `ws_mapping` gate, and the `DroppedItemRecord` channel. Wires morph-bundle
references by source-GUID identity lookup against the per-run target GUID index
(R4) — NOT the 024 possibility resolver (a missing sense is reported +
needs-review, never fabricated).

flexicon Operations (`WfiAnalysisOperations`, `WfiMorphBundleOperations`,
`WordformOperations`, `WfiGlossOperations`, `AgentOperations`,
`SegmentOperations`, `CastingOperations`) are imported lazily INSIDE the
functions so this module stays import-safe without a live LCM host.

Status: Phase 1/2 SCAFFOLD. Signatures are the contracts'; bodies raise
`NotImplementedError` and are filled by the US2–US5 tasks (Phase 4–7,
T019–T035). Nothing in Phase 1/2 calls these — the texts walk (Lib/texts.py)
delegates here starting at T025 — so the scaffold cannot execute yet.
"""
from __future__ import annotations

from typing import List

_PHASE = "Feature 026 US2+ (Phase 4+); see specs/026-texts-wordforms/tasks.md"


# ---------------------------------------------------------------------------
# Human-agent provisioning (US2, FR-009 — contracts/human-agent-provisioning.md)
# ---------------------------------------------------------------------------

def plan_agent(target, ctx):
    """Resolve the owning human agent once per run → `models.ProvisionedAgent`.

    Prefer an existing target human agent (`AgentOperations.GetHumanAgents()` /
    `FindByType(is_human=True)`) → `created=False` (Link in Preview); else plan a
    create → `created=True` (Add). SCAFFOLD (T020)."""
    raise NotImplementedError(_PHASE)


def apply_agent(decision, target, ctx):
    """Move-mode — realize the ProvisionedAgent and cache it on `ctx`.

    When `created`, `AgentOperations.Create(name)` + `SetHuman(agent, person)`;
    then cache so every copied evaluation this run reuses the single agent (no
    per-evaluation duplication, FR-009). Returns the LCM `ICmAgent`.
    SCAFFOLD (T020)."""
    raise NotImplementedError(_PHASE)


# ---------------------------------------------------------------------------
# Analysis human-evaluation walk (US2/US3/US4 — analysis-human-eval-walk.md)
# ---------------------------------------------------------------------------

def plan_analyses(segment, source, target, ctx, resolver_cache, dropped) -> List:
    """Per-segment pure/decision pass → list of `models.AnalysisPlan`.

    Keep only analyses with a non-null `GetHumanEvaluation` (R1, FR-006); set
    verdict from `Approves` (FR-007); resolve `CategoryRA` via
    `resolve_or_report_category` (FR-011); build morph bundles (delegated) and
    compute `needs_review` (FR-014); keep only human-evaluated `WfiGloss`
    (FR-008); capture WS-gated wordform form + spelling status (FR-013).
    SCAFFOLD (T021/T026/T030)."""
    raise NotImplementedError(_PHASE)


def resolve_or_report_category(analysis, target, resolver_cache, dropped):
    """CategoryRA resolve-or-report variant → `models.ReferenceDecision` (FR-011).

    Call `references.decide_reference` against `LangProject.PartsOfSpeechOA`,
    then downgrade any CREATE to REPORT_DROPPED: an absent POS is left unset and
    a DroppedItemRecord is emitted. A POS is NEVER fabricated for an analysis.
    SCAFFOLD (T021)."""
    raise NotImplementedError(_PHASE)


def apply_analyses(plans, source, target, ctx, tag, resolver_cache, dropped) -> None:
    """Move-mode — realize the AnalysisPlans on the target's wordforms.

    Find-or-create the target wordform by form+WS (R7); set spelling status
    (FR-013); `WfiAnalysisOperations.Create` (GUID-preserving where permitted,
    FR-022); apply the category decision; wire morph bundles + copy human
    glosses (delegated); write the verdict — approve/deny via the provisioned
    agent, or NO human evaluation for NEEDS_REVIEW (R2/FR-014). SCAFFOLD
    (T022/T027/T030–T032)."""
    raise NotImplementedError(_PHASE)


# ---------------------------------------------------------------------------
# Morph-bundle identity wiring (US2/US3 — morph-bundle-identity-wiring.md)
# ---------------------------------------------------------------------------

def plan_morph_bundles(analysis, target, ctx, dropped) -> List:
    """Pure/decision pass → list of `models.MorphBundlePlan`.

    For each bundle, capture the WS-gated form and build four `IdentityRef`s
    (`MorphRA`/`MsaRA`/`SenseRA`/`InflTypeRA`) via the per-run target GUID index
    (R4). Every unresolved ref emits one DroppedItemRecord with locate-and-finish
    context (FR-016). SCAFFOLD (T023/T028)."""
    raise NotImplementedError(_PHASE)


def apply_morph_bundles(analysis_obj, plans, target, ctx, dropped) -> None:
    """Move-mode — create bundles in source order, always `SetForm`, wire each
    resolved `IdentityRef` (`SetMSA`/`SetSense`/`SetMorphType`/`SetInflType`),
    leave unresolved refs unset (already reported). SCAFFOLD (T023/T027)."""
    raise NotImplementedError(_PHASE)


# ---------------------------------------------------------------------------
# Segment alignment (US2 — segment-alignment.md, FR-012, SC-006)
# ---------------------------------------------------------------------------

def plan_alignment(segment, ctx, dropped) -> List:
    """Pure/decision pass → ordered list of `models.AlignmentToken`.

    Read `SegmentOperations.GetAnalyses(segment)`; classify each token
    (ANALYSIS/WORDFORM/PUNCTUATION) and record its intended target referent so
    order + count mirror the source (FR-012). SCAFFOLD (T024)."""
    raise NotImplementedError(_PHASE)


def apply_alignment(target_segment, tokens, ctx, dropped) -> None:
    """Move-mode — rebuild the target `AnalysesRS` in source order.

    Append each token's resolved target referent; where the wrapper exposes no
    `AnalysesRS` setter, reach the raw sequence via `project.GetService(...)` +
    `CastingOperations.cast_to_concrete` (Principle II fallback, R5). Preserves
    punctuation / bare-wordform slots. SCAFFOLD (T024). [PROBE] exact write path
    pending live-runtime confirmation."""
    raise NotImplementedError(_PHASE)
