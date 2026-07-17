# Simplify Report — Feature 030 (cycle 1)

**Date:** 2026-07-16
**Scope:** `references.py` Section B (dynamic-owner thesaurus resolver) + `categories.py` glue, worktree @ d6132ff
**Status:** DONE (assessment only — no refactor landed)

## Verdict: proportionate, NOT over-engineered
Section B is ~230 lines (~140 logic) for ten functions, justified by two hard constraints, not speculative generality:
1. `ThesaurusItemsRC` has no fixed home list (unlike every static REFERENCE_FIELD_MAP row) — FR-005 requires per-item owning-list discovery + target mirroring.
2. Research Finding 3 (list GUIDs not stable cross-project) rules out GUID match as *incorrect*, not merely inelegant. Owner+flid is the next-strongest model-stable identifier; Name-match is the only remaining option for a custom-owned list.

Each fallback layer is reachable and non-overlapping (no dead code):
- `_target_singleton_owner` recognizes exactly the two singleton owners (LangProject, LexDb) actually used by REFERENCE_FIELD_MAP — complete set, not a stub.
- `_target_list_by_owner_flid` = precise primary match.
- `_target_list_by_name` / `_iter_target_possibility_lists` = the one case owner+flid can't reach (a custom top-level list).

**Delegating to 024's decide_reference/apply_reference via a synthetic ReferenceFieldSpec is a genuine reuse win, not an awkward adapter.** apply_reference (~350 lines: typed-factory CREATE, WS-Id-keyed UPDATE, LINK, REPORT_DROPPED, already WS-hardened) is served by an 8-line `build_thesaurus_spec` instead of a duplicated path. Strongest design decision in Section B.

## One concrete "would simplify" (reuse win + closes a latent gap — not must-fix)
`_iter_target_possibility_lists` hand-writes 11 accessor lambdas as the Name-fallback candidate set, duplicating a subset of REFERENCE_FIELD_MAP's `target_list_path` accessors. Comparing the two: **three REFERENCE_FIELD_MAP possibility-list accessors are MISSING from the hardcoded set** — `lp.TranslationTagsOA` (CmTranslation.TypeRA), `LexDbOA.VariantEntryTypesOA`, `LexDbOA.ComplexEntryTypesOA` (LexEntryRef). A latent coverage gap in the Name-fallback, not just duplication.

**Recommendation:** derive the candidate set from REFERENCE_FIELD_MAP:
```python
def _iter_target_possibility_lists(target):
    fake = getattr(target, "possibility_lists", None)
    if fake is not None:
        yield from fake
        return
    seen = set()
    for spec in REFERENCE_FIELD_MAP:
        if spec.target_list_path is None:
            continue
        try:
            lst = spec.target_list_path(target)
        except Exception:
            continue
        if lst is None or not hasattr(lst, "PossibilitiesOS"):
            continue
        if id(lst) in seen:
            continue
        seen.add(id(lst))
        yield lst
```
The `hasattr(lst, "PossibilitiesOS")` guard naturally excludes `MoForm.PhoneEnvRC` (→EnvironmentsOS) and `MoForm.StemNameRA` (→None) with no special-casing. **Would-simplify, not must-fix**: both fields vacuous-live everywhere → zero live-data impact today. ~15 fewer lines, one fewer place to keep in sync.

## Rejected simplifications
- Collapse `_target_singleton_owner` into `_target_list_by_owner_flid` — costs testability for ~6 lines.
- Inline `build_thesaurus_spec`/`_thesaurus_drop` into `resolve_thesaurus_item` — merges three single-purpose testable helpers into one mixed-concern function.
- Drop owner+flid, Name-only — out of scope (never-by-list-GUID guard is load-bearing) and a fidelity regression.
- Shrink `_OWNER_WALK_DEPTH_CAP=32` — not a hot path.

## Handoff
No code changed this cycle (assessment only). If the `_iter_target_possibility_lists` change is later applied, verification should re-check the Name-fallback path and the fidelity census (REFERENCE_FIELD_MAP itself unchanged, only its consumer).

**2-line summary:** Not over-engineered — fallback layers each reachable/justified by GUID-instability + dynamic-owner constraints; 024 reuse is a genuine win. Top rec: derive `_iter_target_possibility_lists` from REFERENCE_FIELD_MAP — removes ~15 dup lines AND closes a latent gap (TranslationTagsOA/VariantEntryTypesOA/ComplexEntryTypesOA missing from the Name-fallback set).
