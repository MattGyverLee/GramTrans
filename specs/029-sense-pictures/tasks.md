# Tasks: Sense Pictures (029)

**Feature**: reproduce a copied sense's pictures — the `CmPicture` owned object graph
(caption/description multistrings + layout scalars, in order) **and** the backing image asset
copied into the target `LinkedFiles` area — under 024's never-silent guarantee. Closes the
024-census DROP_REPORTED gap for `LexSense.PicturesOS`.

**Inputs**: [plan.md](plan.md) · [spec.md](spec.md) · [research.md](research.md) ·
[data-model.md](data-model.md) ·
[contracts/sense-picture-reproduction.md](contracts/sense-picture-reproduction.md) ·
[quickstart.md](quickstart.md)

**Discipline**: TDD, RED-before-GREEN — author the failing test in the same unit as its
implementation and confirm it fails first. All code work on the worktree
`../GramTrans-029-sense-pictures` (branch `029-sense-pictures`); spec artifacts stay on `main`.
The behavioral change is a **new `src/gramtrans/Lib/pictures.py`** module (Move leg
`reproduce_sense_pictures` + Preview twin `plan_sense_picture_decisions` + the asset-copy seam)
wired into `categories.py`'s sense loop (Move) and `preview.py`'s sense loop (Preview); the
`PicturesOS` portion is removed from `categories._report_dropped_sense_scope_gaps` (leaving
`AppendixesRC`/`ThesaurusItemsRC` for 030). The only change outside `Lib/` is the
`tests/verification/fidelity_census.py` flip. **Reuse — do NOT reinvent**:
`LexSenseOperations.AddPicture` / `RenamePicture`, `MediaOperations.CopyToProject`,
`FLExProject.GetLinkedFilesDir` (R2/R3); 024's `_copy_multistrings_ws_mapped` ws-mapped copy;
`categories._report_dropped_sense_scope_gaps` seam; `models.DroppedItemRecord` /
`ReferenceDecisionRecord` / `ReferenceAction`.

**MVP** = User Story 1 + User Story 2 (Phases 3–4): a picture's `CmPicture` object **and** its
backing image reproduced end-to-end. US1 alone reproduces the object (pointing at a not-yet-copied
file); US2 makes it display. Delivered together they prove the reproduce-leg + Preview-twin
pattern the remaining stories extend.

**⚠️ Note on parallelism**: all story legs edit the SAME two functions
(`reproduce_sense_pictures` / `plan_sense_picture_decisions`) in the SAME new file
(`Lib/pictures.py`). Their RED test-authoring tasks are `[P]` (distinct test files / functions),
but their GREEN implementation tasks are **sequential** — NOT `[P]` — because they touch the same
functions.

**⚠️ Attended-only**: the live `0 → N` proof (T020) needs a **constructed fixture with real image
files** (Ejagham corpora populate 0 pictures) and is a needs_human item — NEVER run under an
unattended loop.

---

## Phase 1: Setup

- [X] T001 Create the implementation worktree `../GramTrans-029-sense-pictures` on new branch
      `029-sense-pictures` from `main`; confirm `pip install -e D:/Github/_Projects/_LEX/flexlibs2`
      resolves (live tier) and `python -m pytest tests/unit -q` is green modulo the documented
      environment baseline (6 `test_013_apply_syncable_signature` flexicon-tree-absent + 1
      `test_wizard_pos_grammar_wiring`). Record the exact baseline count in task notes; any OTHER
      failure = pre-existing, flag it.
- [X] T002 [P] Add import-smoke scaffold `tests/unit/test_029_sense_picture_reproduction.py`
      (collects clean; covers the object-graph deep-copy + Preview/Move parity + idempotency +
      empty-source families).
- [X] T003 [P] Add import-smoke scaffold `tests/unit/test_029_picture_asset_copy.py`
      (collects clean; covers asset copy / reuse-identical / rename-on-collision / missing-binary
      via a faked `AddPicture` seam + temp files — no live host).

## Phase 2: Foundational (blocking prerequisites)

**⚠️ CRITICAL**: No user-story leg can begin until T004–T006 are complete.

- [X] T004 Gate task — confirm the reuse surface is present: flexicon
      `LexSenseOperations.AddPicture` / `RenamePicture`, `MediaOperations.CopyToProject`,
      `FLExProject.GetLinkedFilesDir` (probe against installed `pyflexicon` per research R2's three
      sub-questions: does `AddPicture` copy the file, handle collisions, set only caption?);
      024's `_copy_multistrings_ws_mapped` (or the current ws-mapped multistring copy helper);
      `categories._report_dropped_sense_scope_gaps` + its Move/Preview call sites
      (categories.py ~5866 sense loop; the preview.py sense loop); `models.DroppedItemRecord` /
      `ReferenceDecisionRecord` / `ReferenceAction`. Record a one-line PASS + line-ref per item; if
      any is absent, STOP and escalate (design assumption R2/R3/R6 broken).
- [X] T005 Create `src/gramtrans/Lib/pictures.py` with the two public entry points as no-op-safe
      skeletons — `reproduce_sense_pictures(src_sense, new_sense, ctx, tag, resolver_cache, dropped)`
      (Move) and `plan_sense_picture_decisions(src_sense, ctx, resolver_cache, dropped) -> list`
      (Preview twin) — plus the private asset-copy seam helpers (`_content_hash(path)`,
      `_source_image_path(src_cmfile, src_handle)`, `_resolve_target_collision(...)`) as stubs, all
      guarded to never raise (module posture per contract G7). Empty/absent source `PicturesOS` →
      return with no effect.
- [X] T006 Wire the dispatch seam (no behavior yet beyond the skeleton): in
      `categories._walk_lex_entry_closure`'s sense loop call `pictures.reproduce_sense_pictures(...)`
      (lazy import, same idiom as the `owned` import) and REMOVE the `PicturesOS` entry from
      `_SENSE_SCOPE_GAP_FIELDS` so `_report_dropped_sense_scope_gaps` no longer double-reports it
      (keep `AppendixesRC`/`ThesaurusItemsRC`); in the `preview.py` sense loop call
      `pictures.plan_sense_picture_decisions(...)` and feed the result onto
      `PlannedAction.reference_decisions`. Add a RED test that a sense with a picture routes through
      the new seam (asserts the drop for `PicturesOS` is gone / a decision is emitted), then GREEN.

**Checkpoint**: the seam is live and the census `PicturesOS` row is no longer a pure drop path;
stories now fill in real reproduction.

---

## Phase 3: User Story 1 — The picture object comes along with the sense (Priority: P1) 🎯 MVP

**Goal**: reproduce each `CmPicture` on the target sense — `Caption`/`Description` (ws-mapped),
`LayoutPos`/`LocationMin`/`LocationMax`/`LocationRangeType`/`ScaleFactor` scalars — preserving
`PicturesOS` order.

**Independent Test**: copy a sense owning a captioned picture (image copy faked/stubbed); target
sense owns a `CmPicture` with the same caption + layout fields at the same position.

- [X] T007 [P] [US1] RED: in `test_029_sense_picture_reproduction.py`, author failing tests for
      the object deep-copy — caption + description multistrings (all WS, ws-mapped), the five layout
      scalars copied, and multi-picture source ORDER preserved in target `PicturesOS`. Use a
      `_FakeSense`/`_FakePicture` with a stubbed asset seam so no file I/O occurs. Confirm RED.
- [X] T008 [US1] GREEN: implement the `CmPicture` object reproduction in
      `pictures.reproduce_sense_pictures` — iterate `src_sense.PicturesOS` in order, create each
      picture on `new_sense` (via the seam), copy caption/description ws-mapped and the layout
      scalars (cast via `cast_to_concrete`). Make T007 pass.
- [X] T009 [US1] GREEN: implement the Preview twin object leg in `plan_sense_picture_decisions` —
      one `ReferenceAction.ADD` `ReferenceDecisionRecord` per source picture (owner=sense,
      field=`PicturesOS`, item=picture caption/identity), read-only. Add a parity assertion in
      `test_029_sense_picture_reproduction.py` (Preview decision count == Move create count).

**Checkpoint**: pictures reproduce as objects (order + fields), Preview/Move in parity — the
object half of the MVP is testable independently.

---

## Phase 4: User Story 2 — The backing image file is copied into the target project (Priority: P1)

**Goal**: copy the source image into the target `LinkedFiles` picture folder and wire the `CmFile`
so `PictureFileRA` resolves — via `LexSenseOperations.AddPicture`, resolving the source path
against the source `LinkedFilesRootDir`.

**Independent Test**: copy a picture whose image exists on the (faked) source disk and is absent
from the target; the (faked) copy seam is invoked with the resolved source path and the target
`CmPicture.PictureFileRA` → `CmFile` resolves.

- [X] T010 [P] [US2] RED: in `test_029_picture_asset_copy.py`, author failing tests that an ADD
      picture invokes the asset-copy seam with the correctly resolved source path (source
      `LinkedFilesRootDir` ⨝ `CmFile.InternalPath`/`AbsoluteInternalPath`) and wires a target
      `CmFile`; and that an image shared by two source pictures is copied ONCE (dedup) with the
      `CmFile` reused. Fake `AddPicture` + temp files. Confirm RED.
- [X] T011 [US2] GREEN: implement the asset-copy happy path in the seam — call
      `LexSenseOperations.AddPicture(new_sense, resolved_source_path, caption, wsHandle)`; if it sets
      only the caption, set layout scalars on the returned picture afterward (fold into T008's copy);
      maintain a per-run content-hash → target-`CmFile` cache on `ctx` for dedup (SC-005). Make T010
      pass.
- [X] T012 [US2] GREEN: extend `plan_sense_picture_decisions` so a picture whose asset will be
      newly copied plans `ADD` and one whose asset already exists identically plans `LINK` (reuse) —
      computed read-only via `_content_hash` over candidate target files. Add a parity test.

**Checkpoint**: MVP complete — a picture's object AND image reproduce; the picture displays from
the target.

---

## Phase 5: User Story 4 — The linguist is told what could not be reproduced (Priority: P1)

**Goal**: never-silent for the filesystem failure modes — missing source binary (still wire a
`CmFile` at the intended target path, no bytes) and unreadable-source / unwritable-target (report).

**Independent Test**: point a picture at a missing image; the `CmPicture` + a `CmFile` at the
intended path are still created and exactly one `DroppedItemRecord` names the sense/picture/path; a
fully-reproducible picture emits none.

- [X] T013 [P] [US4] RED: in `test_029_picture_asset_copy.py`, author failing tests — (a) missing
      source binary → `CmPicture` reproduced + `CmFile` wired at intended `InternalPath` (no bytes
      copied, via the raw-factory fallback) + exactly one `DroppedItemRecord`; (b) unreadable source
      / unwritable target → `DroppedItemRecord` (owner/field/identity/reason), no throw, no partial
      write; (c) parity — `plan_sense_picture_decisions` emits the identical drop set. Confirm RED.
- [X] T014 [US4] GREEN: implement the missing-binary fallback (`project.GetService(ICmPictureFactory
      /ICmFileFactory)` — create picture + `CmFile` with `InternalPath` set, copy no bytes) and the
      unreadable/unwritable report path in the seam; each emits via `_append_dropped`. Make T013's
      Move assertions pass.
- [X] T015 [US4] GREEN: mirror the same drops in `plan_sense_picture_decisions` so the Preview drop
      set is identical by construction. Make T013's parity assertion pass.

**Checkpoint**: every un-reproducible picture/asset is reported; nothing is silent (SC-004).

---

## Phase 6: User Story 5 — Re-running the copy does not duplicate pictures or files (Priority: P1)

**Goal**: idempotency by structural fingerprint (image identity + caption, scoped to the target
sense) and non-destructive empty-source (no-blank).

**Independent Test**: copy an illustrated sense twice; target `PicturesOS`, `CmFile` count, and the
`LinkedFiles` file set are identical after run 2 as after run 1; an empty source `PicturesOS` leaves
a populated target untouched.

- [ ] T016 [P] [US5] RED: in `test_029_sense_picture_reproduction.py`, author failing tests —
      (a) a target sense already carrying a picture with a matching fingerprint (image
      filename+content-hash + caption) is NOT re-created on re-run (0 net-new picture/`CmFile`/file);
      (b) empty/absent source `PicturesOS` leaves a populated target `PicturesOS` untouched. Confirm
      RED.
- [ ] T017 [US5] GREEN: implement the fingerprint skip in `reproduce_sense_pictures` (compute the
      source fingerprint; scan `new_sense.PicturesOS` for a match before creating) and the
      empty-source guard; ensure the Preview twin reports SKIP/no-op consistently. Make T016 pass.

**Checkpoint**: re-runs are stable and non-destructive (SC-006).

---

## Phase 7: User Story 3 — Existing target files are handled without clobbering (Priority: P2)

**Goal**: content-aware, non-destructive collision handling — identical target file reused;
same-name/different-content copied under a de-duplicated name (reported); never overwrite.

**Independent Test**: pre-seed the (faked) target folder with a byte-identical file and a
same-name/different-content file; the identical one is reused (no re-copy) and the different one
triggers a de-duplicated-name copy with the rename reported; neither pre-existing file is modified.

- [ ] T018 [P] [US3] RED: in `test_029_picture_asset_copy.py`, author failing tests — identical
      target content → reuse existing `CmFile`, no re-copy; same-name/different-content → source
      copied under a de-duplicated name via `RenamePicture`, a report line notes the rename, and the
      pre-existing target file is byte-unchanged. Confirm RED.
- [ ] T019 [US3] GREEN: implement `_resolve_target_collision` (content-hash compare → reuse |
      dedup-rename | plain-copy) and wire it into the seam ahead of `AddPicture`; surface the rename
      as a report/`DroppedItemRecord`-style note. Extend `plan_sense_picture_decisions` to plan the
      LINK-reuse vs. renamed-ADD read-only. Make T018 pass.

**Checkpoint**: all five stories independently functional; collisions are safe.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T020 [US-live] **Attended live proof (needs_human)** — build a constructed fixture with real
      image files on a disposable source (`Ejagham029Src`, restored from backup; real Ejagham Mini
      untouched) per [quickstart.md](quickstart.md) Tier 2; restore `Target` clean; run the real
      STEMS/AFFIXES engine via FLExToolsMCP `run_module` (drive at the SOURCE handle). Confirm
      AC1–AC8 (object/order, asset displays, dedup, collision reuse+rename, missing-binary wired+
      reported, idempotent re-Move, non-destructive, census clean). Write evidence to
      `specs/029-sense-pictures/verification-log.md`; restore `Target`. **NEVER unattended.**
- [ ] T021 Flip the `("LexSense", "PicturesOS")` row in `tests/verification/fidelity_census.py`
      from DROP_REPORTED → COPIED, citing `pictures.reproduce_sense_pictures` /
      `plan_sense_picture_decisions` as create sites; keep the never-silent guard; assert a census
      over a sense carrying pictures reports zero unexplained populated-in-source-but-empty-in-target
      `PicturesOS` (SC-007). Run `python -m pytest tests/verification/fidelity_census.py -q`.
- [ ] T022 [P] Full offline gate: `python -m pytest tests/unit tests/verification -q`; confirm no
      new failures beyond the documented environment baseline; `python -m py_compile` (or byte-
      compile) `src/gramtrans/Lib/pictures.py` + `categories.py` + `preview.py` clean. Record counts.
- [ ] T023 Merge `029-sense-pictures` → `main` (`--no-ff`) after T020 PASS + offline gate green;
      remove the worktree; update `STATUS.md`. (Outward-facing — confirm with the human first.)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2, T004–T006)** blocks all stories.
- **US1 (Phase 3)** and **US2 (Phase 4)** are the MVP; US2's asset copy builds on US1's create path.
- **US4 (Phase 5)** depends on US2's asset seam (adds its failure paths).
- **US5 (Phase 6)** depends on the US1/US2 create path (adds fingerprint skip).
- **US3 (Phase 7)** depends on US2's copy seam (inserts collision resolution ahead of it).
- **Polish (Phase 8)**: T021 depends on US1–US2 landing; T020/T022/T023 depend on all stories.

### Same-file sequencing (critical)

All GREEN impl tasks (T008, T009, T011, T012, T014, T015, T017, T019) edit
`reproduce_sense_pictures` / `plan_sense_picture_decisions` in `Lib/pictures.py` → **run
sequentially**, NOT `[P]`. Only the RED test-authoring tasks (T002, T003, T007, T010, T013, T016,
T018) are `[P]` (distinct test files/functions).

### Parallel opportunities

- Setup scaffolds T002, T003 in parallel.
- Each story's RED test task `[P]` can be authored ahead of its GREEN task.
- T022 `[P]` (byte-compile) alongside doc/status work.

---

## Implementation Strategy

1. Phase 1 Setup → Phase 2 Foundational (seam live, census no longer pure-drop).
2. **MVP**: US1 (object) → US2 (asset) → STOP & validate a picture reproduces and displays.
3. Add US4 (never-silent), US5 (idempotent/non-destructive), US3 (collisions) — each independently
   testable, RED-before-GREEN, sequential GREEN on the shared functions.
4. Polish: census flip (T021) + offline gate (T022) → attended live proof (T020) → merge (T023).

## Notes

- [P] = distinct files, no dependency on an incomplete task.
- TDD: confirm each RED test FAILS before its GREEN task.
- Commit after each task or logical group on the worktree; spec artifacts stay on `main`.
- Reuse the flexicon picture surface (`AddPicture`/`RenamePicture`) and 024's ws-mapped copy — do
  not hand-roll `CmFolder`/`CmFile` wiring except in the missing-binary fallback.
- The seam is faked in unit tests (temp files + stubbed `AddPicture`) so the whole feature is
  offline-testable; only T020 needs a live host + constructed fixture.
