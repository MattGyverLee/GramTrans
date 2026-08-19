"""Item-data roles and status-label maps for the wizard's trees (feature 039, T007).

Why this module exists
----------------------
Every wizard tree stores its own bookkeeping on its `QTreeWidgetItem`s under a
`Qt.ItemDataRole.UserRole + N` offset, and until feature 039 those offsets were
declared next to the six page classes that used them -- six separate blocks
spread over three thousand lines of `selection_wizard.py`. Nothing checked that
two blocks had not claimed the same offset, and two of them had: the rules page
and the entry-types page both sat on `UserRole + 70/71/72`, which was harmless
only for as long as they owned disjoint trees. Collecting the offsets into one
file is what makes that class of collision visible at a glance and checkable by
a test (`test_039_module_split.py` guard 3).

The status-label maps travel with the roles because they are the display side of
the same fact: `_STATUS_LABELS` renders what `_SKEL_STATUS_ROLE` and friends
store, and `_CF_LEVEL_LABELS` renders what `_CF_KIND_ROLE` distinguishes.

What is deliberately absent
---------------------------
* No dual-mode `if __package__:` guard. It would have nothing to carry -- this
  module imports `QtCore` and nothing else, so the dotted and flat import paths
  are already identical and an empty two-branch guard would assert a
  distinction that does not exist here (feature 039 FR-007 applies to
  cross-module imports, of which this module has none).
* No `_PHON_MODE_*` / `_ET_MODE_*` aliases. Those are `merge_preview` conflict
  modes, not item-data roles; they stay beside the pages that read them.
* No renumbering. The `_RULES_*` / `_ET_*` collision is retired in its own
  revertible commit (feature 039 US5, T041), not here.
"""
from __future__ import annotations

from PyQt6 import QtCore

# ---------------------------------------------------------------------------
# Item-data roles used throughout _PageItemPicker
# ---------------------------------------------------------------------------

_GUID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1   # entry_guid string
_KIND_ROLE = QtCore.Qt.ItemDataRole.UserRole + 2   # "affix" | "pos_group" | "subgroup"
_ROLE_ROLE = QtCore.Qt.ItemDataRole.UserRole + 3   # "attaches" | "produces" (leaf rows)
_IS_PRODUCES = QtCore.Qt.ItemDataRole.UserRole + 4  # bool: True for deriv_produces rows
# T005 -- Data roles for _PageItemPicker (FR-010, R6)
_ITEM_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 30  # "new" | "in_target" | "similar"
_ITEM_CAT_ROLE    = QtCore.Qt.ItemDataRole.UserRole + 31  # GrammarCategory


# ---------------------------------------------------------------------------
# Data roles for _PageSkeleton and _PageGramDeps trees
# ---------------------------------------------------------------------------

_SKEL_GUID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 10   # slot/tpl/pos guid
_SKEL_KIND_ROLE = QtCore.Qt.ItemDataRole.UserRole + 11   # "pos"|"slot"|"template"|"dep"
_SKEL_READ_ONLY = QtCore.Qt.ItemDataRole.UserRole + 12   # bool: template slot entry
# T006 -- Data roles for _PageSkeleton (FR-010, R6)
_SKEL_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 40  # "new" | "in_target" | "similar"
_SKEL_CAT_ROLE    = QtCore.Qt.ItemDataRole.UserRole + 41  # GrammarCategory (slot / template)
_SKEL_OWNER_ROLE  = QtCore.Qt.ItemDataRole.UserRole + 42  # owner POS GUID (for template/slot preview)
# T007 -- Data roles for _PageGramDeps (FR-010, R6)
# GrammarCategory mapping (research: _populate_deps_tree sections):
#   "Inflection Features" -> GrammarCategory.INFLECTION_FEATURES
#   "Inflection Classes"  -> GrammarCategory.INFLECTION_CLASSES
#   "Stem Names"          -> GrammarCategory.STEM_NAMES
_DEPS_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 50  # "new" | "in_target" | "similar"
_DEPS_CAT_ROLE    = QtCore.Qt.ItemDataRole.UserRole + 51  # GrammarCategory

# Target-status label map (shared with affix picker).
_STATUS_LABELS = {
    "new": "NEW",
    "in_target": "IN TARGET",
    "similar": "SIMILAR",
}


# Data roles for _PageCustomFields
_CF_GUID_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 60  # synthetic "cf:<owner>:<name>" guid
_CF_KIND_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 61  # "group" | "item"
_CF_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 63  # "NEW" | "IN TARGET" | ""

# Display labels for the four owner-class levels.
_CF_LEVEL_LABELS = {
    "LexEntry":           "Entry",
    "LexSense":           "Sense",
    "LexExampleSentence": "Example",
    "MoForm":             "Allomorph",
}


_PHON_GUID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 20   # source GUID (item rows)
_PHON_KIND_ROLE = QtCore.Qt.ItemDataRole.UserRole + 21   # "group" | "item"
_PHON_CAT_ROLE = QtCore.Qt.ItemDataRole.UserRole + 22    # GrammarCategory (group + item)
# T008 -- Data role for _PagePhonology (FR-010, R6)
_PHON_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 23  # "new" | "in_target" | "similar"


# ---------------------------------------------------------------------------
# Data roles for _PageRules (018-rules-page T017)
# ---------------------------------------------------------------------------

_RULES_GUID_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 70  # normalized rule GUID (item rows)
_RULES_KIND_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 71  # "group" | "item"
_RULES_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 72  # "NEW" | "IN TARGET" | "SIMILAR" | ""

# Status display map shared with phonology convention
_RULES_STATUS_LABELS = {
    "NEW": "NEW",
    "IN TARGET": "IN TARGET",
    "SIMILAR": "SIMILAR",
    "": "",
}


# Data roles for _PageEntryTypes
_ET_GUID_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 70  # source GUID (item rows)
_ET_KIND_ROLE   = QtCore.Qt.ItemDataRole.UserRole + 71  # "group" | "item"
_ET_CAT_ROLE    = QtCore.Qt.ItemDataRole.UserRole + 72  # GrammarCategory
_ET_STATUS_ROLE = QtCore.Qt.ItemDataRole.UserRole + 73  # "new" | "in_target" | ""
