# Phase 0 Research: Sense Pictures

**Feature**: `029-sense-pictures` | **Date**: 2026-07-16

All LCM shapes below were **confirmed live via FLExToolsMCP** (`flexicon` api_mode,
read-only, project `Ejagham Mini`) on 2026-07-16 using `flextools_get_object_api` and
`flextools_search_by_capability`. This discharges the spec Notes obligation to re-confirm
shapes at plan time.

---

## R1 — The `LexSense.PicturesOS` → `CmPicture` object graph

**Decision**: Reproduce each `CmPicture` in `LexSense.PicturesOS` as an owned deep-copy,
carrying its display fields, in source order.

**MCP evidence**:
- `ILexSense.PicturesOS` — **ordered** collection of owned objects (children). Ordered, so
  reproduction MUST preserve source order (spec edge case + FR-001).
- `ICmPicture` properties (13, all `requires_cast`): `Caption` (`IMultiString`), `Description`
  (`IMultiString`), `LayoutPos` (`PictureLayoutPosition` enum), `LocationMin` (`Int32`),
  `LocationMax` (`Int32`), `LocationRangeType` (`PictureLocationRangeType` enum), `ScaleFactor`
  (`Int32`), `PictureFileRA` (single referenced object → `ICmFile`), `PublishIn`,
  `DoNotPublishInRC`, plus derived read-only helpers (`EnglishDescriptionAsString`,
  `LayoutPosAsString`, `SenseNumberTSS`).
- `ICmPicture` methods include `UpdatePicture(srcFilename, captionTss, sFolder, ws)` — the
  LCM-native "set the image + caption, copying the file into `sFolder`" operation.

**Rationale**: The "layout/description fields" the spec references are concretely
`Caption`, `Description`, `LayoutPos`, `LocationMin`, `LocationMax`, `LocationRangeType`,
`ScaleFactor`. `Caption`/`Description` are multistrings → copy via 024's
writing-system-mapped multistring helper. The enum/int scalars copy directly.
`PublishIn`/`DoNotPublishInRC` are publication-list references handled the same way 024
handles other publication references (link-if-present, report-if-not) — treated as best-effort
and out of the MVP unless a fixture populates them (deferred; see R7).

**Alternatives considered**: A generic `OWNED_OBJECT_MAP` (owned.py) `FieldSpec` deep-copy —
rejected because that machinery has no leg for the backing **file** asset (R2), which is the
whole point of routing pictures to their own feature.

---

## R2 — Copying the backing image asset (the novel half)

**Decision**: Delegate the asset copy to flexicon's **`LexSenseOperations.AddPicture(sense,
image_path, caption, wsHandle)`** on the happy path — it creates the `CmPicture`, copies the
image into the target's `LinkedFiles` picture folder, and wires the `CmFile` in one call —
resolving the source image path against the **source** project's `LinkedFiles` root.

**MCP evidence** (`search_by_capability`):
- `LexSenseOperations.AddPicture(sense_or_hvo, image_path, caption=None, wsHandle=None)` —
  "Add a picture (image) to a lexical sense." (Creates picture + copies file + wires `CmFile`.)
- `MediaOperations.CopyToProject(external_path, internal_subdir='AudioVisual', label=None,
  wsHandle=None)` — "Copy an external file into the project's LinkedFiles directory and create
  a media reference." (Lower-level asset-copy primitive if `AddPicture` is unsuitable.)
- `FLExProject.GetLinkedFilesDir()` and `ProjectSettingsOperations.GetLinkedFilesRootDir()` —
  resolve a project's `LinkedFiles` root. `ILangProject.LinkedFilesRootDir` (`String`) is the
  raw property.
- `ICmFile` properties: `InternalPath` (`String`, relative to the `LinkedFiles` root),
  `OriginalPath`, `AbsoluteInternalPath`, `Name`, `Copyright`, `Description`.
- Ownership chain: `ILangProject.PicturesOC` → `ICmFolder` (`FilesOC` = owned `CmFile`s,
  `SubFoldersOC`, `Name`). The picture folder is the standard "Local Pictures" `CmFolder`.

**Rationale**: `AddPicture` copies the binary AND does the `CmFile`/folder wiring LCM-correctly,
so GramTrans does not hand-roll `CmFolder`/`CmFile` factory wiring or path encoding on the happy
path. It mints a **fresh** `CmPicture` GUID (not GUID-preserved) — which is exactly why
idempotency must key on a structural fingerprint, not source GUID (R4, spec Clarifications Q1).
The source image path is `source.LinkedFilesRootDir` joined with the source `CmFile.InternalPath`
(or `AbsoluteInternalPath` directly).

**Open sub-question for implementation (flagged, non-blocking)**: confirm on the installed
`pyflexicon` whether `AddPicture` (a) copies the file itself vs. requires a pre-existing path,
(b) applies collision handling, and (c) sets only `Caption` or also the layout fields. If it
sets only the caption, the reproduce leg sets the remaining layout fields on the returned
`CmPicture` afterward (direct property set through a `cast_to_concrete` cast). Capture the probe
in the implementation commit.

**Alternatives considered**:
- Raw `ICmPictureFactory` + `ICmFileFactory` + manual `shutil.copy` into the resolved folder —
  more code, must replicate LCM's path-encoding rules; kept only as the **missing-binary
  fallback** (R5) where no bytes are copied.
- LCM `ICmPicture.UpdatePicture(...)` directly — viable but lower-level than the flexicon
  wrapper; `AddPicture` is the Principle-II-preferred surface.

---

## R3 — Collision handling (non-destructive, content-aware)

**Decision**: Before copying, resolve the destination filename in the target picture folder:
- **Identical content already present** (same content hash) → reuse the existing file; link its
  `CmFile` to the reproduced picture; do not re-copy.
- **Same name, different content** → copy the source image under a de-duplicated name (via
  `LexSenseOperations.RenamePicture(picture, new_filename)` or a pre-copy rename) and emit a
  report line noting the rename; never overwrite the pre-existing target file.
- **No collision** → copy under the source's filename.

**MCP evidence**: `LexSenseOperations.RenamePicture(picture, new_filename)` — "Rename the image
file for a picture and update the reference." `MediaOperations.RenameMediaFile` is the media
sibling. Content comparison uses `hashlib` over the two files (stdlib; no LCM surface).

**Rationale**: Directly implements FR-003 / SC-003 non-destructive collision policy and the
spec Clarifications. Content-hash (not filename) is the equality test (spec Assumptions).

**Alternatives considered**: Overwrite-on-collision (rejected — destroys target assets, breaks
FR-003); skip-and-report without copying (rejected — leaves the picture imageless when a rename
would have preserved it).

---

## R4 — Idempotency identity (structural fingerprint)

**Decision**: Recognize an already-reproduced picture by a **structural fingerprint** =
(image file identity: filename + content hash) + caption — scoped to the owning target sense.
A target picture whose fingerprint matches a source picture is treated as already-present and
not re-created; its asset is likewise matched by content hash in the target folder.

**Rationale**: The reproduced `CmPicture` carries no source GUID (`AddPicture` mints a fresh
one — R2), the exact situation that broke feature 026's analysis idempotency until a structural
fingerprint was added. This is resolution-independent and needs no durable source-GUID marker.
Recorded in spec Clarifications Q1.

**Alternatives considered**: match by `CmFile` only (rejected — ignores caption divergence);
stash a source-GUID marker on the target `CmPicture` (rejected — extra write, no existing field
for it, and 026 already proved the fingerprint approach sufficient).

---

## R5 — Missing / unreadable / unwritable image (never-silent filesystem failures)

**Decision**: When the source image is missing on disk, unreadable, or the target folder cannot
be written:
- **Missing source binary** → reproduce the `CmPicture` object graph via the raw
  `ICmPictureFactory`/`ICmFileFactory` fallback, wiring a `CmFile` whose `InternalPath` is the
  intended target path (no bytes copied), so the picture heals once the linguist supplies the
  file; emit a `DroppedItemRecord` for the missing binary (spec Clarifications Q2 / FR-005).
- **Unreadable source / unwritable target** → emit a `DroppedItemRecord` (owner sense, picture,
  image identity/path, reason); never throw, never silently skip.

**Rationale**: The filesystem adds failure modes the object-graph path never had; the
never-silent guarantee (Principle I, "No silent skips" gate, FR-008) must explicitly cover them.
Wiring the `CmFile` at the intended path mirrors how FieldWorks itself tolerates a missing-on-disk
`CmFile` (the picture shows a broken-image placeholder, not a crash).

**Alternatives considered**: leave `PictureFileRA` unset (rejected — spec Clarifications Q2 chose
the self-healing wired-path form); skip the whole `CmPicture` (rejected — loses recoverable
display data).

---

## R6 — Preview/Move parity (Principle III design obligation)

**Decision**: `plan_sense_picture_decisions` (Preview twin) emits, per source picture, exactly
the decision the Move leg will act on — `ADD` (new picture + asset copy), `LINK` (reuse an
identical target asset / already-present picture), or a `DroppedItemRecord` (missing/unresolvable
asset) — reading the source and the target folder **without writing anything or copying any
file**. The drop set is identical to the Move leg by construction, mirroring
`_plan_moaffix_msenv_decisions` / `reproduce_moaffix_msenv_data` (028) and
`_report_dropped_sense_scope_gaps`'s existing identical-by-construction Move/Preview calls.

**Rationale**: Principle III (NON-NEGOTIABLE) requires every intended addition/skip — including
the planned **file copy** — to appear in Preview before any write. The twin computes the
collision/fingerprint decision read-only (hashing candidate files is a read, not a write).

**Alternatives considered**: none — Principle III is non-negotiable; the only question was where
the twin lives (answer: `Lib/pictures.py`, beside the Move leg, per the Structure Decision).

---

## R7 — Deferred / out-of-scope (non-blocking)

- **`PublishIn` / `DoNotPublishInRC` on `CmPicture`** — publication-list references. Reproduced
  best-effort via 024's reference resolver if a fixture populates them; otherwise vacuous. Not
  MVP; a populated-but-unresolvable publication reference is report-dropped, never silently lost.
- **Non-picture media** (audio/video pronunciation media, entry/example media) — explicitly out
  of scope (spec Out of Scope); this feature is scoped to `LexSense.PicturesOS`.
- **Image transcoding/resizing** — out of scope; files copied byte-for-byte.
- **`AddPicture` behavioral probe** — the three sub-questions in R2 are confirmed at
  implementation time against the installed `pyflexicon` and captured in the commit body; they
  do not change scope or the contract.
