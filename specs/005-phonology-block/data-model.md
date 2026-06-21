# Phase 3a Data Model

Five new `GrammarCategory` enum members + per-category registrations in
`Lib/categories.py`. No new dataclasses are introduced — the existing
Phase 0/1/2 entity model (RunContext, Selection, RunPlan, PlannedAction,
PlannedOverwrite, Skip, RunReport, ConflictPrompt, MergeDecision) covers
everything Phase 3a needs.

---

## E-3a-1 — `GrammarCategory` enum additions

```python
class GrammarCategory(enum.Enum):
    # ... existing members ...
    PHONOLOGICAL_FEATURES = "phonological_features"   # NEW (memo step 2)
    PHONEMES              = "phonemes"                # NEW (memo step 3)
    NATURAL_CLASSES       = "natural_classes"         # NEW (memo step 4)
    PHONOLOGICAL_RULES    = "phonological_rules"      # NEW (memo step 5)
    STRATA                = "strata"                  # NEW (memo step 5b)
    # PH_ENVIRONMENT already exists; Phase 3a relocates its sourcing.
```

Each maps to a registry entry in `Lib/categories.py` matching the
existing five-callback shape.

---

## E-3a-2 — Per-category callback signatures (existing pattern)

All six categories implement the same five callbacks. See
[contracts/category-callbacks.md](contracts/category-callbacks.md) for
the full contract.

```python
def <category>_enumerate_source(context, selection):
    """Read-only walk of source. Returns iterable of pieces."""
    ...

def <category>_dependencies(piece):
    """Returns tuple of GUIDs this piece's closure must include."""
    ...

def <category>_required_writing_systems(piece):
    """Returns frozenset[(ws_id, WSKind)] of WSes piece references."""
    ...

def <category>_plan_action(piece, context, ws_mapping):
    """Build PlannedAction / PlannedOverwrite / Skip per piece.
    READ-ONLY -- no LCM writes."""
    ...

def <category>_execute_action(action, context, ws_mapping, tag):
    """Write piece to target. Returns the new object for
    identity_remap stash if relevant."""
    ...
```

---

## E-3a-3 — Per-category data contracts

### PHONOLOGICAL_FEATURES

| Field | Type | Notes |
|-------|------|-------|
| LCM type | `IFsClosedFeature` (phon subsystem) | Distinct from inflection features in `MsFeatureSystemOA` |
| Owner | `LangProject.PhonologicalDataOA.PhonemeSetsOS[0].FeaturesOA` or similar phon feature system | TBD exact path; MCP-probe in implementation |
| Factory | `IFsClosedFeatureFactory.Create(Guid)` | Assumed Guid-preservable per Phase 0 IF pattern |
| Cross-refs IN | none | Leaf |
| Cross-refs OUT | feature values (owned via FeaturesOA chain) | Internal ownership |

### PHONEMES

| Field | Type | Notes |
|-------|------|-------|
| LCM type | `IPhPhoneme` | |
| Owner | `LangProject.PhonologicalDataOA.PhonemeSetsOS[0].PhonemesOC` | OC (owned collection) |
| Factory | `IPhPhonemeFactory.Create()` | **GUID preservation TBD** — probe at implementation; fall back to identity_remap |
| Cross-refs IN | `IPhPhoneme.FeaturesOA` → owned phon feature struct (OA, intra-object) | Internal |
| Cross-refs OUT | none (leaf for the phonology graph) | |

### NATURAL_CLASSES

| Field | Type | Notes |
|-------|------|-------|
| LCM types | `IPhNCSegments` AND `IPhNCFeatures` (subtypes of `IPhNaturalClass`) | Branch at execute by `ClassName` |
| Owner | `LangProject.PhonologicalDataOA.NaturalClassesOS` | OS |
| Factory | `IPhNCSegmentsFactory.Create()`, `IPhNCFeaturesFactory.Create()` | GUID preservation TBD per subtype |
| Cross-refs IN (Segments) | `SegmentsRC` → IPhPhoneme | RC — phonemes must precede ✓ |
| Cross-refs IN (Features) | `FeaturesOA` → IPhFeatureStruc | OA — owned with class |

### PH_ENVIRONMENT (relocated, no enum change)

| Field | Type | Notes |
|-------|------|-------|
| LCM type | `IPhEnvironment` | |
| Owner | `LangProject.PhonologicalDataOA.EnvironmentsOS` | OS |
| Factory | `IPhEnvironmentFactory.Create(Guid)` | Confirmed Guid-preservable per existing Phase 0 code |
| Cross-refs IN | none direct | |
| Cross-refs OUT | inverse: referenced by `IMoAffixAllomorph.PhoneEnvRC` and `IPhSegRuleRHS.LeftContextRA` etc. | Phase 3a establishes idempotency with allomorph creation |

### PHONOLOGICAL_RULES

| Field | Type | Notes |
|-------|------|-------|
| LCM type | `IPhPhonologicalRule` (concrete subclasses: `IPhSegmentRule`, `IPhRegularRule`, `IPhMetathesisRule`) | Multiple concrete types |
| Owner | `LangProject.PhonologicalDataOA.PhonRulesOS` | OS |
| Factory | `IPhRegularRuleFactory.Create()` (and siblings) | GUID preservation TBD per subtype |
| Cross-refs IN | `StratumRA` → IMoStratum (RA); input segments / output segments / contexts → IPhPhoneme + IPhNaturalClass + IPhEnvironment | Strata MUST precede (5b before 5) |

### STRATA

| Field | Type | Notes |
|-------|------|-------|
| LCM type | `IMoStratum` | |
| Owner | `LangProject.MorphologicalDataOA.StrataOS` | OS |
| Factory | `project.GetService(IMoStratumFactory)` | No StratumOperations class; use ServiceLocator pattern |
| Cross-refs IN | none direct | |
| Cross-refs OUT | inverse: referenced by `IMoInflAffixTemplate.StratumRA`, `IMoDerivAffMsa.StratumRA`, `IMoStemMsa.StratumRA`, `IMoCompoundRule.StratumRA`, `IPhPhonologicalRule.StratumRA` | Future-phase consumers |

---

## E-3a-4 — Modified entities (existing, unchanged interface)

- **`Selection`**: gains no new fields. The category dict accepts the
  new enum members.
- **`RunPlan`**: unchanged. New actions/overwrites/skips for the new
  categories flow through `actions`, `overwrites`, `skips` tuples as
  for any other category.
- **`PlannedAction`** / **`PlannedOverwrite`** / **`Skip`**: unchanged.
- **`CategoryReport`**: unchanged. The 9-counter shape from Phase 2
  covers all needs.

---

## Invariants

1. **Idempotency** (FR-307): for every PhEnvironment present in target
   by GUID, a re-run with phonology-block on emits zero new
   `IPhEnvironment` Create calls.
2. **Closure correctness** (FR-304): no PlannedAction for a
   PhonologicalRule is emitted unless every phoneme + class + env it
   references is either in target by GUID or in the same plan's
   actions (will exist before execute() reaches the rule).
3. **Phase 0/1/2 inviolance** (FR-311): for any `Selection` where the
   five new categories are all `False` AND `ph_environment` is `True`
   (the Phase 0 case), the plan and execution outputs are
   byte-identical to Phase 2's behavior. Verified by Scenario E in
   quickstart.md.
4. **GUID-first identity** (FR-303 / Principle I): every category
   either preserves GUIDs on create or records a remap entry. No
   silent identity drop.
5. **Strata before morphology** (FR-306): a plan whose Selection
   includes both Strata and any future morphology category (#14, #15,
   #17, #18) emits strata actions in plan order BEFORE the morphology
   actions. (Verified once Phase 3b lands; Phase 3a guarantees the
   ordering position.)
