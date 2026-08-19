# Process morphology create path (Phase 0 research, feature 038)

Resolves the Phase 4 / US5 research unknown behind FR-023, FR-024, FR-025 and SC-006.

**Instrument status: FLExToolsMCP was AVAILABLE and used as the primary instrument.**
Server 2.9.1, liblcm 11.0.0 (index match `exact`), flexicon installed 4.5.0 / index 4.4.1
(`fallback_latest`, so flexicon *wrapper-coverage* answers were re-checked against the working
tree at `D:/Github/_Projects/_LEX/flexicon`). Every run used `write_enabled=False` and returned
`write_certification.is_certified_readonly = true`; projects touched were `Ejagham Mini`,
`Esperanto`, `Mbugwe LizzieHC practice`, and `Target` was never opened.

Successful op ids: `op-042510239-010` (factory reflection + Ejagham Mini),
`op-042536212-011` (Esperanto), `op-042605267-012` (Mbugwe enumeration),
`op-042704061-014` (Mbugwe ownership fingerprints). Rejected at the casting/preflight gate:
`op-042335049-005`, `op-042408370-007`, `op-042436633-008`, `op-042643458-013`.

## Summary verdict

**Phase 4 is feasible as specified.** A GUID-preserving create path exists for every class in
the process-rule graph, but not as a flexicon wrapper: it must go through
`ServiceLocator.GetService(<IFactory>)` plus the existing GUID-preserving create helper.
Feasibility depends on three things:

1. Reproducing an ordered, *self-referential* graph. `OutputOS` members reference `InputOS`
   members of the same rule, so Input must be created first and a source-GUID -> new-object map
   carried into the Output pass.
2. Resolving four *external* reference targets in the destination (FR-024): `PhPhoneme`,
   `PhBdryMarker`, `PhNaturalClass`/`PhNCFeatures`, and the finding that most enlarges Phase 4,
   `PhSimpleContext*` objects owned by `PhPhonData.ContextsOS` that a `PhSequenceContext` input
   member references but does **not** own.
3. Phase 1 landing first, because FR-024's "resolve to the destination's matched items and not
   to duplicates" is exactly the phoneme / natural-class matching Phase 1 delivers.

## 1. Does a create path exist?

**No flexicon wrapper. VERIFIED.**

- MCP `find_wrappers_for_lcm`: `IMoAffixProcess` (entity) -> `found: false`;
  `IMoAffixProcessFactory` (factory) -> `found: false`.
- `MorphRuleOperations` disclaims it at
  `flexicon/flexicon/code/Grammar/MorphRuleOperations.py:25-28`: affix processes are "owned by
  LexEntry as allomorphs (LexemeFormOA/AlternateFormsOS), managed through AllomorphOperations,
  not this class." Its creates are only `CreateCompoundRule` (`:299`) and
  `CreateAffixTemplate` (`:361`).
- `AllomorphOperations` does not manage it either.
  `Create(self, entry_or_hvo, form, morphType=None, wsHandle=None)` at
  `flexicon/flexicon/code/Lexicon/AllomorphOperations.py:204` knows only
  `IMoStemAllomorphFactory` / `IMoAffixAllomorphFactory` (`:284`, `:286`) and has **no `guid=`
  kwarg at all**. `Duplicate` (`:371`) raises `FP_ParameterError` on any other `ClassName`
  (`:445-450`).

The create surface is `GetService(IMoAffixProcessFactory)` plus
`BaseOperations._CreateWithGuid(self, factory, guid=None, kind=None)` at
`flexicon/flexicon/code/BaseOperations.py:1884`. GramTrans already has the equivalent:
`create_with_guid(factory, src_guid, kind)` at `src/gramtrans/Lib/categories.py:6248`,
delegating to `owned._create_owned_via_factory`.

**Where the downgrade lives (VERIFIED).** `_dispatch_allomorph_subclass`
(`src/gramtrans/Lib/categories.py:5485-5490`) whitelists only `{"MoAffixAllomorph",
"MoStemAllomorph"}` and returns `None` otherwise; `_walk_entry_allomorphs._mk`
(`src/gramtrans/Lib/categories.py:6185-6187`) then took the ternary's `else` and sent the object
to `IMoAffixAllomorphFactory` anyway. Branch `038-affix-fidelity` (`18c0ece`, unmerged) already
inserted the FR-025 skip at both the Move site and its Preview twin
(`_plan_entry_reference_decisions`), emitting a `DroppedItemRecord`. Phase 4 replaces that skip
with a real create; the skip stays as the fallback.

## 2. The object graph to reproduce

LCM property names, VERIFIED from the liblcm 11.0.0 index served by MCP (`get_object_api` on
`IMoAffixProcess` plus own-property extraction for the members):

| Class | Own properties | Kind / target |
|---|---|---|
| `MoAffixProcess` | `InputOS` | owning sequence of `IPhContextOrVar` (flid **5029002**) |
| | `OutputOS` | owning sequence of `IMoRuleMapping` (flid **5029003**) |
| | `FeatureConstraints` | derived, read-only (`GetFeatureConstraints()`) |
| | inherited `Form`, `MorphTypeRA`, `IsAbstract`, `LiftResidue`, `AllomorphEnvironments`, `InflectionClassesRC` | from `IMoForm` / `IMoAffixForm` |
| `MoCopyFromInput` | `ContentRA` | ref-atomic -> `IPhContextOrVar` (an **Input member of the same rule**) |
| `MoInsertPhones` | `ContentRS` | ref-sequence -> `IPhTerminalUnit` (`PhPhoneme` or `PhBdryMarker`) |
| `MoModifyFromInput` | `ContentRA`, `ModificationRA` | -> `IPhContextOrVar`; -> `IPhNCFeatures` |
| `MoInsertNC` | `ContentRA` | ref-atomic -> `IPhNaturalClass` |
| `PhSimpleContextSeg` | `FeatureStructureRA` | ref-atomic -> `IPhPhoneme` |
| `PhSimpleContextNC` | `FeatureStructureRA`, `PlusConstrRS`, `MinusConstrRS` | -> `IPhNaturalClass`; ref-sequences -> `IPhFeatureConstraint` |
| `PhSimpleContextBdry` | `FeatureStructureRA` | ref-atomic -> `IPhBdryMarker` |
| `PhIterationContext` | `MemberRA`, `Minimum`, `Maximum` | ref-atomic -> `IPhPhonContext`; two Int32 |
| `PhSequenceContext` | `MembersRS` | ref-sequence -> `IPhPhonContext` |
| `PhVariable` | (none) | pure placeholder |

Creation is uniform: `GetService(I<Class>Factory)`, `Create(Guid)`, `Add` to the owning
sequence, then set references. `MoAffixProcess` attaches exactly as an allomorph does:
`entry.LexemeFormOA = obj` or `entry.AlternateFormsOS.Add(obj)`. VERIFIED live: all 18
instances report `MoAffixProcess owned-by LexEntry.flid5002030` (`op-042704061-014`).

**References that must resolve to destination objects (FR-024)**, from `op-042704061-014`:

- `PhSimpleContextSeg.FeatureStructureRA` -> `PhPhoneme owned-by PhPhonemeSet.flid5089002` (x12)
- `MoInsertPhones.ContentRS` -> `PhPhoneme` (x45), `PhBdryMarker owned-by
  PhPhonemeSet.flid5089003` (x18)
- `PhSimpleContextNC.FeatureStructureRA` -> `PhNCFeatures owned-by PhPhonData.flid5099003` (x5)
- `PhSequenceContext.MembersRS` -> `PhSimpleContextNC` (x5), `PhSimpleContextSeg` (x1), each
  `owned-by PhPhonData.flid5099004`

Owner class and flid are VERIFIED. Reading flid 5099003 as `PhPhonData.NaturalClassesOS` and
5099004 as `PhPhonData.ContextsOS` is INFERRED from declared target types plus the live counts
`ContextsOS=93 / FeatConstraintsOS=89` in the same op. That fourth bullet is the sharp edge: a
`PhSequenceContext` in `InputOS` is owned by the rule, but its members are **shared,
project-level contexts**. Transferring the rule without them leaves `MembersRS` empty, a silent
content loss FR-023 / SC-006 must not permit, and a Phase 2 closure edge rather than a Phase 4
local concern.

`PhFeatureConstraint` is owned by `PhPhonData.FeatConstraintsOS` (index) and referenced from
`PlusConstrRS` / `MinusConstrRS`; live `totalFeatureConstraintRefs=0`, so it is
present-but-unexercised. Its `FeatureRA` -> `IFsFeatDefn` ties it to the feature system, i.e. to
the FsFeatStrucType / FsComplexFeature gap parked in Phase 5.

## 3. GUID preservation

**Every class in the graph can be created with a preserved GUID. VERIFIED live**
(`op-042510239-010`, read-only .NET reflection over each concrete factory implementation):
`MoAffixProcessFactory`, `MoCopyFromInputFactory`, `MoInsertPhonesFactory`,
`MoModifyFromInputFactory`, `MoInsertNCFactory`, `PhSimpleContextSegFactory`,
`PhSimpleContextNCFactory`, `PhSimpleContextBdryFactory`, `PhIterationContextFactory`,
`PhSequenceContextFactory`, `PhVariableFactory` and `PhFeatureConstraintFactory` each report
exactly `['Create()', 'Create(Guid guid)']`. **No class here is identity-regenerating by
necessity.** Reflection over the *interface* type returns `[]`; only the concrete implementation
carries the overloads.

The swallowed-`TypeError` hazard therefore has no live instance, *provided* the code calls
`Create(Guid)` on the factory (or `_CreateWithGuid` / `create_with_guid`) rather than a wrapper
method with a nonexistent `guid=` kwarg. `AllomorphOperations.Create` has no such kwarg, so
calling it that way would raise `TypeError` and be swallowed into a generic drop.

Two corollaries. `MoAffixAllomorphFactory` also reports `Create(Guid guid)`, so the comment at
`src/gramtrans/Lib/matcher.py:262` is stale for the allomorph half (out of Phase 4 scope, worth
an issue). And `MoAffixProcess` is already in `residue.CARRIER_A_CLASSES`
(`src/gramtrans/Lib/residue.py:43`), consistent with its inherited `LiftResidue`, so residue
tagging needs no new work.

## 4. Live corroboration

- `Ejagham Mini`: 252 entries, **0** `MoAffixProcess`; `ContextsOS=0`, `FeatConstraintsOS=0`
  (`op-042510239-010`).
- `Esperanto`: 15,318 entries, **0** `MoAffixProcess` (15,262 `MoStemAllomorph`, 72
  `MoAffixAllomorph`); contexts 0 (`op-042536212-011`).
- **`Mbugwe LizzieHC practice`: 255 entries, 18 `MoAffixProcess`** (plus 124
  `MoAffixAllomorph`, 137 `MoStemAllomorph`); `ContextsOS=93`, `FeatConstraintsOS=89`
  (`op-042605267-012`, `op-042704061-014`).

Aggregate member census over those 18 rules: `InputOS` = `PhVariable` 21,
`PhSimpleContextSeg` 12, `PhSequenceContext` 6, `PhSimpleContextNC` 5. `OutputOS` =
`MoInsertPhones` 63, `MoCopyFromInput` 38. **`MoModifyFromInput`, `MoInsertNC`,
`PhSimpleContextBdry` and `PhIterationContext` occur zero times** in any sanctioned project;
their rows above are index-derived, not observed.

Representative rule (entry `re-2`, `311f04ea-eb20-4631-a8c4-bacdaacfa24d`): Input =
`[PhSimpleContextNC -> NC 8f5b331b..., PhVariable]`; Output = `[MoInsertPhones -> PhPhoneme
7325210f..., MoCopyFromInput -> that PhSimpleContextNC, MoInsertPhones -> PhBdryMarker
3bde17ce..., MoCopyFromInput -> the same PhSimpleContextNC, MoCopyFromInput -> the PhVariable]`.
Note one Input member referenced by two Output mappings: the GUID map must be
many-to-one-tolerant, and `OutputOS` order is significant. `Mbugwe LizzieHC practice` is the
corpus Phase 4's acceptance test needs.

## 5. The FR-025 skip contract

When any part of a process rule cannot be reproduced, the engine MUST:

1. Create **nothing** in its place: no `MoAffixAllomorph`, no `MoStemAllomorph`, no
   partially-populated `MoAffixProcess`. A shell created before the failure was detected must be
   rolled back or deleted; a shell with an empty `OutputOS` is a silent alteration of kind and is
   forbidden.
2. Emit exactly one `DroppedItemRecord` (`src/gramtrans/Lib/models.py:1023`) with
   `owner_kind="LexEntry"`, `owner_guid` = source entry GUID, `field_name` = `"LexemeFormOA"` or
   `"AlternateFormsOS"`, `item_name="MoAffixProcess"`, `item_guid` = the rule's source GUID, and
   a `reason` naming the specific blocker, e.g. `"MoAffixProcess input member PhSequenceContext
   <guid> references PhPhonData.ContextsOS context <guid> absent in destination -- rule not
   transferred (FR-024/FR-025)"`. Dedup key is `(owner_guid, field_name, item_guid)`, so the
   reason is diagnostic, not identity.
3. Mark the owning entry `FidelityStatus.PARTIAL` and surface the record in the post-run
   statistics panel. A run that skips a rule MUST NOT be reported as clean (SC-010).
4. Take the same decision in `Lib/preview.py`, not only `Lib/transfer.py` (Principle III):
   Preview must already show the skip and its reason.

**How a test proves the downgrade cannot recur.** Three layers:

- *Unit, class-identity assertion.* Feed `_walk_entry_allomorphs` a fake allomorph with
  `ClassName == "MoAffixProcess"` while the process-rule create path is stubbed to fail. Assert
  (a) neither `IMoAffixAllomorphFactory` nor `IMoStemAllomorphFactory` was invoked, and (b)
  exactly one `DroppedItemRecord` with `item_name == "MoAffixProcess"` was appended. This locks
  the `else`-branch defect at `categories.py:6185-6187`.
- *Unit, negative-whitelist invariant.* Assert that for every `ClassName` where
  `_dispatch_allomorph_subclass(...) is None`, the path returns without calling any allomorph
  factory. That generalises the lock past `MoAffixProcess` to any future `IMoForm` subclass, so
  it tests the FR-025 shape rather than the FR-025 instance.
- *Census gate (the real acceptance).* Transfer `Mbugwe LizzieHC practice` into a restored blank
  target and require `count(MoAffixProcess) == 18` AND `delta(MoAffixAllomorph) == +124
  exactly`. A downgrade shows as `MoAffixProcess 0` with `MoAffixAllomorph +142`, the same
  excess signature (+13 / +1) that exposed the original defect. Add per-member counts
  (`MoInsertPhones` 63, `MoCopyFromInput` 38, `PhVariable` 21, `PhSimpleContextSeg` 12,
  `PhSequenceContext` 6, `PhSimpleContextNC` 5) so an empty-`OutputOS` shell also fails,
  satisfying SC-006's "with their input and output content".

## Decision criteria for Phase 4

Phase 4 may proceed when all of the following hold; otherwise it degrades to the FR-025 skip.

1. **Ordering.** Preview plans `InputOS` before `OutputOS` and carries a source-GUID ->
   target-object map for the intra-rule `ContentRA` back-references. Computed in
   `Lib/preview.py`, executed in `Lib/transfer.py` (Principle III).
2. **GUID preservation everywhere.** All creates go through `create_with_guid`
   (`categories.py:6248`). No bare `Create()`. Any fallback to a fresh identity is logged and
   recorded in `identity_remap`.
3. **External references resolved, never minted.** `PhPhoneme`, `PhBdryMarker`,
   `PhNaturalClass` / `PhNCFeatures` resolve through Phase 1's resolve-or-create with the
   natural-key fallback. **Phase 4 depends on Phase 1 landing first**, or FR-024's "not to
   duplicates" is unachievable, since the destination's 23-phoneme starter inventory is
   precisely what got duplicated.
4. **`PhPhonData.ContextsOS` closure.** Rules with a `PhSequenceContext` input (6 of 18 in the
   Mbugwe corpus, one third) need project-level contexts. Either Phase 2's closure pulls them,
   or those rules skip under FR-025 with the reason naming the missing context. A partially
   populated `MembersRS` is not an acceptable outcome.
5. **Unexercised classes are skipped, not guessed.** `MoModifyFromInput`, `MoInsertNC`,
   `PhSimpleContextBdry`, `PhIterationContext` and non-empty `PlusConstrRS` / `MinusConstrRS`
   have zero live instances. Implement from the index if cheap, but ship behind the FR-025 skip
   until a corpus exercises them, matching the "NEEDS_MANUAL until a corpus exercises them"
   posture at `categories.py:5480`.
6. **Acceptance is a census diff** against `Mbugwe LizzieHC practice`, per section 5.

## Open questions

- **Which flid is which property.** `5099003` / `5099004` on `PhPhonData` are read as
  `NaturalClassesOS` / `ContextsOS` by INFERENCE. One read-only probe printing those two counts
  beside the flids would settle it; skipped to keep the probe count down.
- **Rollback granularity.** Whether `transfer.py` can discard a half-built `MoAffixProcess`
  inside its existing transaction/undo scoping, or must pre-validate the whole graph before the
  first create. Pre-validation in `preview.py` is what criterion 1 assumes, but the executor's
  guarantee is unverified here.
- **`GetFeatureConstraints()`** is derived and read-only; whether reproducing `PlusConstrRS` /
  `MinusConstrRS` suffices, or whether the `PhFeatureConstraint` objects must pre-exist in
  `PhPhonData.FeatConstraintsOS`, is untested (zero live instances). Likewise
  `PhIterationContext.Minimum` / `Maximum` sentinel values.
- **flexicon index staleness.** MCP served 4.4.1 metadata against installed 4.5.0. The "no
  wrapper exists" conclusion was re-confirmed against the 4.5.0 working tree by grep, but
  `python -m flextoolsmcp.refresh` should precede any later claim about flexicon coverage.
- **Upstream ask (out of 038 scope).** Whether flexicon should grow a `MoAffixProcess`
  create/duplicate surface so GramTrans is not the sole holder of this knowledge.
