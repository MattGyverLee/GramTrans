# Contract: Reversal Closure Walk (`Lib/reversals.py`) — Part A

Covers reversal-index content: entries linked to copied senses, their reversal forms, reversal
categories, and recursive sub-entries. Closure-scoped to copied senses; plan-aware
(Principle III). Reuses the 024 resolver, owned-walk pattern, WS mapping, and dropped-item
channel.

## `plan_reversals(copied_senses, src_project, target, ctx, resolver_cache, dropped) -> list[ReversalDecision]`

Pure/decision pass, invoked from the plan-builder (`preview.py`) after the sense closure is
known. No writes.

**Behavior**
- For each source `IReversalIndex` (`ReversalIndexOperations.GetAll()`), gather entries whose
  `SensesRS` intersects `copied_senses` (via `EntriesForSense` or membership scan).
- Skip indexes with no such entries (closure scope, R0.1/R3).
- Map the index `WritingSystem` source→target (`ws_mapping`). If unmappable, emit a
  `DroppedItemRecord` (owner_kind `ReversalIndex`, reason `writing system not mapped`) and skip
  the index.
- For each in-scope entry, produce a `ReversalDecision`: the target index (existing or
  to-create), the `PartOfSpeechRA` `ReferenceDecision` (via `references.decide_reference` with
  the per-index `PartsOfSpeechOA` spec), the `SensesRS` members to link (copied only) plus a
  dropped record for any non-copied member, the reversal-form alternatives to write, and a
  recursive list of sub-entry decisions (`SubentriesOS`).

**Guarantees**
- Deterministic; never writes; never throws on a missing target list/index (reports instead).
- A reversal category shared across entries resolves once via `resolver_cache` (created at most
  once).

## `apply_reversals(decisions, target, ctx, resolver_cache, dropped) -> None`

Move-mode only. Executes the plan.
- Create the target index if the decision says so (`ReversalIndexOperations.Create(name,
  target_ws)`).
- Create each entry (`ReversalIndexEntryOperations.Create(index, form, sense)`), preserving the
  source GUID where the create path allows; write `ReversalForm` per mapped WS
  (non-destructive — never blank a populated target alt from an empty source, 024 FR-007).
- Apply the `PartOfSpeechRA` `ReferenceDecision` (`references.apply_reference`) against the
  target index `PartsOfSpeechOA`.
- Link `SensesRS` to the target senses copied this run.
- Recurse `SubentriesOS` with the same treatment.
- `apply_residue` the created entry/index (R7).

**Postconditions**
- Every in-scope reversal entry exists on the correct target per-WS index, references a real
  reversal category (or the divergence is reported), and links only copied senses.
- Exactly one `DroppedItemRecord` per non-reproduced item (category shared-default divergence,
  unmapped WS, non-copied sense member).

## Non-goals
- Does not copy reversal indexes with no entries linking copied senses.
- Does not touch `LangProject.PartsOfSpeechOA` (reversal categories are per-index — see
  `reversal-category-resolution.md`).
- Does not copy config-view files (see `config-view-copy.md`).
