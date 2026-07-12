# Feature Specification: Full Reversals (STUB)

**Feature Branch**: `025-full-reversals`

**Created**: 2026-07-11

**Status**: Stub / Planned (not yet specified)

**Depends on**: `024-lexicon-reference-fidelity` (reuses its never-silent fidelity
guarantee and referenced-item resolver).

## Purpose

Extend cross-project copy to **reversal indexes**: the reversal-index entries that point
back at senses, and the per-index reversal-index category list they use. Feature 024
deliberately excludes reversals because reversal-index categories are only reachable once
reversal *entries* are copied — which is its own transfer path.

## Intended Scope (to be refined in /speckit-specify)

- **Reversal-index entries** (per writing system) linked to copied senses.
- **Reversal-index categories** — the per-`ReversalIndex.PartsOfSpeechOA` list — resolved
  against the target with the same three-way disposition as 024 (absent → create incl.
  ancestor chain; diverged custom → update; diverged shared/default → link + report;
  identical → link).
- Only reversal content tied to senses actually copied by the transfer (closure-scoped, as
  in 024). No wholesale reversal-index duplication.
- The **never-silent guarantee** carries over: any reversal item that cannot be reproduced
  on the fly is reported (owning object, field, source item name + GUID), not swallowed.

## Out of Scope

- Texts and wordforms (feature 026).
- Reversal-index *configuration* views (`.fwdictconfig` files) unless a later decision
  folds config-file copy in.

## Open Questions (for /speckit-specify)

- Which writing-system reversal indexes to copy — all present, or only those with entries
  referencing copied senses?
- Do reversal-index categories follow the copied senses' POS closure, or are they resolved
  independently?
- Interaction with 024's dropped-items report — one unified report or a reversal section?
