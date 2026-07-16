# Quickstart & Validation: Sense Pictures

**Feature**: `029-sense-pictures` | **Date**: 2026-07-16

How to validate the feature end-to-end. Two tiers: the **offline** gate (primary, unattended)
and the **attended live proof** (needs_human, constructed fixture with real image files).

## Prerequisites

- Repo on the `029-sense-pictures` worktree (implementation lives on the feature worktree per
  the Git Workflow Protocol; spec artifacts stay on `main`).
- `pip install -e D:/Github/_Projects/_LEX/flexlibs2` (pyflexicon>=4.1) for the live tier only.
- The offline tier needs no live host — the asset-copy seam is faked (temp files + a stubbed
  `AddPicture`).

## Tier 1 — Offline gate (primary, unattended)

Run the unit + census suites:

```powershell
python -m pytest tests/unit/test_029_sense_picture_reproduction.py tests/unit/test_029_picture_asset_copy.py -q
python -m pytest tests/verification/fidelity_census.py -q
```

**Expected**:
- `test_029_sense_picture_reproduction.py` — deep-copy of caption/description (ws-mapped) +
  layout scalars; order preserved; Preview/Move parity (identical decision + drop sets);
  idempotency by fingerprint (re-run = 0 net-new); empty-source no-blank.
- `test_029_picture_asset_copy.py` — asset copied on ADD; identical-content reused (no re-copy);
  same-name/different-content renamed + reported; missing source binary → `CmPicture`+`CmFile`
  wired at intended path (no bytes) + one `DroppedItemRecord`; unreadable/unwritable → reported.
- `fidelity_census.py` — the `LexSense.PicturesOS` row asserts **COPIED** (was DROP_REPORTED);
  a census over a sense carrying pictures reports zero unexplained
  populated-in-source-but-empty-in-target `PicturesOS`.
- Full suite: no new failures beyond the documented environment baseline.

## Tier 2 — Attended live proof (needs_human, constructed fixture)

**Never run under an unattended loop.** The Ejagham corpora populate 0 sense pictures, so a
fixture with **real image files on disk** must be constructed, mirroring 027's/028's
constructed-fixture approach.

### Build the fixture (disposable source)

1. Restore a disposable source project (e.g. `Ejagham029Src`) from a backup; leave real
   `Ejagham Mini` untouched.
2. Via FLExToolsMCP `run_module` (write-enabled) on the disposable source, add pictures to a
   sense with `LexSenseOperations.AddPicture(sense, <real image path>, caption=...)` — creating
   at least: one picture with a caption + layout fields; two pictures sharing one image (dedup);
   one picture whose backing file you then delete from disk (missing-binary case).

### Run the transfer (disposable target)

3. Restore `Target` clean (from its backup).
4. Pre-seed the target `LinkedFiles` picture folder with (a) a byte-identical copy of one source
   image and (b) a same-name/different-content file — to exercise reuse and rename.
5. Drive the real STEMS/AFFIXES engine source → target via FLExToolsMCP `run_module` (route the
   driver at the SOURCE handle; restore/open the TARGET in the driver — the coverage/026 lesson).

### Acceptance checks (fresh read-only re-open of the target)

- **AC1 (object)**: target sense owns `CmPicture`s matching source count, captions, layout
  fields, and **order**.
- **AC2 (asset)**: each reproduced picture's image is present under the target `LinkedFiles`
  root and `PictureFileRA` → `CmFile.InternalPath` resolves; picture displays.
- **AC3 (dedup)**: the two pictures sharing an image → one target file + one `CmFile`.
- **AC4 (collision)**: the byte-identical pre-seed is reused (no second file); the
  same-name/different-content pre-seed is untouched and the source image landed under a
  de-duplicated name, with the rename reported.
- **AC5 (missing binary)**: the deleted-file picture → `CmPicture` + `CmFile` wired at the
  intended path (no bytes copied) + one `DroppedItemRecord` naming the sense/picture/path.
- **AC6 (idempotent)**: re-Move → 0 net-new `CmPicture`/`CmFile`/files; picture set stable.
- **AC7 (non-destructive)**: no pre-existing target `LinkedFiles` file overwritten; a sense with
  empty source `PicturesOS` leaves a populated target `PicturesOS` untouched.
- **AC8 (census)**: post-run census reports zero unexplained
  populated-in-source-but-empty-in-target `PicturesOS`.

### Evidence

Write pre/post counts, the dropped-items report, and pre/post Import Residue to
`specs/029-sense-pictures/verification-log.md`. Restore `Target` clean afterward; the disposable
source may be left on disk (note it for cleanup).

## References

- Field shapes & copy mechanism: [research.md](./research.md)
- Fields & dispositions: [data-model.md](./data-model.md)
- Entry points & guarantees: [contracts/sense-picture-reproduction.md](./contracts/sense-picture-reproduction.md)
