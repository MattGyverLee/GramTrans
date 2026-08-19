"""Pages constructed for back-compat but absent from flow() (feature 039, T018).

Why this module exists
----------------------
`_PageScopeConflict` is registered and constructed, and it is not in
`SelectionWizard.flow()` -- so no run shows it. It predates the per-category
scope and conflict-mode decisions moving onto the individual selector pages, and
it survives because the suite still constructs it and reads its constants.

Keeping it in its own module is the honest arrangement: a reader of
`wizard_pages_blocks.py` should not have to work out which of the pages in front
of them a run can actually reach. The module name says it.

Its constants come with it because nothing else uses them --
`_SCHEMA_CATEGORIES`, `_GOLD_RESERVED`, `_CATEGORY_TOGGLES`, `_SCOPE_LABELS`,
`_CONFLICT_LABELS`, `_CUSTOM_FIELDS_ONLY` and `_allowed_modes` were all declared
at the top of the old monolith, hundreds of lines from their only reader, which
is a large part of why the file read as though everything in it was global.

What is deliberately absent
---------------------------
* Any entry in `flow()`. Adding one is a behaviour change and out of scope for
  the split (feature 039 FR-001).
"""
from __future__ import annotations

from PyQt6 import QtWidgets

if __package__:
    from ..models import (
        _DEFAULT_CONFLICT_MODES,
        CategoryScope,
        ConflictMode,
        GrammarCategory,
        Selection,
    )
    from ..selection import PickerState, SourceAffixInventory, build_selection
else:
    from models import (  # type: ignore
        _DEFAULT_CONFLICT_MODES,
        CategoryScope,
        ConflictMode,
        GrammarCategory,
        Selection,
    )
    from selection import (  # type: ignore
        PickerState,
        SourceAffixInventory,
        build_selection,
    )


_SCOPE_LABELS = {
    CategoryScope.NONE: "NONE",
    CategoryScope.AS_NEEDED: "AS-NEEDED (default)",
    CategoryScope.ALL: "ALL",
}

_CONFLICT_LABELS = {
    ConflictMode.ADD_NEW: "Add new (always create a copy)",
    ConflictMode.LINK: "Link (link existing by ID, else add; no field update)",
    ConflictMode.UPDATE: "Update (non-destructive: source wins on diverged fields; never blanks target)",
    ConflictMode.OVERWRITE: "Overwrite (replace target values with source)",
}

# Schema categories for the per-category scope selectors on page 3.
_SCHEMA_CATEGORIES = [
    GrammarCategory.POS,
    GrammarCategory.GRAM_CATEGORIES,
    GrammarCategory.INFLECTION_FEATURES,
    GrammarCategory.INFLECTION_CLASSES,
    GrammarCategory.STEM_NAMES,
    GrammarCategory.EXCEPTION_FEATURES,
    GrammarCategory.VARIANT_TYPES,
    GrammarCategory.COMPLEX_FORM_TYPES,
]

# Categories that are GOLD_RESERVED at Layer 1 (ADD_NEW hidden, OVERWRITE forbidden).
_GOLD_RESERVED = {
    GrammarCategory.GRAM_CATEGORIES,
    GrammarCategory.INFLECTION_FEATURES,
    GrammarCategory.VARIANT_TYPES,
    GrammarCategory.COMPLEX_FORM_TYPES,
    GrammarCategory.POS,
    GrammarCategory.PHONOLOGICAL_FEATURES,
    GrammarCategory.SEMANTIC_DOMAINS,
}

# CUSTOM_FIELDS: conservative (ADD hidden, OVERWRITE forbidden).
_CUSTOM_FIELDS_ONLY = {GrammarCategory.CUSTOM_FIELDS}

# All item category toggles (page 2 / 3).
_CATEGORY_TOGGLES = [
    GrammarCategory.POS,
    GrammarCategory.GRAM_CATEGORIES,
    GrammarCategory.INFLECTION_FEATURES,
    GrammarCategory.INFLECTION_CLASSES,
    GrammarCategory.STEM_NAMES,
    GrammarCategory.EXCEPTION_FEATURES,
    GrammarCategory.VARIANT_TYPES,
    GrammarCategory.COMPLEX_FORM_TYPES,
    GrammarCategory.ADHOC_COMPOUND_RULES,
    GrammarCategory.CUSTOM_FIELDS,
    GrammarCategory.AFFIXES,
    GrammarCategory.SLOTS,
    GrammarCategory.AFFIX_TEMPLATES,
]


# ---------------------------------------------------------------------------
# Layer-1 helper: which ConflictMode values are offered for a category?
# ---------------------------------------------------------------------------

def _allowed_modes(cat: GrammarCategory) -> list:
    """Return the list of ConflictMode values offered for `cat` per Layer 1."""
    if cat in _CUSTOM_FIELDS_ONLY:
        # CUSTOM_FIELDS remains conservative (LINK-only); not a GOLD category.
        return [ConflictMode.LINK]
    # Constitution v7.0.0 GOLD unlock: GOLD_RESERVED categories are ordinary
    # items and offer the full mode set (default UPDATE via _DEFAULT_CONFLICT_MODES).
    return [ConflictMode.ADD_NEW, ConflictMode.LINK, ConflictMode.UPDATE, ConflictMode.OVERWRITE]


# ---------------------------------------------------------------------------
# Page 3 -- Schema scope + conflict mode
# ---------------------------------------------------------------------------

class _PageScopeConflict(QtWidgets.QWizardPage):
    """Per-category three-scope selector + conflict mode. NOT IN THE FLOW.

    Retained for back-compat and constructed by the wizard, but absent from
    `SelectionWizard.flow()` and therefore never registered (conflict UI
    deferred, FR-012). It is the reason FR-011 exists: its title claimed a
    position in a five-step flow for as long as the flow had ten steps,
    because nothing numbered it and nothing renumbered it either. Permanent exclusion and
    per-run skipping now use the same mechanism -- absence from `flow()` --
    so an unreachable page cannot acquire a number it never shows.

    Re-hosts the existing scope-combo controls from main_window and adds
    per-category ConflictMode selectors gated by the Layer-1 kind table.

    The LINK control carries an explicit label ("link existing by ID, else
    add; no field update") per spec section (i) (022: renamed from MERGE).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # T015 / FR-011: the stale step-number-and-total is REMOVED, not
        # renumbered. This page is in no run, so it has no position to state.
        self.setTitle("Schema Scope + Conflict Mode")
        self.setSubTitle(
            "For each schema category, choose how much to transfer (NONE / AS-NEEDED / ALL) "
            "and what to do when a source item already exists in the target."
        )
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)

        # --- Category toggles (which categories to transfer at all) ---
        toggles_group = QtWidgets.QGroupBox("Grammar piece categories to transfer", self)
        toggles_layout = QtWidgets.QGridLayout(toggles_group)
        self._toggles: dict = {}
        for i, cat in enumerate(_CATEGORY_TOGGLES):
            cb = QtWidgets.QCheckBox(cat.value.replace("_", " "), toggles_group)
            toggles_layout.addWidget(cb, i // 3, i % 3)
            self._toggles[cat] = cb
        outer.addWidget(toggles_group)

        # --- Per-schema-category scope + conflict mode combos ---
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(container)
        grid.addWidget(QtWidgets.QLabel("<b>Category</b>", container), 0, 0)
        grid.addWidget(QtWidgets.QLabel("<b>Scope</b>", container), 0, 1)
        grid.addWidget(QtWidgets.QLabel("<b>Conflict mode</b>", container), 0, 2)

        self._scope_combos: dict = {}
        self._conflict_combos: dict = {}
        for row_i, cat in enumerate(_SCHEMA_CATEGORIES, start=1):
            grid.addWidget(
                QtWidgets.QLabel(cat.value.replace("_", " ") + ":", container),
                row_i, 0,
            )

            scope_cb = QtWidgets.QComboBox(container)
            for scope in (CategoryScope.NONE, CategoryScope.AS_NEEDED, CategoryScope.ALL):
                scope_cb.addItem(_SCOPE_LABELS[scope], scope)
            scope_cb.setCurrentIndex(1)  # AS_NEEDED default
            grid.addWidget(scope_cb, row_i, 1)
            self._scope_combos[cat] = scope_cb

            conflict_cb = QtWidgets.QComboBox(container)
            for mode in _allowed_modes(cat):
                conflict_cb.addItem(_CONFLICT_LABELS[mode], mode)
            # Default: Layer-1 default mode
            default_mode = _DEFAULT_CONFLICT_MODES.get(cat, ConflictMode.LINK)  # 022: LINK as ultimate fallback
            for idx in range(conflict_cb.count()):
                if conflict_cb.itemData(idx) == default_mode:
                    conflict_cb.setCurrentIndex(idx)
                    break
            grid.addWidget(conflict_cb, row_i, 2)
            self._conflict_combos[cat] = conflict_cb

        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        # Legacy closure checkbox (back-compat fallback)
        self._closure_cb = QtWidgets.QCheckBox(
            "Include dependency closure (legacy fallback; per-category scopes above take precedence)",
            self,
        )
        self._closure_cb.setChecked(True)
        outer.addWidget(self._closure_cb)

    # ------------------------------------------------------------------
    def collect_selection(self, picker_state: PickerState,
                          inventory: SourceAffixInventory) -> Selection:
        """Build a Selection from this page's current UI state."""
        cats = {cat: True for cat, cb in self._toggles.items() if cb.isChecked()}
        category_scopes = {}
        for cat, combo in self._scope_combos.items():
            scope = combo.currentData()
            if scope is not None:
                category_scopes[cat] = scope
        category_conflict_modes = {}
        for cat, combo in self._conflict_combos.items():
            mode = combo.currentData()
            if mode is not None:
                category_conflict_modes[cat] = mode

        return build_selection(
            picker_state,
            inventory,
            include_closure=self._closure_cb.isChecked(),
            extra_categories=list(cats.keys()),
            category_scopes=category_scopes,
        )._replace_conflict_modes(category_conflict_modes)  # helper below
