"""Selection helpers (T073, spec.md FR-007 / Clarification Q4).

Pure-Python translation between the affix-tree picker's output (template /
slot / affix node toggles) and the `Selection.affix_picks` /
`Selection.template_picks` frozenset that the closure walker consumes.

The tree-picker UI emits a `PickerState` describing which template, slot,
and individual affix nodes are checked. This module collapses that state
into the canonical Selection shape — selecting a template implicitly
selects every affix under it via slot membership, etc.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, Set, Tuple

if __package__:
    from .models import GrammarCategory, Selection
else:
    from models import GrammarCategory, Selection


# ============================================================================
# Source inventory shape (the tree picker's input)
# ============================================================================

@dataclass(frozen=True)
class SourceAffixInventory:
    """A flattened view of the source's affix tree used by both the UI tree
    picker and these selection helpers.

    `template_to_slots` maps template GUID → tuple of slot GUIDs.
    `slot_to_affixes` maps slot GUID → tuple of affix GUIDs filling that slot.
    `unbound_affixes` is the set of affix GUIDs not attached to any template.
    """
    template_to_slots: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    slot_to_affixes: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    unbound_affixes: FrozenSet[str] = field(default_factory=frozenset)

    def all_affix_guids(self) -> FrozenSet[str]:
        affixes: Set[str] = set(self.unbound_affixes)
        for slot_affixes in self.slot_to_affixes.values():
            affixes.update(slot_affixes)
        return frozenset(affixes)

    def all_template_guids(self) -> FrozenSet[str]:
        return frozenset(self.template_to_slots.keys())


# ============================================================================
# Picker state (the UI's checked-node bag)
# ============================================================================

@dataclass(frozen=True)
class PickerState:
    """What the tree picker reports back: three sets of explicitly-checked
    node GUIDs at different tree levels. The semantic 'selecting a template
    selects all its affixes' is collapsed in `compute_required_affixes`."""
    checked_templates: FrozenSet[str] = field(default_factory=frozenset)
    checked_slots: FrozenSet[str] = field(default_factory=frozenset)
    checked_affixes: FrozenSet[str] = field(default_factory=frozenset)


# ============================================================================
# Public helpers (T073)
# ============================================================================

def compute_required_affixes(
    picker: PickerState,
    inventory: SourceAffixInventory,
) -> FrozenSet[str]:
    """Collapse picker state to the affix GUID set the closure walker needs.

    Resolution rules (Q4):
    1. Every explicitly-checked affix is included.
    2. Every affix under an explicitly-checked slot is included.
    3. Every affix under any slot of an explicitly-checked template is included.
    4. Unknown GUIDs (in `checked_*` but not in `inventory`) are ignored —
       the picker can't render them, so it shouldn't emit them, but the
       collapse is defensive.
    """
    affixes: Set[str] = set()

    affixes.update(picker.checked_affixes & inventory.all_affix_guids())

    for slot_guid in picker.checked_slots:
        affixes.update(inventory.slot_to_affixes.get(slot_guid, ()))

    for tpl_guid in picker.checked_templates:
        for slot_guid in inventory.template_to_slots.get(tpl_guid, ()):
            affixes.update(inventory.slot_to_affixes.get(slot_guid, ()))

    return frozenset(affixes)


def compute_required_templates(picker: PickerState,
                               inventory: SourceAffixInventory) -> FrozenSet[str]:
    """The set of template GUIDs that should land in `Selection.template_picks`.

    Currently a pass-through of `picker.checked_templates` filtered against the
    inventory (defensive). Slot- or affix-level checks do NOT pull templates
    in — templates are only transferred when explicitly selected at that level.
    """
    return frozenset(picker.checked_templates & inventory.all_template_guids())


def build_selection(picker: PickerState,
                    inventory: SourceAffixInventory,
                    *,
                    include_closure: bool = True,
                    extra_categories: Iterable[GrammarCategory] = ()) -> Selection:
    """Build a `Selection` from the picker state + inventory.

    `extra_categories` is the list of FR-004 categories the user toggled on
    OUTSIDE the affix tree (e.g., custom fields, inflection features). These
    land in `Selection.categories` with True values; AFFIXES/AFFIX_TEMPLATES are
    set True automatically iff the picker yields non-empty picks for them.
    """
    affix_picks = compute_required_affixes(picker, inventory)
    template_picks = compute_required_templates(picker, inventory)

    categories: Dict[GrammarCategory, bool] = {cat: True for cat in extra_categories}
    if affix_picks:
        categories[GrammarCategory.AFFIXES] = True
    if template_picks:
        categories[GrammarCategory.AFFIX_TEMPLATES] = True

    return Selection(
        categories=categories,
        include_closure=include_closure,
        affix_picks=affix_picks,
        template_picks=template_picks,
    )
