"""T016/T019 -- _PageEntryTypes display, whole-block toggle, and collapse tests.

Spec 021 T016 (US1) and T019 (US2) and T025 (US5). Tests run headless (no Qt
event loop) by inspecting the module-level _PageEntryTypes class attributes and
the collapse/missing-ref logic directly via selection.py helpers.

SC-008 guard: assert _PageEntryTypes renders NO ADD_NEW/MERGE/OVERWRITE
conflict-mode control in its _build_ui method (FR-012).
"""
from __future__ import annotations

import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Minimal SIL.LCModel stub
# ---------------------------------------------------------------------------
_sil = types.ModuleType("SIL")
_lcm = types.ModuleType("SIL.LCModel")
_lcm.ICmObject = None
sys.modules.setdefault("SIL", _sil)
sys.modules.setdefault("SIL.LCModel", _lcm)
_sil.LCModel = _lcm

from gramtrans.Lib.models import GrammarCategory  # noqa: E402
from gramtrans.Lib.selection import (  # noqa: E402
    build_entry_types_inventory,
    collapse_entry_types,
    entry_types_missing_ref_warnings,
)
from _fakes_phonology import (  # noqa: E402
    FakeEntryType,
    FakeInflEntryType,
    FakeLexDb,
    FakeLexDbSource,
)


def _make_source(*, variants=(), complexes=()):
    lex_db = FakeLexDb(variant_entry_types=variants, complex_entry_types=complexes)
    return FakeLexDbSource(lex_db)


# ---------------------------------------------------------------------------
# T016 (US1) -- preselect-all collapse produces transfer-all, no picks keys
# ---------------------------------------------------------------------------

class TestPreviewCollapsePreselectedAll:

    def test_all_checked_no_leaf_item_picks_keys(self):
        """SC-001/SC-002: preselect-all state -> collapse yields transfer-all."""
        vt1 = FakeEntryType("v1", "VT1")
        vt2 = FakeEntryType("v2", "VT2")
        cft1 = FakeEntryType("c1", "CFT1")
        src = _make_source(variants=[vt1, vt2], complexes=[cft1])
        inv = build_entry_types_inventory(src)
        # Simulate all rows checked (the default preselected state)
        checked = {
            GrammarCategory.VARIANT_TYPES: {"v1", "v2"},
            GrammarCategory.COMPLEX_FORM_TYPES: {"c1"},
        }
        result = collapse_entry_types(inv, checked)
        assert result["categories"].get(GrammarCategory.VARIANT_TYPES) is True
        assert result["categories"].get(GrammarCategory.COMPLEX_FORM_TYPES) is True
        # transfer-all => no leaf_item_picks keys
        assert GrammarCategory.VARIANT_TYPES not in result["leaf_item_picks"]
        assert GrammarCategory.COMPLEX_FORM_TYPES not in result["leaf_item_picks"]

    def test_page_title_states_no_total(self):
        """036 FR-009a: the title carries a name, and NO count of pages.

        This test used to assert the opposite -- that the title read "of 10" --
        and it is kept, inverted, rather than deleted, because the assertion it
        made is the exact defect feature 036 removed and the one most likely to
        be reintroduced by someone restoring "helpful" progress information.

        A total is unstateable here, twice over. The page's own constructor
        cannot know one: a position is a fact about a RUN, and the run assigns it
        on entry (`SelectionWizard._apply_step_number`). And no run has a total
        to state either -- pages with nothing to decide drop out (FR-009c), and
        the operator can go back and pick an affix, which re-admits a skipped
        page and shifts every position after it. The old literal proved the
        point: it claimed ten pages while eleven were registered.

        Inspects the source string rather than constructing a QWizardPage, so
        the check needs no QApplication (the original reason, unchanged).
        """
        import inspect
        import re
        from gramtrans.Lib.ui import selection_wizard as _sw
        # Feature 039 T025: scan the CLASS, not the module file.
        # `inspect.getsource` follows the object, so this survives
        # `_PageEntryTypes` moving to `wizard_pages_blocks.py` and any future
        # move, without naming a module path. The `assert match` guard stays --
        # it is what stops the scan passing vacuously if the pattern ever stops
        # matching.
        src = inspect.getsource(_sw._PageEntryTypes)
        match = re.search(r'setTitle\("([^"]+)"\)', src, re.DOTALL)
        assert match, "_PageEntryTypes setTitle not found in source"
        title = match.group(1)
        assert not re.search(r"of \d+", title), (
            f"036 FR-009a: the page title states a total ({title!r}); nothing "
            f"derives a total and nothing may display one."
        )
        assert not re.search(r"[Ss]tep\s*\d+", title), (
            f"036 FR-009: the page title hard-codes a position ({title!r}); the "
            f"run assigns the number on entry."
        )

    def test_page_title_contains_entry_types(self):
        """Check that the title string mentions 'Entry' or 'Types'."""
        import inspect
        import re
        from gramtrans.Lib.ui import selection_wizard as _sw
        # Feature 039 T025: see the sibling title test -- scans the class object,
        # not the module file, so the relocation cannot silently defeat it.
        src = inspect.getsource(_sw._PageEntryTypes)
        match = re.search(r'setTitle\("([^"]+)"\)', src, re.DOTALL)
        assert match, "_PageEntryTypes setTitle not found in source"
        title = match.group(1)
        assert "entry" in title.lower() or "types" in title.lower(), (
            f"Expected 'entry' or 'types' in title, got: {title!r}"
        )


class TestNoConflictModeControls:

    def test_no_conflict_mode_strings_in_page_class(self):
        """SC-008 / FR-012: _PageEntryTypes source must NOT contain conflict-mode
        widget construction (ADD_NEW / MERGE / OVERWRITE combo-box items).

        Inspects the source code string of _PageEntryTypes._build_ui to avoid
        creating a QWizardPage without a running QApplication.
        """
        import inspect
        import re
        from gramtrans.Lib.ui import selection_wizard as _sw
        # Feature 039 T025: `inspect.getsource` returns exactly this class's
        # body, so the old "from `class _PageEntryTypes(` up to the next
        # `class `" regex is gone -- it silently depended on the class being
        # followed by a sibling class in the same file, which the module split
        # ends.
        class_body = inspect.getsource(_sw._PageEntryTypes)
        assert class_body.lstrip().startswith("class _PageEntryTypes"), (
            "_PageEntryTypes source not located"
        )
        # Conflict-mode WIDGET construction patterns must not appear in the class body.
        # Note: comment strings that *mention* ADD_NEW/OVERWRITE/MERGE to document
        # their absence are fine; we check for actual widget-construction patterns.
        for forbidden in (r'addItem\(.*"ADD_NEW"',
                          r'addItem\(.*"OVERWRITE"',
                          r'addItem\(.*"MERGE"',
                          r'QComboBox.*conflict',
                          r'ConflictMode\.',  # actual use of ConflictMode enum
                          ):
            if re.search(forbidden, class_body, re.IGNORECASE):
                raise AssertionError(
                    f"Found forbidden conflict-mode widget pattern {forbidden!r} in "
                    "_PageEntryTypes -- page must not render conflict-mode controls "
                    "(FR-012 / SC-008)"
                )


# ---------------------------------------------------------------------------
# T019 (US2) -- trim and whole-block off
# ---------------------------------------------------------------------------

class TestCollapseTrimmingAndOff:

    def test_whole_block_off_no_categories(self):
        """SC-003: whole-block off -> no categories, no picks."""
        vt1 = FakeEntryType("v1", "VT1")
        src = _make_source(variants=[vt1])
        inv = build_entry_types_inventory(src)
        result = collapse_entry_types(inv, {})
        assert result["categories"] == {}
        assert result["leaf_item_picks"] == {}

    def test_trim_variant_type_emits_subset_picks(self):
        vt1 = FakeEntryType("v1", "VT1")
        vt2 = FakeEntryType("v2", "VT2")
        src = _make_source(variants=[vt1, vt2])
        inv = build_entry_types_inventory(src)
        # Only v1 kept; v2 deselected
        checked = {GrammarCategory.VARIANT_TYPES: {"v1"}}
        result = collapse_entry_types(inv, checked)
        picks = result["leaf_item_picks"].get(GrammarCategory.VARIANT_TYPES)
        assert picks is not None
        assert "v1" in picks
        assert "v2" not in picks

    def test_all_checked_key_omitted(self):
        """Fully-checked category omits the leaf_item_picks key (transfer-all)."""
        vt1 = FakeEntryType("v1", "VT1")
        src = _make_source(variants=[vt1])
        inv = build_entry_types_inventory(src)
        checked = {GrammarCategory.VARIANT_TYPES: {"v1"}}
        result = collapse_entry_types(inv, checked)
        # Only 1 item, checked -> all checked -> no key
        assert GrammarCategory.VARIANT_TYPES not in result["leaf_item_picks"]

    def test_deselect_sibling_category_group_independent(self):
        """Deselecting variant types does not affect complex form types category."""
        vt1 = FakeEntryType("v1", "VT1")
        cft1 = FakeEntryType("c1", "CFT1")
        src = _make_source(variants=[vt1], complexes=[cft1])
        inv = build_entry_types_inventory(src)
        # Only complex form types checked
        checked = {GrammarCategory.COMPLEX_FORM_TYPES: {"c1"}}
        result = collapse_entry_types(inv, checked)
        assert GrammarCategory.COMPLEX_FORM_TYPES in result["categories"]
        assert GrammarCategory.VARIANT_TYPES not in result["categories"]


# ---------------------------------------------------------------------------
# T025 (US5) -- missing-ref warnings aggregated
# ---------------------------------------------------------------------------

class TestMissingRefWarningsAggregated:

    def test_n_missing_ref_warnings_plus_no_double_dialog(self):
        """SC-006: N missing-ref warnings produce count; resolved ref -> 0."""
        val1 = FakeEntryType("val-001", "Val 1")
        val2 = FakeEntryType("val-002", "Val 2")
        iet1 = FakeInflEntryType("v-infl-1", "Infl Variant 1", infl_feats=[val1])
        iet2 = FakeInflEntryType("v-infl-2", "Infl Variant 2", infl_feats=[val2])
        src = _make_source(variants=[iet1, iet2])
        inv = build_entry_types_inventory(src)
        checked = {GrammarCategory.VARIANT_TYPES: {"v-infl-1", "v-infl-2"}}
        # Both refs absent from target
        warnings = entry_types_missing_ref_warnings(inv, checked, target=None)
        assert len(warnings) == 2  # aggregated, one per kept type

    def test_resolved_ref_no_warning(self):
        val = FakeEntryType("val-001", "Val 1")
        iet = FakeInflEntryType("v-infl-1", "Infl Variant 1", infl_feats=[val])
        src = _make_source(variants=[iet])
        inv = build_entry_types_inventory(src)
        checked = {GrammarCategory.VARIANT_TYPES: {"v-infl-1"}}
        # Resolved in target
        warnings = entry_types_missing_ref_warnings(
            inv, checked, target=None,
            target_infl_feat_guids=frozenset(["val-001"])
        )
        assert len(warnings) == 0

    def test_base_entry_type_no_warning(self):
        vt = FakeEntryType("v-base", "Base Variant")
        src = _make_source(variants=[vt])
        inv = build_entry_types_inventory(src)
        checked = {GrammarCategory.VARIANT_TYPES: {"v-base"}}
        warnings = entry_types_missing_ref_warnings(inv, checked, target=None)
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# Feature 039 T043 -- the nested-group walk, and the tristate it drives
# ---------------------------------------------------------------------------
# T042 changed behaviour: `_PageEntryTypes._iter_item_rows` called its own
# recursive generator as a procedure (`_walk(child, False)` on a line by
# itself), so the generator was built and discarded and every row under a
# NESTED group was invisible to the walk. It also guarded the yield with
# `if in_group_item or True:`, which is unconditionally true.
#
# Since the whole whole-block cluster reads the tree through this one method,
# those rows counted toward nothing: not `_has_any_item`, not the
# `checked == total` comparison in `_refresh_whole_block`, not
# `whole_block_on`. A block holding unchecked nested rows could therefore show
# a fully-checked box.
#
# These tests pin the NEW counts, so the change is asserted rather than
# assumed, and so a revert of T042 fails loudly here.

class _FakeItem:
    """The narrow slice of QTreeWidgetItem that `_iter_item_rows` touches."""

    def __init__(self, kind, label="", checked=False, children=()):
        self._kind = kind
        self.label = label
        self._checked = checked
        self._children = list(children)

    # -- tree shape --
    def childCount(self):
        return len(self._children)

    def child(self, i):
        return self._children[i]

    def data(self, _column, role):
        from gramtrans.Lib.ui.wizard_roles import _ET_KIND_ROLE
        return self._kind if role == _ET_KIND_ROLE else None

    # -- check state --
    def checkState(self, _column):
        from PyQt6 import QtCore
        return (QtCore.Qt.CheckState.Checked if self._checked
                else QtCore.Qt.CheckState.Unchecked)

    def setCheckState(self, _column, state):
        from PyQt6 import QtCore
        self._checked = state == QtCore.Qt.CheckState.Checked


class _FakeTree:
    def __init__(self, root_children):
        self._root = _FakeItem("root", children=root_children)

    def invisibleRootItem(self):
        return self._root


class _FakeBox:
    """Stands in for the whole-block QCheckBox."""

    def __init__(self):
        self.enabled = True
        self.state = None

    def setEnabled(self, on):
        self.enabled = on

    def setCheckState(self, state):
        self.state = state


#: The `_BlockPage` methods these tests drive. Copied onto the stand-in below
#: rather than inherited, because `_BlockPage` descends from QWizardPage and
#: constructing one needs a QApplication -- which is the same reason every other
#: test in this module works off the class rather than an instance.
_CLUSTER = ("_iter_item_rows", "_on_whole_block_clicked", "_set_all_items",
            "_refresh_whole_block", "_on_item_changed", "_has_any_item",
            "_all_items_checked", "whole_block_on")


def _page_stand_in():
    """A `_PageEntryTypes` stand-in with the real cluster methods attached.

    Carries exactly the three attributes `_BlockPage` documents as its
    dependencies -- `_tree`, `_whole_block`, `_mirroring` -- so if the base ever
    starts reading a fourth, these tests fail rather than silently testing a
    different object than the one that ships.
    """
    from gramtrans.Lib.ui import selection_wizard as _sw

    ns = {}
    for name in _CLUSTER:
        fn = getattr(_sw._PageEntryTypes, name, None)
        assert fn is not None, (
            "_PageEntryTypes has no %s -- the whole-block cluster changed shape"
            % name
        )
        ns[name] = fn

    def __init__(self, tree):
        self._tree = tree
        self._whole_block = _FakeBox()
        self._mirroring = False

    ns["__init__"] = __init__
    return type("_Page", (), ns)


def _nested_tree(nested_checked=False):
    """A tree with one flat group and one group nested inside a group.

        Variants   (group)
          v1       (item)
          v2       (item)
            v2a    (item, sub-type of v2)
        Complex    (group)
          Inner    (group)   <-- the nested group T042 makes visible
            c1     (item)
            c2     (item)

    Rows the OLD walk saw:  v1, v2, v2a           -> 3
    Rows the NEW walk sees: v1, v2, v2a, c1, c2   -> 5
    """
    v2a = _FakeItem("item", "v2a", checked=True)
    variants = _FakeItem("group", "Variants", children=[
        _FakeItem("item", "v1", checked=True),
        _FakeItem("item", "v2", checked=True, children=[v2a]),
    ])
    inner = _FakeItem("group", "Inner", children=[
        _FakeItem("item", "c1", checked=nested_checked),
        _FakeItem("item", "c2", checked=nested_checked),
    ])
    complexes = _FakeItem("group", "Complex", children=[inner])
    return _FakeTree([variants, complexes])


class TestNestedGroupWalk039:

    def _page(self, **kw):
        pytest.importorskip("PyQt6")
        return _page_stand_in()(_nested_tree(**kw))

    def test_rows_under_a_nested_group_are_now_counted(self):
        """T042: five rows, not the three the discarded generator produced."""
        page = self._page()
        labels = sorted(item.label for _grp, item in page._iter_item_rows())
        assert labels == ["c1", "c2", "v1", "v2", "v2a"], labels

    def test_the_nested_rows_report_their_own_group_as_parent(self):
        """The pair's first element is the row's real parent, not the outer group."""
        page = self._page()
        parents = {item.label: grp.label
                   for grp, item in page._iter_item_rows()}
        assert parents["c1"] == "Inner"
        assert parents["c2"] == "Inner"
        assert parents["v2a"] == "v2"      # a sub-type hangs off its own item
        assert parents["v1"] == "Variants"

    def test_tristate_is_partial_when_only_the_nested_rows_are_unchecked(self):
        """The behaviour change, stated as the thing an operator sees.

        Before T042 this block reported CHECKED -- fully selected -- while two
        entry types under the nested group were not selected at all.
        """
        from PyQt6 import QtCore
        page = self._page(nested_checked=False)
        page._refresh_whole_block()
        assert page._whole_block.enabled is True
        assert page._whole_block.state == QtCore.Qt.CheckState.PartiallyChecked

    def test_tristate_is_checked_when_the_nested_rows_are_checked_too(self):
        from PyQt6 import QtCore
        page = self._page(nested_checked=True)
        page._refresh_whole_block()
        assert page._whole_block.state == QtCore.Qt.CheckState.Checked

    def test_tristate_is_unchecked_and_disabled_on_an_empty_block(self):
        """Acceptance 1.3: empty is NOT vacuously full."""
        pytest.importorskip("PyQt6")
        from PyQt6 import QtCore
        page = _page_stand_in()(_FakeTree([]))
        page._refresh_whole_block()
        assert page._whole_block.enabled is False
        assert page._whole_block.state == QtCore.Qt.CheckState.Unchecked

    def test_set_all_items_reaches_the_nested_rows(self):
        """Check-all must reach every row the walk now yields.

        Otherwise the box would read CHECKED while the nested rows stayed off --
        the same defect from the other direction.
        """
        from PyQt6 import QtCore
        page = self._page(nested_checked=False)
        page._set_all_items(True)
        assert all(item.checkState(0) == QtCore.Qt.CheckState.Checked
                   for _g, item in page._iter_item_rows())
        page._refresh_whole_block()
        assert page._whole_block.state == QtCore.Qt.CheckState.Checked

    def test_the_recursive_walk_is_consumed_not_discarded(self):
        """A direct guard on the defect's shape, so it cannot creep back.

        Checks the CODE, with the docstring stripped -- this method's own
        docstring quotes the removed `if in_group_item or True:` guard in order
        to explain it, and a naive substring scan would match the explanation.
        """
        import ast
        import inspect
        import textwrap
        pytest.importorskip("PyQt6")
        from gramtrans.Lib.ui import selection_wizard as _sw

        fn = ast.parse(
            textwrap.dedent(inspect.getsource(_sw._PageEntryTypes._iter_item_rows))
        ).body[0]
        if (isinstance(fn.body[0], ast.Expr)
                and isinstance(fn.body[0].value, ast.Constant)):
            fn.body = fn.body[1:]          # drop the docstring
        code = ast.unparse(fn)

        assert "yield from _walk(" in code, (
            "the recursive walk must be consumed with `yield from`; a bare "
            "`_walk(...)` call builds a generator and throws it away, which is "
            "the defect T042 fixed"
        )
        # No `_walk(...)` used as a bare statement anywhere.
        bare = [n for n in ast.walk(fn)
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Name)
                and n.value.func.id == "_walk"]
        assert not bare, (
            "`_walk(...)` is called as a statement; its result is a generator "
            "and discarding it yields nothing"
        )
        # No unconditionally-true guard.
        assert not [n for n in ast.walk(fn)
                    if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)
                    and any(isinstance(v, ast.Constant) and v.value is True
                            for v in n.values)], (
            "an `... or True` guard is back; it can never be false"
        )
