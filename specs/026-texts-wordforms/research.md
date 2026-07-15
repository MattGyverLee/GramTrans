# Phase 0 Research: Texts & Wordforms

All decisions grounded on the live flexicon Operations surface via FLExTools MCP (2026-07-12) and
on the reusable seams delivered by feature 024. No open `NEEDS CLARIFICATION` items remain from
Technical Context; the spec's five clarifications (2026-07-12) already locked scope, so this phase
resolves *mechanism*, not scope.

> **Runtime-probe caveat (inherited from spec Domain Grounding).** The MCP `run_module` path
> currently fails at CLR init (`Failed to initialize Python.Runtime.dll`), so live per-project
> counts and the R2 live-appearance confirmation could not be captured. All decisions below rest
> on the **static API surface** (`search_by_capability` / `get_object_api`), which was fully
> available. Items needing a live run are flagged **[PROBE]** and carried to quickstart.md.

---

## R0 — Scope confirmations (spec clarifications, restated for the builder)

- **Decision**: Wordform closure is **text-scoped** (FR-001a) — copy only wordforms occurring in
  the selected texts, and only their human-evaluated analyses. Never pull the project-wide
  human-evaluated inventory independently.
- **Decision**: Genre and text-markup tag values absent from the target are **created** via the
  024 resolver (GUID-preserving); only truly unresolvable references are reported. An analysis's
  grammatical **category** is **resolve-or-report** — never created for an analysis.
- **Decision**: A needs-review analysis is left in the platform's natural no-human-verdict state
  (no in-FLEx marker, no proxy-deny); the report is the only signal.
- **Decision**: Data Notebook is entirely out of scope (`AssociatedNotebookRecord` not copied).
- **Rationale**: These are user-locked in the spec; recorded here so the plan-builder does not
  re-open them.

## R1 — The human-evaluation gate (FR-006/007/008)

- **Decision**: An analysis is copy-eligible **iff** `WfiAnalysisOperations.GetHumanEvaluation(a)`
  is non-null (a human verdict exists). The verdict's approve/deny is read from that evaluation's
  `Approves` flag (LCM `ICmAgentEvaluation.Human=true`, `Approves` bool — the four-state matrix
  from the spec's Domain Grounding). Parser-only analyses (`GetHumanEvaluation` is null but
  `GetAgentEvaluation` / `IsComputerApproved` is set) and un-evaluated analyses are excluded.
  The identical gate applies to `WfiGloss` via its own human evaluation (FR-008).
- **Rationale**: `GetHumanEvaluation` is the single call that both gates eligibility *and* yields
  the verdict, so one read drives both FR-006 and FR-007.
- **Alternatives rejected**: `IsHumanApproved(a)` alone — it returns true only for the *approve*
  case, so it would silently drop every **human-denied** analysis, violating FR-006 (deny is in
  scope) and SC-001. Enumerating `GetEvaluations` and filtering by `Human` works but is strictly
  more code for the same result.

## R2 — Representing needs-review as the natural no-human-verdict state (FR-014)

- **Decision**: To create an analysis without asserting a human verdict, create it
  (`WfiAnalysisOperations.Create(wordform)`) and **do not** call `ApproveAnalysis` /
  `RejectAnalysis` / write any human `ICmAgentEvaluation`. The analysis then sits in the
  three-state approval model's "no opinion" state (`GetApprovalStatus` neither approve nor
  disapprove) — exactly the human-unknown appearance the spec requires. Needs-review is conveyed
  solely by that absence **plus** the `DroppedItemRecord`(s) for its unlinked morphemes (FR-016).
- **Rationale**: The surface exposes a genuine three-state approval status
  (`Get/SetApprovalStatus` distinct from the boolean `ApproveAnalysis`/`RejectAnalysis`),
  confirming the platform has a native no-verdict state to leave the analysis in.
- **[PROBE]**: Confirm on a live target that an analysis created with no human evaluation renders
  as "unanalyzed-but-present" (attached to its baseline token, no green human-approved check) when
  the text is opened in FLEx — the spec Assumptions call for this live confirmation and it needs
  the `run_module` path restored.

## R3 — Human-agent provisioning (FR-009)

- **Decision**: Resolve the owning human agent once per run: prefer
  `AgentOperations.GetHumanAgents()` (or `FindByType(is_human=True)`) and reuse the first; if the
  target has none, `Create(name)` a human agent and `SetHuman(agent, person)` to mark it human.
  Cache the provisioned/selected agent on the run context and reuse it for every copied evaluation
  (no per-evaluation duplication). The provisioning decision appears in Preview as an Add (when
  created) or Link (when reused).
- **Rationale**: `GetHumanAgents` + `Create` + `SetHuman` are the confirmed wrapper calls; the
  agent lives in `AnalyzingAgentsOC`, matching the spec Domain Grounding.
- **Alternatives rejected**: Copying the *source* agent object by GUID — agents are project-scoped
  identities, not transfer content; provisioning/reusing a target agent is the intent of FR-009.

## R4 — Morph-bundle reference wiring by identity (FR-010)

- **Decision**: Each morph bundle's four references are wired to **already-existing** target
  objects looked up **by source GUID** through a per-run target GUID index (built once from the
  024/025 copy-set + the live target): `MorphRA`→`SetForm`/`SetMorphType` allomorph,
  `MsaRA`→`SetMSA`, `SenseRA`→`SetSense`, `InflTypeRA`→`SetInflType` (and `SetInflectionClass`
  where present). This is a **GUID identity lookup against copied lexical objects**, NOT the 024
  possibility resolver — morph-bundle targets are `LexSense`/`MSA`/`MoForm` objects that 024
  already transferred, not possibility-list items.
- **Rationale**: Principle I requires these cross-references resolve to real target objects; 024
  guarantees the objects exist when the sense was copied, so wiring is a lookup, not a create.
- **Alternatives rejected**: Routing morpheme references through `references.decide_reference` —
  that resolver creates absent possibility items, which is wrong here (a missing sense must NOT be
  fabricated from an analysis; it triggers the R5/needs-review path instead).

## R5 — Segment baseline alignment (`Segment.AnalysesRS`) (FR-012, SC-006)

- **Decision**: Reproduce each segment's `AnalysesRS` as the ordered per-token sequence pointing at
  the **target** wordforms/analyses (and preserving punctuation / bare-wordform tokens for
  positional fidelity). Where the flexicon wrapper exposes no setter for `AnalysesRS`, reach the
  raw LCM sequence via `project.GetService(...)` + `CastingOperations.cast_to_concrete` (Principle
  II fallback clause) and append the target `IAnalysis` objects in source order. Build the source→
  target token map from the wordform find/create step (R7) so each source token position maps to
  the target wordform's chosen analysis (or the bare wordform / punctuation token).
- **Rationale**: `SegmentOperations` exposes `GetAnalyses` (read) but no `SetAnalyses` in the
  wrapper surface, so the write side is the one place 026 legitimately drops to the raw interface
  under the Principle II fallback. Alignment is what makes the interlinear render correctly (SC-006).
- **Alternatives considered**: `SegmentOperations.ReparseParagraph` — rejected as the *primary*
  mechanism because reparse re-derives analyses from the parser and would not reproduce the
  human-chosen analysis per token; it may be used only as a pre-step to establish baseline tokens
  before attaching the copied analyses. **[PROBE]**: verify the exact write path for `AnalysesRS`
  on a live target once `run_module` is restored (the static surface confirms the read side and the
  factory fallback, not the precise mutator).

## R6 — Genre / category / text-markup-tag resolution (FR-005/011/017)

- **Decision**: Reuse 024's `references.decide_reference`/`apply_reference` for all three, with two
  target lists and one behavior variant:
  - **Genre** (`IText.GenresRC` → `LangProject.GenreListOA`): full resolver — create absent values
    (GUID-preserving), report only the unresolvable. Cardinality COLLECTION.
  - **Text-markup tag** (segment tag refs → the text-markup `TextMarkupTagsOA` possibility list):
    full resolver — create absent values, report only the unresolvable (FR-017), consistent with
    genre.
  - **Category** (`IWfiAnalysis.CategoryRA` → `LangProject.PartsOfSpeechOA`): a **resolve-or-report**
    variant — call `decide_reference`, but suppress the `CREATE` arm: if the matching POS is absent
    the field is left unset and a `DroppedItemRecord` is emitted (FR-011). A POS is never fabricated
    for an analysis.
- **Rationale**: One resolver, three field specs, keeps the never-silent guarantee uniform; the
  category variant is a thin wrapper (`decide_reference` → downgrade `CREATE` to `REPORT_DROPPED`)
  rather than a second resolver.
- **[PROBE]**: Confirm the exact target-list accessors (`GenreListOA`, text-markup tag list owner)
  on the live LCM surface; the static surface confirms `TextOperations.Get/SetGenre` and the
  possibility-list resolver but not every list's owning path.

## R7 — Non-destructive re-run & identity (FR-021/022, SC-005)

- **Decision**: **Text** identity — match by GUID first, then `TextOperations.Find(title)`;
  re-run UPDATEs non-destructively (never blank a populated target field from an empty source) and
  never creates a duplicate. **Wordform** identity — wordforms are project-global keyed by form+WS;
  find-or-create (`WordformOperations`) so a form shared across texts is created once.
  **Analysis** identity — preserve the source GUID on `Create` where the platform permits; where it
  does not, record the source→target GUID mapping on the run context for reference re-wiring
  (FR-022). Spelling status via `WordformOperations.ApproveSpelling` / status setter (FR-013).
- **Rationale**: Mirrors 024's GUID-first / fingerprint-fallback identity strategy and the UPDATE
  (source-preferring, never-blank) write semantic; wordforms being global is the reason the closure
  is text-scoped rather than wordform-scoped.

## R8 — Residue tagging & pipeline ordering

- **Decision**: Register `Text` (and `StText`/`StTxtPara`) and `WfiWordform`/`WfiAnalysis` as
  residue carriers in `residue.py`. Text/word LCM classes do not expose `LiftResidue`/`ImportResidue`
  the way lexical classes do, so the `[GT-Tag]: GT|<run_id>|<source>|<iso_ts>` marker is appended
  non-destructively to the inherited `Description`/note carrier per the constitution's residue
  clause. 026 runs **after** 024 (lexicon) and 025 (reversals) in the import order so morph-bundle
  targets (senses/MSAs/allomorphs) already exist when analyses are wired (soft dep on 025).
- **Rationale**: Constitution "Residue tagging" gate — every Add/Overwrite must be auditable;
  text/word classes fall under the Description-append fallback.

## Consolidated decisions

| # | Decision | Key API / seam |
|---|---|---|
| R1 | Copy-eligible ⇔ `GetHumanEvaluation` non-null; verdict from `Approves` | `WfiAnalysisOperations.GetHumanEvaluation` |
| R2 | Needs-review = create + write no human evaluation (natural no-opinion) | `Create`; *not* `ApproveAnalysis` |
| R3 | Provision/reuse one human agent per run | `AgentOperations.GetHumanAgents`/`Create`/`SetHuman` |
| R4 | Wire morph-bundle refs by GUID identity lookup (not the resolver) | `WfiMorphBundleOperations.SetMSA`/`SetSense`/`SetForm`/`SetInflType` |
| R5 | Reproduce `AnalysesRS` in token order; raw-LCM fallback for the setter | `SegmentOperations.GetAnalyses` + `GetService` fallback |
| R6 | Genre/tag = create-via-024-resolver; category = resolve-or-report | `references.decide_reference`/`apply_reference` |
| R7 | GUID-first identity; non-destructive UPDATE re-run; global wordform find/create | `TextOperations.Find`, `WordformOperations`, `conflict` update semantic |
| R8 | Residue via Description-append; run after 024+025 | `residue.py` |

**Open [PROBE] items carried to quickstart.md**: R2 (live no-verdict appearance), R5 (exact
`AnalysesRS` write path), R6 (target-list accessors) — all require the MCP `run_module` /
CLR-init path to be restored; none blocks the interface-level design.
