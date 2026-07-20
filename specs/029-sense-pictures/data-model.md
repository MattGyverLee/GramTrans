# Phase 1 Data Model: Sense Pictures

**Feature**: `029-sense-pictures` | **Date**: 2026-07-16

Entities and fields below are the LCM shapes confirmed in [research.md](./research.md)
(FLExToolsMCP, `flexicon`, read-only, `Ejagham Mini`). This feature reproduces one
owned-sequence field on `LexSense` plus its transitive object + asset graph.

## Entities

### `CmPicture` (owned in `LexSense.PicturesOS`)

The owned illustration object. `PicturesOS` is an **ordered** owned collection → source order
is preserved on reproduction.

| Field | Type | Disposition on reproduce |
|---|---|---|
| `Caption` | `IMultiString` | Deep-copy, writing-system-mapped (024's `_copy_multistrings_ws_mapped`). |
| `Description` | `IMultiString` | Deep-copy, writing-system-mapped. |
| `LayoutPos` | `PictureLayoutPosition` enum | Copy scalar. |
| `LocationMin` | `Int32` | Copy scalar. |
| `LocationMax` | `Int32` | Copy scalar. |
| `LocationRangeType` | `PictureLocationRangeType` enum | Copy scalar. |
| `ScaleFactor` | `Int32` | Copy scalar. |
| `PictureFileRA` | atomic ref → `ICmFile` | Wired to the copied/reused target `CmFile` (see asset flow). |
| `PublishIn` / `DoNotPublishInRC` | publication-list refs | Best-effort via 024 reference resolver; report-drop if unresolvable (deferred, research R7). |

**Identity**: no source GUID is preserved on the target (`AddPicture` mints a fresh GUID).
Idempotency key = **structural fingerprint** = image identity (filename + content hash) + caption,
scoped to the owning target sense (research R4).

### `CmFile` (owned in a `CmFolder`)

The LCM object describing a backing file. Owned under `LangProject.PicturesOC` → `CmFolder`
(the standard "Local Pictures" folder) → `FilesOC`.

| Field | Type | Meaning |
|---|---|---|
| `InternalPath` | `String` | Path relative to the project `LinkedFiles` root — the stored, portable path. |
| `AbsoluteInternalPath` | `String` | Absolute resolved path (read for source-file location). |
| `OriginalPath` | `String` | Original import path (informational). |
| `Name` | `IMultiUnicode` | File display name. |

**Identity**: content-addressed — a target `CmFile` whose file content hashes equal to the
source image is reused (no duplicate file, no duplicate `CmFile`).

### `CmFolder` (owned in `LangProject.PicturesOC`)

| Field | Type | Meaning |
|---|---|---|
| `FilesOC` | owned collection of `CmFile` | The files in this folder. |
| `SubFoldersOC` | owned collection of `CmFolder` | Nested folders. |
| `Name` | `IMultiUnicode` | Folder name ("Local Pictures"). |

### Backing image asset (on disk)

The binary image under `<LinkedFilesRootDir>/<picture-folder>/<filename>`. Source root resolved
via `GetLinkedFilesDir()` / `ILangProject.LinkedFilesRootDir`; the file is copied into the target
project's corresponding folder by `LexSenseOperations.AddPicture` (research R2).

### `DroppedItemRecord` (reused — models.py, from 024)

The never-silent report unit. For this feature: `owner_kind="LexSense"`, `owner_guid`/`owner_label`
= the sense, `field_name="PicturesOS"`, `item_name`/`item_guid` = the picture / image identity,
`reason` = why the picture or asset could not be reproduced (missing binary, unreadable,
unwritable, unresolvable publication ref, or a reported collision rename note).

### `ReferenceDecisionRecord` (reused — models.py)

Preview twin output, one per source picture: `ADD` (new picture + asset copy), `LINK` (reuse
identical target asset / already-present picture), carried on `PlannedAction.reference_decisions`.

## State / disposition table (per source picture)

| Source state | Target state | Disposition |
|---|---|---|
| Picture with image present on source disk, absent in target | — | **ADD** — create `CmPicture`, copy asset, wire `CmFile`. |
| Picture whose image is byte-identical to an existing target file | file present | **ADD picture, LINK asset** — reuse existing `CmFile`, no re-copy. |
| Picture whose filename collides with different target content | different file present | **ADD picture, copy asset under de-duplicated name**, report the rename. |
| Picture already reproduced (fingerprint match under the sense) | present | **SKIP** — no net-new picture/`CmFile`/file (idempotent). |
| Picture whose source image is missing on disk | — | **ADD picture + `CmFile` at intended path (no bytes)**, report the missing binary. |
| Picture whose image is unreadable / target folder unwritable | — | **REPORT_DROPPED** — no partial write. |
| Empty/absent source `PicturesOS` | populated | **no-op** — never blank the target (non-destructive). |

## Validation rules

- **Order** (FR-001): reproduced pictures preserve source `PicturesOS` order.
- **Writing systems** (Principle I): caption/description multistrings are ws-validated + mapped
  before write.
- **Non-destructive** (FR-003/FR-006): never overwrite an existing target file; never blank a
  populated target `PicturesOS`.
- **Dedup** (FR-004/SC-005): an image used by K pictures → at most one target file + `CmFile`.
- **Idempotent** (FR-007/SC-006): re-run yields zero net-new pictures/`CmFile`s/files.
- **Never-silent** (FR-008/SC-004): every un-reproduced picture/asset → a `DroppedItemRecord`.
