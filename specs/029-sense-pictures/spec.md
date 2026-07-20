# Feature Specification: Sense Pictures

**Feature Branch**: `029-sense-pictures`

**Created**: 2026-07-12

**Updated**: 2026-07-16 (stub → full specification)

**Status**: Draft (ready for planning)

**Depends on**: `024-lexicon-reference-fidelity` (reuses its never-silent fidelity
guarantee and its owned-child closure/deep-copy discipline).

## Overview

GramTrans copies lexical entries and senses from a source FieldWorks project into a
target project. Feature 024 established that **no data that hangs off a copied entry or
sense is silently lost**: owned children are reproduced and anything that cannot be
reproduced is reported to the linguist rather than swallowed.

Feature 024's model-driven fidelity census (its FR-011) surfaced a specific remaining
gap: a copied sense's **pictures** are never reproduced. A `LexSense.PicturesOS` is an
ordered sequence of owned `CmPicture` objects; each `CmPicture` carries display data
(a caption multistring plus layout/description fields) and points via
`CmPicture.PictureFileRA` to a `CmFile`, which references an **image file on disk** in
the project's `LinkedFiles` area.

024 ships **fidelity-honest** for this subsystem — it emits a dropped-item record per
populated-but-un-reproduced picture — but the actual **reproduction** work was routed
here. It is separated from 024 because reproducing a picture spans two mechanisms: the
LCM object graph (`CmPicture` → `CmFile` → `CmFolder`) that 024 operates in, **and** the
copying of the backing **binary image file** between the two projects' `LinkedFiles`
areas, which is a filesystem/asset concern outside the object-graph machinery. This
feature closes both halves: when a copied sense owns a picture, the picture object graph
**and** its backing image asset are reproduced on the target (or, where they cannot be,
reported — never silently dropped).

The gap is a genuine code-level gap that is **vacuous on the `Ejagham Mini` test project**
(0 senses populate `PicturesOS`), so no live-reachable loss exists there. Live proof
therefore requires a constructed fixture with populated sense pictures (a T037-class
attended item), exactly as feature 027 required for its complex-form path.

## Clarifications

### Session 2026-07-16

- Q: Does asset copy belong to GramTrans, or is reproducing only the LCM object graph
  (and reporting the missing binary) sufficient? → A: **In scope — GramTrans copies the
  binary image file.** The originating request is explicit that both the `CmPicture`
  owned-object graph *and* the backing image asset on disk are reproduced. Reproducing
  the object graph alone would leave the target picture pointing at a file that does not
  exist in the target project — a broken half-copy.
- Q: What happens when the target `LinkedFiles` area already contains a file at the
  destination name? → A: **Non-destructive, content-aware (inherits 024's policy).** If a
  file with identical content is already present, reuse it (link the existing `CmFile`,
  no re-copy). If a file of the same name but **different** content is present, copy the
  source image under a de-duplicated name and wire a fresh `CmFile`, reporting the rename
  — never overwrite an existing target asset.
- Q: What happens when the source `CmFile` points at an image file that is missing on
  disk? → A: **Reproduce the object graph, report the missing binary.** The `CmPicture`
  and its `CmFile` are still valid LCM data worth reproducing; the un-copyable asset is
  surfaced as a dropped-item record so the linguist can supply the file, rather than
  aborting the picture.
- Q: Is remediation of already-copied senses (backfilling pictures onto senses copied by
  a prior GramTrans run) in scope? → A: **No — prevention/forward-copy only**, consistent
  with 024, 028, and 031. This feature ensures a *new* copy carries the pictures; it does
  not retroactively repair targets already populated by an earlier run.
- Q: Are the exact LCM shapes of the picture graph confirmed? → A: **Described from 024's
  MCP-verified census; to be re-confirmed live in `/speckit-plan`'s `research.md`.**
  `LexSense.PicturesOS` = owned sequence → `CmPicture`; `CmPicture.PictureFileRA` = atomic
  reference → `CmFile`; `CmFile` is owned in a `CmFolder` under the project's
  `LangProject.PicturesOC` / `MediaOC` folder area; the binary lives under the project's
  `LinkedFiles` path. `/speckit-plan` MUST re-confirm each shape it depends on via
  FLExToolsMCP and capture the probe evidence.
- Q: How does a re-run recognize a picture/asset already reproduced, given a freshly created
  target `CmPicture` carries no source GUID (the trap that broke feature 026's idempotency)?
  → A: **By structural fingerprint** — image file identity (filename + content hash) plus the
  caption — a target picture with a matching fingerprint under the same sense is treated as
  already-present and not re-created. This is resolution-independent and does not require
  stashing a source-GUID marker on the target.
- Q: When the source image binary is missing on disk, does the reproduced `CmPicture` still get
  a `CmFile` wired, or is `PictureFileRA` left unset? → A: **Wire the `CmFile` at the intended
  target `LinkedFiles` path** (no bytes copied, since none exist), so the picture heals
  automatically once the linguist later supplies the file — mirroring how FieldWorks tolerates a
  missing-on-disk `CmFile`. The missing binary is still reported as a dropped item.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The picture object comes along with the sense (Priority: P1)

A linguist copies an entry whose sense owns one or more pictures (`LexSense.PicturesOS`).
After the transfer the target sense owns equivalent `CmPicture` objects, each carrying the
source picture's caption and layout/description fields, in the same order.

**Why this priority**: The picture object is owned data unique to the sense; without it the
sense loses its illustrations entirely, with no target-side equivalent to fall back on. This
is the core of the feature.

**Independent Test**: Copy an entry whose sense owns a picture with a caption; confirm the
target sense owns a `CmPicture` with the same caption and layout fields, at the same
position in `PicturesOS`.

**Acceptance Scenarios**:

1. **Given** a source sense owning a `CmPicture` with a caption and layout fields, **When**
   the entry is copied, **Then** the target sense owns an equivalent `CmPicture` carrying the
   same caption (all writing systems) and layout/description fields.
2. **Given** a source sense owning several pictures in a specific order, **When** the entry
   is copied, **Then** the target sense's `PicturesOS` contains the same pictures in the same
   order.
3. **Given** a source sense with no pictures, **When** the entry is copied, **Then** no empty
   `CmPicture` is created and any populated target `PicturesOS` is left untouched.

---

### User Story 2 - The backing image file is copied into the target project (Priority: P1)

A linguist copies an entry whose sense picture references an image file on disk. After the
transfer the image file exists in the target project's `LinkedFiles` picture area, and the
target `CmPicture` points at a `CmFile` that resolves to that copied file — so the picture
actually displays.

**Why this priority**: Without the binary, US1's reproduced `CmPicture` points at a file that
does not exist in the target — the picture is broken. The asset copy is what makes the
reproduced picture usable; the two P1 stories together are the MVP.

**Independent Test**: Copy an entry whose sense picture references an image present on the
source disk but absent from the target; confirm the file is copied into the target's
`LinkedFiles` picture area and the target `CmPicture.PictureFileRA` → `CmFile` resolves to it.

**Acceptance Scenarios**:

1. **Given** a source picture whose image file exists on the source disk and is absent from
   the target `LinkedFiles`, **When** the entry is copied, **Then** the file is copied into
   the target's `LinkedFiles` picture area and a `CmFile` (owned under the correct target
   folder) is wired to the target `CmPicture`.
2. **Given** two copied pictures that reference the same source image file, **When** the
   entries are copied, **Then** the image is copied at most once and both target pictures
   reference the same `CmFile` (no duplicated asset or `CmFile`).
3. **Given** the copied file, **When** the target project is opened, **Then** the picture
   resolves and displays (the `CmFile` path is valid relative to the target's `LinkedFiles`
   root).

---

### User Story 3 - Existing target files are handled without clobbering (Priority: P2)

A linguist copies a picture whose destination filename already exists in the target's
`LinkedFiles` area. GramTrans never overwrites an existing target asset: an identical file is
reused, and a same-name-but-different-content file causes the source image to be copied under
a de-duplicated name (the rename is reported).

**Why this priority**: Collisions are common when the same media library seeds both projects,
or across repeated transfers. Getting this wrong either destroys a target asset (overwrite) or
silently mis-wires a picture to the wrong image — both worse than a reported rename. It builds
on US1/US2 but is not required for the first illustrated sense to transfer.

**Independent Test**: Pre-seed the target `LinkedFiles` with (a) a byte-identical file and
(b) a same-name/different-content file; copy pictures referencing each; confirm (a) is reused
with no re-copy and (b) is copied under a new name with the rename reported, and neither target
file is modified.

**Acceptance Scenarios**:

1. **Given** a target `LinkedFiles` file byte-identical to the source image, **When** the
   picture is copied, **Then** the existing file is reused, no second copy is written, and the
   target `CmPicture` links the existing `CmFile`.
2. **Given** a target `LinkedFiles` file with the same name but different content, **When** the
   picture is copied, **Then** the source image is copied under a de-duplicated name, a fresh
   `CmFile` is wired, the rename is reported, and the pre-existing target file is unchanged.

---

### User Story 4 - The linguist is told what could not be reproduced (Priority: P1)

Whenever a picture — or its backing image — cannot be reproduced (the source image is missing
on disk, the file cannot be read or written, or the target folder cannot be resolved), the
transfer report names exactly what was dropped: the owning sense/entry, the picture, and the
image identity/path. Nothing is swallowed.

**Why this priority**: This is the safety backstop inherited from 024 (its US4/FR-010). The
feature's promise is "reproduced or reported"; a reported drop is acceptable, a silent one is
not. Filesystem operations add failure modes (missing/locked/unreadable files) the object-graph
path did not have, so the guarantee must explicitly cover them.

**Independent Test**: Point a source picture at a `CmFile` whose image is missing on disk; run
the transfer; confirm the `CmPicture` object is still reproduced and a structured dropped-item
record names the sense, the picture, and the missing image path — and that a fully-reproducible
picture produces no such record.

**Acceptance Scenarios**:

1. **Given** a source picture whose backing image file is missing on disk, **When** the entry
   is copied, **Then** the `CmPicture` object graph is reproduced — with a `CmFile` wired at the
   intended target path (no bytes copied) — and a structured dropped-item record surfaces naming
   the sense, the picture, and the missing image path; the asset is not silently omitted.
2. **Given** a source image that cannot be read, or a target folder/path that cannot be
   written, **When** the transfer runs, **Then** the failure is reported as a dropped item
   (owner, field, image identity, reason) rather than thrown or silently skipped.
3. **Given** a transfer in which every picture and image was reproduced, **When** the transfer
   completes, **Then** the picture contribution to the dropped-items report is empty and the 024
   census reports no populated-in-source-but-empty-in-target `PicturesOS` for the copied senses.

---

### User Story 5 - Re-running the copy does not duplicate pictures or files (Priority: P1)

A linguist runs the same transfer twice (or copies overlapping selections). The second run
reproduces no additional pictures, `CmFile`s, or image files already present from the first —
counts are stable — and no populated target picture is blanked by an empty source.

**Why this priority**: Idempotency is a hard requirement across GramTrans (SC-005 class); a
picture transfer that grows `PicturesOS` or the `LinkedFiles` area on re-run is a silent
corruption. Non-destructive (no-blank) is inherited from 024 FR-007.

**Independent Test**: Copy an illustrated sense; re-copy the same entry; confirm the target
`PicturesOS`, `CmFile` count, and `LinkedFiles` file set are identical after run 2 as after
run 1.

**Acceptance Scenarios**:

1. **Given** a target sense already carrying the pictures from a prior run, **When** the same
   entry is copied again, **Then** no additional `CmPicture`, `CmFile`, or image file is created
   and the picture set is unchanged.
2. **Given** an empty/unset source `PicturesOS`, **When** the entry is copied, **Then** any
   populated target `PicturesOS` is left untouched (non-destructive).

### Edge Cases

- **Ordered sequence**: `PicturesOS` is an ordered owned sequence; reproduced pictures must
  preserve source order, not be collapsed to a set.
- **Multi-writing-system caption**: the caption is a multistring; all populated writing systems
  must come across (reuse 024's writing-system-mapped multistring copy).
- **Shared image across pictures/senses**: an image referenced by K copied pictures is copied
  at most once and the `CmFile` reused (no per-reference duplication).
- **Missing source image on disk**: the `CmPicture`/`CmFile` object graph is still reproduced;
  the un-copyable binary is reported (US4), not a silent drop and not an abort of the picture.
- **Name collision, different content**: copy under a de-duplicated name and report; never
  overwrite an existing target file (US3).
- **Name collision, identical content**: reuse the existing target file/`CmFile`; do not
  re-copy or duplicate.
- **Relative vs absolute `LinkedFiles` path**: the source `CmFile` may store a path relative to
  the source `LinkedFiles` root or an absolute path; reproduction must resolve it against the
  *source* root and store it correctly against the *target* root so the picture resolves after
  copy.
- **Non-image / unexpected media type**: a `CmFile` referencing a non-picture media type is
  handled by the same copy-or-report path (scope is `PicturesOS`; audio/video owned elsewhere
  is out of scope, see below).
- **Empty source field**: an empty/unset source `PicturesOS` must never blank a populated target
  (non-destructive, inherited from 024 FR-007).
- **Vacuous corpus**: on a corpus where no sense populates `PicturesOS` (e.g. `Ejagham Mini`),
  behavior is unchanged except for an (empty) picture contribution to the report — no regression.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For every sense owned by a copied entry, the system MUST reproduce a populated
  `LexSense.PicturesOS` by deep-copying each owned `CmPicture` into the target sense — carrying
  the caption multistring (all writing systems, writing-system-mapped) and the layout/description
  fields — preserving source order, per 024's owned-child discipline.
- **FR-002**: For each reproduced `CmPicture`, the system MUST copy the backing image file
  referenced through `CmPicture.PictureFileRA` → `CmFile` into the target project's `LinkedFiles`
  picture area, resolving the source path against the source `LinkedFiles` root and storing it
  against the target root, and wire a `CmFile` (owned under the correct target folder) to the
  target `CmPicture` so the picture resolves and displays.
- **FR-003**: The system MUST be non-destructive against existing target assets: a target
  `LinkedFiles` file with content identical to the source image MUST be reused (no re-copy); a
  same-name-but-different-content target file MUST cause the source image to be copied under a
  de-duplicated name with a fresh `CmFile`, and the rename MUST be reported. The system MUST NOT
  overwrite an existing target file.
- **FR-004**: An image (and its `CmFile`) shared by multiple copied pictures MUST be copied and
  wired at most once and reused, not duplicated per reference.
- **FR-005**: When a source picture's backing image file is missing on disk, unreadable, or
  cannot be written to the target, the system MUST reproduce the `CmPicture` object graph —
  including a `CmFile` wired at the intended target `LinkedFiles` path (no bytes copied), so the
  picture resolves once the file is later supplied — and emit a structured, user-surfaced
  dropped-item record identifying the owning sense, the picture, and the image identity/path and
  reason — it MUST NOT silently omit the asset or abort the transfer.
- **FR-006**: The system MUST never blank a populated target `PicturesOS` (or an existing target
  picture/`CmFile`) as a side effect of copying from an empty/unset source (non-destructive rule).
- **FR-007**: Re-running a transfer, or copying overlapping selections, MUST NOT create duplicate
  `CmPicture`, `CmFile`, or image files for pictures/assets already reproduced; picture,
  `CmFile`, and `LinkedFiles` counts MUST be stable across re-runs (idempotency). A target
  picture is recognized as already-present by a **structural fingerprint** — image file identity
  (filename + content hash) plus caption — since the reproduced `CmPicture` carries no source
  GUID; an asset is recognized by its file identity (see FR-003).
- **FR-008**: Whenever any picture or asset cannot be reproduced, the system MUST emit a
  structured dropped-item record via 024's dropped-items channel and report (owning object,
  field, source item identity, reason). It MUST NOT be silently omitted.
- **FR-009**: The system MUST NOT retroactively repair targets already populated by a prior
  transfer; scope is forward-copy prevention only (consistent with 024, 028, and 031).
- **FR-010**: The 024 model-driven fidelity census MUST be updated so `LexSense.PicturesOS` (and
  the associated `CmPicture`/`CmFile` reproduction) moves from DROP_REPORTED to COPIED (with
  concrete code sites), preserving the never-silent guard; a census run over a copied sense
  carrying pictures MUST report zero populated-in-source-but-empty-in-target `PicturesOS`.
- **FR-011**: For a transfer whose senses populate no pictures, behavior and output MUST be
  unchanged from today except for the (empty) picture contribution to the report — no regression
  for the common case.

### Key Entities *(include if feature involves data)*

- **Sense picture** (`CmPicture`, owned in `LexSense.PicturesOS`): an owned object carrying a
  caption multistring and layout/description fields, plus a reference to its image file.
- **Image reference** (`CmPicture.PictureFileRA` → `CmFile`): the atomic reference from a
  picture to the LCM object describing its backing file.
- **File object** (`CmFile`, owned under a `CmFolder`): the LCM object holding the stored path
  (relative to the project's `LinkedFiles` root) of an image on disk.
- **Backing image asset**: the binary image file on disk in the project's `LinkedFiles` picture
  area — the filesystem object the `CmFile` points at; copied between the two projects' areas.
- **Dropped-item record**: the never-silent report unit inherited from 024 — owning object,
  field, source item identity/path, and reason it could not be reproduced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a transfer whose source senses own pictures, 100% of those pictures are present
  in the target afterward as owned `CmPicture` objects with matching captions, layout fields, and
  order.
- **SC-002**: For every reproduced picture whose source image exists on disk, the image resolves
  and displays from the target project (the copied file is present under the target `LinkedFiles`
  root and the `CmFile` path is valid).
- **SC-003**: Zero existing target `LinkedFiles` files are overwritten or modified by a transfer;
  every same-name/different-content collision is resolved by a reported rename.
- **SC-004**: Every picture or asset that is not reproduced appears in the dropped-items report;
  the count of *silent* (unreported) picture/asset losses is zero.
- **SC-005**: An image used by K copied pictures produces at most one copied file and one
  `CmFile` in the target (no per-reference duplication).
- **SC-006**: Re-running the same transfer produces zero net-new `CmPicture`, `CmFile`, or image
  files, and blanks zero populated target `PicturesOS` (idempotent and non-destructive).
- **SC-007**: The 024 census reports zero unexplained populated-in-source-but-empty-in-target
  `PicturesOS` for a copied sense (every remaining gap is matched by a dropped-item record).
- **SC-008**: For a transfer whose senses own no pictures, output is unchanged from today except
  for an (empty) picture report contribution — no regression.

## Assumptions

- The linguist runs GramTrans transfers between two FieldWorks projects; "user-facing" means
  surfaced in the transfer preview/report the linguist already reviews.
- Both projects have a resolvable `LinkedFiles` root (the standard FieldWorks project layout);
  the target's picture folder area exists even if empty, and is the destination for copied assets.
- "Identical content" for collision handling is judged by file content (e.g. byte/hash
  equivalence), not merely by filename — the precise comparison method is an implementation
  detail deferred to `/speckit-plan`.
- Conflict-mode and GOLD/reserved-item semantics established by prior features are reused where
  they apply; no new conflict mode is introduced for pictures.
- `Ejagham Mini` and `Ejagham Full GT-Test` contain no populated sense pictures, so the automated
  regression fixtures and the attended live proof must be **constructed** (with real image files
  on disk) rather than harvested from those projects — a T037-class attended live-proof item,
  never run under an unattended loop.
- Whether the asset copy is performed by GramTrans directly or delegated to an existing
  FieldWorks/LCM file-import helper is an **implementation decision deferred to `/speckit-plan`**;
  both satisfy the requirements above, and the choice does not change scope.

## Out of Scope

- Complex forms and variants (027); reversals (025); texts/wordforms (026); affix morphosyntax
  (028); sense appendix & thesaurus references (030).
- Anything already covered by 024 for senses (referenced possibility lists, other owned children
  reproduced there).
- Non-picture media owned elsewhere in the model (audio/video pronunciation media, entry-level or
  example-level media) — this feature is scoped to `LexSense.PicturesOS`.
- Retroactive remediation of already-copied targets (see FR-009).
- Editing, transcoding, or resizing image assets — files are copied byte-for-byte, not
  transformed.

## Notes

- Field/graph shapes in this spec are described from feature 024's MCP-verified census.
  `/speckit-plan` MUST re-confirm any shape it depends on (`PicturesOS` cardinality/ordering,
  `PictureFileRA` target, `CmFile`/`CmFolder` ownership, `LinkedFiles` path storage) via
  FLExToolsMCP and capture the probe evidence in `research.md`.
- The asset-copy half of this feature is the novel part relative to 024/025/026/027/028/031 (all
  pure object-graph work); `/speckit-plan` should give the filesystem failure modes (missing,
  locked, unreadable, unwritable, path-encoding) explicit design attention under the never-silent
  guarantee.
- No open `[NEEDS CLARIFICATION]` markers remain.
