# Contract: Affix-MsEnv Reproduction

Governs the reproduction of the four `MoAffixAllomorph`/`MoAffixForm` morphosyntactic-
environment fields when a copied entry owns an affix allomorph. Replaces the report-only
`owned._report_dropped_moaffix_msenv_fields` stub. Mirrors the existing PhoneEnvRC contract in
`contracts/owned-object-walk.md` (feature 024).

## Entry points (`Lib/owned.py`)

### Move leg
```
reproduce_moaffix_msenv_data(src_allo, new_allo, ctx, tag, resolver_cache, dropped) -> None
```
Called from `reproduce_allomorph_hung_data` in place of
`_report_dropped_moaffix_msenv_fields`. Reproduces the four fields onto `new_allo`. Never
raises: every per-field failure is caught and emitted as a `DroppedItemRecord`, matching the
module's posture elsewhere.

### Preview twin (read-only)
```
_plan_moaffix_msenv_decisions(src_allo, ctx, dropped) -> list[ReferenceDecisionRecord]
```
Called from `plan_allomorph_hung_data_decisions`. Emits the LINK/CREATE decisions the Move leg
will act on, plus any `DroppedItemRecord` for report-only outcomes, into
`PlannedAction.reference_decisions`. Writes nothing.

## Preconditions

- `src_allo` is a `MoAffixAllomorph` (`_is_moaffix_allomorph` true). For a `MoStemAllomorph`
  (fields absent) or an affix allomorph with none of the four fields populated, both legs are
  **vacuous** (no records) — SC-006 no-regression.
- Reads that require a cast use the MCP-confirmed casts: `IMoAffixAllomorph(obj)` for
  `MsEnvPartOfSpeechRA`/`MsEnvFeaturesOA`/`PositionRS`; `IMoAffixForm(obj)` for
  `InflectionClassesRC`.
- `ctx.target_handle` exposes the live target project; `resolver_cache` is the per-run dedup
  dict; `tag` is the residue tag for created objects.

## Postconditions (per field)

| Field | On success | On failure |
|---|---|---|
| `MsEnvPartOfSpeechRA` | target allomorph's `MsEnvPartOfSpeechRA` references the resolved/created target POS | `DroppedItemRecord(field="MsEnvPartOfSpeechRA")`; target field unchanged |
| `InflectionClassesRC` | each resolvable class linked/created and added to target `InflectionClassesRC` (dedup) | per-class `DroppedItemRecord(field="InflectionClassesRC")`; resolvable classes still added |
| `MsEnvFeaturesOA` | target allomorph owns a deep-copied `IFsFeatStruc` with resolvable values | per-value `DroppedItemRecord(field="MsEnvFeaturesOA")`; resolvable values still reproduced |
| `PositionRS` | target allomorph's `PositionRS` holds resolved environments in **source order** | per-position `DroppedItemRecord(field="PositionRS")`; never creates an environment |

## Guarantees (map to invariants / FRs)

- **G1 (never-silent, FR-007/INV-3)**: no field or member is dropped without a
  `DroppedItemRecord` naming owner, field, and source-item identity.
- **G2 (non-destructive, FR-005/INV-2)**: an empty/unset source field performs no write; a
  populated target field is never blanked.
- **G3 (GUID preserve, Principle I/INV-1)**: created POS and inflection classes preserve the
  source GUID unless the target already holds it.
- **G4 (dedup, FR-006/SC-005/INV-4)**: a POS/class/environment shared by K allomorphs is
  resolved/created once per run via `resolver_cache`.
- **G5 (order, INV-5)**: `PositionRS` output order equals source order.
- **G6 (Preview/Move parity, Principle III/INV-6)**: the plan twin's decisions equal the Move
  leg's actions for the same input.
- **G7 (never-create-environment)**: `PositionRS` and `PhoneEnvRC` never create a phonological
  environment (contract non-goal; environments transfer as their own category).
- **G8 (closure scope, Principle V)**: an inflection class / POS whose owner is out-of-closure
  and absent from target is reported, not invented.

## Non-goals

- Creating phonological environments (G7) or writing-system objects.
- Reproducing complex/open feature values beyond feature 031's supported closed-feature set
  (reported, not reproduced).
- Retroactive remediation of already-copied targets (FR-008).

## Test obligations (for `/speckit-tasks`)

- RED-before-GREEN unit tests per field family: CREATE, LINK, REPORT paths.
- Preview/Move parity test (G6): plan decisions match move outcomes.
- Order test (G5): `PositionRS` with ≥2 positions preserves order; a middle unresolvable
  position is reported without reordering the rest.
- Dedup test (G4): two allomorphs sharing a class/POS → one create.
- Empty-source no-blank test (G2): populated target field survives an empty source field.
- Vacuous test (SC-006): `MoStemAllomorph` and unpopulated `MoAffixAllomorph` emit zero
  records in both legs.
- Census flip test (FR-009): the four rows classify COPIED; `classify_field` never-silent
  guard still passes.
