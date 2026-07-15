# Phase 1 Data Model: Complex Forms & Variants (027)

## LCM objects (target-side, created/wired by this feature)

### LexEntryRef (created)

The relationship container. Owned by `ILexEntry.EntryRefsOS` (an
`ILcmOwningSequence<ILexEntryRef>`; cast `ILexEntry(entry).EntryRefsOS`). Created via
`ILexEntryRefFactory` (no flexicon wrapper — raw `target.GetFactory(...)`), GUID-preserved.
**All member access requires `_cast_lcm(ref, "ILexEntryRef")`.**

| Field | LCM type | Written by | Notes |
|-------|----------|-----------|-------|
| `Guid` | Guid | creation | Preserved from source (identity; idempotency guard). |
| `RefType` | Int32 | creation | 0 = variant (`krtVariant`), 1 = complex-form (`krtComplexForm`). Copied verbatim. |
| `ComponentLexemesRS` | ref sequence → `IVariantComponentLexeme` (entry/sense) | `_run_post_pass_a` | Closure-scoped; source order; membership-guarded. |
| `PrimaryLexemesRS` | ref sequence → entry/sense | `_run_post_pass_a` | Subset of components (complex forms); order preserved. |
| `VariantEntryTypesRS` | ref sequence → `ILexEntryType` | US2 resolver | Three-way disposition vs target list. Variant refs. |
| `ComplexEntryTypesRS` | ref sequence → `ILexEntryType` | US2 resolver | Three-way disposition vs target list. Complex-form refs. |
| `ShowComplexFormsInRS` | ref sequence → `ICmPossibility` (publication) | US2 resolver | 024 publication handling. |
| `OwningEntry` | `ILexEntry` | (derived) | Set implicitly by owning into `EntryRefsOS`. |

Read-only / not written: `MainEntriesOrSensesRS` (on `ILexEntry`, `can_write=false`, derived
aggregate — FR-006), `ComplexFormEntryRefs`, `VariantEntryRefs`, `VisibleVariantEntryRefs`,
`PrimarySensesOrEntries` (all derived enumerables).

### LexEntryType (created or linked)

Variant/complex entry-type possibility item. Resolved against the target's entry-type list
via 024's `references.decide_reference`/`apply_reference`. GOLD/reserved items:
GUID-remapped at creation, never overwritten (Principle I). `ILexEntryTypeFactory` (already
used in `categories.py`).

## In-repo data structures

### `plan.lexentry_ref_bindings` (existing; extended)

Gathered at plan time (`preview.py` / `stems_execute_action`), consumed by the post-pass.
Current shape (per `categories._run_post_pass_a`):

```
{ src_entry_guid: { "ComponentLexemesRS": [src_lex_guid, ...],
                    "PrimaryLexemesRS":   [src_lex_guid, ...] } }
```

**Extension for 027** — the binding must additionally carry, per source ref, enough to
create the container and resolve its types. One entry may own multiple refs, so the value
becomes a list of per-ref records:

```
{ src_entry_guid: [
    { "ref_guid": <src LexEntryRef guid>,
      "ref_type": <int 0|1>,
      "components": [src_lex_guid, ...],
      "primaries":  [src_lex_guid, ...],
      "variant_entry_types":  [src type guid/obj, ...],   # RefType 0
      "complex_entry_types":  [src type guid/obj, ...],   # RefType 1
      "show_complex_forms_in":[src pub guid/obj, ...] },
    ...
] }
```

Backward-compat note: the existing `{ "ComponentLexemesRS": [...], "PrimaryLexemesRS": [...] }`
shape and `_run_post_pass_a`'s consumption of it must be preserved or migrated in lockstep —
the wiring loop keys off the *created* target ref's `EntryRefsOS`, so it can stay
container-driven while the new creation step supplies the containers + types. The task
breakdown decides whether to extend the dict value or add a parallel
`plan.entryref_create_bindings`; either way the Preview gatherer and Move consumer stay in
sync (SC drop-parity).

### Decision records (Preview, read-only)

Reuse 024's `DroppedItemRecord` (owner_kind=`LexEntry`, field_name=`EntryRefsOS`,
item identity = `_lex_entry_ref_identity_label`) for every **un-reproduced** ref/member, and
024's reference-decision rows (Add/Link/Update) for entry-type resolution. No new record type
is required; the change is *which* refs become drops (out-of-closure only) vs. reproductions.

## Invariants

- **INV-1 (identity)**: a created `LexEntryRef` carries the source GUID; no target entry owns
  two refs with the same GUID (idempotency).
- **INV-2 (closure)**: `ComponentLexemesRS`/`PrimaryLexemesRS` contain only target objects
  copied within this transfer's closure; out-of-closure members are reported, not wired.
- **INV-3 (never-silent)**: every source ref/member not reproduced yields exactly one
  `DroppedItemRecord` (0 silent drops).
- **INV-4 (concept↔GUID)**: a created entry-type/publication item's GUID names the closest
  ontological concept; existing target GOLD items are linked, never overwritten (Principle I).
- **INV-5 (preview-clean)**: the Preview path computes the reproduce/report split and writes
  nothing to source or target (Principle III).
- **INV-6 (cast)**: no `LexEntryRef`/`LexEntry` member is accessed without `_cast_lcm`;
  no GUID is resolved without `_resolve_target_by_guid` (issue #28 layers 1+2).
