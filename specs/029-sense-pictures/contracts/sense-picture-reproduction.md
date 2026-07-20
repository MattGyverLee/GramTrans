# Contract: Sense Picture Reproduction

**Feature**: `029-sense-pictures` | **Date**: 2026-07-16

Defines the two entry points that reproduce a copied sense's pictures — the Move leg and its
read-only Preview twin — mirroring the 028 `reproduce_moaffix_msenv_data` /
`_plan_moaffix_msenv_decisions` pair. Both live in the new `Lib/pictures.py`.

## Entry points

### Move leg

```
reproduce_sense_pictures(src_sense, new_sense, ctx, tag, resolver_cache, dropped) -> None
```

- **Called from**: the sense loop of `categories._walk_lex_entry_closure` (the STEMS/AFFIXES
  execute path), immediately alongside the existing `_report_dropped_sense_scope_gaps(src_sense,
  dropped)` call — which continues to report `AppendixesRC` / `ThesaurusItemsRC` (routed to 030)
  but **no longer reports `PicturesOS`** (reproduced here).
- **Effect**: for each `CmPicture` in `src_sense.PicturesOS` (in order), reproduce the picture on
  `new_sense` per the disposition table (data-model.md), copying the backing asset. Writes to the
  target project and the target `LinkedFiles` folder.
- **Guarantees**:
  - **G1 (never-silent)**: any picture or asset not reproduced → a `DroppedItemRecord` on
    `dropped`. No silent omission.
  - **G2 (non-destructive)**: empty/absent source `PicturesOS` → no-op; never blank a populated
    target; never overwrite an existing target `LinkedFiles` file.
  - **G3 (order)**: reproduced pictures preserve source order.
  - **G4 (dedup)**: an image shared by K pictures is copied at most once; the `CmFile` is reused.
  - **G5 (idempotent)**: a picture whose structural fingerprint (image identity + caption) already
    exists under `new_sense` is not re-created; re-run counts are stable.
  - **G6 (missing binary)**: a missing source image still yields a `CmPicture` + `CmFile` wired at
    the intended target path (no bytes) + a reported drop (research R5).
  - **G7 (never raises)**: every per-picture / per-file failure is caught and reported, matching
    the module posture elsewhere.

### Preview twin (read-only)

```
plan_sense_picture_decisions(src_sense, ctx, resolver_cache, dropped) -> list[ReferenceDecisionRecord]
```

- **Called from**: the sense loop of the Preview path (`Lib/preview.py`, the same place the
  existing sense-scope-gap drops are computed for Preview), feeding
  `PlannedAction.reference_decisions`.
- **Effect**: emits the `ADD` / `LINK` decision the Move leg will act on for each source picture
  (including whether the asset will be copied, reused, or renamed), plus **identical**
  `DroppedItemRecord`s for un-reproducible pictures/assets. **Writes nothing and copies no file**
  (candidate-file hashing is a read).
- **Parity (Principle III)**: the drop set and the ADD/LINK decision set are identical to the Move
  leg by construction — same fingerprint/collision logic, computed read-only.

## Asset-copy seam (internal to `Lib/pictures.py`)

- **Happy path**: `LexSenseOperations.AddPicture(new_sense, source_image_abspath, caption,
  wsHandle)` — creates the `CmPicture`, copies the file into the target `LinkedFiles` picture
  folder, wires the `CmFile`. Layout scalars set on the returned picture afterward if `AddPicture`
  sets only the caption (research R2 probe).
- **Collision**: resolve destination filename first (content hash); identical → reuse; same-name
  different-content → `RenamePicture` to a de-duplicated name + report (research R3).
- **Missing binary**: `project.GetService(ICmPictureFactory/ICmFileFactory)` fallback — create the
  `CmPicture` + `CmFile` with `InternalPath` set to the intended target path, copy no bytes, report
  the drop (research R5).
- **Path resolution**: source path = source `LinkedFilesRootDir` ⨝ source `CmFile.InternalPath`
  (or `AbsoluteInternalPath`); target root via the target's `GetLinkedFilesDir()`.

## Non-goals (this contract)

- Does NOT reproduce `AppendixesRC` / `ThesaurusItemsRC` (feature 030).
- Does NOT reproduce non-picture media (audio/video) — scoped to `PicturesOS`.
- Does NOT transcode/resize images — byte-for-byte copy only.
- Does NOT retroactively repair targets populated by a prior run (FR-009, forward-copy only).

## Census contract

`tests/verification/fidelity_census.py`: the `("LexSense", "PicturesOS")` classification row
flips **DROP_REPORTED → COPIED**, citing `pictures.reproduce_sense_pictures` /
`plan_sense_picture_decisions` as the create sites, preserving the never-silent guard. A census
run over a copied sense carrying pictures MUST report zero populated-in-source-but-empty-in-target
`PicturesOS` (SC-007).
