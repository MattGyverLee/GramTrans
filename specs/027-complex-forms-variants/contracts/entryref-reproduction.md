# Contract: LexEntryRef Reproduction Post-Pass (027)

Scope: the STEMS-tail post-pass that creates target `LexEntryRef` containers, wires their
component/primary lexemes, and resolves their entry-type/publication references. Reuses the
024 fidelity infrastructure and the issue-#28 resolution/casting idioms.

## C1 — Container creation (`_run_entryref_create_pass`, new; front of the STEMS tail)

**Inputs**: `context`, `target`, the per-ref create bindings (see data-model
`lexentry_ref_bindings` extension), and `plan.identity_remap`.

**Behavior**: for each `src_entry_guid → [ref_record, ...]`:
1. `target_entry = _cast_lcm(_resolve_target_by_guid(target, remap.get(src_entry_guid,
   src_entry_guid)), "ILexEntry")`. If `None` → `Skip(DEPENDENCY_UNRESOLVED)` (one per
   unresolved entry); continue.
2. For each `ref_record`:
   - **Idempotency**: if `target_entry.EntryRefsOS` already owns a ref whose GUID == the
     record's `ref_guid` → skip creation (already reproduced).
   - Else create via `ILexEntryRefFactory(target.GetFactory(ILexEntryRefFactory))`,
     GUID-preserved from `ref_guid`, owned into `ILexEntry(target_entry).EntryRefsOS`.
   - Set `ILexEntryRef(new_ref).RefType = ref_record["ref_type"]`.
3. **MUST NOT** wire components/primaries here (C2 owns that) — C1 only guarantees a cast,
   GUID-correct, `RefType`-correct empty container exists.

**Postconditions**: after C1, every in-closure source ref has a matching target
`LexEntryRef` (GUID + RefType), or a `Skip`/`DroppedItemRecord` explains its absence. No
duplicate refs (INV-1).

**Errors**: absent `ILexEntryRefFactory`/interface → degrade to report-only (Principle II
graceful degrade), emit `DroppedItemRecord`, never crash the transfer.

## C2 — Component/primary wiring (`_run_post_pass_a`, existing; now reachable)

Unchanged from its current implementation **except** it now finds real containers. For each
created `target_ref` (cast `ILexEntryRef`), for `ComponentLexemesRS` then `PrimaryLexemesRS`:
resolve each member via `plan.in_plan_entries` then `_resolve_target_by_guid`; membership-
guard; `seq.Add(target_lex)`. Unresolved member → `Skip(DEPENDENCY_UNRESOLVED)` +
`DroppedItemRecord` (out-of-closure). Order preserved. Idempotent (membership guard).

## C3 — Entry-type / publication resolution (US2)

For each created `target_ref`:
- `RefType==0` → resolve `variant_entry_types` into `VariantEntryTypesRS`.
- `RefType==1` → resolve `complex_entry_types` into `ComplexEntryTypesRS`.
- always → resolve `show_complex_forms_in` into `ShowComplexFormsInRS`.

Resolution uses `references.decide_reference`/`apply_reference` against the target entry-type
/ publication lists: absent → create incl. ancestor chain (GUID-remapped, Principle I);
diverged custom → update; diverged shared/GOLD → link + report; identical → link. Unresolved
→ `DroppedItemRecord`. No overwrite of existing target GOLD items (INV-4).

## C4 — Never-silent drop policy (`_report_dropped_entry_refs`, behavior change)

**Before**: emits one `DroppedItemRecord` for *every* `LexEntryRef`.
**After**: emits a `DroppedItemRecord` only for a ref (or a specific member) that is **not
reproduced** — i.e. its component/primary/type end is outside the copy closure or otherwise
unresolvable. In-closure refs are reproduced (C1–C3) and are NOT reported as drops.

Called identically from Move (`_walk_lex_entry_closure`) and Preview
(`_plan_entry_reference_decisions`) so the two drop sets remain identical by construction
(INV-3, drop-parity).

## C5 — Preview parity (read-only)

The Preview path computes the same reproduce-vs-report split as Move and surfaces, per ref:
source GUID, RefType/kind, proposed action (Add / Link / Skip), and the closure it pulls.
Preview writes nothing to source or target (INV-5, Principle III). A Preview run followed by
a Move run over the same selection produces the same set of created refs and the same set of
dropped records.

## C6 — Idempotent re-Move

A second Move into the same target: 0 new `LexEntryRef` created (GUID guard C1), 0 memberships
re-added (membership guard C2), 0 entry-type items re-created (three-way "identical → link"
C3). (SC-003.)

## C7 — Empty-source regression

A source with 0 `LexEntryRef`: C1 creates nothing, C2/C3 wire nothing, C4 reports nothing new
→ byte-identical to a 024-only run (SC-005, FR-011).

## Test obligations (offline, TDD RED-first)

- C1: variant create (RefType 0) over duck-typed fakes + fake `ICmObjectRepository` fallback
  branch; GUID preserved; unresolved entry → Skip.
- C1/C2 cast path: `_Bare` (uncast → no-op reproduction) vs `_Typed` (cast → reproduced),
  reproducing the issue #28 layer-2 live no-op offline.
- C2: component/primary wiring, order, membership-guard idempotency (extend
  `test_phase3c_post_pass_a.py`).
- C3: three-way entry-type resolution (absent/diverged-custom/diverged-GOLD/identical) +
  Principle-I GUID-remap-at-create.
- C3 complex-form (US3): RefType 1, multi-component + primary subset, `ComplexEntryTypesRS`.
- C4: in-closure reproduced (0 drop) vs out-of-closure reported (1 drop each); Preview/Move
  parity.
- C7: empty-source parity.
