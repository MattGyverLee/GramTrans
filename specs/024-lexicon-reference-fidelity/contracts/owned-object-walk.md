# Contract: Owned-Object Walk (`Lib/owned.py`)

Covers FR-009 (examples+translations, pronunciations, etymologies, recursive sub-senses) and
FR-009a (allomorph phonological environments + ad-hoc prohibition rules). Invoked from the
entry/sense/allomorph closure walk in `categories.py`, plan-aware (Principle III).

## `walk_owned_children(src_owner, new_owner, ctx, tag, resolver_cache, dropped) -> None`

For a copied owner object, reproduce its owned children per the `OwnedObjectSpec` table.

**Behavior per spec**
- Create the child via its factory under the target owner's owning field.
- Copy the child's own syncable properties (`GetSyncableProperties` / `ApplySyncableProperties`).
- Route each of the child's reference fields through `references.decide_reference` /
  `apply_reference` (e.g. example translation `TypeRA`).
- `apply_residue(child, ws, tag)` — carrier classes already registered in `residue.py`.
- If `spec.recurse` (sub-senses): re-enter the full sense-copy path recursively so a
  sub-sense gets the same reference + owned treatment as a top-level sense.

**Guarantees**
- Every populated owned collection listed in `OwnedObjectSpec` is walked; anything that
  cannot be reproduced appends a `DroppedItemRecord` to `dropped` (never silent).
- Ordering preserved for sequence-owned children (examples).

## `reproduce_allomorph_hung_data(src_allo, new_allo, ctx, tag, resolver_cache, dropped) -> None`

FR-009a.
- Resolve `src_allo.PhoneEnvRC` members against the target phonological-environment list
  (the `PH_ENVIRONMENT` category target) via the resolver; link resolved, report unresolved.
- Discover APRs (`MorphologicalDataOA.AdhocCoProhibitionsOC`) whose members reference the
  copied allomorph / its morpheme; reproduce an APR **only when all its members are in the
  copy set**, else emit a `DroppedItemRecord` (reason `member not in copy set`) — mirrors the
  lexical-relation partial-member rule (FR-008).

**Non-goals**
- Does not create phonological environments from scratch here (environments are their own
  transferable category); it resolves/reports against the target.
