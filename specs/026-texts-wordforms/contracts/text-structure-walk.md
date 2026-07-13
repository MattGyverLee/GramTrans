# Contract: Text Structure Walk (`Lib/texts.py`) — US1 + genre + tags

Covers the interlinear text container and structure: title/abbreviation/source/translation-complete
flag, paragraph/segment structure, baseline vernacular content, free/literal translations, segment
notes, genre assignments, and per-segment text-markup tags. Plan-aware (Principle III). Reuses the
024 resolver (genres/tags), owned-walk pattern (paragraphs→segments), WS-mapping gate, and
dropped-item channel.

## `plan_texts(selected_texts, src_project, target, ctx, resolver_cache, dropped) -> list[TextTransferPlan]`

Pure/decision pass, invoked from the plan-builder (`preview.py`). No writes.

**Behavior**
- For each selected source `IText` (`TextOperations.GetAll()` filtered by the Model-A picker):
  - Determine disposition by identity: GUID match, else `TextOperations.Find(title)` → `UPDATE`/
    `SKIP` (non-destructive, FR-021); no match → `ADD`.
  - Resolve `GenresRC` via `references.decide_reference` against `LangProject.GenreListOA`
    (create-allowed, GUID-preserving, FR-005). Cache shared genres per run.
  - Walk `ContentsOA.ParagraphsOS` → `SegmentOperations.GetAll(para)`, building `ParagraphPlan`/
    `SegmentPlan`. For each segment capture WS-gated baseline, `GetFreeTranslation`,
    `GetLiteralTranslation`, `GetNotes`; every string passes `ws_mapping` — an unmapped WS yields a
    `DroppedItemRecord` (reason `writing system not mapped`) and that string alone is skipped
    (FR-020, edge case).
  - Resolve per-segment text-markup tag references via the resolver against the text-markup tag
    list (create-allowed, FR-017).
  - Delegate each segment's human-evaluated analyses + `AnalysesRS` alignment to `wordforms.py`
    (see `analysis-human-eval-walk.md`, `segment-alignment.md`).

**Guarantees**
- Deterministic; never writes; never throws on a missing target list/genre (reports instead).
- A genre/tag shared across texts/segments resolves once via `resolver_cache`.
- A text with zero human-evaluated analyses still yields a full `TextTransferPlan` (structure +
  translations + notes) — the analysis layer is simply empty and stated, never a silent no-op
  (edge case).

## `apply_texts(plans, target, ctx, resolver_cache, dropped) -> None`

Move-mode only. Executes the plan.
- Create the text (`TextOperations.Create(name, genre)`) preserving source GUID where permitted,
  else record the mapping (FR-022); set abbreviation/source/`SetIsTranslated` (FR-002).
- Create paragraphs (`ParagraphOperations.Create(text, content, wsHandle)`) and segments; write
  baseline, `SetFreeTranslation`/`SetLiteralTranslation`, and notes — **non-destructively** (never
  blank a populated target alt from an empty source, FR-021).
- Apply genre + tag `ReferenceDecision`s (`references.apply_reference`).
- `apply_residue` the created text/paragraph via the Description-append carrier (R8).

**Postconditions**
- Each selected text exists once on the target with matching structure, translations, notes, and
  genre references; every unmapped WS / unresolvable genre / unresolvable tag is reported.
- Re-run produces no duplicate text and no destructive field blanking (SC-005).

## Non-goals
- Does not copy analyses/morph bundles (see `analysis-human-eval-walk.md`).
- Does not copy `AssociatedNotebookRecord`, media files, speaker/media/time offsets (out of scope).
