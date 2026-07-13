"""Part A -- reversal closure walk (feature 025-full-reversals).

For every sense the transfer copies, discover the source reversal-index
entries that link back to it (`IReversalIndexEntry.SensesRS` /
`IReversalIndex.EntriesForSense`), reproduce those entries on the target's
matching per-writing-system index (creating the index via
`ReversalIndexOperations.Create` when absent), carry the entry's reversal
form and recurse its owned sub-entries (`SubentriesOS`), and resolve each
entry's reversal category (`PartOfSpeechRA`) against that index's OWN
`PartsOfSpeechOA` possibility list -- never `LangProject.PartsOfSpeechOA`
-- via feature 024's generic referenced-possibility resolver.

This module is closure-scoped: only reversal indexes with >=1 entry linking
a copied sense enter the plan (research.md R0.1/R3). See
specs/025-full-reversals/data-model.md and
specs/025-full-reversals/contracts/reversal-walk.md /
reversal-category-resolution.md for the full contract.

Reuses (feature 024, unchanged):
- `references.decide_reference` / `references.apply_reference` +
  `ReferenceFieldSpec` -- drives `PartOfSpeechRA` resolution against the
  per-index `PartsOfSpeechOA` list.
- `owned.walk_owned_children` -- the recursive owned-child walk pattern,
  reused for `SubentriesOS` recursion.
- `report.DroppedItemRecord` / `FidelityStatus` -- the unified never-silent
  report channel (new owner_kind values: "ReversalIndexEntry",
  "ReversalIndex"; see `report.py`).
- `protection._is_protected` -- custom-vs-shared classification for
  reversal-category divergence handling.
- `ws_mapping` -- source->target analysis-WS mapping; gates every reversal
  index (R4) before any of its entries are considered in-scope.

This is decision/scaffolding-only (Phase 1 + 2 of tasks.md): `plan_reversals`
/ `apply_reversals` bodies land with User Story 1 (T014/T016).
"""
from __future__ import annotations

if __package__:
    from . import owned
    from . import protection
    from . import report
    from . import references
    from . import ws_mapping
    from .models import (
        ReferenceCardinality,
        ReferenceFieldSpec,
    )
else:
    import owned
    import protection
    import report
    import references
    import ws_mapping
    from models import (
        ReferenceCardinality,
        ReferenceFieldSpec,
    )


# ============================================================================
# Reversal field map (T008; data-model.md "Reversal field map")
# ============================================================================
# The reference/owned fields on a reversal entry, routed through the 024
# resolver (`references.py`) or the owned-walk (`owned.py`). This is the
# completeness contract the fidelity census (T033/tasks.md) verifies against
# live MCP-confirmed LCM members -- every populated field on
# IReversalIndexEntry MUST appear here or be explicitly out of scope.
#
# Each row is either:
#   - a `ReferenceFieldSpec` (routed through `references.decide_reference` /
#     `apply_reference`), for the one reference field (`PartOfSpeechRA`); or
#   - a plain descriptor dict for fields handled by dedicated logic instead
#     of the generic resolver: `SensesRS` (re-wire to the copied-sense set,
#     not a possibility-list reference), `ReversalForm` (IMultiUnicode value
#     copy, non-destructive), and `SubentriesOS` (owned recurse via
#     `owned.walk_owned_children`'s pattern).

REVERSAL_FIELD_MAP = {
    "PartOfSpeechRA": ReferenceFieldSpec(
        owner_class="ReversalIndexEntry",
        field_name="PartOfSpeechRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda tgt_index: tgt_index.PartsOfSpeechOA,
        hierarchical=True,
    ),
    "SensesRS": {
        "kind": "ref_seq_rewire",
        "description": (
            "Ref seq; not a possibility item -- re-wired to the copied "
            "target senses. Members not in the copy set produce a "
            "DroppedItemRecord (owner_kind='ReversalIndexEntry', "
            "reason='member not in copy set')."
        ),
    },
    "ReversalForm": {
        "kind": "multi_unicode_value_copy",
        "description": (
            "IMultiUnicode; copied per mapped writing system (value field, "
            "not a reference). Non-destructive: an empty source alt never "
            "blanks a populated target alt (024 FR-007)."
        ),
    },
    "SubentriesOS": {
        "kind": "owned_recurse",
        "description": (
            "Owned seq; hierarchical sub-entries recursed like sub-senses "
            "via the owned-walk pattern (owned.py), not the resolver."
        ),
    },
}
