# Contract: Morph-Bundle Identity Wiring (`Lib/wordforms.py`) — US2/US3

Wire each copied analysis's morph bundles to the target lexical objects **that 024 already copied**,
by source-GUID identity lookup — and, where a referent was not copied, leave the morpheme unlinked,
downgrade an approve to needs-review, and report. This is the referential-completeness crux (US3).

## `plan_morph_bundles(analysis, target, ctx, dropped) -> list[MorphBundlePlan]`

Pure/decision pass. Uses the per-run **target GUID index** (built once from the 024/025 copy-set +
the live target) — NOT the 024 possibility resolver (R4).

**Behavior**
- For each `WfiMorphBundleOperations.GetAll(analysis)` bundle, capture the WS-gated `GetForm`, then
  build four `IdentityRef`s by looking the source referent GUID up in the target GUID index:
  - `MorphRA` (allomorph / `MoForm`), `MsaRA` (MSA), `SenseRA` (`LexSense`), `InflTypeRA`
    (`LexEntryInflType`, optional).
- `IdentityRef.resolved = target_obj is not None`. For every **unresolved** ref emit a
  `DroppedItemRecord` (owner_kind `WfiMorphBundle`, field = the ref name, reason `referent not
  copied to target`) with enough context (text, segment, wordform, morpheme) to finish it manually
  (FR-016).

## `apply_morph_bundles(analysis_obj, plans, target, ctx, dropped) -> None`

Move-mode only.
- `WfiMorphBundleOperations.Create(analysis_obj)` per plan (source order preserved).
- Write `SetForm` (always — a legible bundle even when refs are unlinked).
- For each **resolved** `IdentityRef`, wire: `SetMorphType`/`SetForm` allomorph via `MorphRA`,
  `SetMSA`, `SetSense`, `SetInflType` (+ `SetInflectionClass` where present).
- For each **unresolved** ref, leave the target field unset (already reported at plan time).

**Interaction with the verdict (FR-014/015)** — computed at plan time, applied by `apply_analyses`:
- ≥1 unresolved ref on a `HUMAN_APPROVED` analysis → `needs_review = True` → the analysis is written
  with **no** human evaluation (natural no-verdict state, R2). The approve is not asserted because
  the linkage can no longer substantiate it.
- ≥1 unresolved ref on a `HUMAN_DENIED` analysis → deny verdict **retained**; the unresolved
  morphemes are still unlinked and reported (FR-015). A deny is never downgraded.

**Postconditions**
- Every morph bundle exists in source order; every resolvable reference is wired to the matching
  target object by identity; every unresolvable reference is unlinked and reported exactly once.
- An approve that lost a referent is needs-review, not falsely approved; a deny keeps its verdict.

## Non-goals
- Does not create senses/MSAs/allomorphs (those come from 024) — a missing referent is a report +
  needs-review, never a fabrication.
