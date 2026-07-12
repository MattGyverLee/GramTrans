# Feature Specification: Affix-Allomorph Morphosyntax (STUB)

**Feature Branch**: `028-affix-allomorph-morphosyntax`

**Created**: 2026-07-12

**Status**: Stub / Planned (not yet specified)

**Depends on**: `024-lexicon-reference-fidelity` (reuses its never-silent fidelity
guarantee and referenced-possibility resolver).

## Origin

Surfaced by feature 024's US5 model-driven fidelity census (`FR-011`). When
cross-project copy creates a `MoAffixAllomorph`, it reproduces only `MorphTypeRA`
(and the shared `MoForm` `PhoneEnvRC`). The census proved that four
affix-specific morphosyntactic-environment fields are **never reproduced** and are
**not** handled by the grammar/MSA transfer path:

- `MoAffixAllomorph.InflectionClassesRC`
- `MoAffixAllomorph.MsEnvFeaturesOA`
- `MoAffixAllomorph.MsEnvPartOfSpeechRA`
- `MoAffixAllomorph.PositionRS`

This is a genuine code-level gap. It is **vacuous** on the `Ejagham Mini` test
project (0 of 106 affix allomorphs populate any of these fields), so no live-reachable
loss exists there — live proof needs a non-Ejagham fixture (a T037-class item).

024 ships fidelity-**honest** for this subsystem — it now emits a `DroppedItemRecord`
per populated-but-un-reproduced field (see 024 cycle-16b) — but the actual
**reproduction** work was never in 024's scope and is routed here.

## Purpose

Extend cross-project copy to reproduce affix-allomorph morphosyntactic-environment
data when transferring entries whose allomorphs carry it.

## Intended Scope (to be refined in /speckit-specify)

- `MsEnvPartOfSpeechRA` — POS reference (resolve against target POS list, as in the
  grammar/MSA POS handling).
- `InflectionClassesRC` — inflection-class references (owned by a POS;
  closure-scoped resolution).
- `MsEnvFeaturesOA` — owned feature-structure (`IFsFeatStruc`); reproduce the owned
  object per 024's owned-child discipline.
- `PositionRS` — position references.
- The **never-silent guarantee** carries over.

## Out of Scope

- Complex forms and variants (feature 027).
- Reversals (025), texts/wordforms (026).
- Anything already covered by 024 (`MorphTypeRA`, `PhoneEnvRC`, MSA objects
  themselves via the POS/MSA path).

## Open Questions (for /speckit-specify)

- A constructed fixture with populated affix-MsEnv fields is required for live proof
  (Ejagham Mini has none).
- Overlap with the existing grammar-transfer MSA path — should MsEnv reproduction
  reuse the MSA POS-resolution machinery, or 024's referenced-possibility resolver?
