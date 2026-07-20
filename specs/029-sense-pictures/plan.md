# Implementation Plan: Sense Pictures

**Branch**: `029-sense-pictures` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/029-sense-pictures/spec.md`

## Summary

Close the sense-picture gap that feature 024's fidelity census surfaced and
DROP_REPORTed: when a copied sense owns pictures (`LexSense.PicturesOS`), reproduce each
owned `CmPicture` (caption + layout fields, in order) **and** copy its backing image file
into the target project's `LinkedFiles` area, wiring a `CmFile` so the picture displays —
carrying over 024's never-silent guarantee.

The work is a **targeted replacement of one report-only stub**. `categories.py` already
isolates the gap in `_report_dropped_sense_scope_gaps` (which report-drops the three
un-reproduced `LexSense` scope-gap fields `AppendixesRC` / `ThesaurusItemsRC` /
`PicturesOS`, called identically from the Move sense loop and the Preview sense loop). This
feature adds a real reproduce leg (Move) plus a Preview-decision twin for the `PicturesOS`
portion — exactly mirroring the `reproduce_moaffix_msenv_data` / `_plan_moaffix_msenv_decisions`
pair feature 028 built — while leaving `AppendixesRC` / `ThesaurusItemsRC` report-dropped
for feature 030. It reuses machinery that **already exists or is provided by flexicon**:

- **The `CmPicture` object graph** → deep-copied per 024's owned-child discipline, carrying
  the `Caption`/`Description` multistrings (writing-system-mapped) and the layout fields
  (`LayoutPos`, `LocationMin`/`LocationMax`, `LocationRangeType`, `ScaleFactor`). Preserves
  source order (`PicturesOS` is an ordered owned sequence).
- **The backing image asset** → copied via flexicon's `LexSenseOperations.AddPicture(sense,
  image_path, caption, wsHandle)`, which creates the `CmPicture`, copies the file into the
  target's `LinkedFiles` picture folder, and wires the `CmFile` in one call (research R2).
  The source path is resolved against the *source* project's `LinkedFiles` root
  (`GetLinkedFilesDir()`); the copy lands under the *target* root.
- **Collision handling** → content-aware and non-destructive (research R3): identical file
  reused; same-name/different-content copied under a de-duplicated name via `RenamePicture`
  and reported; existing target files never overwritten.
- **The never-silent channel** → the existing 024 `DroppedItemRecord` / dropped-items report,
  extended to the new filesystem failure modes (missing/unreadable/unwritable image).

Finally, flip the `fidelity_census.py` `LexSense.PicturesOS` row from DROP_REPORTED to
COPIED (with concrete code sites), preserving the never-silent guard. Prevention/forward-copy
only (FR-009).

## Technical Context

**Language/Version**: Python 3 (CPython + pythonnet), hosted by a stock FlexTools install.

**Primary Dependencies**: flexicon (`pyflexicon>=4.1`) Operations-class API —
`LexSenseOperations.AddPicture` / `RenamePicture`, `MediaOperations.CopyToProject`,
`FLExProject.GetLinkedFilesDir` / `ProjectSettingsOperations.GetLinkedFilesRootDir`;
`SIL.LCModel` interfaces via pythonnet (`ILexSense`, `ICmPicture`, `ICmFile`, `ICmFolder`,
`ILangProject.PicturesOC` / `LinkedFilesRootDir`, plus `ICmPictureFactory` / `ICmFileFactory`
for the missing-binary fallback path); the Python standard library (`os.path`, `shutil`,
`hashlib`) for path resolution and content-hash comparison. PyQt for the host report panel.

**Storage**: FieldWorks `.fwdata` project pair through the LCM cache, **plus** the on-disk
`LinkedFiles` picture-folder tree of each project (the novel storage surface for this feature).
Divergence baseline is the live target project (inherited from 024 FR-005).

**Testing**: pytest under `tests/unit/`; the model-driven fidelity census
(`tests/verification/fidelity_census.py`) is the offline harness whose `LexSense.PicturesOS`
row flips DROP_REPORTED → COPIED. Filesystem operations are covered host-free by faking the
image-copy seam (temp files + a stubbed `AddPicture`).

**Target Platform**: Windows (FlexTools host); source → target between two FLEx projects.

**Project Type**: Single project — FlexTools-compatible module with helpers under
`src/gramtrans/Lib/`.

**Performance Goals**: Bounded per-picture overhead over the existing sense walk. An image
shared by K pictures is copied once and reused via a per-run content-fingerprint cache
(SC-005), so cost is O(distinct images), not O(references).

**Constraints**: Preview-before-mutate (Principle III) — every reproduce decision appears in
the plan as ADD/LINK/Report before any write, via the new Preview twin. Non-destructive: never
blank a populated target field (FR-006) and never overwrite an existing target `LinkedFiles`
file (FR-003). Graceful degrade: a missing/unreadable/unwritable image is reported, never
thrown or silently dropped (Principle I "fail loudly", "No silent skips" gate). flexicon-direct
only (Principle II). Idempotent by structural fingerprint (image identity + caption), since a
reproduced `CmPicture` carries no source GUID (FR-007, spec Clarifications).

**Scale/Scope**: One owned-sequence field on `LexSense`. Vacuous on the Ejagham corpora
(0 senses populate `PicturesOS`), so unit fixtures and the attended live proof must be
**constructed** with real image files on disk (a T037-class attended item, never run under an
unattended loop).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. FLEx Domain Fidelity** (NON-NEGOTIABLE) | **Directly served.** Principle I already requires cross-references to "resolve to real objects in the target after transfer, or … fail loudly rather than silently drop." This feature implements that for a copied sense's pictures and their backing assets. `CmPicture` carries no ontology GUID (it is owned data, not a catalog concept), so the concept↔GUID invariant does not apply; identity is a structural fingerprint (spec Clarifications), and the image `CmFile` is content-addressed. Writing-system identity is validated on the caption/description multistrings via 024's ws-mapped copy. **PASS.** |
| **II. flexicon-Direct** | New code uses flexicon Operations (`LexSenseOperations.AddPicture` / `RenamePicture`, `MediaOperations`, `GetLinkedFilesDir`) + `project.GetService(ICmPictureFactory/ICmFileFactory)` for the missing-binary fallback + `CastingOperations.cast_to_concrete` for the `ICmPicture`/`ICmFile` polymorphic casts the MCP flagged (all 13 `ICmPicture` props `requires_cast`). No adapter indirection. **PASS.** |
| **III. Preview-Before-Mutate** (NON-NEGOTIABLE) | The current stub is report-only (no plan twin). This feature adds a Preview-decision twin (`plan_sense_picture_decisions`) mirroring `_plan_moaffix_msenv_decisions`, so ADD/LINK/Report decisions — including the planned asset copy vs. reuse vs. rename — appear in Preview before any Move write or file copy. **PASS with design obligation** (tracked in research R6). |
| **IV. Phased Merge Discipline** | Reuses existing mode vocabulary and 024's create/link/report semantics. No new mode introduced. Empty source never blanks target (FR-006, update semantic); existing target files never overwritten (FR-003). **PASS.** |
| **V. Referential Completeness** | Pictures "hang off" the sense and travel with it in the copy closure (Principle: everything that hangs off the Lexicon eventually needs handling). A picture whose asset cannot be reproduced is reported, not invented. **PASS.** |
| **Workflow: No silent skips** | Every picture or asset that cannot be reproduced routes into the existing dropped-item report channel (FR-008), including the new filesystem failure modes. The census never-silent guard is preserved and re-run. **PASS** — this gate is the feature's backstop. |

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/029-sense-pictures/
├── plan.md              # This file
├── research.md          # Phase 0 output — MCP-confirmed shapes + the copy-mechanism decision
├── data-model.md        # Phase 1 output — CmPicture/CmFile fields, dispositions, fingerprint
├── quickstart.md        # Phase 1 output — offline + attended-live (constructed-fixture) guide
├── contracts/
│   └── sense-picture-reproduction.md   # Phase 1 output — the reproduce/plan contract
├── checklists/
│   └── requirements.md  # spec quality checklist (from /speckit-specify)
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
src/gramtrans/Lib/
├── pictures.py          # NEW: reproduce_sense_pictures (Move) + plan_sense_picture_decisions
│                        #   (Preview twin) + the asset-copy seam (content hash, collision
│                        #   rename, missing-binary fallback). Isolates filesystem I/O from the
│                        #   object-graph modules so it is unit-testable host-free.
├── categories.py        # MODIFY: in the sense loop of _walk_lex_entry_closure (Move) call
│                        #   pictures.reproduce_sense_pictures; drop the PicturesOS portion from
│                        #   _report_dropped_sense_scope_gaps (leaving AppendixesRC/
│                        #   ThesaurusItemsRC for 030). Preview twin: the sense loop in the
│                        #   preview path calls pictures.plan_sense_picture_decisions.
├── preview.py           # REUSE/WIRE: the Preview sense loop that emits PlannedAction
│                        #   reference_decisions gains the picture decisions.
├── references.py        # REUSE: _guid_str, _item_label helpers.
├── models.py            # REUSE: DroppedItemRecord, ReferenceDecisionRecord, ReferenceAction
│                        #   (no new type expected).
└── report.py            # REUSE: dropped-item channel already carries these records.

tests/
├── unit/
│   ├── test_029_sense_picture_reproduction.py  # NEW: CmPicture deep-copy (caption/layout/
│   │                                           #   order) + Preview/Move parity + idempotency
│   │                                           #   (fingerprint) + empty-source no-blank
│   └── test_029_picture_asset_copy.py          # NEW: asset copy / reuse-identical / rename-
│                                               #   on-collision / missing-binary report — all
│                                               #   host-free via a faked AddPicture + temp files
└── verification/
    └── fidelity_census.py    # MODIFY: LexSense.PicturesOS row DROP_REPORTED → COPIED
```

**Structure Decision**: Single-project FlexTools module. Unlike 028 (which kept allomorph-hung
data together in `owned.py`), this feature introduces a **new `Lib/pictures.py`** module. The
justification is the novel **filesystem/asset** concern: content hashing, `LinkedFiles` path
resolution, collision renaming, and missing-file handling are I/O logic that does not belong in
the object-graph modules (`owned.py` / `categories.py`) and is far more testable in isolation
(a faked copy seam + temp files, no live host). The object-graph deep-copy of `CmPicture` lives
in the same module so the picture logic stays cohesive. The only changes outside `Lib/` are the
census flip and the new tests.

## Complexity Tracking

> No Constitution Check violations — table intentionally omitted.
