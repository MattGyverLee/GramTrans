# Implementation Plan: Affix-Allomorph Morphosyntax Fidelity

**Branch**: `028-affix-allomorph-morphosyntax` | **Date**: 2026-07-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/028-affix-allomorph-morphosyntax/spec.md`

## Summary

Close the affix-allomorph morphosyntax gap that feature 024's fidelity census surfaced and
DROP_REPORTed: reproduce the four un-reproduced fields — `MsEnvPartOfSpeechRA`,
`InflectionClassesRC` (on the parent `MoAffixForm`), `MsEnvFeaturesOA`, `PositionRS` — when a
copied entry owns an affix allomorph carrying them, carrying over 024's never-silent
guarantee.

The work is a **targeted replacement of one existing report-only stub**. `Lib/owned.py`
already isolates the gap in `_report_dropped_moaffix_msenv_fields` (Move) — there is currently
no Preview twin because DROP_REPORT has no CREATE/LINK leg. This feature replaces that stub
with a real reproduce leg (Move) plus a Preview-decision twin, exactly mirroring the existing
`_reproduce_phone_env_rc` / `_plan_phone_env_rc_decisions` pair, and reuses machinery that
**already exists**:

- `MsEnvPartOfSpeechRA` → the grammar/MSA **POS-resolution machinery**
  (`categories._resolve_target_pos` + the POS create-with-ancestors path), NOT 024's
  possibility-list resolver — POS is a grammar object with concept↔GUID remap already handled
  there (resolves the spec's deferred decision; see research R1).
- `InflectionClassesRC` → the existing **inflection-class machinery**
  (`categories._create_inflection_class` / `IMoInflClassFactory`, resolve-by-GUID against the
  owning POS), closure-scoped (Principle V).
- `MsEnvFeaturesOA` → **deep-copy** the owned `IFsFeatStruc` per 024's owned-child discipline,
  resolving feature-value references against the target feature system (reuse feature 031's
  inflection-feature resolution where applicable); report unresolvable values.
- `PositionRS` → the **existing environment-resolution path**
  (`owned._target_phonological_environments`, link-or-report, never create), preserving source
  order (RS vs `PhoneEnvRC`'s RC).

Finally, flip the four `fidelity_census.py` rows from DROP_REPORTED to COPIED (with concrete
code sites), preserving the never-silent guard. Prevention/forward-copy only (FR-008).

## Technical Context

**Language/Version**: Python 3 (CPython + pythonnet), hosted by a stock FlexTools install.

**Primary Dependencies**: flexicon (`pyflexicon>=4.1`) Operations-class API; `SIL.LCModel`
interfaces via pythonnet (`IMoAffixAllomorph`, `IMoAffixForm`, `IPartOfSpeech`,
`IMoInflClass`, `IMoInflClassFactory`, `IFsFeatStruc` + feature-structure factories,
`IPhEnvironment`); PyQt for the host report panel.

**Storage**: FieldWorks `.fwdata` project pair through the LCM cache; divergence baseline is
the live target project (inherited from 024 FR-005).

**Testing**: pytest under `tests/unit/`; the model-driven fidelity census
(`tests/verification/fidelity_census.py`) is the offline harness whose four affix-MsEnv rows
flip DROP_REPORTED → COPIED.

**Target Platform**: Windows (FlexTools host); source → target between two FLEx projects.

**Project Type**: Single project — FlexTools-compatible module with helpers under
`src/gramtrans/Lib/`.

**Performance Goals**: Bounded per-allomorph overhead over the existing closure walk. Target
items (POS, inflection class, environment) resolved once and reused via the existing per-run
`resolver_cache` (SC-005), so cost is O(distinct target items), not O(references).

**Constraints**: Preview-before-mutate (Principle III) — every reproduce decision appears in
the plan as CREATE/LINK/Report before any write, via the new Preview twin. Non-destructive:
never blank a populated target field from an empty source (FR-005). Graceful degrade: an
unresolvable item is reported, never thrown or silently dropped (Principle I "fail loudly",
"No silent skips" gate). flexicon-direct only (Principle II).

**Scale/Scope**: Four fields on `MoAffixAllomorph`/`MoAffixForm`. Vacuous on the Ejagham
corpora (0/106 allomorphs populate any field), so unit fixtures and the attended live proof
must be **constructed** (a T037-class item, never run under an unattended loop).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. FLEx Domain Fidelity** (NON-NEGOTIABLE) | **Directly served.** Principle I already requires "allomorph → environment … MUST resolve to real objects in the target after transfer, or … fail loudly rather than silently drop." This feature implements that clause for the four affix-MsEnv fields. GUID preservation on create (inflection classes via `IMoInflClassFactory.Create(Guid)`; POS via the existing create-with-ancestors path) and the concept↔GUID remap for created POS are inherited from the grammar path. **PASS.** |
| **II. flexicon-Direct** | All new code uses flexicon Operations + `project.GetService(IFooFactory)` fallback + `CastingOperations.cast_to_concrete` for the `IMoAffixAllomorph`/`IMoAffixForm` polymorphic casts the MCP flagged (`requires_cast: true`). No adapter indirection. **PASS.** |
| **III. Preview-Before-Mutate** (NON-NEGOTIABLE) | The current stub is report-only (no plan twin). This feature adds a Preview-decision twin (`_plan_moaffix_msenv_decisions`) mirroring `_plan_phone_env_rc_decisions`, so CREATE/LINK/Report decisions appear in Preview before any Move write. **PASS with design obligation** (tracked in research R2). |
| **IV. Phased Merge Discipline** | Reuses existing mode vocabulary and the grammar path's create/link semantics. No new mode introduced. Empty source never blanks target (FR-005, update semantic). **PASS.** |
| **V. Referential Completeness** | Inflection classes "pull the categories they attach to" (Principle V, verbatim) — the owning POS is resolved/created in-closure; out-of-closure owners are reported, not invented. **PASS.** |
| **Workflow: No silent skips** | Every field that cannot be reproduced routes into the existing dropped-item report channel (FR-007). The census never-silent guard is preserved and re-run. **PASS** — this gate is the feature's backstop. |

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/028-affix-allomorph-morphosyntax/
├── plan.md              # This file
├── research.md          # Phase 0 output — resolves the deferred POS-resolver decision + probes
├── data-model.md        # Phase 1 output — the 4 fields, their targets, dispositions
├── quickstart.md        # Phase 1 output — offline + attended-live validation guide
├── contracts/
│   └── affix-msenv-reproduction.md   # Phase 1 output — the reproduce/plan contract per field
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
src/gramtrans/Lib/
├── owned.py             # MODIFY: replace _report_dropped_moaffix_msenv_fields with
│                        #   reproduce_moaffix_msenv_data (Move) + _plan_moaffix_msenv_decisions
│                        #   (Preview twin); wire both into reproduce_allomorph_hung_data /
│                        #   plan_allomorph_hung_data_decisions. PositionRS reuses
│                        #   _target_phonological_environments; MsEnvFeaturesOA deep-copies.
├── categories.py        # REUSE: _resolve_target_pos + POS create-with-ancestors (MsEnvPOS);
│                        #   _create_inflection_class / IMoInflClassFactory (InflectionClassesRC).
│                        #   New thin helpers may land here if the POS/InflClass entry points
│                        #   need an affix-MsEnv-shaped wrapper.
├── references.py        # REUSE: _guid_str, _item_label, _find_in_possibility_list helpers.
├── models.py            # REUSE: DroppedItemRecord, ReferenceDecisionRecord (no new type expected).
└── report.py            # REUSE: dropped-item channel already carries these records.

tests/
├── unit/
│   ├── test_028_affix_msenv_reproduction.py  # NEW: CREATE/LINK/report per field family +
│   │                                         #   Preview/Move parity + order (PositionRS) +
│   │                                         #   dedup (SC-005) + empty-source no-blank (FR-005)
│   └── test_028_msenv_feature_struct.py      # NEW: MsEnvFeaturesOA deep-copy + feature-value
│                                             #   resolution/report
└── verification/
    └── fidelity_census.py    # MODIFY: 4 MoAffixAllomorph rows DROP_REPORTED → COPIED
```

**Structure Decision**: Single-project FlexTools module. The entire behavioral change is
localized to `Lib/owned.py` (the file that already owns allomorph-hung-data reproduction and
already isolated this gap in one stub), reusing POS/inflection-class machinery from
`categories.py` and the environment path from `owned.py` itself. No new module is warranted —
adding one would fragment the allomorph-hung-data logic that `owned.py` deliberately keeps
together. The census flip is the only change outside `Lib/`.

## Complexity Tracking

> No Constitution Check violations — table intentionally omitted.
