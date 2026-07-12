---
description: "Task list for Lexicon Reference & Owned-Object Fidelity"
---

# Tasks: Lexicon Reference & Owned-Object Fidelity

**Input**: Design documents from `specs/024-lexicon-reference-fidelity/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED. The feature spec and plan explicitly enumerate unit tests
(`tests/unit/test_*`), a verification harness (`tests/verification/fidelity_census.py`,
US5/FR-011), and quickstart validation scenarios. Test tasks are therefore first-class here.

**Organization**: Tasks are grouped by user story to enable independent implementation and
testing of each story.

**Work location**: Per CLAUDE.md Git Workflow Protocol, all code/test work below is done on a
dedicated worktree (`../GramTrans-024-lexicon-reference-fidelity` on branch
`024-lexicon-reference-fidelity`), merged to `main` when validated. Spec artifacts already
live on `main`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths are included in every task.

## Path Conventions

Single-project FlexTools module. Source under `src/gramtrans/Lib/`, tests under `tests/unit/`
and `tests/verification/` at repository root (per plan.md Project Structure).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the worktree and the empty module/test scaffolding the feature will fill.

- [ ] T001 Create the feature worktree `../GramTrans-024-lexicon-reference-fidelity` on branch `024-lexicon-reference-fidelity` from `main` (per CLAUDE.md Git Workflow Protocol); confirm `pip install -e D:/Github/_Projects/_LEX/flexlibs2` resolves in it.
- [X] T002 [P] Create empty module stubs `src/gramtrans/Lib/references.py` and `src/gramtrans/Lib/owned.py` with module docstrings citing the contracts (`contracts/reference-resolver.md`, `contracts/owned-object-walk.md`).
- [X] T003 [P] Create `tests/verification/__init__.py` and an empty `tests/verification/fidelity_census.py` stub so the harness path exists and is importable.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared data types (enums, records, field maps) and the report-channel plumbing
that every user story depends on. NOTHING in US1–US5 can be built until these exist.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Add `ReferenceAction` (LINK/CREATE/UPDATE/REPORT_DROPPED) and `FidelityStatus` (FULL/PARTIAL) enums to `src/gramtrans/Lib/models.py` per data-model.md Enums.
- [X] T005 [P] Add `DroppedItemRecord` dataclass (owner_kind, owner_guid, owner_label, field_name, item_name, item_guid, reason) to `src/gramtrans/Lib/models.py` per data-model.md.
- [X] T006 Add `ReferenceFieldSpec` dataclass (owner_class, field_name, cardinality, target_list_path callable, hierarchical) plus the `ReferenceDecision` result type to `src/gramtrans/Lib/models.py` (depends on T004).
- [X] T007 Add `OwnedObjectSpec` dataclass (owner_class, owning_field, factory, child_refs, recurse) to `src/gramtrans/Lib/models.py` per data-model.md OwnedObjectSpec (depends on T004).
- [X] T008 Build the initial `REFERENCE_FIELD_MAP` (the closed dispatch table from data-model.md: Sense SenseTypeRA/UsageTypesRC/DomainTypesRC/AnthroCodesRC/DialectLabelsRS/StatusRA/SemanticDomainsRC/PublishIn/DoNotPublishInRC/DoNotShowMainEntryInRC; Entry DialectLabelsRS/PublishIn/DoNotPublishInRC/DoNotShowMainEntryInRC/allomorph MorphTypeRA; Example→CmTranslation.TypeRA; Allomorph PhoneEnvRC/StemNameRA; Etymology LanguageRS) in `src/gramtrans/Lib/references.py` (depends on T006).
- [X] T009 Extend `RunReport` in `src/gramtrans/Lib/report.py` with `dropped_items: list[DroppedItemRecord]` and per-object `fidelity: FidelityStatus`; extend `to_snapshot_json`/`_to_snapshot_json` additively so old snapshots load with `dropped_items` defaulting empty (depends on T004, T005; contract dropped-item-report.md "Snapshot compatibility").
- [X] T010 Thread a per-run `dropped: list[DroppedItemRecord]` collector through the closure-walk context/signatures in `src/gramtrans/Lib/categories.py` (entry→sense→sub-sense→allomorph→example) and into `preview.py`/`transfer.py` plan context, without yet appending to it (depends on T005; contract dropped-item-report.md "Collection").

**Checkpoint**: Shared types + report channel exist. User stories can now begin.

---

## Phase 3: User Story 1 — Referenced list items survive the copy (Priority: P1) 🎯 MVP

**Goal**: Every possibility-list item a copied object references is present & correct in the
target afterward (created with ancestor chain, updated if custom-diverged, or linked).

**Independent Test**: Fixture source with one custom referenced item + one renamed-default
referenced item into a target lacking the custom and holding the stale default → custom
created, renamed default LINKed+reported, both entries resolve to the right item.

### Tests for User Story 1 ⚠️ (write first, must FAIL before implementation)

- [X] T011 [P] [US1] Write `tests/unit/test_reference_resolver.py`: LINK (identical GUID), CREATE (absent + ancestor chain), UPDATE (custom diverged), REPORT_DROPPED (shared/default diverged; target list absent), and cache-reuse/idempotency (FR-012) cases against the decision table in contracts/reference-resolver.md.

### Implementation for User Story 1

- [X] T012 [US1] Implement the divergence fingerprint (Name/Abbreviation multistrings across all WS, + Description where relevant) in `src/gramtrans/Lib/references.py`, reusing the multistring-compare helpers in `src/gramtrans/Lib/conflict.py`/`src/gramtrans/Lib/fingerprints.py` (research R7).
  - **Hardening (write-first, commit e7f5e9c → this fix)**: `divergence_fingerprint` compared `(ws_handle, text)` pairs, but a WS handle is per-project cache state, non-portable — the SAME writing system gets a DIFFERENT handle in each project, so Id-for-Id-identical cross-project content always looked diverged. Since `divergence_fingerprint(item)` takes a bare item with no project/Cache handle to resolve a portable Id from, it now compares the sorted bag of TEXT VALUES only (dropping the WS key entirely) — fixes the false-divergence without needing a resolver that isn't reachable from this signature.
- [X] T013 [US1] Implement `decide_reference(source_item, target, spec, cache) -> ReferenceDecision` (pure, no writes, never throws on missing list) in `src/gramtrans/Lib/references.py`, using `protection._is_protected` for custom-vs-shared classification (FR-003/005, research R3) and the T012 fingerprint (depends on T008, T012).
- [X] T014 [US1] Implement ancestor-chain resolution (walk `source_item.Owner` up to the list; ordered root→leaf into `ancestors_to_create`) inside `decide_reference` for hierarchical specs in `src/gramtrans/Lib/references.py` (FR-002, research R4; depends on T013).
  - **Hardening (write-first, commit 6cb1a64 → this fix)**: `_ancestor_chain` now walks `.OwningPossibility` only and stops at `None` — a top-level `ICmPossibility`'s `.Owner` is the owning `ICmPossibilityList` itself (also `.Guid`-shaped), so the old `.Owner`-first walk wrongly included the list. `decide_reference`'s CREATE branch no longer gates the ancestor walk on the static `spec.hierarchical` flag (MCP-confirmed the flag can disagree with a project's live `Depth`); the walk is driven purely by live `OwningPossibility` and no-ops to `(source_item,)` for a genuinely top-level item.
- [X] T015 [US1] Implement `apply_reference(decision, target, owner_obj, spec, cache, tag) -> target_item` in `src/gramtrans/Lib/references.py`: CREATE ancestors top-down preserving GUID under correct parent `SubPossibilitiesOS` + `apply_residue` + cache; UPDATE via `conflict.apply_update_semantic`; LINK sets owner field; REPORT_DROPPED links existing/leaves unchanged (depends on T013, T014).
  - **Hardening (write-first, commit 6cb1a64 → this fix)**: CREATE now selects the factory by the target list's `ItemClsid` (66/26/5042/7 → `ICmSemanticDomainFactory`/`ICmAnthroItemFactory`/`IMoMorphTypeFactory`/`ICmPossibilityFactory`; all four confirmed live, no unmapped clsid in the current field map) instead of always requesting the generic factory — fixes wrong-classed creates in typed lists. A future unmapped clsid fails loud via `UnmappedItemClassError` (a `DroppedItemRecord`, reason `unmapped item class <clsid> for CREATE`) rather than silently defaulting to the generic factory. UPDATE now propagates the full per-WS Name/Abbreviation/Description multistring set (the same one `divergence_fingerprint` compares) instead of collapsing to one best-text alt, so WS-specific divergences the fingerprint detected actually get written; the non-destructive invariant (FR-007) still holds via `conflict.apply_update_semantic`/`_is_empty`'s dict-aware empty check.
  - **Hardening (write-first, commit e7f5e9c → this fix, WS Id-vs-Handle)**: confirmed live + from flexicon `BaseOperations.ApplySyncableProperties`/`_apply_props_loop` — a multistring prop value must be keyed by writing-system **Id** (portable), never **Handle** (per-project cache state, non-portable); the prior UPDATE arm fed `_multistring_dict`'s raw handle-keyed dict straight in, so every non-default-WS alt hit the contract's silent-skip and never landed. `_multistring_dict` now accepts an optional `handle_to_id` resolver; new `_resolve_target_ws_by_id(ops)` builds `{id: handle}` from the target project (tries the real flexicon public `ops.project` attribute, confirmed `BaseOperations.py:498`, then test-double-shaped fallbacks); new `_id_keyed_multi_ws(src_snapshot, tgt_snapshot, target_ws_by_id)` translates the source's handle-keyed snapshot into an Id-keyed one via content-matching against the target's current alts (safe) plus elimination for genuinely-new alts when the remaining counts align 1:1 (never guesses when ambiguous — FR-007). `apply_reference` gained an optional `ws_map` parameter forwarded to `conflict.apply_update_semantic`/`ApplySyncableProperties`, matching the existing `categories.py` closure UPDATE sites (`_apply_reference_fields` now threads `context._ws_map` through from all three call sites). CREATE's content-setting path (previously `_best_text`-only, i.e. best-alt) now goes through the same Id-keyed multi-WS path first, falling back to `_best_text` only when the resolution can't be made (never regresses below the pre-cycle best-alt behaviour). Residual: the Id-keyed translation for a bare LCM item with no directly reachable project handle (source side of UPDATE, and CREATE's brand-new target item) is a best-effort content-match/elimination heuristic, not a true per-project WritingSystemFactory lookup — a future cycle threading the SOURCE project handle into `apply_reference` (today's contract only carries `target`) would make this exact instead of best-effort; flagged for live MCP verification since only `test_reference_ws_keying.py`'s fakes exercise this boundary today.
  - **Hardening (write-first, commit f0449b4 → this fix, real source handle→Id threading)**: the cycle-1 content-match/elimination heuristic (`_id_keyed_multi_ws`) had three confirmed failure modes — (a) a target WS the source item left unpopulated got wrongly counted as an ambiguous "remaining" slot and aborted the whole elimination; (b) two alts diverging in the SAME update could be swapped onto the wrong WS since source-handle sort order has no relationship to target-Id alphabetical order; (c) a source alt whose Id has no target counterpart was silently absorbed with no `DroppedItemRecord` at all. `_id_keyed_multi_ws`, `_resolve_target_ws_by_id`'s content-elimination role, and the `zip(sorted(ids), unmatched-handle-order)` pairing are DELETED. `decide_reference`/`divergence_fingerprint`/`apply_reference` now accept an optional `source` (SOURCE FLExProject handle) parameter, threaded from `categories.py`'s three `_apply_reference_fields`/three `_decide_reference_fields` call sites via `context.source_handle` (both already had the source project in scope). New `_project_handle_to_id(project)` builds `{handle: id}` directly off `project.WritingSystems.GetAll()` (source OR target). When `source` is given, `_multistring_dict(ms, source_handle_to_id)` reads the source's real Id-keyed alts with NO content-matching at all (structural fix for a/b); a mapped Id absent from the target's own registered inventory (`target_ws_by_id`) now appends exactly one `DroppedItemRecord` (reason `source writing system <id> absent in target`) to the newly-threaded `apply_reference(..., dropped=)` collector instead of vanishing (fix for c). `tgt_props` is now built Id-keyed too (not handle-keyed) so `apply_update_semantic`'s identical-skip actually compares like-for-like. `divergence_fingerprint` gained an optional `handle_to_id` param: with a real resolver it compares genuine `(id, text)` pairs (detects a same-text cross-WS SWAP as diverged, which the cycle-1 sorted-text-values-only fix could not); without one (`source=None`, most existing unit fakes) it falls back to a POSITIONAL (ascending-handle-order value sequence) heuristic, replacing the old "sorted bag of text values" comparison — still resolver-free, but now also catches an order-swap. When `source=None` (no real resolver — legacy callers), a new `_best_effort_id_keyed` (exact-content-match, then greedy best-`difflib`-similarity pairing against the target's CURRENT per-id text, highest-confidence first) replaces the deleted zip/elimination hack for both UPDATE and CREATE. Residual: `_best_effort_id_keyed`'s similarity fallback is still a heuristic (used only when a caller doesn't thread `source` through) — every production call site in `categories.py` now does thread it, so this path is exercised only by this file's own legacy-fallback unit tests today; the 3+-registered-WS real-source write path (test (c) in `test_reference_ws_resolution.py`) is fakes-only and still wants live MCP confirmation against a project with 3+ writing systems (Ejagham Mini only has 2).
- [X] T016 [US1] Wire the resolver into `src/gramtrans/Lib/categories.py`: for every reference field in `REFERENCE_FIELD_MAP`, call `decide_reference` in the plan-builder path and `apply_reference` in the move path — replacing/subsuming the existing hand-wired MorphType/Status/MSA/SemanticDomain re-wire (research R1; depends on T015).
- [X] T017 [US1] Surface each per-item `ReferenceDecision` (Add/Link/Update/Skip/Report) in the Preview plan in `src/gramtrans/Lib/preview.py` and execute deferred writes in `src/gramtrans/Lib/transfer.py` (Principle III, research R2; depends on T016).

**Checkpoint**: US1 fully functional — referenced items create/update/link/report; MVP demoable via quickstart Scenario 1.

---

## Phase 4: User Story 2 — Nothing is blanked in the target (Priority: P1)

**Goal**: The object-reference fields collected-then-dropped on apply (SenseType,
DoNotPublishIn, DoNotShowMainEntryIn) are carried, and an empty source never blanks a
populated target field.

**Independent Test**: Populate a target sense with sense-type + publication settings, run an
OVERWRITE-mode copy of the matching source → those fields retain a correct value, never blank.

### Tests for User Story 2 ⚠️ (write first, must FAIL before implementation)

- [X] T018 [P] [US2] Write `tests/unit/test_blanking_fix.py`: overwrite-mode copy does NOT blank a populated target `SenseTypeRA`/`DoNotPublishInRC`/`DoNotShowMainEntryInRC` (FR-006), and an empty/unset source reference never blanks a populated target field across all conflict modes (FR-007/SC-002).

### Implementation for User Story 2

- [X] T019 [US2] Confirm/extend the re-wire pass in `src/gramtrans/Lib/categories.py` so the three previously-dropped sense/entry ref fields (`SenseTypeRA`, `DoNotPublishInRC`, `DoNotShowMainEntryInRC`) route through the T015 resolver instead of being discarded on apply (FR-006, research R1; depends on T016). Confirmed already fully wired via T016's generic `_apply_reference_fields` dispatch (no `skip_fields` excludes them at either the `LexEntry` or `LexSense` call sites in `_walk_lex_entry_closure`) — no additional wiring needed; `tests/unit/test_blanking_fix.py`'s end-to-end tests lock this in.
  - **Correction (follow-up cycle)**: the above confirmation covered only the ADD/closure path. `src/gramtrans/Lib/transfer.py._execute_overwrite`'s SENSE branch (always) and ENTRY/AFFIXES/STEMS branch (default `write_mode`) call the raw flexicon `ApplySyncableProperties(fill_gaps=False)` directly for these same three fields, whose semantics are blank-on-empty (`SenseTypeRA`)/clear-and-rebuild (`DoNotPublishInRC`/`DoNotShowMainEntryInRC`) — the OVERWRITE path was NOT covered and still violated FR-006/007/010 (`tests/unit/test_overwrite_blanking.py`, 4 red tests). Fixed this cycle: `_strip_empty_ref_fields` removes each field from `src_props` before the raw call ONLY when its value is empty/falsy (never the destructive path), then `categories._apply_reference_fields` (same resolver as the ADD path, scoped via `_overwrite_ref_skip_fields`) runs afterward for LINK/CREATE(+ancestors)/UPDATE/REPORT_DROPPED; a raw GUID present in `src_props` with no resolvable live object (`getattr(src_obj, field, None) is None`) gets a targeted `DroppedItemRecord` fallback (FR-010). `dropped`/`resolver_cache` are now threaded into `_execute_overwrite` from `execute()`'s shared per-run collector/cache (previously created only after the OVERWRITE loop; moved earlier). `PlannedOverwrite.reference_decisions` (new field, mirrors `PlannedAction.reference_decisions`) surfaces the same decisions in Preview at the ENTRY/SENSE `PlannedOverwrite` construction sites in `preview.py`. All 4 `test_overwrite_blanking.py` tests + full existing suite pass (baseline-only failure unaffected).
- [X] T020 [US2] Enforce the non-destructive invariant in `src/gramtrans/Lib/references.py` `apply_reference`: when the source item is `None`/unset, leave the target field unchanged — never write empty (FR-007; depends on T015). Cross-check the update path in `src/gramtrans/Lib/conflict.py` honors the same semantic. Confirmed already correct on both sides: `decide_reference(None, ...)` returns `None` and `apply_reference(None, ...)` no-ops without touching the owner field; `conflict.apply_update_semantic`/`_is_empty` independently skip any write where the source value is empty (`if _is_empty(src_val): continue`) — same non-destructive semantic, no fix required.

**Checkpoint**: US1 + US2 both work — no field is blanked under any mode; quickstart Scenario 2 passes.

---

## Phase 5: User Story 4 — The linguist is told what was dropped (Priority: P1)

**Goal**: Every non-reproduced referenced/owned item surfaces as a structured record in Preview
and the post-run panel; a fully-reproduced transfer shows an empty dropped list.

**Independent Test**: Force an unresolvable reference → report contains a record naming owning
object, field, source item name + identity, and reason; a clean transfer → empty report.

> Note: US4 is P1 and is the backstop for the whole guarantee. It builds on the report
> plumbing from Phase 2 (T009/T010) and the REPORT_DROPPED outcome from US1 (T013/T015).

### Tests for User Story 4 ⚠️ (write first, must FAIL before implementation)

- [X] T021 [P] [US4] Write `tests/unit/test_dropped_item_report.py`: a REPORT_DROPPED outcome yields exactly one `DroppedItemRecord` with correct owner/field/item/reason; no duplicate on re-walk (contract invariant); a fully-reproduced transfer yields empty `dropped_items` (SC-003 acceptance 2); render-text format matches the contract line spec.

### Implementation for User Story 4

- [X] T022 [US4] Make `decide_reference`/`apply_reference` in `src/gramtrans/Lib/references.py` build and append a `DroppedItemRecord` to the threaded `dropped` collector on every REPORT_DROPPED (shared-default divergence and target-list-absent), exactly once per (owner, field, item) triple (depends on T015, T010). Implemented one level up, in `src/gramtrans/Lib/categories.py`: `references.py`'s `decide_reference`/`apply_reference` still build the record with owner_guid=""/owner_label="" placeholders (that signature has no owner-instance context, only `spec.owner_class`) -- `categories.py`'s new `_enrich_dropped`/`_append_dropped_once`/`_call_apply_reference` patch in the real owner GUID/label (via the new `owner_guid` kwarg on `_apply_reference_fields`, threaded from `_walk_lex_entry_closure`/the sense loop/`_walk_entry_allomorphs._mk`) and dedup by `(owner_guid, field_name, item_guid)` before every append, covering all three append sites (`decide_reference`'s `.dropped`, `apply_reference`'s direct ws-absent appends, and `UnmappedItemClassError.dropped`).
  - **QC P1 fix (follow-up cycle)**: `_call_apply_reference`'s `except (AttributeError, TypeError, RuntimeError): ok = False` conflated benign duck-typing gaps with `references._add_to_owner`'s deliberate fail-loud orphan-risk `RuntimeError` (Create() succeeded, Add-to-owner failed) — that `RuntimeError` was swallowed with NO log and NO record, hiding an orphaned Create() (violates Principle I). `RuntimeError` now has its own `except` clause: logs via `_logging.getLogger("gramtrans.Lib.categories").error(..., exc_info=True)` AND appends a `DroppedItemRecord` (reason `apply_reference failed: <exc>`) to the `dropped` collector before returning `ok=False`; `AttributeError`/`TypeError` remain silently swallowed (unchanged, benign). QC P2s also closed this cycle: `references._multistring_dict`'s `except Exception: out = {}` now preserves partial results (`pass` instead of resetting) instead of discarding alt slots already collected before a mid-loop failure; `DroppedItemRecord`'s docstring (models.py) now states the dedup key `(owner_guid, field_name, item_guid)` deliberately excludes `reason` (cross-referencing `categories._dropped_key`, which already enforced this).
- [X] T023 [US4] Compute per-object `FidelityStatus` (FULL iff zero records for that object, else PARTIAL with count) in `src/gramtrans/Lib/categories.py` and attach to the report (FR-013; depends on T010, T009). `categories.compute_fidelity_by_guid(dropped)` returns PARTIAL for every owner_guid with >=1 drop; FULL is implied by absence from the dict (per `FidelityStatus`'s own models.py docstring) rather than enumerated explicitly. Wired into all three `RunReport.build_from_plan` call sites (`Lib/transfer.py.execute` for Move, `Lib/ui/selection_wizard.py`/`Lib/ui/main_window.py` for Preview) via `fidelity_by_guid=`.
- [X] T024 [US4] Add the "Dropped references / owned items" section to `render_text_summary` in `src/gramtrans/Lib/report.py` using the contract line format `<owner_label> [<owner_kind> <owner_guid[:8]>] . <field_name> → "<item_name>" (<item_guid[:8]>) — <reason>`; ensure it renders in both Preview and the post-run statistics panel (depends on T009). Rendered with ASCII `->`/`-` (not the contract's unicode →/—) per Windows console rules -- confirmed via the same `report.dropped_items` field feeding both Preview (`extra_dropped_items=payload.dropped_items`) and Move (`extra_dropped_items=_dropped`), so no mode-specific rendering code was needed.

**Checkpoint**: US1 + US2 + US4 — the never-silent guarantee holds for references; quickstart Scenario 4 passes.

---

## Phase 6: User Story 3 — Owned child objects come along (Priority: P2)

**Goal**: Copied entries/senses carry their owned children (examples+translations,
pronunciations, etymologies, recursive sub-senses) and allomorph-hung data (phonological
environments + APRs), each child's references resolved or reported.

**Independent Test**: Copy an entry owning an example (+translation), a pronunciation, an
etymology, and a sense with a sub-sense + an allomorph with an environment + APR → all present
in target with content intact, refs resolved, any unresolved piece listed as dropped.

### Tests for User Story 3 ⚠️ (write first, must FAIL before implementation)

- [X] T025 [P] [US3] Write `tests/unit/test_owned_object_walk.py`: examples (+translation TypeRA resolved), pronunciations, etymology (LanguageRS resolved), and recursive sub-senses are reproduced under the target owner with ordering preserved; anything unreproducible appends a `DroppedItemRecord` (FR-009). Strengthened this cycle (commit dc021b9) with per-factory-real-signature fakes (MCP-confirmed live against Ejagham Mini) that reject the old uniform `Create(guid, owner)` shape; a guard test (`test_owned_object_map_rows_are_disambiguable_by_owner_class`) added alongside the fix below.
- [ ] T026 [P] [US3] Write `tests/unit/test_allomorph_hung_data.py`: allomorph `PhoneEnvRC` resolved against the target environment list; APR reproduced only when all members are in the copy set, else a `DroppedItemRecord` with reason `member not in copy set` (FR-009a, research R6).

### Implementation for User Story 3

- [X] T027 [P] [US3] Build the `OWNED_OBJECT_MAP` (Sense.ExamplesOS w/ child_ref translation TypeRA; Entry.PronunciationsOS; Entry.EtymologyOS w/ LanguageRS; Sense.SensesOS recurse=True) in `src/gramtrans/Lib/owned.py` per data-model.md OwnedObjectSpec (depends on T007). Five rows: Sense.ExamplesOS (`ILexExampleSentenceFactory`, child_refs = new LexExampleSentence PublishIn/DoNotPublishInRC rows — not in the global `REFERENCE_FIELD_MAP`), LexExampleSentence.TranslationsOC (`ICmTranslationFactory`, child_refs = `references.field_specs_for("CmTranslation")` reused verbatim), Entry.PronunciationsOS (`ILexPronunciationFactory`, no child_refs), Entry.EtymologyOS (`ILexEtymologyFactory`, child_refs = `references.field_specs_for("LexEtymology")` reused verbatim), Sense.SensesOS (`ILexSenseFactory`, recurse=True). `factory` is the flexicon service-locator NAME (string) so the map stays pure data.
- [X] T028 [US3] Implement `walk_owned_children(src_owner, new_owner, ctx, tag, resolver_cache, dropped)` in `src/gramtrans/Lib/owned.py`: create each child via flexicon Operations / `project.GetService(IFooFactory)`, copy syncable props, route child ref fields through `references.decide_reference`/`apply_reference`, `apply_residue`, and recurse sub-senses through the full sense-copy path (FR-009, research R5; depends on T027, T015). Sub-sense recursion reuses `categories._apply_reference_fields("LexSense", ...)` (lazy import, no cycle) for the full REFERENCE_FIELD_MAP treatment, rather than duplicating that decide/apply loop; every created child is then recursively walked again for its OWN owned children regardless of `recurse` (that flag only gates the extra full-sense-reference pass). Cycle guard: a `_owner_guid` stack in `resolver_cache` — a child GUID already on the current recursion path is skipped + reported (`DroppedItemRecord`, reason "cyclic owned-object reference") instead of re-entered, guaranteeing termination. `tests/unit/test_owned_object_walk.py`'s 5 red tests now pass; full `tests/unit/` suite stays at baseline (1 known-unrelated failure in `test_wizard_pos_grammar_wiring.py`) + 5 new passes.
  - **Hardening (this cycle)**: `_resolve_service_type`'s "SIL.LCModel unimportable -> use the bare string" fallback broke once an EARLIER, unrelated test in the same pytest session triggered pythonnet's real CLR bootstrap — `SIL.LCModel` then becomes genuinely importable process-wide, so the resolved factory type is a real (but unmapped-in-the-fake) interface class instead of the string key the test doubles' `GetService` expects. Fixed via `_get_owned_factory(target, name)`: try the resolved real type first (production-correct), retry with the bare string on ANY failure — correct across all three environments (no CLR loaded yet, CLR loaded by an earlier test this session, live host) without special-casing any of them.
  - **Per-factory-correct create (this cycle, follow-up to the T025 strengthening)**: added `models.OwnedCreateKind` (OWNER_TAKING / UNOWNED_THEN_ADD / OWNER_PLUS_TYPE) + `OwnedObjectSpec.create_kind`/`type_ref_field`. `owned._create_owned_child` dispatches per kind: ExampleSentence/sub-Sense stay OWNER_TAKING (`Create(guid, owner)`); Pronunciation/Etymology are UNOWNED_THEN_ADD (`Create(guid)` then `owner.<field>.Add(obj)`); CmTranslation is OWNER_PLUS_TYPE — `TypeRA` is resolved via `decide_reference`/`apply_reference` BEFORE create (inverted order vs. every other child ref), then `Create(owner, resolved_type, guid)`. GUID preservation verified in all three shapes. Lead-decided fallback policy (`_create_owner_plus_type_child`) when `TypeRA` does not resolve: substitute the target's first-available translation type + `DroppedItemRecord` ("translation type unresolved; substituted <fallback>") when the target has >=1 type; skip the translation entirely + `DroppedItemRecord` ("no translation type available in target") when it has none. QC P1a: replaced the duck-typed `hasattr(src_owner, spec.owning_field)` `OWNED_OBJECT_MAP` dispatch with `_matches_owner_class` — matches by real `ClassName` first (structurally resolves the `ILexEntry.SensesOS` vs `ILexSense.SensesOS` collision), falling back to `hasattr` only when no `ClassName` is available (host-free fakes) — plus a static guard test (`test_owned_object_map_rows_are_disambiguable_by_owner_class`) asserting no two rows share an identical (owner_class, owning_field) pair. QC P2: `_copy_one_owned_child`'s syncable-property copy no longer swallows `AttributeError`/`TypeError` silently — logs AND emits a `DroppedItemRecord` ("child content not copied: ...") for a would-be content-less child shell. Full `tests/unit/` suite: 1433 passed (1432 baseline + 1 new guard test), 1 failed (same known-unrelated `test_wizard_pos_grammar_wiring.py` failure), 9 skipped, 14 xfailed, 14 xpassed — baseline preserved.
- [ ] T029 [US3] Implement `reproduce_allomorph_hung_data(src_allo, new_allo, ctx, tag, resolver_cache, dropped)` in `src/gramtrans/Lib/owned.py`: resolve `PhoneEnvRC` via the resolver (link/report, do not create environments here); discover APRs in `MorphologicalDataOA.AdhocCoProhibitionsOC` whose `FirstAllomorphRA`/`RestOfAllosRS`/`AllomorphsRS` reference a copied allomorph/morpheme and reproduce only all-members-in-copy-set, else report (FR-009a, research R6; depends on T027, T015).
- [ ] T030 [US3] Invoke `walk_owned_children` (from the entry/sense closure) and `reproduce_allomorph_hung_data` (from the allomorph copy) in `src/gramtrans/Lib/categories.py`, and surface owned-object decisions in the Preview plan / execute in move (`preview.py`/`transfer.py`, Principle III; depends on T028, T029, T017).
  - **owned-CHILD portion DONE (this cycle)**: `categories._walk_lex_entry_closure` now calls `owned.walk_owned_children` twice -- ENTRY level (`owning_fields={"PronunciationsOS", "EtymologyOS"}`) and SENSE level (unfiltered -- `ExamplesOS` + recursive sub-senses via `OwnedObjectSpec.recurse`). The `owning_fields` filter (new optional kwarg on `walk_owned_children`, default `None` = unfiltered, back-compat with all 5 pre-existing `test_owned_object_walk.py` calls) exists specifically to stop the entry-level call from ALSO matching `OWNED_OBJECT_MAP`'s `LexSense.SensesOS` row -- a real `ILexEntry` duck-types a `SensesOS` attribute too (its own top-level senses), which would otherwise re-create every top-level sense a second time as a phantom owned child, double-processing the senses `_walk_lex_entry_closure`'s own `for src_sense in src_entry.SensesOS` loop already creates directly. Preview-side: `owned.plan_owned_object_decisions` (+ `_plan_child_ref_decisions` / `_plan_full_sense_reference_decisions`), a read-only twin of the write walk (decide-only, never creates/writes), wired the same way (entry-level filtered, sense-level unfiltered) into `categories._plan_entry_reference_decisions`, appending to the same `PlannedAction.reference_decisions` tuple the top-level entry/sense/allomorph decisions already populate. `transfer.py` needed NO changes -- its `execute()` already threads `_dropped`/`_resolver_cache`/`_ws_map` onto `exec_ctx` and dispatches AFFIXES/STEMS `execute_action` straight into `_walk_lex_entry_closure`, so the owned-object writes flow through the existing generic leaf-dispatch loop unchanged. Allomorph leg (`reproduce_allomorph_hung_data`, T029) NOT invoked -- explicit `# TODO(024 cycle-10)` marker left in `categories._walk_entry_allomorphs._mk` at the plug-in point. Full `tests/unit/` suite: 1432 passed, 1 failed (same known-unrelated `test_wizard_pos_grammar_wiring.py` failure), 9 skipped, 14 xfailed, 14 xpassed -- identical to pre-change baseline (no new tests added this cycle; no existing test's expected output needed adjustment).
- [ ] T031 [US3] Reproduce lexical relations for copied members only (preserve mapping/tree/pair structure; report members not in the copy set) in `src/gramtrans/Lib/categories.py` via the resolver, reusing residue's registered `LexReference` carrier (FR-008; depends on T016).

**Checkpoint**: US1–US4 complete; owned children + allomorph-hung data + lexical relations reproduced; quickstart Scenario 3 passes.

---

## Phase 7: User Story 5 — Model-driven fidelity verification (Priority: P2)

**Goal**: A dev/CI harness enumerates every populated owning/reference field from the LCM
model on each source object and asserts the target copy reproduces the same set (or the gap is
matched by a `DroppedItemRecord`).

**Independent Test**: Run the census over a copied entry/sense pair → zero *unexplained*
populated-in-source-but-empty-in-target owning/reference fields.

### Tests for User Story 5 ⚠️

- [ ] T032 [P] [US5] Add a pytest entry in `tests/verification/fidelity_census.py` that runs `run_census` over a constructed custom/modified fixture pair and asserts zero unexplained gaps (SC-004); mark it appropriately so it is an offline harness, not a per-transfer runtime gate.

### Implementation for User Story 5

- [ ] T033 [US5] Implement `populated_ref_owned_fields(obj, cache) -> set[FieldKey]` in `tests/verification/fidelity_census.py`: `GetFields(ClassID, includeSuperclasses=True, kgrfcptAll)`, keep field types {23,24,25,26,27,28}, populated test via `ISilDataAccess` (`get_ObjectProp != 0` for atomic, `get_VecSize > 0` for coll/seq), include custom fields (research R8, contract fidelity-census.md).
- [ ] T034 [US5] Implement `census_pair(src_obj, tgt_obj, cache) -> CensusResult` (gaps = populated(src) − populated(tgt), owned+reference only) and `run_census(src_project, tgt_project, guid_pairs) -> CensusReport` grouped by class with reconciled-vs-unexplained split, asserting each gap maps to a `DroppedItemRecord` (SC-004; depends on T033).

**Checkpoint**: All five user stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Regression guarding, docs, and end-to-end validation.

- [ ] T035 [P] Add a regression test (or extend an existing report snapshot test) asserting SC-006: a no-custom-lists transfer (plain Ejagham Mini → target) produces an empty `dropped_items` and otherwise-identical report output.
- [ ] T036 [P] Update module/docstring documentation and `docs/` (ARCHITECTURE / API notes) to describe `references.py`, `owned.py`, the field maps, and the dropped-item report channel.
- [ ] T037 Run the full quickstart.md validation (Scenarios 1–5 + regression gate) against the Ejagham Mini → disposable `*-GT-Test` pair via the GUI harness; capture pre/post evidence.
- [ ] T038 Run the full `tests/unit/` + `tests/verification/` suites; confirm green, then merge the `024-lexicon-reference-fidelity` worktree branch back to `main`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories.
- **User Stories (Phase 3–7)**: all depend on Foundational.
  - US1 (P1) is the MVP and the resolver foundation the others reuse.
  - US2 (P1) depends on US1's `apply_reference` (T015/T016).
  - US4 (P1) depends on US1's REPORT_DROPPED outcome (T013/T015) + Phase 2 report plumbing.
  - US3 (P2) depends on US1's resolver (T015) for child references.
  - US5 (P2) depends only on Phase 2 types + the transfer producing `DroppedItemRecord`s to reconcile against (best run after US1/US3).
- **Polish (Phase 8)**: depends on all desired user stories.

### Critical path

T001→T002→(T004..T008)→T012→T013→T014→T015→T016→T017 (US1 MVP) → then US2/US4/US3/US5 fan out.

### Parallel Opportunities

- Phase 1: T002, T003 in parallel.
- Phase 2: T004, T005 in parallel; T006/T007 after T004; T009/T010 after T004/T005.
- All five story test-writing tasks (T011, T018, T021, T025, T026, T032) are `[P]` — different files, write-first.
- Once Foundational is done and US1's resolver (T015/T016) lands, US2, US3, US4, US5 can proceed largely in parallel by different developers.
- Phase 8: T035, T036 in parallel.

---

## Parallel Example: kicking off the story test suites (after Phase 2)

```bash
Task: "Write tests/unit/test_reference_resolver.py"       # T011 [US1]
Task: "Write tests/unit/test_blanking_fix.py"             # T018 [US2]
Task: "Write tests/unit/test_dropped_item_report.py"      # T021 [US4]
Task: "Write tests/unit/test_owned_object_walk.py"        # T025 [US3]
Task: "Write tests/unit/test_allomorph_hung_data.py"      # T026 [US3]
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL) → 3. Phase 3 US1 → **STOP & VALIDATE**
   quickstart Scenario 1 (custom item created, renamed default linked+reported).

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → referenced-item fidelity (MVP) → validate Scenario 1.
3. US2 → blanking fix → validate Scenario 2.
4. US4 → never-silent report → validate Scenario 4.
5. US3 → owned children + allomorph-hung data → validate Scenario 3.
6. US5 → census harness → validate Scenario 5 + regression gate SC-006.

Each story is independently testable and adds value without breaking the prior ones.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- [Story] label maps every user-story task to US1–US5 for traceability.
- Tests are written first within each story and must FAIL before implementation (TDD per plan).
- All code/test work happens on the `024-lexicon-reference-fidelity` worktree; commit after
  each task or logical group; merge to `main` only at T038 after the suites are green.
- Principle III: every resolver/owned decision appears in Preview before any write.
