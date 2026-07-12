# Feature Specification: Sense Pictures (STUB)

**Feature Branch**: `029-sense-pictures`

**Created**: 2026-07-12

**Status**: Stub / Planned (not yet specified)

**Depends on**: `024-lexicon-reference-fidelity` (reuses its never-silent fidelity
guarantee and owned-child closure).

## Origin

Surfaced by feature 024's US5 model-driven fidelity census (`FR-011`). A copied
sense's `LexSense.PicturesOS` — owned `CmPicture` objects, each pointing via
`CmPicture.PictureFileRA` to a `CmFile` that references an **image file on disk** —
is never reproduced by the transfer.

Per the governing principle ("anything that hangs off the Lexicon eventually needs
to be handled") this is not permanently excluded: 024 emits a `DroppedItemRecord`
per un-reproduced picture (never-silent), and the actual reproduction is routed
here. It is separated from 024 because copying the backing **binary image file**
between two projects' `LinkedFiles` areas is a filesystem/asset concern outside the
LCM object-graph mechanism 024 operates in.

## Purpose

Extend cross-project copy to reproduce sense pictures — the `CmPicture` owned object
graph **and** the backing image asset on disk.

## Intended Scope (to be refined in /speckit-specify)

- `LexSense.PicturesOS` — reproduce each owned `CmPicture` (caption multistring,
  layout fields).
- `CmPicture.PictureFileRA` → `CmFile` → copy the backing image file into the target
  project's LinkedFiles/pictures area; wire `CmFolder`/`CmFile` ownership.
- Handle the file-already-present / name-collision / missing-source-file cases
  (never-silent: report what could not be copied).
- The **never-silent guarantee** carries over.

## Out of Scope

- Complex forms/variants (027), affix morphosyntax (028), reversals (025),
  texts/wordforms (026).
- Anything already covered by 024.

## Open Questions (for /speckit-specify)

- LinkedFiles path resolution and relative-vs-absolute storage across the two
  projects.
- A constructed fixture with populated sense pictures is required (Ejagham Mini has
  0 populated `PicturesOS`).
- Does asset copy belong to GramTrans or a separate file-sync step?
